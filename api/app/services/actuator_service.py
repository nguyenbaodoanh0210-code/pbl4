"""Soil-based irrigation with bounded commands and explicit board feedback."""
from datetime import datetime, timedelta, timezone
import os
import uuid
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from ..models import ActuatorLog, ActuatorState, Device, Greenhouse, SensorLog, User
from ..schemas import ActuatorUpdateInput
from ..schemas.actuator import IrrigationRules
from .sensor_validation import quality_problems, utc
from .mqtt_publisher import control_topic, publish_mqtt_json
from .weather_service import forecast, weather_adjustment


def policy(item):
    try:
        return IrrigationRules.model_validate(item.auto_rules or {})
    except (ValidationError, TypeError):
        return None


def logs_for(db, item, since=None):
    query = db.query(ActuatorLog).filter(ActuatorLog.actuator_id == item.actuator_id)
    if since:
        query = query.filter(ActuatorLog.created_at >= since)
    return query.order_by(ActuatorLog.created_at.desc()).all()


def latest_start(db, item):
    return db.query(ActuatorLog).filter(ActuatorLog.actuator_id == item.actuator_id,
        ActuatorLog.action == "TURN_ON", ActuatorLog.ack_status != "FAILED").order_by(ActuatorLog.created_at.desc()).first()


def runtime_used(db, item, now):
    # Conservative budget: each accepted start reserves its entire requested duration.
    # Failed broker sends are excluded; no dependency on ACK delivery.
    return sum(log.duration_seconds or 120 for log in logs_for(db, item, now-timedelta(hours=24))
        if log.action == "TURN_ON" and log.ack_status != "FAILED")


def serialize_actuator(item, db=None, now=None):
    now = now or datetime.now(timezone.utc)
    rules = policy(item)
    start = latest_start(db, item) if db else None
    deadline = utc(start.acknowledged_at or start.created_at)+timedelta(seconds=start.duration_seconds or 120) if start and item.is_on else None
    fresh = item.reported_at is not None and (now-utc(item.reported_at)).total_seconds() <= 120
    state = "UNKNOWN"
    if fresh:
        state = "RUNNING" if item.reported_on else "STOPPED"
    if item.is_on and (not fresh or not item.reported_on):
        state = "PENDING"
    if not item.is_on and fresh and item.reported_on:
        state = "PENDING_STOP"
    last_ack = None
    if db:
        last_ack = db.query(ActuatorLog).filter(ActuatorLog.actuator_id == item.actuator_id,
            ActuatorLog.action == "TURN_ON", ActuatorLog.acknowledged_at.is_not(None)).order_by(ActuatorLog.acknowledged_at.desc()).first()
    return dict(actuator_id=item.actuator_id, greenhouse_id=item.greenhouse_id, area_id=item.area_id,
        device_id=item.device_id, actuator_type=item.actuator_type, control_mode=item.control_mode,
        is_on=bool(item.is_on), status=state, reported_on=item.reported_on if fresh else None,
        reported_at=item.reported_at.isoformat() if item.reported_at else None,
        started_at=last_ack.acknowledged_at.isoformat() if last_ack and fresh and item.reported_on else None,
        scheduled_stop_at=deadline.isoformat() if deadline else None,
        last_irrigation_at=last_ack.acknowledged_at.isoformat() if last_ack else None,
        next_irrigation_at=None,
        next_irrigation_reason="Chờ số đo đất mới và điều kiện an toàn" if item.control_mode == "AUTO" else "Thủ công; chưa có lịch tưới",
        auto_rules=item.auto_rules or {}, last_changed_by=item.last_changed_by,
        updated_at=item.updated_at.isoformat() if item.updated_at else None)


def serialize_actuator_log(item):
    return dict(log_id=item.log_id, actuator_id=item.actuator_id, user_id=item.user_id,
        action=item.action, trigger_source=item.trigger_source, reason=item.reason, ack_status=item.ack_status,
        created_at=item.created_at.isoformat(), acknowledged_at=item.acknowledged_at.isoformat() if item.acknowledged_at else None)


def ensure_default_actuators(db, greenhouse_id):
    rows = db.query(ActuatorState).filter(ActuatorState.greenhouse_id == greenhouse_id,
        ActuatorState.actuator_type == "PUMP").order_by(ActuatorState.actuator_id).all()
    if not rows:
        row = ActuatorState(actuator_id="act-"+uuid.uuid4().hex[:12], greenhouse_id=greenhouse_id,
            actuator_type="PUMP", control_mode="MANUAL", is_on=False, auto_rules={},
            last_changed_by="USER", updated_at=datetime.now(timezone.utc))
        db.add(row)
        db.flush()
        rows = [row]
    return rows


def daily_statistics(logs, zone, now):
    """Confirmed intervals only. An unmatched start has UNKNOWN duration, never invented liters."""
    result = {}
    active = None
    for log in sorted((l for l in logs if l.acknowledged_at), key=lambda l: l.acknowledged_at):
        moment = utc(log.acknowledged_at)
        key = moment.astimezone(zone).date().isoformat()
        row = result.setdefault(key, dict(date=key, starts=0, confirmed_seconds=0, volume_liters=None))
        if log.action == "TURN_ON" and active is None:
            row["starts"] += 1
            active = moment
        elif log.action == "TURN_OFF" and active is not None:
            cursor = active
            while cursor < moment:
                local = cursor.astimezone(zone)
                midnight = datetime.combine(local.date()+timedelta(days=1), datetime.min.time(), zone).astimezone(timezone.utc)
                end = min(moment, midnight)
                day = result.setdefault(local.date().isoformat(), dict(date=local.date().isoformat(), starts=0, confirmed_seconds=0, volume_liters=None))
                day["confirmed_seconds"] += max(0, int((end-cursor).total_seconds()))
                cursor = end
            active = None
    return sorted(result.values(), key=lambda r: r["date"], reverse=True)[:7]


def get_garden_actuators_payload(db, greenhouse_id):
    rows = ensure_default_actuators(db, greenhouse_id)
    now = datetime.now(timezone.utc)
    logs = db.query(ActuatorLog).filter(ActuatorLog.actuator_id.in_([r.actuator_id for r in rows]),
        ActuatorLog.created_at >= now-timedelta(days=8)).order_by(ActuatorLog.created_at.desc()).all()
    serialized = []
    for item in rows:
        rule = policy(item)
        data = serialize_actuator(item, db, now)
        data["daily_statistics"] = daily_statistics([l for l in logs if l.actuator_id == item.actuator_id],
            ZoneInfo(rule.timezone if rule else "Asia/Ho_Chi_Minh"), now)
        data["weather"] = forecast(rule.latitude, rule.longitude, rule.timezone) if rule else {"available": False, "reason": "Chưa cấu hình tọa độ vườn"}
        serialized.append(data)
    db.commit()
    return {"greenhouse_id": greenhouse_id, "actuators": serialized,
            "recent_logs": [serialize_actuator_log(l) for l in logs[:30]]}


def binding_problem(db, item, rule):
    if not rule or not rule.hardware_verified:
        return "Cần cấu hình và xác nhận hiệu chuẩn cảm biến, bộ ngắt bơm trên board"
    for ident, sensor in [(rule.sensor_device_id, True), (item.device_id, False)]:
        dev = db.query(Device).filter(Device.device_id == ident, Device.greenhouse_id == item.greenhouse_id,
                                     Device.deleted_at.is_(None), Device.status == "ACTIVE").first()
        if not dev or dev.area_id != item.area_id or (sensor and dev.device_type != "SENSOR_NODE") or (not sensor and dev.device_type not in {"ACTUATOR", "PUMP", "SENSOR_NODE"}):
            return "Cảm biến và bơm phải hoạt động, thuộc đúng vườn và cùng khu vực đã chọn"
    return None


def start_problem(db, item, rule, now):
    problem = binding_problem(db, item, rule)
    if problem:
        return problem
    if rule.locked:
        return "Đang khóa tưới"
    readings = db.query(SensorLog).filter(SensorLog.device_id == rule.sensor_device_id).order_by(SensorLog.timestamp.desc()).limit(120).all()
    if not readings:
        return "Chưa có số đo đất"
    problems = quality_problems(readings[0], readings[1:], now=now, max_age=rule.max_sensor_age_seconds)
    if problems:
        return "; ".join(problems)
    latest = readings[0]
    if latest.soil_moisture >= rule.stop_at_pct:
        return "Độ ẩm đất đã đạt ngưỡng dừng"
    if rule.max_temperature_c is not None and latest.temperature > rule.max_temperature_c:
        return "Ngoài giới hạn nhiệt độ đã cấu hình"
    if rule.max_light_lux is not None and latest.light_level > rule.max_light_lux:
        return "Ngoài giới hạn ánh sáng đã cấu hình"
    clock = now.astimezone(ZoneInfo(rule.timezone)).strftime("%H:%M")
    if rule.allowed_start:
        inside = rule.allowed_start <= clock < rule.allowed_end if rule.allowed_start < rule.allowed_end else clock >= rule.allowed_start or clock < rule.allowed_end
        if not inside:
            return "Ngoài khung giờ tưới"
    if not item.is_on:
        last = latest_start(db, item)
        if last and (now-utc(last.created_at)).total_seconds() < rule.max_run_seconds + rule.cooldown_seconds:
            return "Chưa hết khoảng nghỉ giữa hai lần tưới"
        if runtime_used(db, item, now) + rule.max_run_seconds > rule.max_daily_seconds:
            return "Đã đạt ngân sách thời gian tưới trong 24 giờ"
    return None


def send_command(db, item, turn_on, source, reason, user_id=None, duration=None):
    now = datetime.now(timezone.utc)
    rule = policy(item)
    command_id = str(uuid.uuid4())
    token = os.getenv("DEVICE_INGEST_TOKEN", "")
    seconds = min(duration or (rule.max_run_seconds if rule else 30), 120)
    payload = dict(command_id=command_id, device_id=item.device_id, greenhouse_id=item.greenhouse_id,
        command_token=token, actuator_type="PUMP", control_mode=item.control_mode, is_on=turn_on,
        issued_at=int(now.timestamp()), expires_at=int(now.timestamp())+10, run_seconds=seconds)
    result = publish_mqtt_json(control_topic(item.greenhouse_id), payload) if token and item.device_id else {"published": False, "error": "Thiếu token hoặc thiết bị bơm"}
    db.add(ActuatorLog(log_id=command_id, actuator_id=item.actuator_id, user_id=user_id,
        action="TURN_ON" if turn_on else "TURN_OFF", trigger_source=source, reason=reason,
        ack_status="PENDING" if result["published"] else "FAILED", created_at=now, duration_seconds=seconds if turn_on else 0))
    if result["published"]:
        item.is_on = turn_on
        item.last_changed_by = "USER" if source == "MANUAL" else "AUTO_RULE"
        item.updated_at = now
    db.flush()
    return result


def update_actuator_control(db: Session, greenhouse: Greenhouse, actuator_type: str,
                            body: ActuatorUpdateInput, current_user: User):
    if actuator_type.upper() != "PUMP":
        raise HTTPException(422, "Chỉ hỗ trợ PUMP")
    rows = ensure_default_actuators(db, greenhouse.greenhouse_id)
    target = next((r for r in rows if r.area_id == body.area_id), None)
    if target is None:
        from ..models import GreenhouseArea
        if not db.query(GreenhouseArea).filter_by(area_id=body.area_id, greenhouse_id=greenhouse.greenhouse_id).first():
            raise HTTPException(422, "Khu vực không thuộc vườn")
        target = ActuatorState(actuator_id="act-"+uuid.uuid4().hex[:12], greenhouse_id=greenhouse.greenhouse_id,
            area_id=body.area_id, actuator_type="PUMP", control_mode="MANUAL", is_on=False,
            auto_rules={}, last_changed_by="USER", updated_at=datetime.now(timezone.utc))
        db.add(target)
        db.flush()
    target = db.query(ActuatorState).filter_by(actuator_id=target.actuator_id).with_for_update().one()
    mode = body.control_mode.upper() if body.control_mode else target.control_mode
    if mode not in {"AUTO", "MANUAL"}:
        raise HTTPException(422, "Chế độ phải là AUTO hoặc MANUAL")
    # STOP always allowed, even in AUTO or with invalid/missing sensor readings.
    if body.is_on is False:
        target.control_mode = "MANUAL"
        result = send_command(db, target, False, "MANUAL", body.reason or "Yêu cầu dừng", current_user.user_id)
        db.commit()
        return {"actuator": serialize_actuator(target, db), "mqtt": result}
    if target.is_on and (body.auto_rules is not None or body.device_id is not None or mode != target.control_mode):
        raise HTTPException(409, "Dừng bơm trước khi đổi cấu hình")
    if body.auto_rules is not None:
        target.auto_rules = body.auto_rules.model_dump()
    if body.device_id is not None:
        target.device_id = body.device_id
        shared = db.query(ActuatorState).filter(ActuatorState.device_id == target.device_id,
            ActuatorState.actuator_id != target.actuator_id).first()
        if shared:
            raise HTTPException(409, "Board bơm đã gắn với khu vực khác")
    rule = policy(target)
    if mode == "AUTO" or body.is_on:
        problem = binding_problem(db, target, rule)
        if problem:
            raise HTTPException(422, problem)
    if body.is_on and mode != "MANUAL":
        raise HTTPException(409, "Chọn Thủ công để bật bằng tay")
    target.control_mode = mode
    result = {"published": False, "error": None}
    if body.is_on and not target.is_on:
        problem = start_problem(db, target, rule, datetime.now(timezone.utc))
        if problem:
            raise HTTPException(409, problem)
        result = send_command(db, target, True, "MANUAL", body.reason or "Tưới thủ công có thời hạn", current_user.user_id)
    target.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"actuator": serialize_actuator(target, db), "mqtt": result}


def evaluate_auto_actuators(db, device, sensor_log, thresholds=None):
    now = datetime.now(timezone.utc)
    changes = []
    rows = db.query(ActuatorState).filter_by(greenhouse_id=device.greenhouse_id, control_mode="AUTO").with_for_update().all()
    for item in rows:
        rule = policy(item)
        if not rule or rule.sensor_device_id != device.device_id:
            continue
        problem = start_problem(db, item, rule, now)
        if item.is_on and problem:
            changes.append(send_command(db, item, False, "AUTO_RULE", problem))
        elif not item.is_on and not problem and sensor_log.soil_moisture < rule.start_below_pct:
            weather = forecast(rule.latitude, rule.longitude, rule.timezone)
            factor, reason = weather_adjustment(rule, weather, now)
            # max_run_seconds is a hard cap; baseline is chosen below it to allow morning increase.
            duration = min(rule.max_run_seconds, max(1, round(rule.base_run_seconds * factor)))
            changes.append(send_command(db, item, True, "AUTO_RULE", reason, duration=duration))
    return changes


def enforce_timeouts(db, now=None):
    now = now or datetime.now(timezone.utc)
    rows = db.query(ActuatorState).filter_by(is_on=True).with_for_update().all()
    for item in rows:
        rule = policy(item)
        start = latest_start(db, item)
        overdue = not start or (now-utc(start.created_at)).total_seconds() >= (start.duration_seconds or 120)
        problem = start_problem(db, item, rule, now)
        if overdue or problem:
            send_command(db, item, False, "AUTO_RULE", "Hết thời hạn tưới" if overdue else problem)
    db.commit()
