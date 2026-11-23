"""ESP32-CAM capture, multimodal disease diagnosis, and secure image serving controller."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException, MultiPartParser
from sqlalchemy.orm import Session

from ..core.auth import bearer_scheme, decode_access_token, get_current_user
from ..core.database import get_db
from ..models import CameraLog, Device, Greenhouse, GreenhouseArea, User
from ..schemas import CameraLogStatusInput, CaptureTriggerInput
from ..services.access_service import (
    accessible_greenhouses,
    require_area_access,
    require_device_access,
    require_greenhouse_access,
)
from ..services.camera_service import (
    MAX_IMAGE_BYTES,
    VALID_CAMERA_STATUSES,
    resolve_stored_image_path,
    resolve_uploaded_filename,
    run_camera_diagnosis,
    serialize_camera_log,
    trigger_esp32_capture,
    validate_camera_binding,
)

router = APIRouter(prefix="/api/camera", tags=["camera & multimodal AI"])


class BoundedCameraMultipartParser(MultiPartParser):
    # The complete request is bounded before parsing. Keep these small uploads in
    # memory instead of spilling to Windows' potentially full C: temporary drive.
    spool_max_size = MAX_IMAGE_BYTES + 65536


def _authenticate_user_or_device(
    db: Session,
    authorization: str | None,
    x_device_token: str | None,
) -> tuple[User | None, bool]:
    """Allow either Bearer JWT user auth or X-Device-Token for ESP32-CAM hardware."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        user_id = decode_access_token(token)
        user = db.query(User).filter(User.user_id == user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Tài khoản không còn tồn tại")
        return user, False

    if x_device_token:
        expected = os.getenv("DEVICE_INGEST_TOKEN", "").strip()
        if not expected or not hmac.compare_digest(x_device_token.strip(), expected):
            raise HTTPException(status_code=401, detail="X-Device-Token không hợp lệ")
        return None, True

    raise HTTPException(
        status_code=401,
        detail="Cần đăng nhập (Bearer token) hoặc cung cấp X-Device-Token của ESP32-CAM",
    )


def _require_camera_log_access(
    log_id: str, db: Session, current_user: User
) -> CameraLog:
    query = db.query(CameraLog).filter(CameraLog.log_id == log_id)
    if current_user.role != "ADMIN":
        query = query.join(
            Greenhouse, CameraLog.greenhouse_id == Greenhouse.greenhouse_id
        ).filter(Greenhouse.user_id == current_user.user_id)
    item = query.first()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi camera")
    return item


@router.post("/diagnose", status_code=201)
async def diagnose_camera_image(
    request: Request,
    greenhouse_id: Optional[str] = Query(default=None),
    area_id: Optional[str] = Query(default=None),
    device_id: Optional[str] = Query(default=None),
    trigger_type: str = Query(default="MANUAL"),
    capture_id: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    x_device_token: Optional[str] = Header(default=None, alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """Receive an ESP32-CAM or Web-uploaded image, run CNN + Multimodal logic, and persist logs."""
    current_user, is_device = _authenticate_user_or_device(
        db, authorization, x_device_token
    )

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    expected_image_type: str | None = None

    if content_type not in {"multipart/form-data", "image/jpeg", "image/png"}:
        raise HTTPException(415, "Chỉ hỗ trợ ảnh JPEG/PNG hoặc multipart/form-data")
    # Bound the whole request before parsing multipart or reading a file into RAM.
    limit = MAX_IMAGE_BYTES + (65536 if content_type == "multipart/form-data" else 0)
    buf = bytearray()
    async for chunk in request.stream():
        if len(buf) + len(chunk) > limit:
            raise HTTPException(413, "Ảnh vượt quá giới hạn 10 MB")
        buf.extend(chunk)
    if content_type == "multipart/form-data":
        async def body_stream():
            yield bytes(buf)
        try:
            form = await BoundedCameraMultipartParser(request.headers, body_stream(),
                max_files=1, max_fields=8, max_part_size=65536).parse()
        except MultiPartException:
            raise HTTPException(400, "Biểu mẫu ảnh không hợp lệ hoặc vượt giới hạn") from None
        upload = form.get("file") or form.get("image")
        if upload is None or not hasattr(upload, "read"):
            await form.close()
            raise HTTPException(status_code=422, detail="Thiếu trường tệp ảnh (file)")
        image_bytes = await upload.read(MAX_IMAGE_BYTES + 1)
        upload_ct = (getattr(upload, "content_type", None) or "").split(";", 1)[0].strip().lower()
        await form.close()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Ảnh vượt quá giới hạn 10 MB")
        if upload_ct not in {"image/jpeg", "image/png"}:
            raise HTTPException(415, "Chỉ hỗ trợ ảnh JPEG hoặc PNG")
        expected_image_type = upload_ct
        greenhouse_id = str(form.get("greenhouse_id") or greenhouse_id or "").strip() or None
        area_id = str(form.get("area_id") or area_id or "").strip() or None
        device_id = str(form.get("device_id") or device_id or "").strip() or None
        trigger_type = str(form.get("trigger_type") or trigger_type or "MANUAL").strip()
        capture_id = str(form.get("capture_id") or capture_id or "").strip() or None
    elif content_type in {"image/jpeg", "image/png"}:
        expected_image_type = content_type
        image_bytes = bytes(buf)
    else:
        raise HTTPException(
            status_code=415,
            detail="Hỗ trợ multipart/form-data (trường file) hoặc ảnh thô image/jpeg, image/png",
        )

    # Resolve device, area, and greenhouse
    if is_device and not device_id:
        raise HTTPException(422, "Thiết bị phải gửi device_id")
    if capture_id and not is_device:
        raise HTTPException(422, "capture_id chỉ dành cho ảnh trả về từ camera")
    device = None
    if device_id:
        if is_device:
            device = (
                db.query(Device)
                .filter(Device.device_id == device_id, Device.deleted_at.is_(None))
                .first()
            )
            if device is None:
                raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị camera")
        else:
            device = require_device_access(device_id, db, current_user)
        if not greenhouse_id:
            greenhouse_id = device.greenhouse_id
        if not area_id:
            area_id = device.area_id

    if not greenhouse_id:
        raise HTTPException(status_code=422, detail="Thiếu greenhouse_id hoặc device_id")

    if is_device:
        greenhouse = (
            db.query(Greenhouse)
            .filter(Greenhouse.greenhouse_id == greenhouse_id)
            .first()
        )
        if greenhouse is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy khu vườn")
    else:
        greenhouse = require_greenhouse_access(greenhouse_id, db, current_user)

    area = None
    if area_id:
        if is_device:
            area = (
                db.query(GreenhouseArea)
                .filter(
                    GreenhouseArea.greenhouse_id == greenhouse.greenhouse_id,
                    GreenhouseArea.area_id == area_id,
                )
                .first()
            )
            if area is None:
                raise HTTPException(status_code=404, detail="Không tìm thấy khu vực trồng")
        else:
            area = require_area_access(greenhouse.greenhouse_id, area_id, db, current_user)

    if device:
        validate_camera_binding(device, greenhouse, area)
    return await run_in_threadpool(run_camera_diagnosis,
        db=db,
        greenhouse=greenhouse,
        image_bytes=image_bytes,
        expected_content_type=expected_image_type,
        area=area,
        device=device,
        trigger_type=trigger_type,
        capture_id=capture_id,
    )


@router.post("/capture-trigger")
def capture_trigger(
    body: CaptureTriggerInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gh_id = body.greenhouse_id
    if not gh_id:
        first_gh = accessible_greenhouses(db, current_user).first()
        if not first_gh:
            raise HTTPException(status_code=404, detail="Không tìm thấy khu vườn nào")
        gh_id = first_gh.greenhouse_id

    greenhouse = require_greenhouse_access(gh_id, db, current_user)
    area = (
        require_area_access(gh_id, body.area_id, db, current_user)
        if body.area_id
        else None
    )
    device = (
        require_device_access(body.device_id, db, current_user)
        if body.device_id
        else None
    )
    if device is None:
        cameras = db.query(Device).filter(Device.greenhouse_id == gh_id,
            Device.device_type.in_(["CAMERA", "CAMERA_NODE"]), Device.status == "ACTIVE",
            Device.deleted_at.is_(None))
        if area:
            cameras = cameras.filter(Device.area_id == area.area_id)
        choices = cameras.limit(2).all()
        if len(choices) != 1:
            raise HTTPException(422, "Chọn một camera đang hoạt động trong vườn")
        device = choices[0]
    if area is None and device.area_id:
        area = require_area_access(gh_id, device.area_id, db, current_user)
    validate_camera_binding(device, greenhouse, area)
    return trigger_esp32_capture(
        greenhouse=greenhouse,
        area=area,
        device=device,
        trigger_type=body.trigger_type,
    )


@router.get("/logs")
def list_camera_logs(
    greenhouse_id: Optional[str] = None,
    area_id: Optional[str] = None,
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if status is not None and status.upper() not in VALID_CAMERA_STATUSES:
        raise HTTPException(
            status_code=422, detail="status phải là NEW, REVIEWED hoặc RESOLVED"
        )
    allowed_gh_ids = [
        row.greenhouse_id for row in accessible_greenhouses(db, current_user).all()
    ]
    if not allowed_gh_ids:
        return []

    query = db.query(CameraLog).filter(CameraLog.greenhouse_id.in_(allowed_gh_ids))
    if greenhouse_id:
        query = query.filter(CameraLog.greenhouse_id == greenhouse_id)
    if area_id:
        query = query.filter(CameraLog.area_id == area_id)
    if device_id:
        query = query.filter(CameraLog.device_id == device_id)
    if status:
        query = query.filter(CameraLog.status == status.upper())

    logs = (
        query.order_by(CameraLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [serialize_camera_log(row) for row in logs]


@router.get("/logs/{log_id}")
def get_camera_log(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _require_camera_log_access(log_id, db, current_user)
    return serialize_camera_log(item)


@router.patch("/logs/{log_id}/status")
def update_camera_log_status(
    log_id: str,
    body: CameraLogStatusInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_status = body.status.strip().upper()
    if new_status not in VALID_CAMERA_STATUSES:
        raise HTTPException(
            status_code=422, detail="status phải là NEW, REVIEWED hoặc RESOLVED"
        )
    item = _require_camera_log_access(log_id, db, current_user)
    item.status = new_status
    db.commit()
    db.refresh(item)
    return serialize_camera_log(item)


@router.get("/logs/{log_id}/image")
def get_camera_log_image(
    log_id: str,
    token: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    raw_token = (
        authorization.split(" ", 1)[1].strip()
        if authorization and authorization.lower().startswith("bearer ")
        else token
    )
    user = _image_user(raw_token, db)
    item = _require_camera_log_access(log_id, db, user)
    path, media_type = resolve_stored_image_path(item.image_url)
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})


def _image_user(token, db):
    if not token:
        raise HTTPException(401, "Cần đăng nhập để xem ảnh")
    user = db.query(User).filter_by(user_id=decode_access_token(token)).first()
    if user is None:
        raise HTTPException(401, "Tài khoản không còn tồn tại")
    return user


@router.get("/images/{filename}")
def get_uploaded_camera_image(
    filename: str,
    token: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    raw_token = (
        authorization.split(" ", 1)[1].strip()
        if authorization and authorization.lower().startswith("bearer ")
        else token
    )
    user = _image_user(raw_token, db)
    item = db.query(CameraLog).filter(CameraLog.image_url.in_([
        f"uploads/camera/{filename}", f"/api/camera/images/{filename}"])).first()
    if item is None:
        raise HTTPException(404, "Không tìm thấy ảnh")
    _require_camera_log_access(item.log_id, db, user)
    path, media_type = resolve_uploaded_filename(filename)
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})
