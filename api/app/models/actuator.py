from sqlalchemy import Boolean, Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text
from sqlalchemy.sql import func

from ..core.database import Base
from .common import JSONType


class ActuatorState(Base):
    __tablename__ = "actuator_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["area_id", "greenhouse_id"],
            ["greenhouse_areas.area_id", "greenhouse_areas.greenhouse_id"],
            name="fk_actuator_states_area_greenhouse",
        ),
    )
    actuator_id = Column(String(50), primary_key=True)
    greenhouse_id = Column(String(50), ForeignKey("greenhouses.greenhouse_id"), nullable=False)
    area_id = Column(String(50), ForeignKey("greenhouse_areas.area_id"))
    device_id = Column(String(50), ForeignKey("devices.device_id"))
    actuator_type = Column(String(20), nullable=False)
    control_mode = Column(String(20), default="MANUAL", nullable=False)
    is_on = Column(Boolean, default=False, nullable=False)
    reported_on = Column(Boolean)
    reported_at = Column(DateTime(timezone=True))
    auto_rules = Column(JSONType)
    last_changed_by = Column(String(30), default="AUTO_RULE", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActuatorLog(Base):
    __tablename__ = "actuator_logs"
    log_id = Column(String(50), primary_key=True)
    actuator_id = Column(String(50), ForeignKey("actuator_states.actuator_id"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.user_id"))
    action = Column(String(20), nullable=False)
    trigger_source = Column(String(20), nullable=False)
    reason = Column(Text)
    ack_status = Column(String(20), default="PENDING", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
