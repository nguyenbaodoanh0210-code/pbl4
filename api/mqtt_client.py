import paho.mqtt.client as mqtt
import json
import uuid
import os
import hmac
from datetime import datetime, timezone
from database import SessionLocal
from models import Device, SensorLog, Recommendation

# 1. Load mô hình AI từ thư mục pbl4
MODEL_PATH = None  # Pickle local chưa được xác minh; không nạp tự động.
ai_model = None

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "smart_greenhouse/24T_Nhat1/sensors")
DEVICE_INGEST_TOKEN = os.getenv("DEVICE_INGEST_TOKEN", "")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"

def _number(payload, canonical, aliases, minimum, maximum):
    value = next((payload[key] for key in (canonical, *aliases) if key in payload), None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Trường {canonical} phải là số")
    value = float(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"Trường {canonical} ngoài khoảng hợp lệ")
    return value


def _parse_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Thiếu timestamp ISO 8601 có múi giờ")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp phải có múi giờ")
    return parsed.astimezone(timezone.utc)


def _demo_diagnosis(values):
    keys = {"N": "REF_N_MIN", "P": "REF_P_MIN", "K": "REF_K_MIN"}
    if not all(os.getenv(env_key) is not None for env_key in keys.values()):
        return (
            "Chưa cấu hình ngưỡng tham chiếu N-P-K cho cây trồng; không thể kết luận thiếu dinh dưỡng.",
            "Chưa đề xuất loại hoặc liều phân bón. Cần cấu hình theo cây và giai đoạn.",
        )
    try:
        thresholds = {name: float(os.environ[env_key]) for name, env_key in (("Nitơ", keys["N"]), ("Photpho", keys["P"]), ("Kali", keys["K"]))}
        if any(not 0 <= value <= 5000 for value in thresholds.values()):
            raise ValueError("Ngưỡng N-P-K ngoài phạm vi")
    except (TypeError, ValueError):
        return ("Cấu hình ngưỡng N-P-K không hợp lệ; không thể đưa ra nhận định.", "Kiểm tra biến môi trường ngưỡng trước khi khuyến nghị.")
    low = [name for name in thresholds if values[name] < thresholds[name]]
    diagnosis = "Giá trị thấp hơn ngưỡng tham chiếu thử nghiệm: " + ", ".join(low) if low else "N-P-K không thấp hơn các ngưỡng tham chiếu thử nghiệm đã cấu hình."
    action = "Đối chiếu kết quả xét nghiệm đất và ngưỡng theo cây/giai đoạn; không tự động áp liều."
    return diagnosis, action


def on_connect(client, userdata, flags, rc):
    print(f"Đã kết nối MQTT Broker với mã: {rc}")
    client.subscribe(MQTT_TOPIC)

def _legacy_on_message(client, userdata, msg):
    try:
        # Giải mã dữ liệu từ ESP32
        payload = json.loads(msg.payload.decode("utf-8"))
        print("Nhận được dữ liệu:", payload)
        
        db = SessionLocal()
        
        # Trích xuất thông số
        device_id = payload.get("device_id", "NODE_01")
        temp = payload.get("temp", 0)
        hum = payload.get("hum", 0)
        moisture = payload.get("moisture", 0)
        pH = payload.get("pH", 0)
        N = payload.get("N", 0)
        P = payload.get("P", 0)
        K = payload.get("K", 0)
        
        # 2. Lưu Cảm Biến Vào Database
        new_log = SensorLog(
            log_id=str(uuid.uuid4()),
            device_id=device_id,
            temperature=temp, humidity=hum, soil_moisture=moisture, soil_pH=pH,
            N=N, P=P, K=K
        )
        db.add(new_log)
        
        # 3. Chạy Mô Hình AI
        # (Lưu ý: Nếu bị lỗi sai số lượng features, bạn mở file app_ai.py của bạn kia 
        # xem thứ tự các biến trong input_data là gì để sắp xếp lại mảng này cho khớp)
        input_data = [[N, P, K, temp, hum, pH, moisture]] 
        
        try:
            prediction_result = ai_model.predict(input_data)[0]
        except Exception as model_err:
            prediction_result = f"Lỗi Model: {model_err}"
            
        # 4. Lưu Đề Xuất Phân Bón Vào Database
        new_rec = Recommendation(
            rec_id=str(uuid.uuid4()),
            device_id=device_id,
            condition_diagnosis="AI phân tích tự động",
            fertilizer_action=str(prediction_result)
        )
        db.add(new_rec)
        
        db.commit()
        db.close()
        print(f"-> Đã lưu DB & AI Đề xuất: {prediction_result}\n")
        
    except Exception as e:
        print("Lỗi xử lý MQTT/AI:", e)

def on_message(client, userdata, msg):
    db = SessionLocal()
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Payload phải là JSON object")
        if not DEVICE_INGEST_TOKEN:
            raise PermissionError("DEVICE_INGEST_TOKEN chưa được cấu hình")
        supplied_token = payload.pop("device_token", "")
        if not isinstance(supplied_token, str) or not hmac.compare_digest(supplied_token, DEVICE_INGEST_TOKEN):
            raise PermissionError("Thiết bị không được xác thực")

        device_id = payload.get("device_id")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("Thiếu device_id")
        device_id = device_id.strip()
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if device is None or device.status != "ACTIVE":
            raise ValueError("Thiết bị không tồn tại hoặc không hoạt động")

        measured_at = _parse_timestamp(payload.get("timestamp"))
        values = {
            "Temperature": _number(payload, "temperature", ("temp", "Temperature"), -40, 85),
            "Humidity": _number(payload, "humidity", ("hum", "Humidity"), 0, 100),
            "Soil_Moisture": _number(payload, "soil_moisture", ("moisture", "Soil_Moisture"), 0, 100),
            "Soil_pH": _number(payload, "pH", ("soil_pH", "Soil_pH"), 0, 14),
            "N": _number(payload, "nitrogen", ("N", "Nitrogen"), 0, 5000),
            "P": _number(payload, "phosphorus", ("P", "Phosphorus"), 0, 5000),
            "K": _number(payload, "potassium", ("K", "Potassium"), 0, 5000),
        }
        duplicate = db.query(SensorLog).filter(
            SensorLog.device_id == device_id,
            SensorLog.timestamp == measured_at,
        ).first()
        if duplicate:
            print(f"Bỏ qua bản tin MQTT trùng timestamp cho thiết bị {device_id}")
            return

        # Các giới hạn rộng dưới đây chỉ phát hiện giá trị phi thực tế, không thay thế ngưỡng cây trồng.
        warnings = []
        if values["Temperature"] > 60 or values["Temperature"] < -10:
            warnings.append("temperature ngoài vùng vận hành thường gặp")
        if values["Soil_pH"] < 3 or values["Soil_pH"] > 10:
            warnings.append("pH đáng ngờ, cần kiểm tra cảm biến")

        new_log = SensorLog(
            log_id=str(uuid.uuid4()), device_id=device_id, timestamp=measured_at,
            temperature=values["Temperature"], humidity=values["Humidity"],
            soil_moisture=values["Soil_Moisture"], soil_pH=values["Soil_pH"],
            N=values["N"], P=values["P"], K=values["K"],
        )
        db.add(new_log)
        device.is_online = True
        diagnosis, action = _demo_diagnosis({"Nitơ": values["N"], "Photpho": values["P"], "Kali": values["K"]})
        if warnings:
            diagnosis += " Cảnh báo chất lượng dữ liệu: " + "; ".join(warnings) + "."
            action = "Kiểm tra cảm biến và phép đo trước khi quyết định bón phân."
        db.add(Recommendation(
            rec_id=str(uuid.uuid4()), device_id=device_id,
            condition_diagnosis=diagnosis, fertilizer_action=action, status="PENDING",
        ))
        db.commit()
        print(f"Đã lưu dữ liệu và khuyến nghị thử nghiệm cho thiết bị {device_id}")
    except (ValueError, PermissionError, json.JSONDecodeError) as err:
        db.rollback()
        print(f"Từ chối bản tin MQTT: {err}")
    except Exception as err:
        db.rollback()
        print(f"Lỗi xử lý bản tin MQTT ({type(err).__name__})")
    finally:
        db.close()


def start_mqtt():
    client = mqtt.Client()
    if MQTT_USERNAME or MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
