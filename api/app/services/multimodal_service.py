"""Multimodal Logic combining ESP32-CAM CNN disease predictions with DHT22 + LDR Light data."""

from __future__ import annotations

from typing import Any


MODEL_VERSION = "chili_cnn_v1+multimodal_v1"

DISEASE_CATALOG: dict[str, dict[str, Any]] = {
    "bacterial": {
        "label_vi": "Dấu hiệu bệnh do vi khuẩn",
        "profile": "bacterial",
        "action_chili": "Kiểm tra trực tiếp vết bệnh trên lá ớt, vệ sinh dụng cụ và theo dõi ảnh chụp tiếp theo.",
        "action_lettuce": "Kiểm tra trực tiếp lá xà lách và đối chiếu thêm trước khi xử lý.",
    },
    "healthy": {
        "label_vi": "Khỏe mạnh",
        "profile": "healthy",
        "action_chili": "Tiếp tục duy trì chế độ tưới gốc buổi sáng và theo dõi định kỳ trên Cây ớt.",
        "action_lettuce": "Tiếp tục duy trì tưới ẩm vừa phải và thoáng gió cho luống Cây xà lách.",
    },
    "leaf spot": {
        "label_vi": "Nấm đốm lá (Leaf Spot)",
        "profile": "fungal",
        "action_chili": (
            "Cắt tỉa lá ớt bị đốm nặng, tạm ngưng bơm tưới vào chiều tối để giảm ẩm bề mặt lá, "
            "tạo thông thoáng tự nhiên ngoài trời và theo dõi lại sau 24 giờ."
        ),
        "action_lettuce": (
            "Loại bỏ lá xà lách bị đốm, tạm ngưng bơm tưới phun lên lá, "
            "giữ luống thoát nước tốt và tránh đọng nước ban đêm."
        ),
    },
    "fungal": {
        "label_vi": "Nấm bệnh (Fungal)",
        "profile": "fungal",
        "action_chili": (
            "Tỉa thưa tán Cây ớt để tăng thông thoáng tự nhiên, tạm ngưng bơm tưới khi độ ẩm > 80% "
            "và xử lý sinh học phòng nấm nếu vết bệnh lan rộng."
        ),
        "action_lettuce": (
            "Tỉa bỏ lá nhiễm nấm, tạm ngưng bơm tưới ngay và giữ luống Xà lách thoáng ráo."
        ),
    },
    "yellowish": {
        "label_vi": "Vàng lá (Yellowish)",
        "profile": "yellowish",
        "action_chili": (
            "Kiểm tra tình trạng úng nước hoặc thiếu nắng ngoài trời của Cây ớt, "
            "điều chỉnh chu kỳ tưới và bổ sung dinh dưỡng cân đối nếu lá tiếp tục vàng."
        ),
        "action_lettuce": (
            "Kiểm tra độ thoát nước và cường độ ánh sáng luống Xà lách, "
            "loại bỏ lá già úa để tránh phát sinh nấm thứ cấp."
        ),
    },
    "leaf curl": {
        "label_vi": "Xoăn lá (Leaf Curl)",
        "profile": "heat_pest",
        "action_chili": (
            "Kiểm tra mặt dưới lá ớt xem có bọ trĩ/nhện đỏ không, tăng tưới mát gốc khi trời nắng gắt "
            "và cách ly cây bị xoăn lá nặng."
        ),
        "action_lettuce": (
            "Che nắng nhẹ giờ cao điểm trưa, kiểm tra sâu chích hút và giữ ẩm ổn định cho Cây xà lách."
        ),
    },
    "whitefly": {
        "label_vi": "Bọ phấn trắng (Whitefly)",
        "profile": "heat_pest",
        "action_chili": (
            "Kiểm tra mặt dưới lá ớt, đặt bẫy dính vàng quanh khu vườn ngoài trời "
            "và rửa lá bằng nước sạch vào sáng sớm."
        ),
        "action_lettuce": (
            "Dùng bẫy dính vàng sinh học xung quanh luống Xà lách và kiểm tra lá non hàng ngày."
        ),
    },
}


def _clamp(value: float, low: float = 0.0, high: float = 0.99) -> float:
    return round(max(low, min(high, float(value))), 4)


def _crop_is_lettuce(crop_config: dict | None) -> bool:
    name = str((crop_config or {}).get("crop_name") or "").casefold()
    return "xà lách" in name or "lettuce" in name


def _lookup_disease(class_name: str) -> dict[str, Any]:
    key = (class_name or "").strip().casefold()
    if key in DISEASE_CATALOG:
        return DISEASE_CATALOG[key]
    if key == "ot_dom_vi_khuan":
        return DISEASE_CATALOG["bacterial"]
    if "healthy" in key or "khoe" in key:
        return DISEASE_CATALOG["healthy"]
    if "spot" in key or "fung" in key or "nam" in key:
        return DISEASE_CATALOG["leaf spot"]
    if "yellow" in key or "vang" in key:
        return DISEASE_CATALOG["yellowish"]
    if "curl" in key or "xoan" in key:
        return DISEASE_CATALOG["leaf curl"]
    return {
        "label_vi": class_name or "Bất thường chưa phân loại",
        "profile": "fungal",
        "action_chili": "Kiểm tra trực tiếp lá Cây ớt và đối chiếu thông số môi trường trước khi xử lý.",
        "action_lettuce": "Kiểm tra trực tiếp lá Cây xà lách và theo dõi thêm thông số nhiệt độ, độ ẩm, ánh sáng.",
    }


def summarize_env_window(
    env_snapshot: dict | None,
    env_history: list[dict] | None,
    crop_config: dict | None,
) -> dict[str, Any]:
    """Summarize DHT22 & LDR light metrics over the recent observation window."""
    cfg = crop_config or {}
    fungal_hum = float(cfg.get("fungal_humidity_threshold", 85.0))
    fungal_light = float(cfg.get("fungal_light_threshold", 8000.0))
    max_temp = float(cfg.get("max_temp", 33.0))
    min_hum = float(cfg.get("min_humidity", 55.0))
    window_minutes = int(cfg.get("fungal_duration_minutes", 60))

    records = [row for row in (env_history or []) if isinstance(row, dict)]
    if env_snapshot and not records:
        records = [env_snapshot]

    temps = [float(r["temperature"]) for r in records if r.get("temperature") is not None]
    hums = [float(r["humidity"]) for r in records if r.get("humidity") is not None]
    lights = [float(r["light_level"]) for r in records if r.get("light_level") is not None]

    cur_temp = (
        float(env_snapshot["temperature"])
        if env_snapshot and env_snapshot.get("temperature") is not None
        else (temps[-1] if temps else None)
    )
    cur_hum = (
        float(env_snapshot["humidity"])
        if env_snapshot and env_snapshot.get("humidity") is not None
        else (hums[-1] if hums else None)
    )
    cur_light = (
        float(env_snapshot["light_level"])
        if env_snapshot and env_snapshot.get("light_level") is not None
        else (lights[-1] if lights else None)
    )

    avg_temp = round(sum(temps) / len(temps), 2) if temps else None
    avg_hum = round(sum(hums) / len(hums), 2) if hums else None
    avg_light = round(sum(lights) / len(lights), 1) if lights else None

    high_hum_count = sum(1 for h in hums if h >= fungal_hum)
    high_hum_ratio = round(high_hum_count / len(hums), 3) if hums else 0.0
    sustained_high_humidity = bool(
        (cur_hum is not None and cur_hum >= fungal_hum)
        and (high_hum_count >= 2 or (len(hums) == 1 and high_hum_count == 1) or high_hum_ratio >= 0.5)
    )
    low_light_detected = bool(
        (cur_light is not None and cur_light <= fungal_light)
        or (avg_light is not None and avg_light <= fungal_light)
    )
    heat_stress = bool(cur_temp is not None and cur_temp >= max_temp)
    dry_stress = bool(cur_hum is not None and cur_hum <= min_hum)

    return {
        "has_sensor_data": any(v is not None for v in (cur_temp, cur_hum, cur_light)),
        "window_minutes": window_minutes,
        "sample_count": len(records),
        "temperature": cur_temp,
        "humidity": cur_hum,
        "light_level": cur_light,
        "avg_temp": avg_temp,
        "avg_humidity": avg_hum,
        "avg_light": avg_light,
        "fungal_humidity_threshold": fungal_hum,
        "fungal_light_threshold": fungal_light,
        "high_humidity_samples": high_hum_count,
        "high_humidity_ratio": high_hum_ratio,
        "sustained_high_humidity": sustained_high_humidity,
        "low_light_detected": low_light_detected,
        "heat_stress": heat_stress,
        "dry_stress": dry_stress,
    }


def fuse_multimodal_diagnosis(
    cnn_result: dict[str, Any],
    env_snapshot: dict | None = None,
    env_history: list[dict] | None = None,
    crop_config: dict | None = None,
    model_version: str = MODEL_VERSION,
) -> dict[str, Any]:
    """Combine CNN image classification scores with DHT22 + LDR Light environmental context."""
    raw_class = str(cnn_result.get("class_name") or "unknown")
    raw_scores = dict(cnn_result.get("scores") or {})
    cnn_conf = float(raw_scores.get(raw_class, max(raw_scores.values(), default=0.0)))
    cnn_conf = _clamp(cnn_conf, 0.0, 1.0)

    info = _lookup_disease(raw_class)
    profile = info["profile"]
    is_healthy = profile == "healthy"
    crop_name = str((crop_config or {}).get("crop_name") or "Cây trồng ngoài trời")
    action = info["action_lettuce"] if _crop_is_lettuce(crop_config) else info["action_chili"]

    summary = summarize_env_window(env_snapshot, env_history, crop_config)
    cur_temp = summary["temperature"]
    cur_hum = summary["humidity"]
    cur_light = summary["light_level"]
    fungal_hum = summary["fungal_humidity_threshold"]
    fungal_light = summary["fungal_light_threshold"]

    delta = 0.0
    if not summary["has_sensor_data"]:
        reason = (
            f"Nhận diện qua hình ảnh lá: '{info['label_vi']}' ({cnn_conf * 100:.1f}%). "
            "Chưa có dữ liệu đo thời tiết xung quanh để đối chiếu thêm."
        )
    elif profile == "bacterial":
        reason = f"Hình ảnh gợi ý {info['label_vi']} ({cnn_conf * 100:.1f}%). Cần kiểm tra trực tiếp; cảm biến môi trường không xác nhận tác nhân vi khuẩn."
    elif profile == "fungal":
        if summary["sustained_high_humidity"] and summary["low_light_detected"]:
            delta = 0.12
            reason = (
                f"Hình ảnh ghi nhận dấu hiệu {info['label_vi']} ({cnn_conf * 100:.1f}%). "
                f"Thời tiết ngoài vườn đang có độ ẩm cao {cur_hum:.1f}% (≥{fungal_hum:.0f}% kéo dài) "
                f"kết hợp ánh sáng yếu ({cur_light:.0f} Lux) tại luống {crop_name} "
                f"→ điều kiện thuận lợi cho nấm bệnh phát triển (+{delta * 100:.0f}% độ tin cậy)."
            )
        elif summary["sustained_high_humidity"]:
            delta = 0.07
            reason = (
                f"Hình ảnh ghi nhận dấu hiệu {info['label_vi']} ({cnn_conf * 100:.1f}%). "
                f"Độ ẩm không khí ngoài trời đạt {cur_hum:.1f}% (≥{fungal_hum:.0f}%) thuận lợi cho nấm phát triển "
                f"→ tăng độ tin cậy chẩn đoán (+{delta * 100:.0f}%)."
            )
        elif (
            cur_hum is not None
            and cur_hum < float((crop_config or {}).get("max_humidity", 80.0)) - 10.0
            and not summary["low_light_detected"]
        ):
            delta = -0.08
            reason = (
                f"Hình ảnh nghi ngờ {info['label_vi']} ({cnn_conf * 100:.1f}%), nhưng điều kiện thời tiết "
                f"tại luống {crop_name} đang khô thoáng (độ ẩm {cur_hum:.1f}%, ánh sáng {cur_light or 0:.0f} Lux) "
                "→ giảm bớt nguy cơ nấm, nên kiểm tra trực tiếp mặt lá."
            )
        else:
            reason = (
                f"Hình ảnh dự đoán {info['label_vi']} ({cnn_conf * 100:.1f}%). "
                f"Thời tiết lúc chụp ở mức bình thường (nhiệt độ {cur_temp}°C, độ ẩm {cur_hum}%)."
            )
    elif profile == "yellowish":
        if summary["sustained_high_humidity"] or summary["low_light_detected"]:
            delta = 0.08
            reason = (
                f"Hình ảnh nhận diện {info['label_vi']} ({cnn_conf * 100:.1f}%). "
                f"Thời tiết ngoài trời tại luống {crop_name} ghi nhận độ ẩm cao hoặc thiếu sáng "
                f"(ẩm {cur_hum}%, ánh sáng {cur_light} Lux) → củng cố chẩn đoán (+{delta * 100:.0f}%)."
            )
        else:
            delta = -0.04
            reason = (
                f"Hình ảnh nhận diện {info['label_vi']} ({cnn_conf * 100:.1f}%). "
                f"Nhiệt độ ({cur_temp}°C), độ ẩm ({cur_hum}%) và ánh sáng ({cur_light} Lux) đang ổn định "
                "→ cần kiểm tra thêm khả năng thoát nước hoặc dinh dưỡng rễ cây."
            )
    elif profile == "heat_pest":
        if summary["heat_stress"] or summary["dry_stress"]:
            delta = 0.09
            reason = (
                f"Hình ảnh phát hiện {info['label_vi']} ({cnn_conf * 100:.1f}%). "
                f"Thời tiết ngoài vườn đang nóng và khô (nhiệt độ {cur_temp}°C, độ ẩm {cur_hum}%) "
                f"tại luống {crop_name} → tăng nguy cơ xoăn lá và sâu chích hút (+{delta * 100:.0f}%)."
            )
        else:
            delta = -0.04
            reason = (
                f"Hình ảnh phát hiện {info['label_vi']} ({cnn_conf * 100:.1f}%). "
                f"Nhiệt độ ({cur_temp}°C) và độ ẩm ({cur_hum}%) chưa có dấu hiệu nắng gắt "
                "→ nên kiểm tra trực tiếp mặt dưới lá cây."
            )
    else:  # healthy
        if summary["sustained_high_humidity"] and summary["low_light_detected"]:
            delta = -0.05
            reason = (
                f"Lá cây hiện tại chưa có vết bệnh ({cnn_conf * 100:.1f}%), nhưng thời tiết đang "
                f"ẩm ướt {cur_hum:.1f}% (≥{fungal_hum:.0f}%) kèm trời râm thiếu sáng ({cur_light:.0f} Lux) "
                f"— cảnh báo sớm nguy cơ phát sinh nấm bệnh tại luống {crop_name}."
            )
            action = (
                f"Cây {crop_name} chưa có vết bệnh rõ nhưng độ ẩm cao kéo dài: "
                "nên tạm ngưng bơm tưới nước, tránh tưới lên lá vào chiều tối và kiểm tra lại sau vài giờ."
            )
        else:
            delta = 0.02
            reason = (
                f"Cây đang phát triển khỏe mạnh bình thường ({cnn_conf * 100:.1f}%), các chỉ số "
                f"nhiệt độ, độ ẩm và ánh sáng tại luống {crop_name} đều nằm trong ngưỡng lý tưởng."
            )

    final_conf = _clamp(cnn_conf + delta, 0.05, 0.99)
    return {
        "cnn_diagnosis": raw_class,
        "cnn_confidence": round(cnn_conf, 4),
        "cnn_scores": raw_scores,
        "final_diagnosis": info["label_vi"],
        "is_healthy": is_healthy,
        "multimodal_confidence": final_conf,
        "confidence_delta": round(final_conf - cnn_conf, 4),
        "env_snapshot": {
            "temperature": cur_temp,
            "humidity": cur_hum,
            "light_level": cur_light,
        },
        "env_window_summary": summary,
        "multimodal_reason": reason,
        "recommended_action": action,
        "model_version": model_version,
    }
