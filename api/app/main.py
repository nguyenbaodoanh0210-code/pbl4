from datetime import datetime, timezone
import logging
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError, TimeoutError as DatabaseTimeoutError
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    get_token_secret,
    hash_password,
    normalize_email,
    verify_password,
)
from .database import engine, get_db
from .models import Device, Greenhouse, GreenhouseArea, Recommendation, SensorLog, User
from .ai.greenhouse import MODEL_PATH as GREENHOUSE_MODEL_PATH
from .ai.greenhouse import load_ai_model, predict_greenhouse
from .ai.disease import (
    DiseaseModelUnavailable,
    InvalidDiseaseImage,
    predict_disease,
)


app = FastAPI(title="Smart Greenhouse API", version="1.0.0")
logger = logging.getLogger(__name__)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    # Driver messages and SQL parameters can contain credentials or user data.
    # Log only the exception category and SQLSTATE, never the exception text.
    sqlstate = getattr(getattr(exc, "orig", None), "pgcode", None)
    logger.error("Database request failed: category=%s sqlstate=%s", type(exc).__name__, sqlstate)
    if isinstance(exc, (OperationalError, DatabaseTimeoutError)):
        return JSONResponse(status_code=503, content={
            "detail": "Không kết nối được cơ sở dữ liệu. Quản trị viên cần kiểm tra DATABASE_URL và dịch vụ PostgreSQL.",
            "code": "DATABASE_UNAVAILABLE",
        })
    if sqlstate in {"42P01", "42703", "3F000"}:
        return JSONResponse(status_code=503, content={
            "detail": "Cấu trúc cơ sở dữ liệu chưa sẵn sàng. Quản trị viên cần kiểm tra và áp dụng migration.",
            "code": "DATABASE_SCHEMA_NOT_READY",
        })
    return JSONResponse(status_code=500, content={
        "detail": "Không thể xử lý dữ liệu lúc này. Vui lòng liên hệ quản trị viên.",
        "code": "DATABASE_ERROR",
    })


@app.get("/health", tags=["health"])
def health(check_database: bool = False):
    if check_database:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    return {"status": "ok"}


class RegisterInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    phone_number: Optional[str] = Field(default=None, max_length=40)


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateInput(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(default=None, max_length=40)


class UserOutput(BaseModel):
    user_id: str
    full_name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    role: str


class TokenOutput(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserOutput


def user_output(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role or "FARMER",
    }


def token_output(user: User) -> dict:
    token, expires_in = create_access_token(user.user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user_output(user),
    }


def accessible_greenhouses(db: Session, current_user: User):
    query = db.query(Greenhouse)
    if current_user.role != "ADMIN":
        query = query.filter(Greenhouse.user_id == current_user.user_id)
    return query


def accessible_devices(db: Session, current_user: User):
    query = db.query(Device).join(
        Greenhouse, Device.greenhouse_id == Greenhouse.greenhouse_id
    )
    if current_user.role != "ADMIN":
        query = query.filter(Greenhouse.user_id == current_user.user_id)
    return query


def require_greenhouse_access(
    greenhouse_id: str, db: Session, current_user: User
) -> Greenhouse:
    greenhouse = accessible_greenhouses(db, current_user).filter(
        Greenhouse.greenhouse_id == greenhouse_id
    ).first()
    if greenhouse is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà kính")
    return greenhouse


def require_device_access(device_id: str, db: Session, current_user: User) -> Device:
    device = accessible_devices(db, current_user).filter(
        Device.device_id == device_id
    ).first()
    if device is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")
    return device


def require_recommendation_access(
    rec_id: str, db: Session, current_user: User
) -> Recommendation:
    query = db.query(Recommendation).filter(Recommendation.rec_id == rec_id)
    if current_user.role != "ADMIN":
        query = query.outerjoin(
            Device, Recommendation.device_id == Device.device_id
        ).outerjoin(
            GreenhouseArea, Recommendation.area_id == GreenhouseArea.area_id
        ).join(
            Greenhouse,
            or_(
                Greenhouse.greenhouse_id == Device.greenhouse_id,
                Greenhouse.greenhouse_id == GreenhouseArea.greenhouse_id,
            ),
        )
        query = query.filter(Greenhouse.user_id == current_user.user_id)
    recommendation = query.first()
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khuyến nghị")
    return recommendation


@app.post(
    "/api/auth/register",
    status_code=201,
    response_model=TokenOutput,
    tags=["authentication"],
)
def register(body: RegisterInput, db: Session = Depends(get_db)):
    get_token_secret()
    try:
        email = normalize_email(body.email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if not body.full_name.strip():
        raise HTTPException(status_code=422, detail="full_name không được để trống")
    duplicate = db.query(User).filter(func.lower(func.trim(User.email)) == email).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Email đã được đăng ký")

    user = User(
        user_id=str(uuid.uuid4()),
        full_name=body.full_name.strip(),
        email=email,
        phone_number=body.phone_number.strip() if body.phone_number else None,
        password_hash=hash_password(body.password),
        role="FARMER",
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email đã được đăng ký") from None
    return token_output(user)


@app.post(
    "/api/auth/login",
    response_model=TokenOutput,
    tags=["authentication"],
)
def login(body: LoginInput, db: Session = Depends(get_db)):
    get_token_secret()
    try:
        email = normalize_email(body.email)
    except ValueError:
        email = "invalid-address"
    user = db.query(User).filter(func.lower(func.trim(User.email)) == email).first()
    password_matches = verify_password(
        body.password, user.password_hash if user is not None else None
    )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=401,
            detail="Email hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_output(user)


@app.get(
    "/api/auth/me",
    response_model=UserOutput,
    tags=["authentication"],
)
def get_profile(current_user: User = Depends(get_current_user)):
    return user_output(current_user)


@app.patch(
    "/api/auth/me",
    response_model=UserOutput,
    tags=["authentication"],
)
def update_profile(
    body: ProfileUpdateInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = body.dict(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Không có trường hồ sơ cần cập nhật")
    if "full_name" in changes:
        full_name = (changes["full_name"] or "").strip()
        if not full_name:
            raise HTTPException(status_code=422, detail="full_name không được để trống")
        current_user.full_name = full_name
    if "phone_number" in changes:
        current_user.phone_number = (
            changes["phone_number"].strip() if changes["phone_number"] else None
        )
    db.commit()
    db.refresh(current_user)
    return user_output(current_user)


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


@app.post("/api/greenhouses", status_code=201)
def create_greenhouse(
    body: GreenhouseInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(Greenhouse).filter(Greenhouse.greenhouse_id == body.greenhouse_id).first():
        raise HTTPException(status_code=409, detail="greenhouse_id đã tồn tại")
    item = Greenhouse(
        **body.dict(),
        user_id=current_user.user_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/greenhouses/{greenhouse_id}")
def get_greenhouse(
    greenhouse_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_greenhouse_access(greenhouse_id, db, current_user)


@app.put("/api/greenhouses/{greenhouse_id}")
def update_greenhouse(
    greenhouse_id: str,
    body: GreenhouseInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = require_greenhouse_access(greenhouse_id, db, current_user)
    if body.greenhouse_id != greenhouse_id:
        raise HTTPException(status_code=422, detail="Không thể đổi greenhouse_id")
    item.name = body.name
    item.area_sqm = body.area_sqm
    item.location = body.location
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/greenhouses/{greenhouse_id}", status_code=204)
def delete_greenhouse(
    greenhouse_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = require_greenhouse_access(greenhouse_id, db, current_user)
    if db.query(Device).filter(Device.greenhouse_id == greenhouse_id).first():
        raise HTTPException(status_code=409, detail="Nhà kính còn thiết bị liên kết; không xóa để giữ lịch sử")
    db.delete(item)
    db.commit()


@app.get("/api/devices")
def get_devices(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        accessible_devices(db, current_user)
        .order_by(Device.device_id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@app.post("/api/devices", status_code=201)
def register_device(
    body: DeviceInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_greenhouse_access(body.greenhouse_id, db, current_user)
    if db.query(Device).filter(Device.device_id == body.device_id).first():
        raise HTTPException(status_code=409, detail="device_id đã tồn tại")
    item = Device(**body.dict(), status="ACTIVE", is_online=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/api/devices/{device_id}/status")
def update_device_status(
    device_id: str,
    body: DeviceStatusInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.status not in {"ACTIVE", "INACTIVE"}:
        raise HTTPException(status_code=422, detail="status phải là ACTIVE hoặc INACTIVE")
    item = require_device_access(device_id, db, current_user)
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

# 2. API: Lấy dữ liệu cảm biến theo thiết bị (Phục vụ vẽ biểu đồ Frontend)
@app.get("/api/sensors/{device_id}")
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
        raise HTTPException(status_code=422, detail="start/end phải có múi giờ ISO 8601")
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start phải nhỏ hơn hoặc bằng end")
    require_device_access(device_id, db, current_user)
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
def get_latest_sensor(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_device_access(device_id, db, current_user)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if status is not None and status not in {"PENDING", "APPLIED", "IGNORED"}:
        raise HTTPException(status_code=422, detail="status phải là PENDING, APPLIED hoặc IGNORED")
    query = db.query(Recommendation)
    if current_user.role != "ADMIN":
        query = query.outerjoin(
            Device, Recommendation.device_id == Device.device_id
        ).outerjoin(
            GreenhouseArea, Recommendation.area_id == GreenhouseArea.area_id
        ).join(
            Greenhouse,
            or_(
                Greenhouse.greenhouse_id == Device.greenhouse_id,
                Greenhouse.greenhouse_id == GreenhouseArea.greenhouse_id,
            ),
        )
        query = query.filter(Greenhouse.user_id == current_user.user_id)
    if device_id:
        query = query.filter(Recommendation.device_id == device_id)
    if status:
        query = query.filter(Recommendation.status == status)
    recs = query.order_by(Recommendation.created_at.desc()).offset(offset).limit(limit).all()

    return recs


@app.get("/api/recommendations/{rec_id}")
def get_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_recommendation_access(rec_id, db, current_user)

# 4. API: Nông dân xác nhận đã thực hiện bón phân theo đề xuất (Cập nhật trạng thái)
@app.put("/api/recommendations/{rec_id}/apply")
def apply_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = require_recommendation_access(rec_id, db, current_user)

    rec.status = "APPLIED"
    db.commit()
    return {"message": f"Đã cập nhật trạng thái đề xuất {rec_id} thành APPLIED"}
