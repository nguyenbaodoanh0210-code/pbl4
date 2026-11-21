from typing import Optional

from pydantic import BaseModel, Field


class CaptureTriggerInput(BaseModel):
    greenhouse_id: Optional[str] = Field(default=None, max_length=50)
    area_id: Optional[str] = Field(default=None, max_length=50)
    device_id: Optional[str] = Field(default=None, max_length=50)
    trigger_type: str = Field(default="MANUAL", max_length=20)


class CameraLogStatusInput(BaseModel):
    status: str = Field(min_length=1, max_length=30)
