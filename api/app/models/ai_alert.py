from sqlalchemy import Column, DateTime, Float, ForeignKey, ForeignKeyConstraint, String, Text
from sqlalchemy.sql import func

from ..core.database import Base
from .common import JSONType


class CameraLog(Base):
    __tablename__ = "camera_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["area_id", "greenhouse_id"],
            ["greenhouse_areas.area_id", "greenhouse_areas.greenhouse_id"],
            name="fk_camera_logs_area_greenhouse",
        ),
    )
    log_id = Column(String(50), primary_key=True)
    device_id = Column(String(50), ForeignKey("devices.device_id"))
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"))
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    sensor_log_id = Column(String(50), ForeignKey("sensor_logs.log_id"))
    image_url = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    trigger_type = Column(String(20), default="MANUAL", nullable=False)
    cnn_diagnosis = Column(String(120))
    cnn_confidence = Column(Float)
    cnn_scores = Column(JSONType)
    ai_diagnosis = Column(String)
    confidence_score = Column(Float)
    multimodal_reason = Column(Text)
    recommended_action = Column(Text)
    temperature_at_capture = Column(Float)
    humidity_at_capture = Column(Float)
    light_at_capture = Column(Float)
    env_window_summary = Column(JSONType)
    model_version = Column(String(50))
    status = Column(String(30), default="NEW")


class Recommendation(Base):
    __tablename__ = "recommendations"
    rec_id = Column(String(length=50), primary_key=True)
    device_id = Column(String(length=50), ForeignKey("devices.device_id"))
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    camera_log_id = Column(String(50), ForeignKey("camera_logs.log_id"))
    source_type = Column(String(20), default="SENSOR_ONLY", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    condition_diagnosis = Column(String(255))
    fertilizer_action = Column(Text)
    dosage = Column(Float)
    action_note = Column(Text)
    status = Column(String(20), default="PENDING")


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
