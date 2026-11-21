from typing import Optional

from pydantic import BaseModel, Field


class GreenhouseInput(BaseModel):
    greenhouse_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    area_sqm: Optional[float] = Field(default=None, gt=0)
    location: Optional[str] = Field(default=None, max_length=255)
    environment_type: Optional[str] = Field(default="OUTDOOR", max_length=30)


class AreaCreateInput(BaseModel):
    area_id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    area_sqm: float = Field(gt=0)
    crop_stage_id: Optional[str] = Field(default=None, max_length=50)
    custom_min_temp: Optional[float] = Field(default=None, ge=-40, le=85)
    custom_max_temp: Optional[float] = Field(default=None, ge=-40, le=85)
    custom_min_humidity: Optional[float] = Field(default=None, ge=0, le=100)
    custom_max_humidity: Optional[float] = Field(default=None, ge=0, le=100)
    custom_min_light: Optional[float] = Field(default=None, ge=0)
    custom_max_light: Optional[float] = Field(default=None, ge=0)
    custom_fungal_humidity_threshold: Optional[float] = Field(default=None, ge=0, le=100)


class AreaUpdateInput(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    area_sqm: Optional[float] = Field(default=None, gt=0)
    crop_stage_id: Optional[str] = Field(default=None, max_length=50)
    custom_min_temp: Optional[float] = Field(default=None, ge=-40, le=85)
    custom_max_temp: Optional[float] = Field(default=None, ge=-40, le=85)
    custom_min_humidity: Optional[float] = Field(default=None, ge=0, le=100)
    custom_max_humidity: Optional[float] = Field(default=None, ge=0, le=100)
    custom_min_light: Optional[float] = Field(default=None, ge=0)
    custom_max_light: Optional[float] = Field(default=None, ge=0)
    custom_fungal_humidity_threshold: Optional[float] = Field(default=None, ge=0, le=100)
