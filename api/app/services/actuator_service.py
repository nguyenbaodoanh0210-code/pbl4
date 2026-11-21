"""Business logic for outdoor Pump actuator controls (Manual & Auto)."""

from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ActuatorLog, ActuatorState, Device, Greenhouse, SensorLog, User
from ..schemas import ActuatorUpdateInput
from .mqtt_publisher import control_topic, publish_mqtt_json


VALID_ACTUATOR_TYPES = {"PUMP"}
VALID_CONTROL_MODES = {"MANUAL", "AUTO"}

DEFAULT_AUTO_RULES = {
    "PUMP": {
        "turn_on_temp_above": 33.0,
        "turn_on_humidity_below": 50.0,
        "turn_off_humidity_above": 75.0,
    },
}


def serialize_actuator(item: ActuatorState) -> dict:
    return {
        "actuator_id": item.actuator_id,
        "greenhouse_id": item.greenhouse_id,
        "area_id": item.area_id,
        "device_id": item.device_id,
        "actuator_type": item.actuator_type,
        "control_mode": item.control_mode,
        "is_on": bool(item.is_on),
        "auto_rules": item.auto_rules or DEFAULT_AUTO_RULES.get(item.actuator_type, {}),
        "last_changed_by": item.last_changed_by,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def serialize_actuator_log(item: ActuatorLog) -> dict:
    return {
        "log_id": item.log_id,
        "actuator_id": item.actuator_id,
        "user_id": item.user_id,
        "action": item.action,
        "trigger_source": item.trigger_source,
        "reason": item.reason,
        "ack_status": item.ack_status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def ensure_default_actuators(db: Session, greenhouse_id: str) -> list[ActuatorState]:
    existing = (
        db.query(ActuatorState)
        .filter(
            ActuatorState.greenhouse_id == greenhouse_id,
            ActuatorState.area_id.is_(None),
            ActuatorState.actuator_type == "PUMP",
        )
        .first()
    )
    if existing is None:
        now = datetime.now(timezone.utc)
        existing = ActuatorState(
            actuator_id=f"act-{uuid.uuid4().hex[:12]}",
            greenhouse_id=greenhouse_id,
            area_id=None,
            actuator_type="PUMP",
            control_mode="AUTO",
            is_on=False,
            auto_rules=dict(DEFAULT_AUTO_RULES["PUMP"]),
            last_changed_by="AUTO_RULE",
            updated_at=now,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)
    return [existing]


def get_garden_actuators_payload(db: Session, greenhouse_id: str) -> dict:
    actuators = ensure_default_actuators(db, greenhouse_id)
    actuator_ids = [item.actuator_id for item in actuators]
    logs = (
        db.query(ActuatorLog)
        .filter(ActuatorLog.actuator_id.in_(actuator_ids))
        .order_by(ActuatorLog.created_at.desc())
        .limit(10)
        .all()
        if actuator_ids
        else []
    )
    return {
        "greenhouse_id": greenhouse_id,
        "actuators": [serialize_actuator(item) for item in actuators],
        "recent_logs": [serialize_actuator_log(item) for item in logs],
    }


def update_actuator_control(
    db: Session,
    greenhouse: Greenhouse,
    actuator_type: str,
    body: ActuatorUpdateInput,
    current_user: User,
) -> dict:
    kind = actuator_type.strip().upper()
    if kind not in VALID_ACTUATOR_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Hệ thống khu vườn ngoài trời chỉ hỗ trợ điều khiển Bơm nước (PUMP)",
        )

    actuators = ensure_default_actuators(db, greenhouse.greenhouse_id)
    target = actuators[0]

    new_mode = target.control_mode
    if body.control_mode is not None:
        candidate_mode = body.control_mode.strip().upper()
        if candidate_mode not in VALID_CONTROL_MODES:
            raise HTTPException(
                status_code=422, detail="control_mode phải là MANUAL hoặc AUTO"
            )
        new_mode = candidate_mode

    if body.is_on is not None and new_mode != "MANUAL":
        raise HTTPException(
            status_code=409,
            detail="Bơm nước đang ở chế độ Tự động (AUTO). Hãy chuyển sang Thủ công (MANUAL) trước khi bật/tắt.",
        )

    mode_changed = new_mode != target.control_mode
    state_changed = body.is_on is not None and bool(body.is_on) != bool(target.is_on)

    now = datetime.now(timezone.utc)
    target.control_mode = new_mode
    if body.is_on is not None:
        target.is_on = bool(body.is_on)
    if body.auto_rules is not None:
        target.auto_rules = body.auto_rules
    target.last_changed_by = "USER"
    target.updated_at = now

    if state_changed:
        action = "TURN_ON" if target.is_on else "TURN_OFF"
    elif mode_changed:
        action = "MODE_CHANGE"
    else:
        action = "TURN_ON" if target.is_on else "TURN_OFF"

    mqtt_payload = {
        "greenhouse_id": greenhouse.greenhouse_id,
        "device_id": target.device_id,
        "actuator_type": "PUMP",
        "control_mode": target.control_mode,
        "is_on": bool(target.is_on),
        "timestamp": now.isoformat(),
    }
    mqtt_result = publish_mqtt_json(
        control_topic(greenhouse.greenhouse_id), mqtt_payload
    )

    default_reason = (
        f"Người dùng chuyển Bơm nước sang chế độ {target.control_mode}"
        if mode_changed and not state_changed
        else f"Người dùng {'bật' if target.is_on else 'tắt'} Bơm nước ở chế độ {target.control_mode}"
    )
    log = ActuatorLog(
        log_id=str(uuid.uuid4()),
        actuator_id=target.actuator_id,
        user_id=current_user.user_id,
        action=action,
        trigger_source="MANUAL",
        reason=(body.reason.strip() if body.reason else default_reason),
        ack_status="ACK" if mqtt_result["published"] else "PENDING",
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(target)
    db.refresh(log)

    return {
        "actuator": serialize_actuator(target),
        "log": serialize_actuator_log(log),
        "mqtt": mqtt_result,
    }


def evaluate_auto_actuators(
    db: Session,
    device: Device,
    sensor_log: SensorLog,
    thresholds: dict,
) -> list[dict]:
    """Evaluate AUTO rules for the outdoor water Pump based on DHT22 + Light readings."""
    if not device.greenhouse_id:
        return []

    actuators = ensure_default_actuators(db, device.greenhouse_id)
    changes: list[dict] = []
    now = datetime.now(timezone.utc)
    temp = sensor_log.temperature
    hum = sensor_log.humidity

    for item in actuators:
        if item.control_mode != "AUTO" or item.actuator_type != "PUMP":
            continue
        rules = item.auto_rules or DEFAULT_AUTO_RULES["PUMP"]
        desired = bool(item.is_on)
        reason = None

        temp_on = float(rules.get("turn_on_temp_above", thresholds.get("max_temp", 33.0)))
        hum_on = float(rules.get("turn_on_humidity_below", thresholds.get("min_humidity", 50.0)))
        hum_off = float(rules.get("turn_off_humidity_above", 75.0))

        if (hum is not None and hum <= hum_on) or (
            temp is not None and temp >= temp_on and (hum is None or hum < hum_off)
        ):
            desired = True
            reason = (
                f"Tự động bật Bơm nước: độ ẩm không khí thấp ({hum}%) hoặc nắng nóng ({temp}°C)."
            )
        elif hum is not None and hum >= hum_off:
            desired = False
            reason = f"Tự động tắt Bơm nước: độ ẩm đã đạt {hum}% (≥ {hum_off}%)."

        if desired != bool(item.is_on) and reason:
            item.is_on = desired
            item.last_changed_by = "AUTO_RULE"
            item.updated_at = now
            mqtt_result = publish_mqtt_json(
                control_topic(device.greenhouse_id),
                {
                    "greenhouse_id": device.greenhouse_id,
                    "device_id": item.device_id,
                    "actuator_type": "PUMP",
                    "control_mode": "AUTO",
                    "is_on": desired,
                    "reason": reason,
                    "timestamp": now.isoformat(),
                },
            )
            log = ActuatorLog(
                log_id=str(uuid.uuid4()),
                actuator_id=item.actuator_id,
                user_id=None,
                action="TURN_ON" if desired else "TURN_OFF",
                trigger_source="AUTO_RULE",
                reason=reason,
                ack_status="ACK" if mqtt_result["published"] else "PENDING",
                created_at=now,
            )
            db.add(log)
            changes.append({"actuator_type": "PUMP", "is_on": desired, "reason": reason})

    return changes
