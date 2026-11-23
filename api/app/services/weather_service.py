"""Regional forecast, never presented as a sensor observation or a trained local model."""
from datetime import datetime, timezone
import json
import math
import threading
import time
from urllib.parse import urlencode
from urllib.request import urlopen

_cache = {}
_lock = threading.Lock()


def forecast(latitude, longitude, timezone_name="Asia/Ho_Chi_Minh"):
    if latitude is None or longitude is None:
        return {"available": False, "reason": "Chưa cấu hình tọa độ vườn", "source": "Open-Meteo"}
    if not all(math.isfinite(float(v)) for v in (latitude, longitude)) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return {"available": False, "reason": "Tọa độ không hợp lệ", "source": "Open-Meteo"}
    key = (latitude, longitude, timezone_name)
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            return cached[1]
    params = urlencode(dict(latitude=latitude, longitude=longitude, timezone=timezone_name,
        current="temperature_2m,relative_humidity_2m,precipitation,weather_code",
        daily="temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
        forecast_days=2))
    try:
        with urlopen("https://api.open-meteo.com/v1/forecast?" + params, timeout=4) as response:
            raw = json.load(response)
        days = raw["daily"]
        if len(days["time"]) < 2:
            raise ValueError("Incomplete forecast")
        result = {"available": True, "source": "Open-Meteo", "source_url": "https://open-meteo.com/",
            "fetched_at": datetime.now(timezone.utc).isoformat(), "timezone": raw["timezone"],
            "latitude": latitude, "longitude": longitude, "current": raw.get("current", {}),
            "days": [{"date": days["time"][i], "max_temperature_c": days["temperature_2m_max"][i],
                      "min_temperature_c": days["temperature_2m_min"][i],
                      "rain_mm": days["precipitation_sum"][i],
                      "rain_probability_pct": days["precipitation_probability_max"][i]} for i in range(2)]}
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        result = {"available": False, "source": "Open-Meteo", "reason": "Không lấy được dự báo; không điều chỉnh tưới theo thời tiết"}
    with _lock:
        # Bound memory for long-lived multi-garden servers.
        if len(_cache) >= 256:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic() - (0 if result["available"] else 840), result)
    return result


def weather_adjustment(rules, weather, now):
    """Opt-in bounded duration adjustment, not a learned crop water requirement."""
    from zoneinfo import ZoneInfo
    local = now.astimezone(ZoneInfo(rules.timezone))
    if not weather.get("available"):
        return 1.0, "Không có dự báo hợp lệ; dùng thời lượng cơ sở"
    days = weather.get("days", [])
    if len(days) < 2 or days[0]["date"] != local.date().isoformat():
        return 1.0, "Dự báo không đúng ngày; dùng thời lượng cơ sở"
    today, tomorrow = days[:2]
    # Forecast rain matters only when this growing area receives outdoor rain.
    if local.hour >= 16 and rules.rain_exposed and (tomorrow.get("rain_probability_pct") or 0) >= rules.rain_probability_pct and (tomorrow.get("rain_mm") or 0) >= rules.rain_mm:
        return rules.rainy_evening_multiplier, "Giảm thời lượng chiều theo dự báo mưa ngày mai (khu nhận mưa)"
    if 4 <= local.hour < 10 and (today.get("max_temperature_c") or -100) >= rules.hot_day_c:
        return rules.morning_multiplier, "Điều chỉnh buổi sáng theo dự báo nhiệt độ cao trong ngày"
    return 1.0, "Dùng thời lượng cơ sở"
