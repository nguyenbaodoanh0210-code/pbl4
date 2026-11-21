"""AI inference controller (legacy endpoints preserved; camera multimodal added in Stage 3B)."""

from fastapi import APIRouter, HTTPException, Request

from ..ai.disease import (
    DiseaseModelUnavailable,
    InvalidDiseaseImage,
    predict_disease,
)
from ..ai.greenhouse import MODEL_PATH as GREENHOUSE_MODEL_PATH
from ..ai.greenhouse import load_ai_model, predict_greenhouse
from ..schemas import (
    DiseasePredictionOutput,
    FertilizerPredictionInput,
    FertilizerPredictionOutput,
)

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/fertilizer/predict", response_model=FertilizerPredictionOutput)
def predict_fertilizer(body: FertilizerPredictionInput):
    """Run the local demo model on supplied crop and sensor values."""
    model_bundle = load_ai_model(GREENHOUSE_MODEL_PATH)
    if model_bundle is None:
        raise HTTPException(status_code=503, detail="Model khuyến nghị chưa sẵn sàng")
    try:
        prediction = predict_greenhouse(body.model_dump(), model_bundle)
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


@router.post(
    "/disease/predict",
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
                raise HTTPException(
                    status_code=413, detail="Ảnh vượt quá giới hạn 10 MB"
                )
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Content-Length không hợp lệ"
            ) from None

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
