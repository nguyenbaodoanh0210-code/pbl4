"""Optional image-disease inference for the Chili Plant Disease dataset."""

from functools import lru_cache
import json
import hashlib
import io
import math
import os
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[2] / "ml_models"
MODEL_PATH = Path(os.getenv("DISEASE_MODEL_PATH", str(MODEL_DIR / "plant_disease_model.keras")))
METADATA_PATH = Path(os.getenv("DISEASE_METADATA_PATH", str(MODEL_DIR / "plant_disease_model_metadata.json")))
MAX_IMAGE_PIXELS = 20_000_000


class DiseaseModelUnavailable(RuntimeError):
    """Raised when the trained image model or its runtime is unavailable."""


class InvalidDiseaseImage(ValueError):
    """Raised when image bytes cannot be decoded or scored safely."""


def model_info():
    try:
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        return {"model": metadata.get("model_name", MODEL_PATH.stem),
                "class_names": metadata["class_names"], "image_size": metadata["image_size"],
                "weights_present": MODEL_PATH.is_file(), "experimental": True,
                "evaluation": metadata.get("evaluation"),
                "note": "Chưa có kiểm định độc lập; điểm model không phải xác suất mắc bệnh đã hiệu chuẩn."}
    except (OSError, ValueError, KeyError):
        raise DiseaseModelUnavailable("Không đọc được cấu hình model ảnh") from None


@lru_cache(maxsize=1)
def _load_model():
    if not MODEL_PATH.is_file() or not METADATA_PATH.is_file():
        raise DiseaseModelUnavailable("Model nhận diện bệnh từ ảnh chưa được train")

    try:
        import tensorflow as tf
    except ImportError as exc:
        raise DiseaseModelUnavailable(
            "Thiếu TensorFlow tùy chọn để chạy model nhận diện ảnh"
        ) from exc

    try:
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        class_names = metadata["class_names"]
        image_size = metadata["image_size"]
        if (not isinstance(class_names, list) or len(class_names) < 2
                or any(not isinstance(name, str) or not name for name in class_names)
                or len(set(class_names)) != len(class_names)):
            raise ValueError("Invalid class metadata")
        if not isinstance(image_size, int) or not 32 <= image_size <= 1024:
            raise ValueError("Invalid image size metadata")
        if metadata.get("model_sha256") and hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != metadata["model_sha256"]:
            raise ValueError("Model checksum does not match metadata")
        model = tf.keras.models.load_model(MODEL_PATH, compile=False, safe_mode=True)
        if int(model.output_shape[-1]) != len(class_names):
            raise ValueError("Model output does not match class metadata")
        if tuple(model.input_shape[1:]) != (image_size, image_size, 3):
            raise ValueError("Model input does not match metadata")
        return tf, model, metadata
    except Exception as exc:
        raise DiseaseModelUnavailable(
            "Model nhận diện ảnh hoặc metadata không hợp lệ"
        ) from exc


def _image_dimensions(image_bytes: bytes) -> tuple[str, int, int]:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(image_bytes) < 24 or image_bytes[12:16] != b"IHDR":
            raise InvalidDiseaseImage("Header PNG không hợp lệ")
        width = int.from_bytes(image_bytes[16:20], "big")
        height = int.from_bytes(image_bytes[20:24], "big")
        return "image/png", width, height

    if image_bytes.startswith(b"\xff\xd8"):
        frame_markers = {
            0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
        }
        index = 2
        while index < len(image_bytes):
            if image_bytes[index] != 0xFF:
                index += 1
                continue
            while index < len(image_bytes) and image_bytes[index] == 0xFF:
                index += 1
            if index >= len(image_bytes):
                break
            marker = image_bytes[index]
            index += 1
            if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
                continue
            if index + 2 > len(image_bytes):
                break
            segment_length = int.from_bytes(image_bytes[index:index + 2], "big")
            if segment_length < 2 or index + segment_length > len(image_bytes):
                break
            if marker in frame_markers:
                if segment_length < 7:
                    break
                height = int.from_bytes(image_bytes[index + 3:index + 5], "big")
                width = int.from_bytes(image_bytes[index + 5:index + 7], "big")
                return "image/jpeg", width, height
            index += segment_length
        raise InvalidDiseaseImage("Không xác định được kích thước JPEG")

    raise InvalidDiseaseImage("Nội dung không phải ảnh JPEG hoặc PNG")


def predict_disease(image_bytes: bytes, expected_content_type: str | None = None) -> dict:
    if not image_bytes:
        raise InvalidDiseaseImage("Ảnh tải lên đang rỗng")
    content_type, width, height = _image_dimensions(image_bytes)
    if expected_content_type and content_type != expected_content_type:
        raise InvalidDiseaseImage("Content-Type không khớp định dạng ảnh")
    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
        raise InvalidDiseaseImage("Kích thước ảnh không hợp lệ hoặc vượt giới hạn 20 megapixel")

    tf, model, metadata = _load_model()
    image_size = metadata["image_size"]
    try:
        if metadata.get("preprocessing") == "pil_rgb_bicubic_0_255":
            # Match the supplied ai-service exactly; the model embeds Rescaling.
            import numpy as np
            from PIL import Image
            try:
                with Image.open(io.BytesIO(image_bytes)) as original:
                    image = np.asarray(original.convert("RGB").resize(
                        (image_size, image_size), Image.Resampling.BICUBIC), dtype=np.float32)
            except (OSError, ValueError) as exc:
                raise InvalidDiseaseImage("Không đọc được nội dung ảnh hợp lệ") from exc
        else:
            image = tf.io.decode_image(image_bytes, channels=3, expand_animations=False)
            image = tf.ensure_shape(image, (None, None, 3))
            image = tf.image.resize(image, (image_size, image_size), antialias=True)
        scores = model(tf.expand_dims(image, axis=0), training=False).numpy()[0]
    except InvalidDiseaseImage:
        raise
    except (tf.errors.InvalidArgumentError, ValueError) as exc:
        raise InvalidDiseaseImage("Không đọc được nội dung ảnh hợp lệ") from exc
    except Exception as exc:
        raise DiseaseModelUnavailable("Không thể chạy model nhận diện ảnh") from exc

    class_names = metadata["class_names"]
    if len(scores) != len(class_names):
        raise DiseaseModelUnavailable("Kết quả model không khớp danh sách lớp")
    ranked = sorted(
        zip(class_names, scores.tolist()), key=lambda item: item[1], reverse=True
    )
    if any(not math.isfinite(float(v)) or not 0 <= v <= 1 for _, v in ranked) or abs(sum(v for _, v in ranked) - 1) > 0.01:
        raise DiseaseModelUnavailable("Điểm model không hợp lệ")
    return {
        "class_name": ranked[0][0],
        "class_group": metadata.get("class_groups", {}).get(ranked[0][0], "unknown"),
        "model": metadata.get("model_name", MODEL_PATH.stem),
        "scores": {name: round(float(score), 6) for name, score in ranked},
        "score_note": "Điểm softmax thử nghiệm, chưa được hiệu chuẩn thành độ tin cậy.",
        "experimental": True,
    }
