"""Recommendations and Notifications controller."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import Device, Greenhouse, GreenhouseArea, Notification, Recommendation, User
from ..services import require_notification_access, require_recommendation_access

router = APIRouter(prefix="/api", tags=["alerts & recommendations"])


@router.get("/recommendations")
def get_recommendations(
    device_id: Optional[str] = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if status is not None and status not in {"PENDING", "APPLIED", "IGNORED"}:
        raise HTTPException(
            status_code=422, detail="status phải là PENDING, APPLIED hoặc IGNORED"
        )
    query = db.query(Recommendation)
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
    if device_id:
        query = query.filter(Recommendation.device_id == device_id)
    if status:
        query = query.filter(Recommendation.status == status)
    return (
        query.order_by(Recommendation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/recommendations/{rec_id}")
def get_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_recommendation_access(rec_id, db, current_user)


@router.put("/recommendations/{rec_id}/apply")
def apply_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = require_recommendation_access(rec_id, db, current_user)
    rec.status = "APPLIED"
    db.commit()
    return {"message": f"Đã cập nhật trạng thái đề xuất {rec_id} thành APPLIED"}


@router.get("/notifications")
def get_notifications(
    greenhouse_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if status is not None and status not in {"UNREAD", "READ", "RESOLVED"}:
        raise HTTPException(
            status_code=422, detail="status phải là UNREAD, READ hoặc RESOLVED"
        )
    query = db.query(Notification)
    if current_user.role != "ADMIN":
        query = query.outerjoin(
            Greenhouse, Notification.greenhouse_id == Greenhouse.greenhouse_id
        ).filter(
            or_(
                Notification.user_id == current_user.user_id,
                Greenhouse.user_id == current_user.user_id,
            )
        )
    if greenhouse_id:
        query = query.filter(Notification.greenhouse_id == greenhouse_id)
    if status:
        query = query.filter(Notification.status == status)
    if category:
        query = query.filter(Notification.category == category)

    return (
        query.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = require_notification_access(notification_id, db, current_user)
    if item.status == "UNREAD":
        item.status = "READ"
    item.read_at = item.read_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item
