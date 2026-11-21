from typing import Any, Optional

from pydantic import BaseModel, Field


class ActuatorUpdateInput(BaseModel):
    control_mode: Optional[str] = Field(default=None, max_length=20)
    is_on: Optional[bool] = None
    auto_rules: Optional[dict[str, Any]] = None
    reason: Optional[str] = Field(default=None, max_length=300)
    area_id: Optional[str] = Field(default=None, max_length=50)
