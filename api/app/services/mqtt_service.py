"""MQTT telemetry ingestion service for NodeMCU v2.0.0 (DHT22 + LDR Light)."""

from datetime import datetime, timedelta, timezone
import hmac
import json
import logging
import os
import uuid

from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models import Device, Greenhouse, GreenhouseArea, Notification, SensorLog
from .access_service import resolve_effective_thresholds
from .actuator_service import evaluate_auto_actuators
from .mqtt_publisher import camera_cmd_topic, create_mqtt_client, publish_mqtt_json


logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "smart_greenhouse/24T_Nhat1/sensors")
DEVICE_INGEST_TOKEN = os.getenv("DEVICE_INGEST_TOKEN", "")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"


def _number(payload: dict, canonical: str, aliases: tuple[str, ...], minimum: float, maximum: float, required: bool = True) -> float | None:
    value = next((payload[key] for key in (canonical, *aliases) if key in payload and payload[key] is not None), None)
    if value is None:
        if required:
            raise ValueError(f"Thiếu trường {canonical}")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Trường {canonical} phải là số")
    value = float(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"Trường {canonical} ngoài khoảng hợp lệ [{minimum}, {maximum}]")
    return value


def _parse_timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Thiếu timestamp ISO 8601 có múi giờ")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp phải có múi giờ")
    return parsed.astimezone(timezone.utc)


def _check_abnormal_environment(
    db: Session,
    device: Device,
    greenhouse: Greenhouse | None,
    area: GreenhouseArea | None,
    sensor_log: SensorLog,
    thresholds: dict,
) -> dict:
    """Detect abnormal DHT22/light conditions, create ENV_ALERT notification, and trigger ESP32-CAM."""
    reasons: list[str] = []
    severity = "WARNING"

    fungal_hum = float(thresholds["fungal_humidity_threshold"])
    fungal_light = float(thresholds["fungal_light_threshold"])
    duration_min = int(thresholds["fungal_duration_minutes"])

    # Inspect recent sensor window to detect sustained high humidity (>85%)
    window_start = sensor_log.timestamp - timedelta(minutes=duration_min)
    recent_logs = (
        db.query(SensorLog)
        .filter(
            SensorLog.device_id == device.device_id,
            SensorLog.timestamp >= window_start,
            SensorLog.timestamp <= sensor_log.timestamp,
        )
        .order_by(SensorLog.timestamp.asc())
        .all()
    )
    high_hum_samples = [
        row for row in recent_logs if row.humidity is not None and row.humidity >= fungal_hum
    ]
    sustained_high_hum = (
        sensor_log.humidity is not None
        and sensor_log.humidity >= fungal_hum
        and (len(high_hum_samples) >= 2 or len(recent_logs) == 1)
    )
    low_light = sensor_log.light_level is not None and sensor_log.light_level <= fungal_light

    if sustained_high_hum and low_light:
        severity = "CRITICAL"
        reasons.append(
            f"Độ ẩm không khí cao ({sensor_log.humidity:.1f}% ≥ {fungal_hum:.0f}%) kèm ánh sáng yếu "
            f"({sensor_log.light_level:.0f} Lux ≤ {fungal_light:.0f} Lux) — nguy cơ nấm bệnh cao"
        )
    elif sustained_high_hum:
        reasons.append(
            f"Độ ẩm không khí vượt ngưỡng cảnh báo nấm bệnh ({sensor_log.humidity:.1f}% ≥ {fungal_hum:.0f}%)"
        )
    elif low_light:
        reasons.append(
            f"Cường độ ánh sáng thấp ({sensor_log.light_level:.0f} Lux ≤ {fungal_light:.0f} Lux)"
        )

    if sensor_log.temperature is not None:
        if sensor_log.temperature > thresholds["max_temp"]:
            reasons.append(
                f"Nhiệt độ cao ({sensor_log.temperature:.1f}°C > {thresholds['max_temp']:.1f}°C)"
            )
        elif sensor_log.temperature < thresholds["min_temp"]:
            reasons.append(
                f"Nhiệt độ thấp ({sensor_log.temperature:.1f}°C < {thresholds['min_temp']:.1f}°C)"
            )

    if not reasons:
        return {"alert_created": False, "camera_triggered": False, "reasons": []}

    # Deduplicate ENV_ALERT notifications per device within 30 minutes
    cooldown_since = datetime.now(timezone.utc) - timedelta(minutes=30)
    recent_alert = (
        db.query(Notification)
        .filter(
            Notification.device_id == device.device_id,
            Notification.category == "ENV_ALERT",
            Notification.created_at >= cooldown_since,
        )
        .first()
    )
    alert_created = False
    if recent_alert is None and greenhouse is not None:
        zone_name = area.name if area else greenhouse.name
        db.add(
            Notification(
                notification_id=str(uuid.uuid4()),
                user_id=greenhouse.user_id,
                greenhouse_id=greenhouse.greenhouse_id,
                area_id=area.area_id if area else None,
                device_id=device.device_id,
                category="ENV_ALERT",
                severity=severity,
                title=f"Cảnh báo môi trường tại {zone_name}",
                message="; ".join(reasons) + ". Hệ thống đã kích hoạt ESP32-cam kiểm tra lá cây.",
                status="UNREAD",
                created_at=datetime.now(timezone.utc),
            )
        )
        alert_created = True

    camera_result = {"published": False}
    if False and greenhouse is not None:  # Đã tắt tự động chụp khi có cảnh báo môi trường
        camera_result = publish_mqtt_json(
            camera_cmd_topic(greenhouse.greenhouse_id),
            {
                "command": "CAPTURE",
                "trigger_type": "ENV_ALERT",
                "greenhouse_id": greenhouse.greenhouse_id,
                "area_id": area.area_id if area else None,
                "source_device_id": device.device_id,
                "reasons": reasons,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {
        "alert_created": alert_created,
        "camera_triggered": bool(camera_result.get("published")),
        "reasons": reasons,
    }


def process_sensor_payload(payload: dict, db: Session, verify_token: bool = True) -> dict:
    """Validate and persist one NodeMCU v2.0.0 MQTT payload, evaluate AUTO actuators & ENV alerts."""
    if not isinstance(payload, dict):
        raise ValueError("Payload phải là JSON object")

    data = dict(payload)
    if verify_token:
        ingest_token = os.getenv("DEVICE_INGEST_TOKEN", DEVICE_INGEST_TOKEN)
        if not ingest_token:
            raise PermissionError("DEVICE_INGEST_TOKEN chưa được cấu hình")
        supplied_token = data.pop("device_token", "")
        if not isinstance(supplied_token, str) or not hmac.compare_digest(supplied_token, ingest_token):
            raise PermissionError("Thiết bị không được xác thực")

    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("Thiếu device_id")
    device_id = device_id.strip()

    device = (
        db.query(Device)
        .filter(Device.device_id == device_id, Device.deleted_at.is_(None))
        .first()
    )
    if device is None or device.status != "ACTIVE":
        raise ValueError("Thiết bị không tồn tại hoặc không hoạt động")

    measured_at = _parse_timestamp(data.get("timestamp"))
    temperature = _number(data, "temperature", ("temp", "Temperature"), -40, 85, required=True)
    humidity = _number(data, "humidity", ("hum", "Humidity"), 0, 100, required=True)
    light_level = _number(
        data, "light_level", ("light", "lux", "ldr", "Light_Level"), 0, 200000, required=False
    )
    soil_moisture = _number(
        data, "soil_moisture", ("moisture", "Soil_Moisture"), 0, 100, required=False
    )
    soil_ph = _number(data, "pH", ("soil_pH", "soil_ph", "Soil_pH"), 0, 14, required=False)
    nitrogen = _number(data, "nitrogen", ("N", "Nitrogen"), 0, 5000, required=False)
    phosphorus = _number(data, "phosphorus", ("P", "Phosphorus"), 0, 5000, required=False)
    potassium = _number(data, "potassium", ("K", "Potassium"), 0, 5000, required=False)

    duplicate = (
        db.query(SensorLog)
        .filter(SensorLog.device_id == device_id, SensorLog.timestamp == measured_at)
        .first()
    )
    if duplicate:
        return {"status": "duplicate", "log_id": duplicate.log_id}

    new_log = SensorLog(
        log_id=str(uuid.uuid4()),
        device_id=device_id,
        timestamp=measured_at,
        temperature=temperature,
        humidity=humidity,
        light_level=light_level,
        soil_moisture=soil_moisture,
        soil_pH=soil_ph,
        N=nitrogen,
        P=phosphorus,
        K=potassium,
    )
    db.add(new_log)
    device.is_online = True
    device.last_updated = measured_at
    db.flush()

    greenhouse = (
        db.query(Greenhouse)
        .filter(Greenhouse.greenhouse_id == device.greenhouse_id)
        .first()
        if device.greenhouse_id
        else None
    )
    area = (
        db.query(GreenhouseArea)
        .filter(GreenhouseArea.area_id == device.area_id)
        .first()
        if device.area_id
        else None
    )
    thresholds = resolve_effective_thresholds(db, area=area, greenhouse=greenhouse)
    actuator_changes = evaluate_auto_actuators(db, device, new_log, thresholds)
    alert_info = _check_abnormal_environment(
        db, device, greenhouse, area, new_log, thresholds
    )

    db.commit()
    return {
        "status": "saved",
        "log_id": new_log.log_id,
        "actuator_changes": actuator_changes,
        "alert": alert_info,
    }


def on_connect(client, userdata, flags, rc):
    print(f"Đã kết nối MQTT Broker với mã: {rc}")
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    db = SessionLocal()
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        result = process_sensor_payload(payload, db, verify_token=True)
        print(f"Xử lý bản tin MQTT ({payload.get('device_id')}): {result['status']}")
    except (ValueError, PermissionError, json.JSONDecodeError) as err:
        db.rollback()
        print(f"Từ chối bản tin MQTT: {err}")
    except Exception as err:
        db.rollback()
        print(f"Lỗi xử lý bản tin MQTT ({type(err).__name__})")
    finally:
        db.close()


def start_mqtt():
    client = create_mqtt_client()
    if MQTT_USERNAME or MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    return client