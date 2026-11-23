"""Outdoor Garden, Planting Areas (Chili/Lettuce), and Crops controller."""

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import (
    ActuatorState,
    CameraLog,
    Crop,
    Device,
    Greenhouse,
    GreenhouseArea,
    Notification,
    Recommendation,
    User,
)
from ..schemas import AreaCreateInput, AreaUpdateInput, GreenhouseInput
from ..services import (
    accessible_greenhouses,
    require_area_access,
    require_greenhouse_access,
    resolve_effective_thresholds,
)

router = APIRouter(prefix="/api", tags=["gardens"])


def _validate_threshold_pairs(values: dict) -> None:
    pairs = (
        ("custom_min_temp", "custom_max_temp", "Nhiệt độ tối thiểu phải nhỏ hơn hoặc bằng tối đa"),
        ("custom_min_humidity", "custom_max_humidity", "Độ ẩm tối thiểu phải nhỏ hơn hoặc bằng tối đa"),
        ("custom_min_light", "custom_max_light", "Ánh sáng tối thiểu phải nhỏ hơn hoặc bằng tối đa"),
    )
    for lo_key, hi_key, message in pairs:
        lo, hi = values.get(lo_key), values.get(hi_key)
        if lo is not None and hi is not None and lo > hi:
            raise HTTPException(status_code=422, detail=message)


def _serialize_area(db: Session, area: GreenhouseArea, greenhouse: Greenhouse) -> dict:
    return {
        "area_id": area.area_id,
        "greenhouse_id": area.greenhouse_id,
        "crop_stage_id": area.crop_stage_id,
        "name": area.name,
        "area_sqm": area.area_sqm,
        "custom_min_temp": area.custom_min_temp,
        "custom_max_temp": area.custom_max_temp,
        "custom_min_humidity": area.custom_min_humidity,
        "custom_max_humidity": area.custom_max_humidity,
        "custom_min_light": area.custom_min_light,
        "custom_max_light": area.custom_max_light,
        "custom_fungal_humidity_threshold": area.custom_fungal_humidity_threshold,
        "effective_thresholds": resolve_effective_thresholds(
            db, area=area, greenhouse=greenhouse
        ),
        "created_at": area.created_at.isoformat() if area.created_at else None,
        "updated_at": area.updated_at.isoformat() if area.updated_at else None,
    }


@router.get("/crops")
def list_crops(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..services.public_fields import crop_fields
    return [crop_fields(row) for row in (
        db.query(Crop)
        .order_by(Crop.crop_name.asc(), Crop.crop_stage_id.asc())
        .all()
    )]


@router.get("/greenhouses")
def get_greenhouses(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        accessible_greenhouses(db, current_user)
        .order_by(Greenhouse.greenhouse_id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/greenhouses", status_code=201)
def create_greenhouse(
    body: GreenhouseInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    greenhouse_id = body.greenhouse_id.strip()
    name = body.name.strip()
    if not greenhouse_id or not name:
        raise HTTPException(
            status_code=422, detail="greenhouse_id và name không được để trống"
        )
    if (
        db.query(Greenhouse)
        .filter(Greenhouse.greenhouse_id == greenhouse_id)
        .first()
    ):
        raise HTTPException(status_code=409, detail="greenhouse_id đã tồn tại")

    env_type = (body.environment_type or "OUTDOOR").strip().upper()
    if env_type not in {"OUTDOOR", "GREENHOUSE"}:
        raise HTTPException(
            status_code=422, detail="environment_type phải là OUTDOOR hoặc GREENHOUSE"
        )

    item = Greenhouse(
        greenhouse_id=greenhouse_id,
        name=name,
        area_sqm=body.area_sqm,
        location=body.location.strip() if body.location else None,
        environment_type=env_type,
        user_id=current_user.user_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/greenhouses/{greenhouse_id}")
def get_greenhouse(
    greenhouse_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_greenhouse_access(greenhouse_id, db, current_user)


@router.put("/greenhouses/{greenhouse_id}")
@router.patch("/greenhouses/{greenhouse_id}")
def update_greenhouse(
    greenhouse_id: str,
    body: GreenhouseInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = require_greenhouse_access(greenhouse_id, db, current_user)
    if body.greenhouse_id != greenhouse_id:
        raise HTTPException(status_code=422, detail="Không thể đổi greenhouse_id")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name không được để trống")
    env_type = (body.environment_type or item.environment_type or "OUTDOOR").strip().upper()
    if env_type not in {"OUTDOOR", "GREENHOUSE"}:
        raise HTTPException(
            status_code=422, detail="environment_type phải là OUTDOOR hoặc GREENHOUSE"
        )
    item.name = name
    item.area_sqm = body.area_sqm
    item.location = body.location.strip() if body.location else None
    item.environment_type = env_type
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/greenhouses/{greenhouse_id}", status_code=204)
def delete_greenhouse(
    greenhouse_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = require_greenhouse_access(greenhouse_id, db, current_user)
    active_device = (
        db.query(Device)
        .filter(
            Device.greenhouse_id == greenhouse_id,
            Device.deleted_at.is_(None),
            Device.status != "RETIRED",
        )
        .first()
    )
    if active_device:
        raise HTTPException(
            status_code=409,
            detail="Khu vườn còn thiết bị đang liên kết; không xóa để giữ lịch sử",
        )
    # Detach any retired devices before removing garden records
    db.query(Device).filter(Device.greenhouse_id == greenhouse_id).update(
        {Device.area_id: None, Device.greenhouse_id: None}, synchronize_session=False
    )
    db.query(Notification).filter(Notification.greenhouse_id == greenhouse_id).delete(
        synchronize_session=False
    )
    db.query(CameraLog).filter(CameraLog.greenhouse_id == greenhouse_id).delete(
        synchronize_session=False
    )
    db.query(ActuatorState).filter(ActuatorState.greenhouse_id == greenhouse_id).delete(
        synchronize_session=False
    )
    db.query(GreenhouseArea).filter(
        GreenhouseArea.greenhouse_id == greenhouse_id
    ).delete(synchronize_session=False)
    db.delete(item)
    db.commit()


@router.get("/greenhouses/{greenhouse_id}/areas")
def list_areas(
    greenhouse_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    greenhouse = require_greenhouse_access(greenhouse_id, db, current_user)
    areas = (
        db.query(GreenhouseArea)
        .filter(GreenhouseArea.greenhouse_id == greenhouse_id)
        .order_by(GreenhouseArea.name.asc())
        .all()
    )
    return [_serialize_area(db, area, greenhouse) for area in areas]


@router.post("/greenhouses/{greenhouse_id}/areas", status_code=201)
def create_area(
    greenhouse_id: str,
    body: AreaCreateInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    greenhouse = require_greenhouse_access(greenhouse_id, db, current_user)
    data = body.model_dump()
    _validate_threshold_pairs(data)

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Tên khu vực không được để trống")

    if body.crop_stage_id:
        crop = db.query(Crop).filter(Crop.crop_stage_id == body.crop_stage_id).first()
        if crop is None:
            raise HTTPException(status_code=422, detail="Không tìm thấy cấu hình cây trồng")

    area_id = (body.area_id.strip() if body.area_id else f"area-{uuid.uuid4().hex[:10]}")
    now = datetime.now(timezone.utc)
    area = GreenhouseArea(
        area_id=area_id,
        greenhouse_id=greenhouse_id,
        crop_stage_id=body.crop_stage_id,
        name=name,
        area_sqm=body.area_sqm,
        custom_min_temp=body.custom_min_temp,
        custom_max_temp=body.custom_max_temp,
        custom_min_humidity=body.custom_min_humidity,
        custom_max_humidity=body.custom_max_humidity,
        custom_min_light=body.custom_min_light,
        custom_max_light=body.custom_max_light,
        custom_fungal_humidity_threshold=body.custom_fungal_humidity_threshold,
        created_at=now,
        updated_at=now,
    )
    db.add(area)
    try:
        db.commit()
        db.refresh(area)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Mã khu vực hoặc tên khu vực trong vườn đã tồn tại",
        ) from None
    return _serialize_area(db, area, greenhouse)


@router.put("/greenhouses/{greenhouse_id}/areas/{area_id}")
@router.patch("/greenhouses/{greenhouse_id}/areas/{area_id}")
def update_area(
    greenhouse_id: str,
    area_id: str,
    body: AreaUpdateInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    greenhouse = require_greenhouse_access(greenhouse_id, db, current_user)
    area = require_area_access(greenhouse_id, area_id, db, current_user)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Không có thông tin cần cập nhật")

    merged = {
        "custom_min_temp": changes.get("custom_min_temp", area.custom_min_temp),
        "custom_max_temp": changes.get("custom_max_temp", area.custom_max_temp),
        "custom_min_humidity": changes.get("custom_min_humidity", area.custom_min_humidity),
        "custom_max_humidity": changes.get("custom_max_humidity", area.custom_max_humidity),
        "custom_min_light": changes.get("custom_min_light", area.custom_min_light),
        "custom_max_light": changes.get("custom_max_light", area.custom_max_light),
    }
    _validate_threshold_pairs(merged)

    if "crop_stage_id" in changes and changes["crop_stage_id"]:
        crop = (
            db.query(Crop)
            .filter(Crop.crop_stage_id == changes["crop_stage_id"])
            .first()
        )
        if crop is None:
            raise HTTPException(status_code=422, detail="Không tìm thấy cấu hình cây trồng")

    if "name" in changes:
        name = (changes["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Tên khu vực không được để trống")
        changes["name"] = name

    for key, value in changes.items():
        setattr(area, key, value)
    area.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(area)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Tên khu vực trong cùng khu vườn bị trùng"
        ) from None
    return _serialize_area(db, area, greenhouse)


@router.delete("/greenhouses/{greenhouse_id}/areas/{area_id}", status_code=204)
def delete_area(
    greenhouse_id: str,
    area_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    area = require_area_access(greenhouse_id, area_id, db, current_user)
    db.query(Device).filter(Device.area_id == area_id).update(
        {Device.area_id: None}, synchronize_session=False
    )
    db.query(CameraLog).filter(CameraLog.area_id == area_id).update(
        {CameraLog.area_id: None}, synchronize_session=False
    )
    db.query(ActuatorState).filter(ActuatorState.area_id == area_id).update(
        {ActuatorState.area_id: None}, synchronize_session=False
    )
    db.query(Recommendation).filter(Recommendation.area_id == area_id).update(
        {Recommendation.area_id: None}, synchronize_session=False
    )
    db.query(Notification).filter(Notification.area_id == area_id).update(
        {Notification.area_id: None}, synchronize_session=False
    )
    db.delete(area)
    db.commit()
