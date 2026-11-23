import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from tests import support
from app.core.database import SessionLocal
from app.models import ActuatorLog, ActuatorState, SensorLog, Device
from app.schemas.actuator import IrrigationRules
from app.services import actuator_service as svc
from app.services.actuator_feedback import record_feedback
from app.services.sensor_validation import quality_problems, timestamp_problem
from app.services.weather_service import weather_adjustment
from fastapi import HTTPException
from pydantic import ValidationError


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.rule = IrrigationRules(sensor_device_id="SAFETY-SENSOR", start_below_pct=35., stop_at_pct=60.,
                                    hardware_verified=True)
        self.db = SessionLocal()
        if not self.db.get(Device, "SAFETY-SENSOR"):
            self.db.add(Device(device_id="SAFETY-SENSOR", greenhouse_id="garden-outdoor-01",
                area_id="area-chili-01", status="ACTIVE", device_type="SENSOR_NODE"))
            self.db.commit()
        self.db.query(ActuatorLog).delete()
        self.db.query(ActuatorState).delete()
        self.db.query(SensorLog).filter_by(device_id="SAFETY-SENSOR").delete()
        self.item = ActuatorState(actuator_id="safety-pump", greenhouse_id="garden-outdoor-01",
            area_id="area-chili-01", device_id="SAFETY-SENSOR", actuator_type="PUMP",
            control_mode="AUTO", is_on=False, auto_rules=self.rule.model_dump(), updated_at=self.now)
        self.db.add(self.item)
        self.reading = SensorLog(log_id="safety-reading", device_id="SAFETY-SENSOR",
            temperature=29, humidity=50, soil_moisture=30, light_level=2000, timestamp=self.now)
        self.db.add(self.reading)
        self.db.commit()
        self.env = patch.dict(os.environ, {"DEVICE_INGEST_TOKEN": "test-device-secret"})
        self.env.start()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ActuatorLog).filter_by(actuator_id="safety-pump").delete()
        self.db.query(ActuatorState).filter_by(actuator_id="safety-pump").delete()
        self.db.query(SensorLog).filter_by(device_id="SAFETY-SENSOR").delete()
        self.db.query(Device).filter_by(device_id="SAFETY-SENSOR").delete()
        self.db.commit()
        self.db.close()
        self.env.stop()

    def test_bad_thresholds_and_nonfinite_rejected(self):
        for updates in ({"start_below_pct": 65.}, {"stop_at_pct": float("nan")},
                        {"allowed_start": "06:00"}, {"base_run_seconds": 121}):
            with self.assertRaises(ValidationError):
                IrrigationRules(**(self.rule.model_dump() | updates))

    def test_stale_future_missing_and_jump(self):
        self.assertIsNotNone(timestamp_problem(self.now-timedelta(seconds=121), self.now))
        self.assertIsNotNone(timestamp_problem(self.now+timedelta(seconds=6), self.now))
        self.reading.soil_moisture = None
        self.assertTrue(quality_problems(self.reading, now=self.now))
        self.reading.soil_moisture = 30
        old = SimpleNamespace(timestamp=self.now-timedelta(seconds=10), soil_moisture=70, temperature=29, humidity=50)
        self.assertTrue(quality_problems(self.reading, [old], self.now))

    def test_soil_stop_even_when_air_dry(self):
        self.reading.soil_moisture = 65
        self.reading.humidity = 15
        self.db.flush()
        self.assertIn("đất", svc.start_problem(self.db, self.item, self.rule, self.now))

    def test_wrong_zone_cannot_start(self):
        self.item.area_id = None
        self.assertIsNotNone(svc.start_problem(self.db, self.item, self.rule, self.now))

    def test_failed_publish_does_not_claim_pump_started(self):
        with patch.object(svc, "publish_mqtt_json", return_value={"published": False}):
            svc.send_command(self.db, self.item, True, "AUTO_RULE", "test")
        self.assertFalse(self.item.is_on)
        self.assertEqual(svc.logs_for(self.db, self.item)[0].ack_status, "FAILED")

    def test_broker_delivery_is_pending_until_device_ack(self):
        with patch.object(svc, "publish_mqtt_json", return_value={"published": True}):
            svc.send_command(self.db, self.item, True, "AUTO_RULE", "test", duration=20)
        self.db.commit()
        log = svc.latest_start(self.db, self.item)
        self.assertEqual(log.ack_status, "PENDING")
        self.assertEqual(svc.serialize_actuator(self.item, self.db)["status"], "PENDING")
        with self.assertRaises(HTTPException):
            record_feedback(self.db, "SAFETY-SENSOR", log.log_id, True, "wrong")
        record_feedback(self.db, "SAFETY-SENSOR", log.log_id, True, "test-device-secret")
        self.assertEqual(svc.serialize_actuator(self.item, self.db)["status"], "RUNNING")
        record_feedback(self.db, "SAFETY-SENSOR", log.log_id, False, "test-device-secret")
        self.assertFalse(self.item.is_on)
        self.assertEqual(svc.serialize_actuator(self.item, self.db)["status"], "STOPPED")

    def test_watchdog_stops_without_new_packets_and_cooldown(self):
        with patch.object(svc, "publish_mqtt_json", return_value={"published": True}) as send:
            svc.send_command(self.db, self.item, True, "AUTO_RULE", "test", duration=10)
            self.db.commit()
            svc.enforce_timeouts(self.db, self.now+timedelta(seconds=15))
            self.assertFalse(self.item.is_on)
            self.assertFalse(send.call_args.args[1]["is_on"])
        self.assertIsNotNone(svc.start_problem(self.db, self.item, self.rule, self.now+timedelta(seconds=16)))

    def test_failed_stop_keeps_desired_on_for_retry(self):
        self.item.is_on = True
        with patch.object(svc, "publish_mqtt_json", return_value={"published": False}):
            svc.send_command(self.db, self.item, False, "AUTO_RULE", "test")
        self.assertTrue(self.item.is_on)

    def test_daily_stats_split_midnight_and_do_not_invent_volume(self):
        a = datetime(2026, 1, 1, 23, 59, 50, tzinfo=timezone.utc)
        logs = [SimpleNamespace(action="TURN_ON", acknowledged_at=a),
                SimpleNamespace(action="TURN_OFF", acknowledged_at=a+timedelta(seconds=30))]
        days = svc.daily_statistics(logs, timezone.utc, a)
        self.assertEqual([r["confirmed_seconds"] for r in days], [20, 10])
        self.assertTrue(all(r["volume_liters"] is None for r in days))

    def test_rain_does_not_reduce_covered_garden(self):
        moment = datetime(2026, 1, 1, 11, tzinfo=timezone.utc)  # 18:00 VN
        weather = {"available": True, "days": [{"date": "2026-01-01", "max_temperature_c": 38},
            {"date": "2026-01-02", "rain_mm": 10, "rain_probability_pct": 90}]}
        rule = self.rule.model_copy(update={"rainy_evening_multiplier": .5})
        self.assertEqual(weather_adjustment(rule, weather, moment)[0], 1)
        self.assertEqual(weather_adjustment(rule.model_copy(update={"rain_exposed": True}), weather, moment)[0], .5)
        self.assertEqual(weather_adjustment(rule, {"available": False}, moment)[0], 1)

    def test_auto_start_is_capped_then_wet_soil_stops(self):
        device = self.db.get(Device, "SAFETY-SENSOR")
        with patch.object(svc, "forecast", return_value={"available": True}), \
             patch.object(svc, "weather_adjustment", return_value=(1.5, "hot morning")), \
             patch.object(svc, "publish_mqtt_json", return_value={"published": True}) as send:
            svc.evaluate_auto_actuators(self.db, device, self.reading)
            self.assertTrue(self.item.is_on)
            self.assertEqual(send.call_args.args[1]["run_seconds"], 30)
            self.reading.soil_moisture = 61
            svc.evaluate_auto_actuators(self.db, device, self.reading)
            self.assertFalse(self.item.is_on)
            self.assertFalse(send.call_args.args[1]["is_on"])

    def test_daily_budget_blocks_new_start(self):
        self.db.add(ActuatorLog(log_id="spent-budget", actuator_id=self.item.actuator_id,
            action="TURN_ON", trigger_source="AUTO_RULE", ack_status="PENDING",
            created_at=self.now-timedelta(hours=1), duration_seconds=120))
        self.db.flush()
        limited = self.rule.model_copy(update={"max_daily_seconds": 140})
        self.assertIn("ngân sách", svc.start_problem(self.db, self.item, limited, self.now))

    def test_duplicate_and_out_of_order_packets_never_trigger_pump(self):
        from app.services.mqtt_service import process_sensor_payload
        data = dict(device_id="SAFETY-SENSOR", device_token="test-device-secret",
            timestamp=self.now.isoformat(), temperature=29, humidity=50,
            light_level=2000, soil_moisture=30)
        with patch.object(svc, "publish_mqtt_json") as send:
            self.assertEqual(process_sensor_payload(data, self.db)["status"], "duplicate")
            data["timestamp"] = (self.now-timedelta(seconds=1)).isoformat()
            with self.assertRaises(ValueError):
                process_sensor_payload(data, self.db)
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
