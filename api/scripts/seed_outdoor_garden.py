"""Idempotent seed for the Outdoor Garden (Chili & Lettuce) 11-table schema.

Populates:
- Demo farmer account (demo@smartgreenhouse.local / Demo@12345678, preserved if existing)
- Standard outdoor crop presets for Cây ớt and Cây xà lách
- 1 outdoor garden with 2 planting areas (Chili & Lettuce)
- NodeMCU v2.0.0, ESP32-CAM, and Pump actuator devices
- 48 hours of DHT22 + LDR light sensor logs (including a recent fungal-risk window)
- Pump actuator_states + actuator_logs
- Sample multimodal camera_logs, recommendations, and notifications
"""

from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import engine
from app.models import (
    ActuatorLog,
    ActuatorState,
    CameraLog,
    Crop,
    Device,
    Greenhouse,
    GreenhouseArea,
    Notification,
    Recommendation,
    SensorLog,
    User,
)


ROOT = Path(__file__).resolve().parents[1]

DEMO_USER_ID = "demo-farmer-0001"
DEMO_USER_EMAIL = "demo@smartgreenhouse.local"
# Matches api/data/demo_user_seed.sql (Demo@12345678, PBKDF2-HMAC-SHA256)
DEMO_PASSWORD_HASH = (
    "pbkdf2_sha256$600000$Xatb6i_fd2ZIRiTevi0WFw$"
    "B_RaPZ2VHdeEnvJIAeSdtYdZXRu_puJeQ9EDBh90f2E"
)


def _find_sample_image(subfolder: str) -> str:
    base = ROOT / "data" / "chili_plant_disease" / "test" / subfolder
    candidates = sorted(base.glob("*.jpg"))
    if candidates:
        return quote(candidates[0].relative_to(ROOT).as_posix(), safe="/")
    fallback = sorted((ROOT / "data" / "chili_plant_disease" / "test").rglob("*.jpg"))
    if fallback:
        return quote(fallback[0].relative_to(ROOT).as_posix(), safe="/")
    return "data/chili_plant_disease/test/healthy/sample.jpg"


def seed_outdoor_garden() -> dict[str, int]:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    anchor = now.replace(minute=(now.minute // 30) * 30)

    crops_data = [
        {
            "crop_stage_id": "crop-chili-seedling",
            "crop_name": "Cây ớt",
            "growth_stage": "SEEDLING",
            "environment_type": "OUTDOOR",
            "min_temp": 22.0,
            "max_temp": 30.0,
            "min_humidity": 60.0,
            "max_humidity": 80.0,
            "min_light": 12000.0,
            "max_light": 35000.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 8000.0,
            "fungal_duration_minutes": 60,
        },
        {
            "crop_stage_id": "crop-chili-vegetative",
            "crop_name": "Cây ớt",
            "growth_stage": "VEGETATIVE",
            "environment_type": "OUTDOOR",
            "min_temp": 22.0,
            "max_temp": 33.0,
            "min_humidity": 55.0,
            "max_humidity": 80.0,
            "min_light": 18000.0,
            "max_light": 55000.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 10000.0,
            "fungal_duration_minutes": 60,
        },
        {
            "crop_stage_id": "crop-chili-fruiting",
            "crop_name": "Cây ớt",
            "growth_stage": "FRUITING",
            "environment_type": "OUTDOOR",
            "min_temp": 20.0,
            "max_temp": 32.0,
            "min_humidity": 50.0,
            "max_humidity": 75.0,
            "min_light": 20000.0,
            "max_light": 60000.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 10000.0,
            "fungal_duration_minutes": 60,
        },
        {
            "crop_stage_id": "crop-lettuce-seedling",
            "crop_name": "Cây xà lách",
            "growth_stage": "SEEDLING",
            "environment_type": "OUTDOOR",
            "min_temp": 16.0,
            "max_temp": 25.0,
            "min_humidity": 60.0,
            "max_humidity": 80.0,
            "min_light": 8000.0,
            "max_light": 25000.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 6000.0,
            "fungal_duration_minutes": 45,
        },
        {
            "crop_stage_id": "crop-lettuce-vegetative",
            "crop_name": "Cây xà lách",
            "growth_stage": "VEGETATIVE",
            "environment_type": "OUTDOOR",
            "min_temp": 15.0,
            "max_temp": 26.0,
            "min_humidity": 55.0,
            "max_humidity": 80.0,
            "min_light": 10000.0,
            "max_light": 32000.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 6000.0,
            "fungal_duration_minutes": 45,
        },
        {
            "crop_stage_id": "crop-lettuce-harvest",
            "crop_name": "Cây xà lách",
            "growth_stage": "HARVEST",
            "environment_type": "OUTDOOR",
            "min_temp": 15.0,
            "max_temp": 24.0,
            "min_humidity": 55.0,
            "max_humidity": 78.0,
            "min_light": 10000.0,
            "max_light": 30000.0,
            "fungal_humidity_threshold": 85.0,
            "fungal_light_threshold": 6000.0,
            "fungal_duration_minutes": 45,
        },
    ]

    garden_id = "garden-outdoor-01"
    chili_area_id = "area-chili-01"
    lettuce_area_id = "area-lettuce-01"

    devices_data = [
        {
            "device_id": "NODEMCU-CHILI-01",
            "greenhouse_id": garden_id,
            "area_id": chili_area_id,
            "device_type": "SENSOR_NODE",
            "hardware_model": "NodeMCU v2.0.0 (DHT22 + Quang trở LDR)",
            "is_online": True,
            "battery_level": 92,
            "send_interval": 30,
            "last_updated": anchor,
            "status": "ACTIVE",
        },
        {
            "device_id": "NODEMCU-LETTUCE-01",
            "greenhouse_id": garden_id,
            "area_id": lettuce_area_id,
            "device_type": "SENSOR_NODE",
            "hardware_model": "NodeMCU v2.0.0 (DHT22 + Quang trở LDR)",
            "is_online": True,
            "battery_level": 88,
            "send_interval": 30,
            "last_updated": anchor,
            "status": "ACTIVE",
        },
        {
            "device_id": "ESP32CAM-CHILI-01",
            "greenhouse_id": garden_id,
            "area_id": chili_area_id,
            "device_type": "CAMERA_NODE",
            "hardware_model": "ESP32-CAM AI-Thinker",
            "is_online": True,
            "battery_level": 85,
            "send_interval": 1800,
            "last_updated": anchor - timedelta(minutes=15),
            "status": "ACTIVE",
        },
        {
            "device_id": "ESP32CAM-LETTUCE-01",
            "greenhouse_id": garden_id,
            "area_id": lettuce_area_id,
            "device_type": "CAMERA_NODE",
            "hardware_model": "ESP32-CAM AI-Thinker",
            "is_online": True,
            "battery_level": 90,
            "send_interval": 1800,
            "last_updated": anchor - timedelta(minutes=20),
            "status": "ACTIVE",
        },
        {
            "device_id": "ACTUATOR-PUMP-01",
            "greenhouse_id": garden_id,
            "area_id": None,
            "device_type": "ACTUATOR",
            "hardware_model": "Relay Bơm nước tưới ngoài trời",
            "is_online": True,
            "battery_level": 100,
            "send_interval": 60,
            "last_updated": anchor,
            "status": "ACTIVE",
        },
    ]

    sensor_rows = []
    # 48 hours at 30-minute intervals = 96 readings per sensor node
    for idx in range(96):
        ts = anchor - timedelta(minutes=30 * (95 - idx))
        local_hour = (ts.hour + 7) % 24
        daylight = max(0.0, math.sin((local_hour - 6) * math.pi / 12)) if 6 <= local_hour <= 18 else 0.0

        # Chili node: last 4 samples simulate prolonged high humidity (>85%) + low light (fungal risk)
        if idx >= 92:
            chili_temp = round(25.2 + (idx - 92) * 0.1, 1)
            chili_hum = round(87.5 + (idx - 92) * 0.8, 1)
            chili_light = round(4200.0 - (idx - 92) * 300.0, 1)
        else:
            chili_temp = round(26.5 + 4.5 * daylight + 0.5 * math.sin(idx / 5), 1)
            chili_hum = round(76.0 - 16.0 * daylight + 2.0 * math.cos(idx / 4), 1)
            chili_light = round(1200.0 + 36000.0 * daylight, 1)

        sensor_rows.append({
            "log_id": f"seed-chili-log-{idx:03d}",
            "device_id": "NODEMCU-CHILI-01",
            "timestamp": ts,
            "temperature": chili_temp,
            "humidity": chili_hum,
            "light_level": chili_light,
        })

        # Lettuce node: healthy outdoor conditions
        lettuce_temp = round(21.5 + 3.8 * daylight + 0.4 * math.cos(idx / 6), 1)
        lettuce_hum = round(70.0 - 10.0 * daylight + 1.5 * math.sin(idx / 5), 1)
        lettuce_light = round(1000.0 + 24000.0 * daylight, 1)
        sensor_rows.append({
            "log_id": f"seed-lettuce-log-{idx:03d}",
            "device_id": "NODEMCU-LETTUCE-01",
            "timestamp": ts,
            "temperature": lettuce_temp,
            "humidity": lettuce_hum,
            "light_level": lettuce_light,
        })

    spot_image = _find_sample_image("unhealthy/leaf spot")
    healthy_image = _find_sample_image("healthy")

    camera_rows = [
        {
            "log_id": "seed-cam-chili-01",
            "device_id": "ESP32CAM-CHILI-01",
            "greenhouse_id": garden_id,
            "area_id": chili_area_id,
            "sensor_log_id": "seed-chili-log-095",
            "image_url": spot_image,
            "timestamp": anchor - timedelta(minutes=10),
            "trigger_type": "ENV_ALERT",
            "cnn_diagnosis": "leaf spot",
            "cnn_confidence": 0.81,
            "cnn_scores": {
                "leaf spot": 0.81,
                "yellowish": 0.11,
                "leaf curl": 0.04,
                "whitefly": 0.02,
                "healthy": 0.02,
            },
            "ai_diagnosis": "Nấm đốm lá (Leaf Spot)",
            "confidence_score": 0.93,
            "multimodal_reason": (
                "Ảnh ESP32-cam phát hiện dấu hiệu nấm đốm lá (CNN 81%). Đối chiếu DHT22 cho thấy "
                "độ ẩm không khí đạt 89.9% (>85% kéo dài 90 phút) kèm ánh sáng yếu (3,300 Lux) "
                "→ tăng độ tin cậy chẩn đoán nấm bệnh lên 93%."
            ),
            "recommended_action": (
                "Cắt tỉa lá bị đốm nặng trên Cây ớt, tạm ngưng bơm tưới nước vào chiều tối "
                "để giảm độ ẩm bề mặt lá và theo dõi lại sau 24 giờ."
            ),
            "temperature_at_capture": 25.5,
            "humidity_at_capture": 89.9,
            "light_at_capture": 3300.0,
            "env_window_summary": {
                "window_minutes": 90,
                "avg_humidity": 88.7,
                "avg_light": 3750.0,
                "high_humidity_minutes": 90,
                "low_light_detected": True,
            },
            "model_version": "chili_cnn_v1+multimodal_v1",
            "status": "NEW",
        },
        {
            "log_id": "seed-cam-lettuce-01",
            "device_id": "ESP32CAM-LETTUCE-01",
            "greenhouse_id": garden_id,
            "area_id": lettuce_area_id,
            "sensor_log_id": "seed-lettuce-log-095",
            "image_url": healthy_image,
            "timestamp": anchor - timedelta(minutes=25),
            "trigger_type": "SCHEDULED",
            "cnn_diagnosis": "healthy",
            "cnn_confidence": 0.94,
            "cnn_scores": {
                "healthy": 0.94,
                "yellowish": 0.03,
                "leaf spot": 0.02,
                "leaf curl": 0.01,
            },
            "ai_diagnosis": "Khỏe mạnh",
            "confidence_score": 0.96,
            "multimodal_reason": (
                "Ảnh ESP32-cam cho thấy lá xanh đều (CNN 94%). Thông số DHT22 và ánh sáng tại "
                "khu Cây xà lách đang nằm trong ngưỡng tối ưu ngoài trời."
            ),
            "recommended_action": "Tiếp tục duy trì chế độ tưới và theo dõi định kỳ.",
            "temperature_at_capture": 23.2,
            "humidity_at_capture": 65.4,
            "light_at_capture": 18500.0,
            "env_window_summary": {
                "window_minutes": 60,
                "avg_humidity": 66.1,
                "avg_light": 17800.0,
                "high_humidity_minutes": 0,
                "low_light_detected": False,
            },
            "model_version": "chili_cnn_v1+multimodal_v1",
            "status": "REVIEWED",
        },
    ]

    actuator_states_data = [
        {
            "actuator_id": "act-garden01-pump",
            "greenhouse_id": garden_id,
            "area_id": None,
            "device_id": "ACTUATOR-PUMP-01",
            "actuator_type": "PUMP",
            "control_mode": "AUTO",
            "is_on": False,
            "auto_rules": {
                "turn_on_temp_above": 33.0,
                "turn_on_humidity_below": 50.0,
                "turn_off_humidity_above": 75.0,
            },
            "last_changed_by": "AUTO_RULE",
            "updated_at": anchor - timedelta(minutes=15),
        },
    ]

    actuator_logs_data = [
        {
            "log_id": "seed-actlog-01",
            "actuator_id": "act-garden01-pump",
            "user_id": None,
            "action": "TURN_OFF",
            "trigger_source": "AUTO_RULE",
            "reason": "Độ ẩm khu Cây ớt vượt 85% kéo dài — giữ Bơm nước ở trạng thái tắt để hạn chế nấm bệnh.",
            "ack_status": "ACK",
            "created_at": anchor - timedelta(minutes=12),
        },
        {
            "log_id": "seed-actlog-02",
            "actuator_id": "act-garden01-pump",
            "user_id": DEMO_USER_ID,
            "action": "TURN_OFF",
            "trigger_source": "MANUAL",
            "reason": "Tắt bơm nước thủ công sau khi hoàn tất tưới buổi sáng.",
            "ack_status": "ACK",
            "created_at": anchor - timedelta(hours=3),
        },
    ]

    recommendations_data = [
        {
            "rec_id": "seed-rec-chili-01",
            "device_id": "NODEMCU-CHILI-01",
            "area_id": chili_area_id,
            "camera_log_id": "seed-cam-chili-01",
            "source_type": "MULTIMODAL",
            "created_at": anchor - timedelta(minutes=9),
            "condition_diagnosis": "Nấm đốm lá (Leaf Spot) — Xác nhận đa phương thức 93%",
            "fertilizer_action": "Tỉa lá bệnh, tạm ngưng bơm tưới nước và giữ tán lá thoáng ráo tự nhiên.",
            "dosage": 0.0,
            "action_note": "Độ ẩm không khí > 85% kéo dài kết hợp ánh sáng yếu tại khu Cây ớt ngoài trời.",
            "status": "PENDING",
        }
    ]

    notifications_data = [
        {
            "notification_id": "seed-notif-01",
            "user_id": DEMO_USER_ID,
            "greenhouse_id": garden_id,
            "area_id": chili_area_id,
            "device_id": "ESP32CAM-CHILI-01",
            "recommendation_id": "seed-rec-chili-01",
            "camera_log_id": "seed-cam-chili-01",
            "category": "DISEASE_ALERT",
            "severity": "CRITICAL",
            "title": "Cảnh báo Nấm đốm lá tại Khu trồng Cây ớt (93%)",
            "message": "ESP32-cam phát hiện đốm lá kết hợp độ ẩm DHT22 89.9% và ánh sáng yếu 3,300 Lux.",
            "status": "UNREAD",
            "created_at": anchor - timedelta(minutes=9),
            "read_at": None,
        },
        {
            "notification_id": "seed-notif-02",
            "user_id": DEMO_USER_ID,
            "greenhouse_id": garden_id,
            "area_id": chili_area_id,
            "device_id": "NODEMCU-CHILI-01",
            "recommendation_id": None,
            "camera_log_id": "seed-cam-chili-01",
            "category": "ENV_ALERT",
            "severity": "WARNING",
            "title": "Độ ẩm cao >85% kéo dài — Đã tự động kích hoạt ESP32-cam",
            "message": "NodeMCU v2.0.0 ghi nhận độ ẩm 89.9% kéo dài 90 phút; hệ thống giữ Bơm nước tắt và chụp ảnh kiểm tra.",
            "status": "UNREAD",
            "created_at": anchor - timedelta(minutes=12),
            "read_at": None,
        },
    ]

    with engine.begin() as conn:
        # 1. User
        conn.execute(
            insert(User.__table__).values(
                user_id=DEMO_USER_ID,
                full_name="Demo Farmer",
                email=DEMO_USER_EMAIL,
                password_hash=DEMO_PASSWORD_HASH,
                phone_number="0905000111",
                role="FARMER",
                is_active=True,
            ).on_conflict_do_nothing()
        )
        # Resolve actual demo user_id in case email already existed under another ID
        actual_user_id = conn.execute(
            select(User.user_id).where(func.lower(func.btrim(User.email)) == DEMO_USER_EMAIL)
        ).scalar_one()

        # 2. Crops
        conn.execute(insert(Crop.__table__).values(crops_data).on_conflict_do_nothing())

        # 3. Outdoor Garden (greenhouses)
        conn.execute(
            insert(Greenhouse.__table__).values(
                greenhouse_id=garden_id,
                user_id=actual_user_id,
                crop_stage_id="crop-chili-vegetative",
                name="Khu vườn ngoài trời — Ớt & Xà lách",
                area_sqm=45.0,
                location="Khu vườn ngoài trời (Đà Nẵng)",
                environment_type="OUTDOOR",
                created_at=anchor - timedelta(days=14),
                updated_at=anchor,
            ).on_conflict_do_nothing()
        )

        # 4. Areas (Chili & Lettuce)
        conn.execute(
            insert(GreenhouseArea.__table__).values([
                {
                    "area_id": chili_area_id,
                    "greenhouse_id": garden_id,
                    "crop_stage_id": "crop-chili-vegetative",
                    "name": "Khu trồng Cây ớt ngoài trời",
                    "area_sqm": 25.0,
                    "created_at": anchor - timedelta(days=14),
                    "updated_at": anchor,
                },
                {
                    "area_id": lettuce_area_id,
                    "greenhouse_id": garden_id,
                    "crop_stage_id": "crop-lettuce-vegetative",
                    "name": "Khu trồng Cây xà lách ngoài trời",
                    "area_sqm": 20.0,
                    "created_at": anchor - timedelta(days=14),
                    "updated_at": anchor,
                },
            ]).on_conflict_do_nothing()
        )

        # 5. Devices
        conn.execute(insert(Device.__table__).values(devices_data).on_conflict_do_nothing())

        # 6. Sensor logs
        conn.execute(insert(SensorLog.__table__).values(sensor_rows).on_conflict_do_nothing())

        # 7. Camera logs
        conn.execute(insert(CameraLog.__table__).values(camera_rows).on_conflict_do_nothing())

        # 8. Actuator states & logs
        conn.execute(insert(ActuatorState.__table__).values(actuator_states_data).on_conflict_do_nothing())
        for log in actuator_logs_data:
            if log["user_id"] == DEMO_USER_ID:
                log["user_id"] = actual_user_id
        conn.execute(insert(ActuatorLog.__table__).values(actuator_logs_data).on_conflict_do_nothing())

        # 9. Recommendations
        conn.execute(insert(Recommendation.__table__).values(recommendations_data).on_conflict_do_nothing())

        # 10. Notifications
        for n in notifications_data:
            n["user_id"] = actual_user_id
        conn.execute(insert(Notification.__table__).values(notifications_data).on_conflict_do_nothing())

        # Collect row counts across all 11 tables
        tables = (
            User,
            Crop,
            Greenhouse,
            GreenhouseArea,
            Device,
            SensorLog,
            CameraLog,
            ActuatorState,
            ActuatorLog,
            Recommendation,
            Notification,
        )
        counts = {
            model.__tablename__: conn.execute(select(func.count()).select_from(model.__table__)).scalar_one()
            for model in tables
        }
    return counts


if __name__ == "__main__":
    summary = seed_outdoor_garden()
    print("Seed hoàn tất! Tổng số dòng theo từng bảng:")
    for table_name, total in summary.items():
        print(f"  - {table_name}: {total}")
