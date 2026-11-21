from typing import Optional

from pydantic import BaseModel, Field


class DeviceInput(BaseModel):
    device_id: str = Field(min_length=1, max_length=50)
    greenhouse_id: str = Field(min_length=1, max_length=50)
    area_id: Optional[str] = Field(default=None, max_length=50)
    device_type: str = Field(default="SENSOR_NODE", min_length=1, max_length=20)
    hardware_model: Optional[str] = Field(default=None, max_length=60)
    status: Optional[str] = Field(default="ACTIVE", max_length=20)


class DeviceStatusInput(BaseModel):
    status: str
