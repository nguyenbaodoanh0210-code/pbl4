"""Unit & integration checks for Multimodal AI fusion and ESP32-CAM diagnosis pipeline."""

from pathlib import Path
import unittest

from fastapi import HTTPException

from app.core.database import SessionLocal
from app.models import CameraLog, Device, Greenhouse, GreenhouseArea, Notification, Recommendation, User
from app.services.camera_service import (
    UPLOAD_DIR,
    resolve_stored_image_path,
    resolve_uploaded_filename,
    run_camera_diagnosis,
)
from app.services.multimodal_service import fuse_multimodal_diagnosis


API_ROOT = Path(__file__).resolve().parents[1]


class TestMultimodalFusion(unittest.TestCase):
    def test_fungal_disease_corroborated_by_high_humidity_and_low_light(self):
        cnn = {"class_name": "leaf spot", "scores": {"leaf spot": 0.80, "healthy": 0.20}}
        env_snapshot = {"temperature": 25.5, "humidity": 89.5, "light_level": 3500.0}
        env_history = [
            {"temperature": 25.2, "humidity": 87.0, "light_level": 4100.0},
            {"temperature": 25.4, "humidity": 88.5, "light_level": 3800.0},
            env_snapshot,
        ]
        crop = {
            "crop_name": "Cây ớt",
            "max_temp": 33.0,
            "min_humidity": 55.0,
            "max_humidity": 80.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 8000.0,
            "fungal_duration_minutes": 60,
        }
        result = fuse_multimodal_diagnosis(cnn, env_snapshot, env_history, crop)
        self.assertEqual(result["final_diagnosis"], "Nấm đốm lá (Leaf Spot)")
        self.assertFalse(result["is_healthy"])
        self.assertGreater(result["multimodal_confidence"], result["cnn_confidence"])
        self.assertAlmostEqual(result["multimodal_confidence"], 0.92, places=2)
        self.assertIn("89.5%", result["multimodal_reason"])
        self.assertIn("Cây ớt", result["multimodal_reason"])
        self.assertIn("lá ớt", result["recommended_action"])

    def test_fungal_disease_dampened_when_outdoor_environment_is_dry_and_bright(self):
        cnn = {"class_name": "leaf spot", "scores": {"leaf spot": 0.72, "healthy": 0.28}}
        env_snapshot = {"temperature": 29.0, "humidity": 58.0, "light_level": 32000.0}
        crop = {
            "crop_name": "Cây ớt",
            "max_humidity": 80.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 8000.0,
        }
        result = fuse_multimodal_diagnosis(cnn, env_snapshot, [env_snapshot], crop)
        self.assertLess(result["multimodal_confidence"], result["cnn_confidence"])
        self.assertIn("khô thoáng", result["multimodal_reason"])

    def test_healthy_leaf_with_high_fungal_risk_emits_preventive_warning(self):
        cnn = {"class_name": "healthy", "scores": {"healthy": 0.91, "leaf spot": 0.09}}
        env_snapshot = {"temperature": 24.0, "humidity": 90.0, "light_level": 4000.0}
        env_history = [
            {"temperature": 24.0, "humidity": 88.0, "light_level": 4200.0},
            env_snapshot,
        ]
        crop = {
            "crop_name": "Cây xà lách",
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 6000.0,
        }
        result = fuse_multimodal_diagnosis(cnn, env_snapshot, env_history, crop)
        self.assertTrue(result["is_healthy"])
        self.assertEqual(result["final_diagnosis"], "Khỏe mạnh")
        self.assertIn("cảnh báo sớm", result["multimodal_reason"])
        self.assertIn("bơm tưới", result["recommended_action"])

    def test_path_traversal_is_blocked(self):
        with self.assertRaises(HTTPException) as ctx:
            resolve_uploaded_filename("../.env")
        self.assertEqual(ctx.exception.status_code, 400)


class TestCameraPipelineIntegration(unittest.TestCase):
    def test_end_to_end_camera_diagnosis_persists_and_alerts(self):
        sample_images = sorted(
            (API_ROOT / "data" / "chili_plant_disease" / "test" / "unhealthy" / "leaf spot").glob("*.jpg")
        )
        self.assertTrue(sample_images, "Expected at least one sample chili image in test dataset")
        image_bytes = sample_images[0].read_bytes()

        def fake_cnn(raw_bytes: bytes, content_type: str | None = None) -> dict:
            return {
                "class_name": "leaf spot",
                "scores": {"leaf spot": 0.82, "yellowish": 0.10, "healthy": 0.08},
                "model_version": "unit_test_cnn+multimodal_v1",
            }

        db = SessionLocal()
        created_log_id = None
        saved_filename = None
        try:
            garden = db.query(Greenhouse).filter(Greenhouse.greenhouse_id == "garden-outdoor-01").first()
            area = db.query(GreenhouseArea).filter(GreenhouseArea.area_id == "area-chili-01").first()
            device = db.query(Device).filter(Device.device_id == "ESP32CAM-CHILI-01").first()
            self.assertIsNotNone(garden)
            self.assertIsNotNone(area)

            res = run_camera_diagnosis(
                db=db,
                greenhouse=garden,
                image_bytes=image_bytes,
                expected_content_type="image/jpeg",
                area=area,
                device=device,
                trigger_type="ENV_ALERT",
                predictor=fake_cnn,
            )
            cam_log = res["camera_log"]
            created_log_id = cam_log["log_id"]
            saved_filename = cam_log["image_url"].split("/")[-1]

            self.assertEqual(cam_log["trigger_type"], "ENV_ALERT")
            self.assertEqual(cam_log["ai_diagnosis"], "Nấm đốm lá (Leaf Spot)")
            self.assertGreater(cam_log["confidence_score"], cam_log["cnn_confidence"])
            self.assertIsNotNone(cam_log["temperature_at_capture"])
            self.assertIsNotNone(cam_log["humidity_at_capture"])
            self.assertIsNotNone(cam_log["light_at_capture"])
            self.assertTrue(res["notification_created"])
            self.assertIsNotNone(res["recommendation_id"])

            # Verify stored image resolves safely
            path, media_type = resolve_stored_image_path(cam_log["image_url"])
            self.assertTrue(path.is_file())
            self.assertEqual(media_type, "image/jpeg")
        finally:
            if created_log_id:
                db.query(Notification).filter(Notification.camera_log_id == created_log_id).delete(synchronize_session=False)
                db.query(Recommendation).filter(Recommendation.camera_log_id == created_log_id).delete(synchronize_session=False)
                db.query(CameraLog).filter(CameraLog.log_id == created_log_id).delete(synchronize_session=False)
                db.commit()
            if saved_filename:
                (UPLOAD_DIR / saved_filename).unlink(missing_ok=True)
            db.close()


if __name__ == "__main__":
    unittest.main()
