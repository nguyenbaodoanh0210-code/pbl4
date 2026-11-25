import paho.mqtt.client as mqtt
import json
import random
import os
from pathlib import Path
from datetime import datetime, timezone
import time
from dotenv import load_dotenv

# Load biến môi trường từ api/.env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "smart_greenhouse/24T_Nhat1/sensors")
DEVICE_INGEST_TOKEN = os.getenv("DEVICE_INGEST_TOKEN", "")

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)

print(f"Bắt đầu giả lập NodeMCU v2.0.0 gửi dữ liệu lên {MQTT_BROKER}:{MQTT_PORT} (Topic: {MQTT_TOPIC})...")
try:
    while True:
        # Tạo dữ liệu ngẫu nhiên mô phỏng cảm biến ngoài trời (DHT22 + Quang trở LDR)
        payload = {
            "device_id": "NODEMCU-CHILI-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_token": DEVICE_INGEST_TOKEN,
            "temperature": round(random.uniform(25.0, 32.0), 1),
            "humidity": round(random.uniform(60.0, 85.0), 1),
            "light_level": round(random.uniform(15000.0, 35000.0), 0),
            "soil_moisture": round(random.uniform(40.0, 75.0), 1),
            "pH": round(random.uniform(5.5, 7.5), 1),
            "nitrogen": random.randint(80, 150),
            "phosphorus": random.randint(30, 60),
            "potassium": random.randint(100, 200),
        }
        
        # Gửi gói tin lên MQTT
        client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"Đã gửi: {payload}")
        
        # Đợi 5 giây rồi gửi tiếp
        time.sleep(5)
except KeyboardInterrupt:
    print("Đã dừng giả lập.")
