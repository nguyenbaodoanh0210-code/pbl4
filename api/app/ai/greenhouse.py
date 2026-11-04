"""Inference helpers for the greenhouse sensor recommendation model."""

from functools import lru_cache
import logging
import math
from pathlib import Path

import joblib
import pandas as pd


MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODEL_DIR / "greenhouse_demo_model.joblib"
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_ai_model(path: Path = MODEL_PATH):
    if not path.is_file():
        logger.error("Greenhouse model artifact is missing; run the training script.")
        return None
    try:
        model_bundle = joblib.load(path)
        required = {
            "artifact_version",
            "model",
            "feature_columns",
            "categorical_columns",
            "numeric_ranges",
            "category_values",
            "diagnosis_by_action",
        }
        if not isinstance(model_bundle, dict) or not required.issubset(model_bundle):
            raise ValueError("Unexpected greenhouse model artifact format")
        if model_bundle["artifact_version"] != 1:
            raise ValueError("Unsupported greenhouse model artifact version")
        logger.info("Greenhouse demo model loaded.")
        return model_bundle
    except Exception as exc:
        logger.error("Could not load greenhouse model artifact (%s).", type(exc).__name__)
        return None


def make_model_input(sensor_data: dict, model_bundle: dict) -> pd.DataFrame:
    feature_columns = model_bundle["feature_columns"]
    missing = [
        name
        for name in feature_columns
        if name not in sensor_data or sensor_data[name] is None
    ]
    if missing:
        raise ValueError("Thiếu trường đầu vào: " + ", ".join(missing))

    values = {}
    for name in feature_columns:
        value = sensor_data[name]
        if name in model_bundle["categorical_columns"]:
            value = str(value).strip()
            if value not in model_bundle["category_values"].get(name, []):
                raise ValueError(f"{name} không có trong nhóm giá trị đã train")
        else:
            if isinstance(value, bool):
                raise ValueError(f"{name} phải là số hữu hạn")
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{name} phải là số hữu hạn") from None
            if not math.isfinite(value):
                raise ValueError(f"{name} phải là số hữu hạn")
            lower, upper = model_bundle["numeric_ranges"][name]
            if not lower <= value <= upper:
                raise ValueError(
                    f"{name}={value:g} ngoài khoảng dataset đã train "
                    f"[{lower:g}, {upper:g}]; không đưa ra dự đoán"
                )
        values[name] = value
    return pd.DataFrame([values], columns=feature_columns)


def predict_greenhouse(sensor_data: dict, model_bundle: dict | None = None) -> dict:
    """Return the demo model's diagnosis and action for one sensor record."""
    if model_bundle is None:
        model_bundle = load_ai_model()
    if model_bundle is None:
        raise RuntimeError("Model khuyến nghị chưa sẵn sàng")

    input_frame = make_model_input(sensor_data, model_bundle)
    action = str(model_bundle["model"].predict(input_frame)[0])
    diagnosis = model_bundle["diagnosis_by_action"].get(action)
    if diagnosis is None:
        raise RuntimeError("Model trả về nhãn chưa có ánh xạ chẩn đoán")
    return {"condition_diagnosis": diagnosis, "fertilizer_action": action}
