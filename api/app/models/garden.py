from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from ..core.database import Base


class Crop(Base):
    __tablename__ = "crops"
    crop_stage_id = Column(String(50), primary_key=True)
    crop_name = Column(String, nullable=False)
    growth_stage = Column(String, nullable=False)
    environment_type = Column(String(30), default="OUTDOOR", nullable=False)
    min_temp = Column(Float)
    max_temp = Column(Float)
    min_humidity = Column(Float)
    max_humidity = Column(Float)
    min_light = Column(Float)
    max_light = Column(Float)
    fungal_humidity_threshold = Column(Float, default=85.0, nullable=False)
    fungal_light_threshold = Column(Float)
    fungal_duration_minutes = Column(Integer, default=60, nullable=False)
    min_soil_moisture = Column(Float)
    optimum_ph = Column(Float)
    target_n = Column(Float)
    target_p = Column(Float)
    target_k = Column(Float)


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
    environment_type = Column(String(30), default="OUTDOOR", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GreenhouseArea(Base):
    __tablename__ = "greenhouse_areas"
    __table_args__ = (
        UniqueConstraint("area_id", "greenhouse_id", name="uq_greenhouse_areas_id_greenhouse"),
    )
    area_id = Column(String(50), primary_key=True)
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"), nullable=False)
    crop_stage_id = Column(String(50), ForeignKey("crops.crop_stage_id"))
    name = Column(String(100), nullable=False)
    area_sqm = Column(Float, nullable=False)
    custom_min_temp = Column(Float)
    custom_max_temp = Column(Float)
    custom_min_humidity = Column(Float)
    custom_max_humidity = Column(Float)
    custom_min_light = Column(Float)
    custom_max_light = Column(Float)
    custom_fungal_humidity_threshold = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
