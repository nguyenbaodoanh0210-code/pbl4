from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from .database import Base

# Bảng Nhà Kính
class Greenhouse(Base):
    __tablename__ = "greenhouses"
    greenhouse_id = Column(String(50), primary_key=True)
    user_id = Column(
        String(50),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        index=True,
    )
    crop_stage_id = Column(String(50), ForeignKey("crops.crop_stage_id"))
    name = Column(String(100), nullable=False)
    area_sqm = Column(Float)
    location = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Bảng Thiết bị
class Device(Base):
    __tablename__ = "devices"
    device_id = Column(String(length=50), primary_key=True)
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"))
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    device_type = Column(String(20), default="SENSOR_NODE")
    is_online = Column(Boolean, default=False)
    battery_level = Column(Integer)
    send_interval = Column(Integer, default=5)
    last_updated = Column(DateTime(timezone=True))
    status = Column(String(20), default="ACTIVE")

# Bảng Nhật ký Cảm biến
class SensorLog(Base):
    __tablename__ = "sensor_logs"
    log_id = Column(String(length=50), primary_key=True)
    device_id = Column(String(length=50), ForeignKey("devices.device_id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    temperature = Column(Float)
    humidity = Column(Float)
    soil_moisture = Column(Float)
    soil_pH = Column("soil_ph", Float)
    N = Column("n", Float)
    P = Column("p", Float)
    K = Column("k", Float)

# Bảng Đề xuất Phân bón (AI)
class Recommendation(Base):
    __tablename__ = "recommendations"
    rec_id = Column(String(length=50), primary_key=True)
    device_id = Column(String(length=50), ForeignKey("devices.device_id"))
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    condition_diagnosis = Column(String(100))
    fertilizer_action = Column(String(100))
    dosage = Column(Float)
    action_note = Column(Text)
    status = Column(String(20), default="PENDING")

class User(Base):
    __tablename__ = "users"
    user_id = Column(String(50), primary_key=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String)
    email = Column(String(254))
    password_hash = Column(String(255))
    fcm_token = Column(Text)
    role = Column(String(30), default="FARMER")


class Crop(Base):
    __tablename__ = "crops"
    crop_stage_id = Column(String(50), primary_key=True)
    crop_name = Column(String, nullable=False)
    growth_stage = Column(String, nullable=False)
    min_temp = Column(Float)
    max_temp = Column(Float)
    min_humidity = Column(Float)
    max_humidity = Column(Float)
    min_soil_moisture = Column(Float)
    optimum_ph = Column(Float)
    target_n = Column(Float)
    target_p = Column(Float)
    target_k = Column(Float)


class GreenhouseArea(Base):
    __tablename__ = "greenhouse_areas"
    area_id = Column(String(50), primary_key=True)
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"), nullable=False)
    crop_stage_id = Column(String(50), ForeignKey("crops.crop_stage_id"))
    name = Column(String(100), nullable=False)
    area_sqm = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CameraLog(Base):
    __tablename__ = "camera_logs"
    log_id = Column(String(50), primary_key=True)
    device_id = Column(String(50), ForeignKey("devices.device_id"))
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"))
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    image_url = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ai_diagnosis = Column(String)
    confidence_score = Column(Float)
    status = Column(String(30), default="NEW")


class Notification(Base):
    __tablename__ = "notifications"
    notification_id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.user_id"))
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"))
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    device_id = Column(String(50), ForeignKey("devices.device_id"))
    recommendation_id = Column(String(50), ForeignKey("recommendations.rec_id"))
    camera_log_id = Column(String(50), ForeignKey("camera_logs.log_id"))
    category = Column(String(30), nullable=False)
    severity = Column(String(20), default="INFO", nullable=False)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="UNREAD", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True))
