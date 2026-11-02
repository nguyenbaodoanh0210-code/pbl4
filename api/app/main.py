from datetime import datetime, timezone
import hmac
import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .models import Device, Greenhouse, Recommendation, SensorLog
from .ai.greenhouse import MODEL_PATH as GREENHOUSE_MODEL_PATH
from .ai.greenhouse import load_ai_model, predict_greenhouse
from .ai.disease import (
    DiseaseModelUnavailable,
    InvalidDiseaseImage,
    predict_disease,
)


app = FastAPI(title="Smart Greenhouse API", version="1.0.0")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


class GreenhouseInput(BaseModel):
    greenhouse_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    area_sqm: Optional[float] = Field(default=None, gt=0)
    location: Optional[str] = Field(default=None, max_length=255)


class DeviceInput(BaseModel):
    device_id: str = Field(min_length=1, max_length=50)
    greenhouse_id: str = Field(min_length=1, max_length=50)
    device_type: str = Field(default="SENSOR_NODE", max_length=20)


class DeviceStatusInput(BaseModel):
    status: str


class FertilizerPredictionInput(BaseModel):
    Crop_Type: str = Field(min_length=1, max_length=50)
    Growth_Stage: str = Field(min_length=1, max_length=50)
    Temperature: float = Field(allow_inf_nan=False)
    Humidity: float = Field(allow_inf_nan=False)
    Soil_Moisture: float = Field(allow_inf_nan=False)
    Soil_pH: float = Field(allow_inf_nan=False)
    Nitrogen: float = Field(allow_inf_nan=False)
    Phosphorus: float = Field(allow_inf_nan=False)
    Potassium: float = Field(allow_inf_nan=False)


class FertilizerPredictionOutput(BaseModel):
    condition_diagnosis: str
    fertilizer_action: str
    model: str
    experimental: bool
    note: str


class DiseasePredictionOutput(BaseModel):
    class_name: str
    scores: dict[str, float]
    score_note: str
    experimental: bool


def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    expected = os.getenv("ADMIN_API_TOKEN", "")
    if not expected or not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai thông tin quản trị")


@app.post("/api/greenhouses", status_code=201)
def create_greenhouse(body: GreenhouseInput, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Greenhouse).filter(Greenhouse.greenhouse_id == body.greenhouse_id).first():
        raise HTTPException(status_code=409, detail="greenhouse_id đã tồn tại")
    item = Greenhouse(**body.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/greenhouses/{greenhouse_id}")
def get_greenhouse(greenhouse_id: str, db: Session = Depends(get_db)):
    item = db.query(Greenhouse).filter(Greenhouse.greenhouse_id == greenhouse_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà kính")
    return item


@app.put("/api/greenhouses/{greenhouse_id}")
def update_greenhouse(greenhouse_id: str, body: GreenhouseInput, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(Greenhouse).filter(Greenhouse.greenhouse_id == greenhouse_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà kính")
    if body.greenhouse_id != greenhouse_id:
        raise HTTPException(status_code=422, detail="Không thể đổi greenhouse_id")
    item.name = body.name
    item.area_sqm = body.area_sqm
    item.location = body.location
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/greenhouses/{greenhouse_id}", status_code=204)
def delete_greenhouse(greenhouse_id: str, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(Greenhouse).filter(Greenhouse.greenhouse_id == greenhouse_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà kính")
    if db.query(Device).filter(Device.greenhouse_id == greenhouse_id).first():
        raise HTTPException(status_code=409, detail="Nhà kính còn thiết bị liên kết; không xóa để giữ lịch sử")
    db.delete(item)
    db.commit()


@app.get("/api/devices")
def get_devices(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.device_id).offset(offset).limit(limit).all()


@app.post("/api/devices", status_code=201)
def register_device(body: DeviceInput, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.query(Greenhouse).filter(Greenhouse.greenhouse_id == body.greenhouse_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà kính")
    if db.query(Device).filter(Device.device_id == body.device_id).first():
        raise HTTPException(status_code=409, detail="device_id đã tồn tại")
    item = Device(**body.dict(), status="ACTIVE", is_online=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/api/devices/{device_id}/status")
def update_device_status(device_id: str, body: DeviceStatusInput, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    if body.status not in {"ACTIVE", "INACTIVE"}:
        raise HTTPException(status_code=422, detail="status phải là ACTIVE hoặc INACTIVE")
    item = db.query(Device).filter(Device.device_id == device_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")
    item.status = body.status
    if body.status == "INACTIVE":
        item.is_online = False
    db.commit()
    db.refresh(item)
    return item

# 1. API: Lấy danh sách các khu vực/nhà kính đang quản lý
@app.get("/api/greenhouses")
def get_greenhouses(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    db: Session = Depends(get_db),
):
    # Lấy tạm toàn bộ nhà kính, sau này có thể filter theo user_id
    greenhouses = db.query(Greenhouse).order_by(Greenhouse.greenhouse_id).offset(offset).limit(limit).all()
    return greenhouses

# 2. API: Lấy dữ liệu cảm biến theo thiết bị (Phục vụ vẽ biểu đồ Frontend)
@app.get("/api/sensors/{device_id}")
def get_sensor_by_device(
    device_id: str,
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    if (start and start.tzinfo is None) or (end and end.tzinfo is None):
        raise HTTPException(status_code=422, detail="start/end phải có múi giờ ISO 8601")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start phải nhỏ hơn hoặc bằng end")
    query = db.query(SensorLog).filter(SensorLog.device_id == device_id)
    if start:
        query = query.filter(SensorLog.timestamp >= start)
    if end:
        query = query.filter(SensorLog.timestamp <= end)
    logs = query.order_by(SensorLog.timestamp.desc()).offset(offset).limit(limit).all()
    if not logs:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu cho thiết bị này")
    return logs


@app.get("/api/sensors/{device_id}/latest")
def get_latest_sensor(device_id: str, db: Session = Depends(get_db)):
    log = db.query(SensorLog).filter(SensorLog.device_id == device_id).order_by(SensorLog.timestamp.desc()).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu cho thiết bị này")
    return log


@app.post(
    "/api/ai/fertilizer/predict",
    tags=["AI"],
    response_model=FertilizerPredictionOutput,
)
def predict_fertilizer(body: FertilizerPredictionInput):
    """Run the local demo model on supplied crop and sensor values."""
    model_bundle = load_ai_model(GREENHOUSE_MODEL_PATH)
    if model_bundle is None:
        raise HTTPException(status_code=503, detail="Model khuyến nghị chưa sẵn sàng")
    try:
        prediction = predict_greenhouse(body.dict(), model_bundle)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(
            status_code=503, detail="Không thể chạy model khuyến nghị"
        ) from None
    return {
        **prediction,
        "model": model_bundle.get("model_name", "unknown"),
        "experimental": True,
        "note": "Nhãn học từ dataset demo, chưa phải khuyến nghị nông học đã kiểm chứng.",
    }


@app.post(
    "/api/ai/disease/predict",
    tags=["AI"],
    response_model=DiseasePredictionOutput,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                "image/png": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
async def predict_chili_disease(request: Request):
    """Classify one raw JPEG/PNG request body without storing the image."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Chỉ nhận ảnh JPEG hoặc PNG")

    max_bytes = 10 * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(status_code=413, detail="Ảnh vượt quá giới hạn 10 MB")
        except ValueError:
            raise HTTPException(status_code=400, detail="Content-Length không hợp lệ") from None

    image_bytes = bytearray()
    async for chunk in request.stream():
        image_bytes.extend(chunk)
        if len(image_bytes) > max_bytes:
            raise HTTPException(status_code=413, detail="Ảnh vượt quá giới hạn 10 MB")
    try:
        return predict_disease(bytes(image_bytes), content_type)
    except InvalidDiseaseImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except DiseaseModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

# 3. API: Lấy danh sách đề xuất đã lưu
@app.get("/api/recommendations")
def get_recommendations(
    device_id: Optional[str] = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    db: Session = Depends(get_db),
):
    if status is not None and status not in {"PENDING", "APPLIED", "IGNORED"}:
        raise HTTPException(status_code=422, detail="status phải là PENDING, APPLIED hoặc IGNORED")
    query = db.query(Recommendation)
    if device_id:
        query = query.filter(Recommendation.device_id == device_id)
    if status:
        query = query.filter(Recommendation.status == status)
    recs = query.order_by(Recommendation.created_at.desc()).offset(offset).limit(limit).all()

    return recs


@app.get("/api/recommendations/{rec_id}")
def get_recommendation(rec_id: str, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.rec_id == rec_id).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khuyến nghị")
    return rec

# 4. API: Nông dân xác nhận đã thực hiện bón phân theo đề xuất (Cập nhật trạng thái)
@app.put("/api/recommendations/{rec_id}/apply")
def apply_recommendation(rec_id: str, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.rec_id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã đề xuất này")

    rec.status = "APPLIED"
    db.commit()
    return {"message": f"Đã cập nhật trạng thái đề xuất {rec_id} thành APPLIED"}
