from typing import Literal, Optional
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IrrigationRules(BaseModel):
    """Explicit per-zone setup. No universal crop thresholds are inferred."""
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    schema_version: Literal[2] = 2
    sensor_device_id: str = Field(min_length=1, max_length=50)
    start_below_pct: float = Field(ge=0, lt=100)
    stop_at_pct: float = Field(gt=0, le=100)
    max_run_seconds: int = Field(default=30, ge=1, le=120)
    base_run_seconds: int = Field(default=20, ge=1, le=120)
    cooldown_seconds: int = Field(default=600, ge=60, le=86400)
    max_sensor_age_seconds: int = Field(default=120, ge=10, le=120)
    locked: bool = False
    hardware_verified: bool = False
    max_daily_seconds: int = Field(default=600, ge=1, le=3600)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    rain_exposed: bool = False
    hot_day_c: float = Field(default=35, ge=25, le=50)
    morning_multiplier: float = Field(default=1.0, ge=1, le=1.5)
    rainy_evening_multiplier: float = Field(default=1.0, ge=0.25, le=1)
    rain_probability_pct: float = Field(default=70, ge=0, le=100)
    rain_mm: float = Field(default=5, gt=0, le=100)
    timezone: str = "Asia/Ho_Chi_Minh"
    allowed_start: str | None = None
    allowed_end: str | None = None
    max_temperature_c: float | None = Field(default=None, ge=-40, le=85)
    max_light_lux: float | None = Field(default=None, ge=0, le=200000)

    @model_validator(mode="after")
    def check_policy(self):
        if self.base_run_seconds > self.max_run_seconds:
            raise ValueError("Thời lượng cơ sở không được vượt thời hạn tự ngắt")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Cần nhập cả vĩ độ và kinh độ")
        if not self.sensor_device_id.strip():
            raise ValueError("sensor_device_id không được rỗng")
        if self.start_below_pct >= self.stop_at_pct:
            raise ValueError("Ngưỡng bật phải nhỏ hơn ngưỡng dừng độ ẩm đất")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Múi giờ không hợp lệ") from None
        if (self.allowed_start is None) != (self.allowed_end is None):
            raise ValueError("Cần cả allowed_start và allowed_end")
        if self.allowed_start is not None:
            for value in (self.allowed_start, self.allowed_end):
                parsed = time.fromisoformat(value)
                if len(value) != 5 or parsed.tzinfo or parsed.second or parsed.microsecond:
                    raise ValueError("Khung giờ phải theo HH:MM")
            if self.allowed_start == self.allowed_end:
                raise ValueError("Giờ bắt đầu và kết thúc phải khác nhau; bỏ cả hai để cho phép cả ngày")
        return self


class ActuatorUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    control_mode: Optional[str] = Field(default=None, max_length=20)
    is_on: Optional[bool] = None
    auto_rules: Optional[IrrigationRules] = None
    device_id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    reason: Optional[str] = Field(default=None, max_length=300)
    area_id: Optional[str] = Field(default=None, max_length=50)
