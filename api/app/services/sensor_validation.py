"""Pure telemetry checks shared by ingestion, manual control and the watchdog."""
from datetime import datetime, timezone
import math

MAX_AGE_SECONDS = 120
MAX_FUTURE_SECONDS = 5
STUCK_WINDOW_SECONDS = 600
FIELDS = ("temperature", "humidity", "soil_moisture", "light_level")
RANGES = {"temperature": (-40, 85), "humidity": (0, 100),
          "soil_moisture": (0, 100), "light_level": (0, 200000)}


def utc(value):
    # SQLite returns timezone-naive UTC, PostgreSQL returns aware timestamps.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def timestamp_problem(measured_at, now=None, max_age=MAX_AGE_SECONDS):
    now = now or datetime.now(timezone.utc)
    age = (utc(now) - utc(measured_at)).total_seconds()
    if age < -MAX_FUTURE_SECONDS:
        return "Thời gian đo nằm ở tương lai"
    if age > max_age:
        return "Dữ liệu cảm biến quá cũ"
    return None


def quality_problems(reading, history=(), now=None, max_age=MAX_AGE_SECONDS):
    if reading is None:
        return ["Chưa có dữ liệu cảm biến"]
    problems = []
    for name, (low, high) in RANGES.items():
        value = getattr(reading, name, None)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
            problems.append(f"Thiếu hoặc sai số đo {name}")
    if reading.timestamp is None:
        problems.append("Thiếu thời gian đo")
        return problems
    problem = timestamp_problem(reading.timestamp, now, max_age)
    if problem:
        problems.append(problem)
    if problems:
        return problems
    previous = sorted([r for r in history if r.timestamp and utc(r.timestamp) < utc(reading.timestamp)],
                      key=lambda r: utc(r.timestamp), reverse=True)
    if previous:
        seconds = (utc(reading.timestamp) - utc(previous[0].timestamp)).total_seconds()
        if 0 < seconds <= 60:
            # Conservative plausibility flags, not proof a sensor is defective.
            for name, limit in (("temperature", 10), ("humidity", 30), ("soil_moisture", 30)):
                old = getattr(previous[0], name, None)
                if old is not None and abs(getattr(reading, name) - old) > limit:
                    problems.append(f"Số đo {name} thay đổi đột ngột; cần kiểm tra lại")
    same = [reading]
    for row in previous:
        if (utc(same[-1].timestamp) - utc(row.timestamp)).total_seconds() > MAX_AGE_SECONDS:
            break
        if not all(getattr(row, f, None) is not None and abs(getattr(row, f) - getattr(reading, f)) <= .001 for f in FIELDS):
            break
        same.append(row)
    if len(same) >= 5 and (utc(reading.timestamp) - utc(same[-1].timestamp)).total_seconds() >= STUCK_WINDOW_SECONDS:
        problems.append("Toàn bộ số đo không đổi ít nhất 10 phút; nghi ngờ bản tin/cảm biến đứng số")
    return problems
