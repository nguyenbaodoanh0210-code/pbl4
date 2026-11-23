"""ESP32-CAM image storage, Multimodal diagnosis pipeline, and safe image serving."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
from typing import Callable
from urllib.parse import unquote
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..ai.disease import (
    DiseaseModelUnavailable,
    InvalidDiseaseImage,
    _image_dimensions,
    predict_disease,
)
from ..models import (
    CameraLog,
    Device,
    Greenhouse,
    GreenhouseArea,
    Notification,
    Recommendation,
    SensorLog,
)
from .access_service import resolve_effective_thresholds
from .mqtt_publisher import camera_cmd_topic, publish_mqtt_json
from .multimodal_service import MODEL_VERSION, fuse_multimodal_diagnosis


API_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = API_ROOT / "uploads" / "camera"
DATASET_DIR = API_ROOT / "data" / "chili_plant_disease"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
VALID_TRIGGER_TYPES = {"MANUAL", "SCHEDULED", "ENV_ALERT"}
VALID_CAMERA_STATUSES = {"NEW", "REVIEWED", "RESOLVED"}


def _demo_vision_fallback(image_bytes: bytes, content_type: str | None = None) -> dict:
    """Explicit opt-in demo fallback ONLY when ALLOW_DEMO_VISION_FALLBACK=true and TensorFlow is absent."""
    _image_dimensions(image_bytes)
    return {
        "class_name": "leaf spot",
        "scores": {
            "leaf spot": 0.78,
            "yellowish": 0.11,
            "leaf curl": 0.05,
            "whitefly": 0.03,
            "healthy": 0.03,
        },
        "score_note": "Chế độ demo fallback (ALLOW_DEMO_VISION_FALLBACK=true) do máy chưa cài TensorFlow.",
        "experimental": True,
        "model_version": "demo_fallback+multimodal_v1",
    }


def serialize_camera_log(item: CameraLog) -> dict:
    return {
        "log_id": item.log_id,
        "device_id": item.device_id,
        "greenhouse_id": item.greenhouse_id,
        "area_id": item.area_id,
        "sensor_log_id": item.sensor_log_id,
        "image_url": item.image_url,
        "image_endpoint": f"/api/camera/logs/{item.log_id}/image",
        "timestamp": item.timestamp.isoformat() if item.timestamp else None,
        "trigger_type": item.trigger_type,
        "cnn_diagnosis": item.cnn_diagnosis,
        "cnn_confidence": item.cnn_confidence,
        "cnn_scores": item.cnn_scores or {},
        "ai_diagnosis": item.ai_diagnosis,
        "confidence_score": item.confidence_score,
        "multimodal_reason": item.multimodal_reason,
        "recommended_action": item.recommended_action,
        "temperature_at_capture": item.temperature_at_capture,
        "humidity_at_capture": item.humidity_at_capture,
        "light_at_capture": item.light_at_capture,
        "env_window_summary": item.env_window_summary or {},
        "model_version": item.model_version,
        "status": item.status,
    }


def save_camera_image(image_bytes: bytes, expected_content_type: str | None = None) -> tuple[str, str]:
    if not image_bytes:
        raise InvalidDiseaseImage("Ảnh tải lên đang rỗng")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh vượt quá giới hạn 10 MB")
    detected_type, width, height = _image_dimensions(image_bytes)
    if expected_content_type and detected_type != expected_content_type:
        raise InvalidDiseaseImage("Content-Type không khớp định dạng ảnh")
    if width < 1 or height < 1:
        raise InvalidDiseaseImage("Kích thước ảnh không hợp lệ")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".png" if detected_type == "image/png" else ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(image_bytes)
    return filename, detected_type


def resolve_stored_image_path(image_url: str) -> tuple[Path, str]:
    """Resolve an image path inside UPLOAD_DIR or DATASET_DIR safely (blocks path traversal)."""
    cleaned = unquote((image_url or "").strip()).lstrip("/")
    if not cleaned:
        raise HTTPException(status_code=404, detail="Không tìm thấy đường dẫn ảnh")

    # Case 1: /api/camera/images/<filename> or uploads/camera/<filename>
    if cleaned.startswith("api/camera/images/"):
        filename = cleaned.split("/")[-1]
        candidate = (UPLOAD_DIR / filename).resolve()
        if candidate.parent == UPLOAD_DIR.resolve() and candidate.is_file():
            media = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
            return candidate, media

    if cleaned.startswith("uploads/camera/"):
        filename = cleaned.split("/")[-1]
        candidate = (UPLOAD_DIR / filename).resolve()
        if candidate.parent == UPLOAD_DIR.resolve() and candidate.is_file():
            media = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
            return candidate, media

    # Case 2: Seeded dataset sample image under api/data/chili_plant_disease/
    if cleaned.startswith("data/chili_plant_disease/"):
        candidate = (API_ROOT / cleaned).resolve()
        try:
            candidate.relative_to(DATASET_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Đường dẫn ảnh không hợp lệ") from None
        if candidate.is_file():
            media = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
            return candidate, media

    raise HTTPException(status_code=404, detail="Tệp ảnh không tồn tại trên máy chủ")


def resolve_uploaded_filename(filename: str) -> tuple[Path, str]:
    if not filename or not SAFE_FILENAME_RE.match(filename) or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Tên tệp ảnh không hợp lệ")
    candidate = (UPLOAD_DIR / filename).resolve()
    if candidate.parent != UPLOAD_DIR.resolve() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    media = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
    return candidate, media


def _fetch_sensor_context(
    db: Session,
    greenhouse_id: str,
    area_id: str | None,
    window_minutes: int,
) -> tuple[SensorLog | None, list[dict]]:
    """Find latest SensorLog and recent window for the area (falling back to garden sensor node)."""
    sensor_query = db.query(Device).filter(
        Device.greenhouse_id == greenhouse_id,
        Device.device_type == "SENSOR_NODE",
        Device.deleted_at.is_(None),
    )
    sensor_devices = []
    if area_id:
        sensor_devices = sensor_query.filter(Device.area_id == area_id).all()
    if not sensor_devices:
        sensor_devices = sensor_query.all()
    if not sensor_devices:
        return None, []

    device_ids = [d.device_id for d in sensor_devices]
    latest_log = (
        db.query(SensorLog)
        .filter(SensorLog.device_id.in_(device_ids))
        .order_by(SensorLog.timestamp.desc())
        .first()
    )
    if latest_log is None:
        return None, []

    window_start = latest_log.timestamp - timedelta(minutes=window_minutes)
    history_logs = (
        db.query(SensorLog)
        .filter(
            SensorLog.device_id == latest_log.device_id,
            SensorLog.timestamp >= window_start,
            SensorLog.timestamp <= latest_log.timestamp,
        )
        .order_by(SensorLog.timestamp.asc())
        .all()
    )
    history = [
        {
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "temperature": row.temperature,
            "humidity": row.humidity,
            "light_level": row.light_level,
        }
        for row in history_logs
    ]
    return latest_log, history


def run_camera_diagnosis(
    db: Session,
    greenhouse: Greenhouse,
    image_bytes: bytes,
    expected_content_type: str | None = None,
    area: GreenhouseArea | None = None,
    device: Device | None = None,
    trigger_type: str = "MANUAL",
    predictor: Callable[[bytes, str | None], dict] | None = None,
) -> dict:
    """Save ESP32-CAM image, run CNN + Multimodal fusion, persist CameraLog + Alert + Recommendation."""
    trig = (trigger_type or "MANUAL").strip().upper()
    if trig not in VALID_TRIGGER_TYPES:
        raise HTTPException(
            status_code=422,
            detail="trigger_type phải là MANUAL, SCHEDULED hoặc ENV_ALERT",
        )

    try:
        filename, detected_type = save_camera_image(image_bytes, expected_content_type)
    except InvalidDiseaseImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    # 1. Run CNN disease inference
    infer_fn = predictor or predict_disease
    model_version = MODEL_VERSION
    try:
        cnn_result = infer_fn(image_bytes, detected_type)
        if isinstance(cnn_result, dict):
            model_version = str(cnn_result.get("model_version") or cnn_result.get("model") or MODEL_VERSION)
    except InvalidDiseaseImage as exc:
        (UPLOAD_DIR / filename).unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except DiseaseModelUnavailable as exc:
        allow_fallback = os.getenv("ALLOW_DEMO_VISION_FALLBACK", "false").lower() == "true"
        if allow_fallback and predictor is None:
            cnn_result = _demo_vision_fallback(image_bytes, detected_type)
            model_version = cnn_result["model_version"]
        else:
            (UPLOAD_DIR / filename).unlink(missing_ok=True)
            raise HTTPException(status_code=503, detail=str(exc)) from None

    # 2. Fetch DHT22 + LDR Light context & outdoor crop thresholds
    thresholds = resolve_effective_thresholds(db, area=area, greenhouse=greenhouse)
    latest_sensor, env_history = _fetch_sensor_context(
        db,
        greenhouse.greenhouse_id,
        area.area_id if area else None,
        int(thresholds.get("fungal_duration_minutes", 60)),
    )
    env_snapshot = (
        {
            "temperature": latest_sensor.temperature,
            "humidity": latest_sensor.humidity,
            "light_level": latest_sensor.light_level,
        }
        if latest_sensor is not None
        else None
    )

    # 3. Run Multimodal Fusion
    fused = fuse_multimodal_diagnosis(
        cnn_result=cnn_result,
        env_snapshot=env_snapshot,
        env_history=env_history,
        crop_config=thresholds,
        model_version=model_version,
    )

    now = datetime.now(timezone.utc)
    log_id = f"cam-{uuid.uuid4().hex[:12]}"
    camera_log = CameraLog(
        log_id=log_id,
        device_id=device.device_id if device else None,
        greenhouse_id=greenhouse.greenhouse_id,
        area_id=area.area_id if area else None,
        sensor_log_id=latest_sensor.log_id if latest_sensor else None,
        image_url=f"uploads/camera/{filename}",
        timestamp=now,
        trigger_type=trig,
        cnn_diagnosis=fused["cnn_diagnosis"],
        cnn_confidence=fused["cnn_confidence"],
        cnn_scores=fused["cnn_scores"],
        ai_diagnosis=fused["final_diagnosis"],
        confidence_score=fused["multimodal_confidence"],
        multimodal_reason=fused["multimodal_reason"],
        recommended_action=fused["recommended_action"],
        temperature_at_capture=fused["env_snapshot"]["temperature"],
        humidity_at_capture=fused["env_snapshot"]["humidity"],
        light_at_capture=fused["env_snapshot"]["light_level"],
        env_window_summary=fused["env_window_summary"],
        model_version=fused["model_version"],
        status="NEW",
    )
    db.add(camera_log)
    if device is not None:
        device.is_online = True
        device.last_updated = now
    db.flush()

    created_notification = None
    created_recommendation = None
    if (not fused["is_healthy"]) and fused["multimodal_confidence"] >= 0.65:
        rec_id = f"rec-{uuid.uuid4().hex[:12]}"
        created_recommendation = Recommendation(
            rec_id=rec_id,
            device_id=latest_sensor.device_id if latest_sensor else (device.device_id if device else None),
            area_id=area.area_id if area else None,
            camera_log_id=log_id,
            source_type="MULTIMODAL",
            created_at=now,
            condition_diagnosis=f"{fused['final_diagnosis']} ({fused['multimodal_confidence'] * 100:.0f}%)",
            fertilizer_action=fused["recommended_action"],
            dosage=0.0,
            action_note=fused["multimodal_reason"],
            status="PENDING",
        )
        db.add(created_recommendation)
        db.flush()

        zone_name = area.name if area else greenhouse.name
        severity = "CRITICAL" if fused["multimodal_confidence"] >= 0.80 else "WARNING"
        created_notification = Notification(
            notification_id=f"notif-{uuid.uuid4().hex[:12]}",
            user_id=greenhouse.user_id,
            greenhouse_id=greenhouse.greenhouse_id,
            area_id=area.area_id if area else None,
            device_id=device.device_id if device else None,
            recommendation_id=rec_id,
            camera_log_id=log_id,
            category="DISEASE_ALERT",
            severity=severity,
            title=f"Cảnh báo {fused['final_diagnosis']} tại {zone_name} ({fused['multimodal_confidence'] * 100:.0f}%)",
            message=fused["multimodal_reason"],
            status="UNREAD",
            created_at=now,
        )
        db.add(created_notification)

    db.commit()
    db.refresh(camera_log)

    return {
        "camera_log": serialize_camera_log(camera_log),
        "multimodal": fused,
        "notification_created": created_notification is not None,
        "recommendation_id": created_recommendation.rec_id if created_recommendation else None,
    }


def trigger_esp32_capture(
    greenhouse: Greenhouse,
    area: GreenhouseArea | None = None,
    device: Device | None = None,
    trigger_type: str = "MANUAL",
) -> dict:
    trig = (trigger_type or "MANUAL").strip().upper()
    if trig not in VALID_TRIGGER_TYPES:
        raise HTTPException(
            status_code=422,
            detail="trigger_type phải là MANUAL, SCHEDULED hoặc ENV_ALERT",
        )
    now = datetime.now(timezone.utc)
    payload = {
        "command": "CAPTURE",
        "trigger_type": trig,
        "greenhouse_id": greenhouse.greenhouse_id,
        "area_id": area.area_id if area else None,
        "device_id": device.device_id if device else None,
        "timestamp": now.isoformat(),
    }
    mqtt_result = publish_mqtt_json(camera_cmd_topic(greenhouse.greenhouse_id), payload)
    return {
        "greenhouse_id": greenhouse.greenhouse_id,
        "area_id": area.area_id if area else None,
        "device_id": device.device_id if device else None,
        "trigger_type": trig,
        "dispatched": bool(mqtt_result["published"]),
        "mqtt": mqtt_result,
        "message": (
            "Đã gửi lệnh chụp ảnh đến ESP32-CAM qua MQTT."
            if mqtt_result["published"]
            else "Chưa kết nối được MQTT Broker tới ESP32-CAM; bạn có thể tải ảnh trực tiếp để chẩn đoán ngay."
        ),
    }
