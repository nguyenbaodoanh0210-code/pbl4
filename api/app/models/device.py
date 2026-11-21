from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, String
from sqlalchemy.sql import func

from ..core.database import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["area_id", "greenhouse_id"],
            ["greenhouse_areas.area_id", "greenhouse_areas.greenhouse_id"],
            name="fk_devices_area_greenhouse",
        ),
    )
    device_id = Column(String(length=50), primary_key=True)
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"))
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    device_type = Column(String(20), default="SENSOR_NODE")
    hardware_model = Column(String(60))
    is_online = Column(Boolean, default=False)
    battery_level = Column(Integer)
    send_interval = Column(Integer, default=5)
    last_updated = Column(DateTime(timezone=True))
    status = Column(String(20), default="ACTIVE")
    deleted_at = Column(DateTime(timezone=True))


class SensorLog(Base):
    __tablename__ = "sensor_logs"
    log_id = Column(String(length=50), primary_key=True)
    device_id = Column(String(length=50), ForeignKey("devices.device_id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    temperature = Column(Float)
    humidity = Column(Float)
    light_level = Column(Float)
    soil_moisture = Column(Float)
    soil_pH = Column("soil_ph", Float)
    N = Column("n", Float)
    P = Column("p", Float)
    K = Column("k", Float)
