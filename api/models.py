from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from database import Base

# Bảng Nhà Kính
class Greenhouse(Base):
    __tablename__ = "greenhouses"
    greenhouse_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    area_sqm = Column(Float)
    location = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Bảng Thiết bị
class Device(Base):
    __tablename__ = "devices"
    device_id = Column(String(length=50), primary_key=True)
    greenhouse_id = Column(String(length=50))
    device_type = Column(String(20), default="SENSOR_NODE")
    is_online = Column(Boolean, default=False)
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
    soil_pH = Column(Float)
    N = Column(Float)
    P = Column(Float)
    K = Column(Float)

# Bảng Đề xuất Phân bón (AI)
class Recommendation(Base):
    __tablename__ = "recommendations"
    rec_id = Column(String(length=50), primary_key=True)
    device_id = Column(String(length=50), ForeignKey("devices.device_id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    condition_diagnosis = Column(String(100))
    fertilizer_action = Column(String(100))
    status = Column(String(20), default="PENDING")