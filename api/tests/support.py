"""Isolated fixtures: never use the project's Neon database or a real MQTT broker."""
import atexit
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Keep test databases/images on the project drive, not the often-small Windows C: drive.
_temp_root = Path(__file__).resolve().parents[1] / ".pytest_cache"
_temp_root.mkdir(parents=True, exist_ok=True)
_temp = tempfile.TemporaryDirectory(prefix="pbl4-tests-", dir=_temp_root)
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_temp.name) / "test.db").as_posix()
os.environ["AUTH_TOKEN_SECRET"] = "test-only-not-production-secret-20261122"
os.environ["MQTT_PUBLISH_ENABLED"] = "false"

# Set the environment before importing any project module.
from app.core.database import Base, SessionLocal, engine
from app.core.auth import hash_password
from app.models import Crop, Device, Greenhouse, GreenhouseArea, SensorLog, User
from app.services import camera_service

camera_service.UPLOAD_DIR = Path(_temp.name) / "images"
camera_service.UPLOAD_DIR.mkdir()
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(User(user_id="test-farmer", full_name="Test farmer", role="FARMER",
                email="demo@smartgreenhouse.local", password_hash=hash_password("Demo@12345678")))
    db.add_all([Crop(crop_stage_id="crop-chili-vegetative", crop_name="Cây ớt", growth_stage="Vegetative"),
                Crop(crop_stage_id="crop-lettuce-vegetative", crop_name="Cây xà lách", growth_stage="Vegetative")])
    db.commit()
    db.add(Greenhouse(greenhouse_id="garden-outdoor-01", user_id="test-farmer", name="Test garden",
                      crop_stage_id="crop-chili-vegetative", area_sqm=30))
    db.commit()
    db.add(GreenhouseArea(area_id="area-chili-01", greenhouse_id="garden-outdoor-01",
                          crop_stage_id="crop-chili-vegetative", name="Test chili", area_sqm=10))
    db.commit()
    db.add_all([Device(device_id="ESP32CAM-CHILI-01", device_type="CAMERA_NODE", status="ACTIVE",
                       greenhouse_id="garden-outdoor-01", area_id="area-chili-01"),
                Device(device_id="SENSOR-TEST", device_type="SENSOR_NODE", status="ACTIVE",
                       greenhouse_id="garden-outdoor-01", area_id="area-chili-01")])
    db.commit()
    for i in range(13):
        db.add(SensorLog(log_id=f"test-sensor-{i}", device_id="SENSOR-TEST", temperature=25,
                        humidity=90, light_level=1000, soil_moisture=55,
                        timestamp=datetime.now(timezone.utc)-timedelta(minutes=5*i)))
    db.commit()

def _cleanup():
    engine.dispose()
    _temp.cleanup()

atexit.register(_cleanup)
