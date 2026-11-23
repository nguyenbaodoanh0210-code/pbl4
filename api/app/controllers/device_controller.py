"""Devices (NodeMCU v2.0.0, ESP32-CAM, Actuators) and Sensor Logs controller."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import Device, SensorLog, User
from ..schemas import DeviceInput, DeviceStatusInput
from ..services.public_fields import sensor_fields
from ..services import (
    accessible_devices,
    require_area_access,
    require_device_access,
    require_greenhouse_access,
)

router = APIRouter(prefix="/api", tags=["devices & sensors"])

VALID_DEVICE_TYPES = {"SENSOR_NODE", "CAMERA_NODE", "CAMERA", "ACTUATOR"}
VALID_DEVICE_STATUSES = {"ACTIVE", "INACTIVE", "ERROR"}


@router.get("/devices")
def get_devices(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_retired: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        accessible_devices(db, current_user, include_retired=include_retired)
        .order_by(Device.device_id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/devices", status_code=201)
def register_device(
    body: DeviceInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_greenhouse_access(body.greenhouse_id, db, current_user)
    if body.area_id:
        require_area_access(body.greenhouse_id, body.area_id, db, current_user)

    device_id = body.device_id.strip()
    if not device_id:
        raise HTTPException(status_code=422, detail="device_id không được để trống")
    if db.query(Device).filter(Device.device_id == device_id).first():
        raise HTTPException(status_code=409, detail="device_id đã tồn tại")

    device_type = body.device_type.strip().upper()
    if device_type not in VALID_DEVICE_TYPES:
        raise HTTPException(
            status_code=422,
            detail="device_type phải là SENSOR_NODE, CAMERA_NODE hoặc ACTUATOR",
        )

    status = (body.status or "ACTIVE").upper().strip()
    if status not in VALID_DEVICE_STATUSES:
        raise HTTPException(
            status_code=422, detail="status phải là ACTIVE, INACTIVE hoặc ERROR"
        )

    default_hw = {
        "SENSOR_NODE": "NodeMCU v2.0.0 (DHT22 + Quang trở LDR)",
        "CAMERA_NODE": "ESP32-CAM",
        "CAMERA": "ESP32-CAM",
        "ACTUATOR": "Bộ điều khiển Bơm nước",
    }
    item = Device(
        device_id=device_id,
        greenhouse_id=body.greenhouse_id,
        area_id=body.area_id or None,
        device_type=device_type,
        hardware_model=(
            body.hardware_model.strip()
            if body.hardware_model and body.hardware_model.strip()
            else default_hw[device_type]
        ),
        status=status,
        is_online=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete device (RETIRED) to preserve historical sensor_logs and camera_logs."""
    item = require_device_access(device_id, db, current_user)
    item.status = "RETIRED"
    item.is_online = False
    item.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.patch("/devices/{device_id}/status")
def update_device_status(
    device_id: str,
    body: DeviceStatusInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status = body.status.strip().upper()
    if status not in VALID_DEVICE_STATUSES:
        raise HTTPException(
            status_code=422, detail="status phải là ACTIVE, INACTIVE hoặc ERROR"
        )
    item = require_device_access(device_id, db, current_user)
    item.status = status
    if status in {"INACTIVE", "ERROR"}:
        item.is_online = False
    db.commit()
    db.refresh(item)
    return item


@router.get("/sensors/{device_id}")
def get_sensor_by_device(
    device_id: str,
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (start and start.tzinfo is None) or (end and end.tzinfo is None):
        raise HTTPException(
            status_code=422, detail="start/end phải có múi giờ ISO 8601"
        )
    if start and end and start > end:
        raise HTTPException(
            status_code=422, detail="start phải nhỏ hơn hoặc bằng end"
        )
    require_device_access(device_id, db, current_user, include_retired=True)
    query = db.query(SensorLog).filter(SensorLog.device_id == device_id)
    if start:
        query = query.filter(SensorLog.timestamp >= start)
    if end:
        query = query.filter(SensorLog.timestamp <= end)
    logs = (
        query.order_by(SensorLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    if not logs:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy dữ liệu cho thiết bị này"
        )
    return [sensor_fields(row) for row in logs]


@router.get("/sensors/{device_id}/latest")
def get_latest_sensor(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_device_access(device_id, db, current_user, include_retired=True)
    log = (
        db.query(SensorLog)
        .filter(SensorLog.device_id == device_id)
        .order_by(SensorLog.timestamp.desc())
        .first()
    )
    if log is None:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy dữ liệu cho thiết bị này"
        )
    return sensor_fields(log)
