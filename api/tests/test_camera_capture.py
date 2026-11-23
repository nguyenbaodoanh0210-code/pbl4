"""Camera regression tests; isolated database, mocked inference and no hardware traffic."""
import os
import hashlib
import hmac
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from tests import support
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import create_access_token
from app.core.database import SessionLocal
from app.models import CameraLog, Device, Greenhouse, SensorLog, User
from app.services import camera_service as svc


class CameraCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer " + create_access_token("test-farmer")[0]}
        cls.photo = next(Path("data/chili_plant_disease/test").rglob("*.jpg")).read_bytes()
        with SessionLocal() as db:
            db.add(User(user_id="camera-other-user", full_name="Other", role="FARMER", email="other-camera@example.test"))
            db.commit()
            db.add(Greenhouse(greenhouse_id="camera-other-garden", user_id="camera-other-user", name="Other", area_sqm=1))
            db.commit()

    def setUp(self):
        svc.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.predict = patch.object(svc, "predict_disease", return_value={"class_name": "healthy",
            "scores": {"healthy": .99, "fungal": .01}, "model_version": "test-camera"})
        self.model = self.predict.start()
        self.token = patch.dict(os.environ, {"DEVICE_INGEST_TOKEN": "camera-test-secret", "ALLOW_DEMO_VISION_FALLBACK": "false"})
        self.token.start()

    def tearDown(self):
        self.predict.stop()
        self.token.stop()
        with SessionLocal() as db:
            for log in db.query(CameraLog).filter_by(model_version="test-camera").all():
                (svc.UPLOAD_DIR / log.image_url.split("/")[-1]).unlink(missing_ok=True)
                db.delete(log)
            db.commit()

    @classmethod
    def tearDownClass(cls):
        with SessionLocal() as db:
            db.query(Greenhouse).filter_by(greenhouse_id="camera-other-garden").delete()
            db.query(User).filter_by(user_id="camera-other-user").delete()
            db.commit()

    def upload(self):
        return self.client.post("/api/camera/diagnose", headers=self.headers,
            data={"greenhouse_id": "garden-outdoor-01", "area_id": "area-chili-01"},
            files={"file": ("leaf.jpg", self.photo, "image/jpeg")})

    def test_multipart_upload_has_log_and_real_response_fields(self):
        result = self.upload()
        self.assertEqual(result.status_code, 201, result.text)
        log = result.json()["camera_log"]
        self.assertTrue(log["log_id"])
        self.assertIn("timestamp", log)
        self.assertIn("ai_diagnosis", log)
        self.assertIsNotNone(log["temperature_at_capture"])

    def test_image_requires_auth_and_ownership_for_both_urls(self):
        log = self.upload().json()["camera_log"]
        paths = [log["image_endpoint"], "/api/camera/images/" + log["image_url"].split("/")[-1]]
        other = {"Authorization": "Bearer " + create_access_token("camera-other-user")[0]}
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.get(path + "?token=invalid").status_code, 401)
            self.assertEqual(self.client.get(path, headers=other).status_code, 404)
            allowed = self.client.get(path, headers=self.headers)
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.content, self.photo)
            self.assertIn("no-store", allowed.headers["cache-control"])

    def test_capture_contract_and_upload_correlation_are_idempotent(self):
        with patch.object(svc, "publish_mqtt_json", return_value={"published": True}) as publish:
            sent = self.client.post("/api/camera/capture-trigger", headers=self.headers,
                json={"greenhouse_id": "garden-outdoor-01", "device_id": "ESP32CAM-CHILI-01"})
        self.assertEqual(sent.status_code, 200, sent.text)
        request_id = sent.json()["capture_id"]
        payload = publish.call_args.args[1]
        self.assertEqual(payload["command"], "CAPTURE")
        self.assertEqual(payload["capture_id"], request_id)
        self.assertEqual(payload["device_id"], "ESP32CAM-CHILI-01")
        self.assertIn("expires_at", payload)
        signed = f"{request_id}|ESP32CAM-CHILI-01|garden-outdoor-01|MANUAL|{payload['expires_at']}"
        self.assertEqual(payload["signature"], hmac.new(b"camera-test-secret", signed.encode(), hashlib.sha256).hexdigest())
        path = "/api/camera/logs/" + request_id
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 404)
        for _ in range(2):
            upload = self.client.post("/api/camera/diagnose", headers={"X-Device-Token": "camera-test-secret"},
                data={"device_id": "ESP32CAM-CHILI-01", "capture_id": request_id, "trigger_type": "MANUAL"},
                files={"file": ("leaf.jpg", self.photo, "image/jpeg")})
            self.assertEqual(upload.status_code, 201, upload.text)
            self.assertEqual(upload.json()["camera_log"]["log_id"], request_id)
        self.assertEqual(self.model.call_count, 1)
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 200)

    def test_failed_broker_does_not_claim_dispatch(self):
        with patch.object(svc, "publish_mqtt_json", return_value={"published": False, "error": "offline"}):
            result = self.client.post("/api/camera/capture-trigger", headers=self.headers,
                json={"greenhouse_id": "garden-outdoor-01", "device_id": "ESP32CAM-CHILI-01"})
        self.assertFalse(result.json()["dispatched"])

    def test_sensor_or_inactive_device_cannot_capture(self):
        with patch.object(svc, "publish_mqtt_json") as publish:
            result = self.client.post("/api/camera/capture-trigger", headers=self.headers,
                json={"greenhouse_id": "garden-outdoor-01", "device_id": "SENSOR-TEST"})
            self.assertEqual(result.status_code, 422)
            publish.assert_not_called()
        with SessionLocal() as db:
            camera = db.get(Device, "ESP32CAM-CHILI-01")
            camera.status = "INACTIVE"
            with self.assertRaises(Exception):
                svc.validate_camera_binding(camera, db.get(Greenhouse, "garden-outdoor-01"))

    def test_device_upload_requires_registered_camera_and_matching_garden(self):
        h = {"X-Device-Token": "camera-test-secret", "Content-Type": "image/jpeg"}
        for query in ("greenhouse_id=garden-outdoor-01", "device_id=SENSOR-TEST",
                      "device_id=ESP32CAM-CHILI-01&greenhouse_id=camera-other-garden"):
            result = self.client.post("/api/camera/diagnose?" + query, headers=h, content=self.photo)
            self.assertIn(result.status_code, (404, 422), result.text)
        self.model.assert_not_called()

    def test_wrong_file_type_and_oversize_do_not_run_model(self):
        result = self.client.post("/api/camera/diagnose", headers=self.headers,
            files={"file": ("leaf.webp", self.photo, "image/webp")})
        self.assertEqual(result.status_code, 415)
        with patch("app.controllers.camera_controller.MAX_IMAGE_BYTES", 10):
            self.assertEqual(self.upload().status_code, 413)
        self.model.assert_not_called()

    def test_stale_or_other_area_sensor_context_is_not_used(self):
        with SessionLocal() as db:
            self.assertEqual(svc._fetch_sensor_context(db, "garden-outdoor-01", "missing-area", 60), (None, []))
            db.query(SensorLog).filter_by(device_id="SENSOR-TEST").update({"timestamp": datetime.now(timezone.utc)-timedelta(hours=2)})
            self.assertEqual(svc._fetch_sensor_context(db, "garden-outdoor-01", "area-chili-01", 60), (None, []))
            db.rollback()

    def test_database_failure_removes_new_file(self):
        before = set(svc.UPLOAD_DIR.iterdir())
        with SessionLocal() as db, patch.object(db, "commit", side_effect=RuntimeError("test commit failure")):
            with self.assertRaises(RuntimeError):
                svc.run_camera_diagnosis(db, db.get(Greenhouse, "garden-outdoor-01"), self.photo, "image/jpeg")
        self.assertEqual(set(svc.UPLOAD_DIR.iterdir()), before)

    def test_environment_capture_is_targeted_and_obeys_alert_cooldown(self):
        from app.models import GreenhouseArea
        from app.services.access_service import resolve_effective_thresholds
        from app.services.mqtt_service import _check_abnormal_environment
        with SessionLocal() as db, patch.object(svc, "publish_mqtt_json", return_value={"published": True}) as publish:
            device = db.get(Device, "SENSOR-TEST")
            garden = db.get(Greenhouse, "garden-outdoor-01")
            area = db.get(GreenhouseArea, "area-chili-01")
            latest = db.query(SensorLog).filter_by(device_id=device.device_id).order_by(SensorLog.timestamp.desc()).first()
            thresholds = resolve_effective_thresholds(db, area=area, greenhouse=garden)
            result = _check_abnormal_environment(db, device, garden, area, latest, thresholds)
            self.assertTrue(result["camera_triggered"])
            self.assertEqual(publish.call_args.args[1]["device_id"], "ESP32CAM-CHILI-01")
            self.assertEqual(publish.call_args.args[1]["trigger_type"], "ENV_ALERT")
            db.flush()
            self.assertFalse(_check_abnormal_environment(db, device, garden, area, latest, thresholds)["camera_triggered"])
            self.assertEqual(publish.call_count, 1)
            db.rollback()
