"""Create a demo farmer, or populate every project table for that account."""

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import math
import os
from pathlib import Path
import uuid
from urllib.parse import quote

from sqlalchemy import DateTime, MetaData, func, inspect, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.auth import get_token_secret, hash_password, normalize_email
from app.database import SessionLocal, engine
from app.models import User


ROOT = Path(__file__).resolve().parents[1]
DEMO_TABLES = (
    "users", "crops", "greenhouses", "greenhouse_areas", "devices",
    "sensor_logs", "recommendations", "camera_logs", "notifications",
)


def demo_rows(user: dict, prefix: str, anchor: datetime) -> dict[str, list[dict]]:
    """Build explicit fixtures; no model, MQTT or notification service is called."""
    rows = {name: [] for name in DEMO_TABLES}
    rows["users"] = [{
        **user,
        "phone_number": user["phone_number"] or "0000000000",
        "fcm_token": user["fcm_token"] or "DEMO_NOT_A_REAL_FCM_TOKEN",
    }]
    stages = ("1_Cay_con_DEMO", "2_Phat_trien_than_la_DEMO", "3_Truong_thanh_DEMO")
    crop_names = ("Ớt", "Xà lách", "Cà chua")
    images = sorted((ROOT / "data/chili_plant_disease/test").rglob("*.jpg"))
    if len(images) < 18:
        raise ValueError("Cần ít nhất 18 ảnh trong dataset ớt hiện có để tạo metadata camera.")

    for crop_index, crop_name in enumerate(crop_names, 1):
        for stage_index, stage in enumerate(stages, 1):
            rows["crops"].append({
                "crop_stage_id": f"{prefix}-crop-{crop_index}-{stage_index}",
                "crop_name": f"[DEMO] {crop_name}", "growth_stage": stage,
                # Synthetic UI reference values, not validated agronomic targets.
                "min_temp": 18.0 + stage_index, "max_temp": 30.0 + stage_index,
                "min_humidity": 45.0, "max_humidity": 80.0,
                "min_soil_moisture": 35.0 + stage_index,
                "optimum_ph": 6.2, "target_n": 80.0 + 10 * stage_index,
                "target_p": 40.0 + 5 * stage_index, "target_k": 100.0 + 10 * stage_index,
            })

        greenhouse_id = f"{prefix}-gh-{crop_index}"
        area_sqm = (120.0, 90.0, 150.0)[crop_index - 1]
        rows["greenhouses"].append({
            "greenhouse_id": greenhouse_id, "user_id": user["user_id"],
            "crop_stage_id": f"{prefix}-crop-{crop_index}-2",
            "name": f"[DEMO] Nhà kính {crop_name.lower()}",
            "area_sqm": area_sqm,
            "location": f"Khu mô phỏng {crop_index} — dữ liệu ảo, không phải địa điểm thật",
            "created_at": anchor - timedelta(days=60),
        })
        for bed_index in (1, 2):
            number = (crop_index - 1) * 2 + bed_index
            area_id = f"{prefix}-area-{number:02d}"
            sensor_id = f"{prefix}-device-{number:02d}-sensor"
            camera_id = f"{prefix}-device-{number + 6:02d}-camera"
            rows["greenhouse_areas"].append({
                "area_id": area_id, "greenhouse_id": greenhouse_id,
                "crop_stage_id": f"{prefix}-crop-{crop_index}-{bed_index + 1}",
                "name": f"[DEMO] Luống {bed_index} — {crop_name.lower()}",
                "area_sqm": area_sqm / 2,
                "created_at": anchor - timedelta(days=14),
                "updated_at": anchor - timedelta(days=1),
            })
            last_measurement = anchor - timedelta(hours=6 if number == 6 else 0)
            for device_id, kind in ((sensor_id, "SENSOR_NODE"), (camera_id, "CAMERA")):
                rows["devices"].append({
                    "device_id": device_id, "greenhouse_id": greenhouse_id,
                    "area_id": area_id, "device_type": kind,
                    "is_online": number != 6,
                    "battery_level": 18 if number == 6 else 96 - number * 5,
                    "send_interval": 1800 if kind == "SENSOR_NODE" else 43200,
                    "last_updated": last_measurement if kind == "SENSOR_NODE" else anchor - timedelta(hours=2),
                    "status": "INACTIVE" if number == 6 and kind == "CAMERA" else "ACTIVE",
                })

            # Seven days, one measurement every 30 minutes, for each sensor.
            for sample in range(336):
                measured_at = last_measurement - timedelta(minutes=30 * (335 - sample))
                wave = math.sin(2 * math.pi * sample / 48 + number / 3)
                readings = {
                    "temperature": round(26 + 3.5 * wave + number * 0.2, 2),
                    "humidity": round(65 - 9 * wave, 2),
                    "soil_moisture": round(58 + 6 * math.sin(sample / 15 + number), 2),
                    "soil_ph": round(6.2 + 0.25 * math.sin(sample / 20), 2),
                    "n": round(105 + 12 * wave, 2),
                    "p": round(52 + 6 * math.cos(sample / 18), 2),
                    "k": round(135 + 15 * math.sin(sample / 22), 2),
                }
                if sample >= 330:
                    if number == 2:
                        readings["soil_moisture"] = 88.0
                    elif number == 3:
                        readings["soil_ph"] = 4.8
                    elif number == 4:
                        readings["n"] = 42.0
                    elif number == 5:
                        readings["temperature"] = 35.5
                rows["sensor_logs"].append({
                    "log_id": f"{prefix}-sensor-{number:02d}-{sample:04d}",
                    "device_id": sensor_id, "timestamp": measured_at, **readings,
                })

            camera_times = []
            for shot in range(3):
                captured_at = anchor - timedelta(days=2 - shot, hours=2)
                camera_times.append(captured_at)
                relative_image = images[(number - 1) * 3 + shot].relative_to(ROOT).as_posix()
                rows["camera_logs"].append({
                    "log_id": f"{prefix}-camera-{number:02d}-{shot}",
                    "device_id": camera_id, "greenhouse_id": greenhouse_id,
                    "area_id": area_id, "image_url": quote(relative_image, safe="/"),
                    "timestamp": captured_at,
                    "ai_diagnosis": "[DEMO] Ảnh tham chiếu dataset ớt; chưa chạy model AI",
                    "confidence_score": 0.0, "status": "NEW",
                })

            scenario = (
                "Số đo môi trường mô phỏng ổn định", "Độ ẩm đất mô phỏng cao",
                "pH mô phỏng thấp", "Chỉ số Nitơ mô phỏng thấp",
                "Nhiệt độ mô phỏng cao", "Thiết bị mô phỏng mất kết nối",
            )[number - 1]
            for event in range(6):
                rec_id = f"{prefix}-rec-{number:02d}-{event}"
                created_at = anchor - timedelta(days=5 - event, hours=3)
                rec_status = ("APPLIED", "IGNORED", "PENDING")[event % 3]
                rows["recommendations"].append({
                    "rec_id": rec_id, "device_id": sensor_id, "area_id": area_id,
                    "created_at": created_at, "condition_diagnosis": f"[DEMO] {scenario}",
                    "fertilizer_action": "[DEMO] Kiểm tra cảm biến và lấy mẫu xác nhận trước khi cân nhắc bón phân",
                    "dosage": 0.0,
                    "action_note": (
                        f"Dữ liệu giả để demo trạng thái {rec_status}; không phải kết quả AI hay hướng dẫn bón thật. "
                        f"Diện tích luống {area_sqm / 2:g} m². dosage dùng đơn vị g/m²; "
                        "0 nghĩa là chưa chỉ định liều lượng. Tổng lượng minh hoạ: 0 g."
                    ),
                    "status": rec_status,
                })
                notified_at = max(created_at, camera_times[event % 3]) + timedelta(minutes=1)
                rows["notifications"].append({
                    "notification_id": f"{prefix}-notice-{number:02d}-{event}",
                    "user_id": user["user_id"], "greenhouse_id": greenhouse_id,
                    "area_id": area_id, "device_id": sensor_id,
                    "recommendation_id": rec_id,
                    "camera_log_id": f"{prefix}-camera-{number:02d}-{event % 3}",
                    "category": "DEMO_ENVIRONMENT",
                    "severity": ("INFO", "WARNING", "CRITICAL")[event % 3],
                    "title": f"[DEMO] {scenario}",
                    "message": "Thông báo giả, liên kết ảnh tham chiếu và khuyến nghị mẫu; chưa gửi FCM.",
                    # These fixtures are read/resolved so read_at is meaningful and filled.
                    "status": "READ" if event % 2 == 0 else "RESOLVED",
                    "created_at": notified_at, "read_at": notified_at + timedelta(minutes=2),
                })
    return rows


def seed_demo_data(email: str, dry_run: bool = False) -> dict:
    with engine.connect() as connection, connection.begin() as transaction:
        connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext(:scope))"), {"scope": "greenhouse-demo:" + email})
        actual_tables = set(inspect(connection).get_table_names(schema="public"))
        if actual_tables != set(DEMO_TABLES):
            raise ValueError("Schema đã thay đổi; cần đối chiếu lại các bảng trước khi tạo dữ liệu demo.")
        metadata = MetaData(schema="public")
        metadata.reflect(bind=connection, only=DEMO_TABLES)
        tables = {name: metadata.tables[f"public.{name}"] for name in DEMO_TABLES}
        users = tables["users"]
        user = connection.execute(
            select(users).where(func.lower(func.btrim(users.c.email)) == email).with_for_update()
        ).mappings().one_or_none()
        if user is None or not user["password_hash"]:
            raise ValueError("Cần tạo tài khoản demo có mật khẩu trước khi bổ sung dữ liệu.")
        if user["role"] != "FARMER":
            raise ValueError("Bộ dữ liệu này yêu cầu tài khoản demo FARMER.")
        user = dict(user)
        prefix = "demo-" + hashlib.sha256(user["user_id"].encode()).hexdigest()[:10]
        first_house = tables["greenhouses"]
        stored_anchor = connection.execute(
            select(first_house.c.created_at).where(first_house.c.greenhouse_id == f"{prefix}-gh-1")
        ).scalar_one_or_none()
        if stored_anchor is None:
            anchor = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            anchor = anchor.replace(minute=anchor.minute // 30 * 30)
        else:
            anchor = stored_anchor.replace(tzinfo=timezone.utc) if stored_anchor.tzinfo is None else stored_anchor.astimezone(timezone.utc)
            anchor += timedelta(days=60)
        rows = demo_rows(user, prefix, anchor)
        result = {}
        for name in DEMO_TABLES:
            table = tables[name]
            keys = set(table.c.keys())
            pk = list(table.primary_key.columns)[0]
            for row in rows[name]:
                if set(row) != keys or any(value is None for value in row.values()):
                    raise ValueError(f"Dữ liệu demo chưa phủ đủ mọi cột của bảng {name}.")
                for column in table.columns:
                    value = row[column.name]
                    if isinstance(value, str) and getattr(column.type, "length", None) and len(value) > column.type.length:
                        raise ValueError(f"Giá trị demo vượt độ dài cột {name}.{column.name}.")
                    if isinstance(column.type, DateTime):
                        row[column.name] = value.astimezone(timezone.utc)
                        if not column.type.timezone:
                            row[column.name] = row[column.name].replace(tzinfo=None)
            identifiers = [row[pk.name] for row in rows[name]]
            existing = {
                item[pk.name]: item for item in connection.execute(
                    select(table).where(pk.in_(identifiers))
                ).mappings()
            }
            if name == "users":
                changes = {key: rows[name][0][key] for key in ("phone_number", "fcm_token") if not user[key]}
                if changes:
                    connection.execute(users.update().where(users.c.user_id == user["user_id"]).values(**changes))
            else:
                # Never attach fixtures to records with conflicting ownership/relationships.
                fk_columns = {fk.parent.name for fk in table.foreign_keys}
                for row in rows[name]:
                    previous = existing.get(row[pk.name])
                    if previous is not None and any(previous[key] != row[key] for key in fk_columns):
                        raise ValueError(f"ID demo đã có liên kết khác trong bảng {name}; hủy để giữ dữ liệu.")
                statement = insert(table).on_conflict_do_nothing(index_elements=[pk.name])
                connection.execute(statement, rows[name])
            count = connection.execute(select(func.count()).select_from(table).where(pk.in_(identifiers))).scalar_one()
            incomplete = connection.execute(select(func.count()).select_from(table).where(
                pk.in_(identifiers), or_(*(column.is_(None) for column in table.columns))
            )).scalar_one()
            if count != len(rows[name]) or incomplete:
                raise ValueError(f"Dữ liệu demo chưa đủ hoặc còn ô NULL trong bảng {name}.")
            result[name] = {"total_demo_rows": count, "inserted": count - len(existing), "null_rows": incomplete}
        if dry_run:
            transaction.rollback()
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-data", action="store_true", help="Tạo dữ liệu mọi bảng cho tài khoản demo đã có.")
    parser.add_argument("--dry-run", action="store_true", help="Kiểm tra --with-data trong transaction rồi rollback.")
    args = parser.parse_args()
    if args.dry_run and not args.with_data:
        parser.error("--dry-run requires --with-data")
    if os.getenv("DEMO_MODE", "false").strip().lower() != "true":
        print("Set DEMO_MODE=true in the local .env before seeding a demo account.")
        return 2

    try:
        get_token_secret()
    except Exception as exc:
        print(f"Authentication configuration is not ready ({type(exc).__name__}).")
        return 2

    raw_email = os.getenv("DEMO_USER_EMAIL", "demo@smartgreenhouse.local")
    try:
        email = normalize_email(raw_email)
    except ValueError:
        print("DEMO_USER_EMAIL is not a valid email address.")
        return 2

    if args.with_data:
        try:
            result = seed_demo_data(email, args.dry_run)
        except ValueError as exc:
            print(str(exc))
            return 2
        except SQLAlchemyError as exc:
            print(f"Demo seed rolled back ({type(exc).__name__}); no connection strings or SQL parameters are logged.")
            return 2
        print("DEMO DATA VALIDATED AND ROLLED BACK" if args.dry_run else "DEMO DATA SAVED")
        for table, counts in result.items():
            print(f"{table}: total={counts['total_demo_rows']}, inserted={counts['inserted']}, null_rows={counts['null_rows']}")
        return 0

    password = getpass.getpass("New demo account password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm demo account password: ")
    if len(password) < 12 or len(password) > 128:
        print("Password must contain between 12 and 128 characters.")
        return 2
    if password != confirmation:
        print("Passwords do not match.")
        return 2

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        schema = inspect(engine)
        if not schema.has_table("users"):
            print("Database table users is missing; create the project schema first.")
            return 2
        user_columns = {column["name"] for column in schema.get_columns("users")}
        if "password_hash" not in user_columns:
            print("Apply the authentication/ownership SQL migration before seeding.")
            return 2
    except SQLAlchemyError:
        print("Cannot connect to the configured database; check DATABASE_URL in .env.")
        return 2

    with SessionLocal() as db:
        existing = (
            db.query(User)
            .filter(func.lower(func.trim(User.email)) == email)
            .first()
        )
        if existing is not None:
            print("That email already belongs to an account; no data was changed.")
            return 2

        db.add(
            User(
                user_id=str(uuid.uuid4()),
                full_name="Demo Farmer",
                email=email,
                password_hash=hash_password(password),
                role="FARMER",
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print("That email is already registered; no existing account was changed.")
            return 2

    print(f"Created demo FARMER account: {email}")
    print("Use the password entered above to sign in via POST /api/auth/login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
