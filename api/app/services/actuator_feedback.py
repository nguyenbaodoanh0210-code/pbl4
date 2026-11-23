"""Device acknowledgements; broker PUBACK alone never proves the pump is running."""
from datetime import datetime, timedelta, timezone
import hmac
import os
import uuid
from fastapi import HTTPException
from ..models import ActuatorLog, ActuatorState, Device
from .sensor_validation import utc


def record_feedback(db, device_id, command_id, is_on, token):
    expected = os.getenv("DEVICE_INGEST_TOKEN", "")
    if not expected or not hmac.compare_digest(str(token), expected):
        raise HTTPException(401, "Token thiết bị không hợp lệ")
    command = db.query(ActuatorLog).filter_by(log_id=command_id).first()
    if not command or command.ack_status == "FAILED":
        raise HTTPException(404, "Không có lệnh đã gửi")
    item = db.query(ActuatorState).filter_by(actuator_id=command.actuator_id).with_for_update().one()
    device = db.query(Device).filter_by(device_id=device_id, status="ACTIVE").first()
    if not device or device.deleted_at or item.device_id != device_id or item.greenhouse_id != device.greenhouse_id:
        raise HTTPException(403, "Thiết bị không thuộc lệnh")
    newest = db.query(ActuatorLog).filter_by(actuator_id=item.actuator_id).order_by(ActuatorLog.created_at.desc()).first()
    # Feedback from superseded commands cannot overwrite the current state.
    if newest.log_id != command_id:
        if not is_on and command.ack_status == "ACK" and item.reported_on is False:
            return {"status": "duplicate"}
        raise HTTPException(409, "Lệnh đã được thay thế")
    now = datetime.now(timezone.utc)
    if is_on and (command.action != "TURN_ON" or not item.is_on or now > utc(command.created_at)+timedelta(seconds=15)):
        raise HTTPException(409, "Xác nhận bật đã hết hạn hoặc không khớp")
    if is_on and command.acknowledged_at:
        return {"status": "duplicate"}
    if not is_on and command.action == "TURN_ON":
        # Board's independent lease stop is a distinct confirmed event.
        db.add(ActuatorLog(log_id=str(uuid.uuid4()), actuator_id=item.actuator_id, action="TURN_OFF",
            trigger_source="AUTO_RULE", reason="Board xác nhận tự ngắt", ack_status="ACK",
            created_at=now, acknowledged_at=now, duration_seconds=0))
    else:
        command.ack_status = "ACK"
        if command.acknowledged_at is None:
            command.acknowledged_at = now
    item.reported_on, item.reported_at = is_on, now
    if not is_on:
        item.is_on = False
    db.commit()
    return {"status": "acknowledged", "is_on": is_on}
