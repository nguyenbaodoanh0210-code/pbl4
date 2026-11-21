"""Ownership checks and effective outdoor crop threshold resolution."""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import (
    Crop,
    Device,
    Greenhouse,
    GreenhouseArea,
    Notification,
    Recommendation,
    User,
)


def accessible_greenhouses(db: Session, current_user: User):
    query = db.query(Greenhouse)
    if current_user.role != "ADMIN":
        query = query.filter(Greenhouse.user_id == current_user.user_id)
    return query


def accessible_devices(db: Session, current_user: User, include_retired: bool = False):
    query = db.query(Device).join(
        Greenhouse, Device.greenhouse_id == Greenhouse.greenhouse_id
    )
    if not include_retired:
        query = query.filter(Device.deleted_at.is_(None), Device.status != "RETIRED")
    if current_user.role != "ADMIN":
        query = query.filter(Greenhouse.user_id == current_user.user_id)
    return query


def require_greenhouse_access(
    greenhouse_id: str, db: Session, current_user: User
) -> Greenhouse:
    greenhouse = (
        accessible_greenhouses(db, current_user)
        .filter(Greenhouse.greenhouse_id == greenhouse_id)
        .first()
    )
    if greenhouse is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khu vườn")
    return greenhouse


def require_area_access(
    greenhouse_id: str, area_id: str, db: Session, current_user: User
) -> GreenhouseArea:
    require_greenhouse_access(greenhouse_id, db, current_user)
    area = (
        db.query(GreenhouseArea)
        .filter(
            GreenhouseArea.greenhouse_id == greenhouse_id,
            GreenhouseArea.area_id == area_id,
        )
        .first()
    )
    if area is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khu vực trồng")
    return area


def require_device_access(
    device_id: str,
    db: Session,
    current_user: User,
    include_retired: bool = False,
) -> Device:
    device = (
        accessible_devices(db, current_user, include_retired=include_retired)
        .filter(Device.device_id == device_id)
        .first()
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")
    return device


def require_recommendation_access(
    rec_id: str, db: Session, current_user: User
) -> Recommendation:
    query = db.query(Recommendation).filter(Recommendation.rec_id == rec_id)
    if current_user.role != "ADMIN":
        query = (
            query.outerjoin(Device, Recommendation.device_id == Device.device_id)
            .outerjoin(GreenhouseArea, Recommendation.area_id == GreenhouseArea.area_id)
            .join(
                Greenhouse,
                or_(
                    Greenhouse.greenhouse_id == Device.greenhouse_id,
                    Greenhouse.greenhouse_id == GreenhouseArea.greenhouse_id,
                ),
            )
            .filter(Greenhouse.user_id == current_user.user_id)
        )
    recommendation = query.first()
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khuyến nghị")
    return recommendation


def require_notification_access(
    notification_id: str, db: Session, current_user: User
) -> Notification:
    query = db.query(Notification).filter(
        Notification.notification_id == notification_id
    )
    if current_user.role != "ADMIN":
        query = query.outerjoin(
            Greenhouse, Notification.greenhouse_id == Greenhouse.greenhouse_id
        ).filter(
            or_(
                Notification.user_id == current_user.user_id,
                Greenhouse.user_id == current_user.user_id,
            )
        )
    notification = query.first()
    if notification is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    return notification


def resolve_effective_thresholds(
    db: Session,
    area: GreenhouseArea | None = None,
    greenhouse: Greenhouse | None = None,
) -> dict:
    """Resolve active outdoor thresholds: area custom overrides > crop defaults > fallback."""
    crop_stage_id = None
    if area is not None and area.crop_stage_id:
        crop_stage_id = area.crop_stage_id
    elif greenhouse is not None and greenhouse.crop_stage_id:
        crop_stage_id = greenhouse.crop_stage_id

    crop = (
        db.query(Crop).filter(Crop.crop_stage_id == crop_stage_id).first()
        if crop_stage_id
        else None
    )

    def pick(custom_val, crop_val, default_val):
        if custom_val is not None:
            return custom_val
        if crop_val is not None:
            return crop_val
        return default_val

    return {
        "crop_stage_id": crop.crop_stage_id if crop else crop_stage_id,
        "crop_name": crop.crop_name if crop else "Cây trồng ngoài trời",
        "growth_stage": crop.growth_stage if crop else "VEGETATIVE",
        "environment_type": (crop.environment_type if crop else None) or "OUTDOOR",
        "min_temp": pick(area.custom_min_temp if area else None, crop.min_temp if crop else None, 20.0),
        "max_temp": pick(area.custom_max_temp if area else None, crop.max_temp if crop else None, 33.0),
        "min_humidity": pick(area.custom_min_humidity if area else None, crop.min_humidity if crop else None, 55.0),
        "max_humidity": pick(area.custom_max_humidity if area else None, crop.max_humidity if crop else None, 80.0),
        "min_light": pick(area.custom_min_light if area else None, crop.min_light if crop else None, 10000.0),
        "max_light": pick(area.custom_max_light if area else None, crop.max_light if crop else None, 55000.0),
        "fungal_humidity_threshold": pick(
            area.custom_fungal_humidity_threshold if area else None,
            crop.fungal_humidity_threshold if crop else None,
            85.0,
        ),
        "fungal_light_threshold": pick(None, crop.fungal_light_threshold if crop else None, 8000.0),
        "fungal_duration_minutes": pick(None, crop.fungal_duration_minutes if crop else None, 60),
    }
