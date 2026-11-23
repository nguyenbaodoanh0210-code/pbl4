"""Pump and Fan actuator control controller (Manual & Auto)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import User
from ..schemas import ActuatorUpdateInput
from ..services import (
    get_garden_actuators_payload,
    require_greenhouse_access,
    update_actuator_control,
)

router = APIRouter(prefix="/api/greenhouses", tags=["actuators"])


class PumpFeedback(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    device_id: str = Field(min_length=1, max_length=50)
    command_id: str = Field(min_length=1, max_length=50)
    is_on: bool
    device_token: str = Field(min_length=1, max_length=300)


@router.post("/pump-feedback")
def pump_feedback(body: PumpFeedback, db: Session = Depends(get_db)):
    from ..services.actuator_feedback import record_feedback
    return record_feedback(db, body.device_id, body.command_id, body.is_on, body.device_token)


@router.get("/{greenhouse_id}/actuators")
def get_actuators(
    greenhouse_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_greenhouse_access(greenhouse_id, db, current_user)
    return get_garden_actuators_payload(db, greenhouse_id)


@router.put("/{greenhouse_id}/actuators/{actuator_type}")
@router.patch("/{greenhouse_id}/actuators/{actuator_type}")
def set_actuator(
    greenhouse_id: str,
    actuator_type: str,
    body: ActuatorUpdateInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    greenhouse = require_greenhouse_access(greenhouse_id, db, current_user)
    return update_actuator_control(db, greenhouse, actuator_type, body, current_user)
