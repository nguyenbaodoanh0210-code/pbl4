import paho.mqtt.client as mqtt
import json
import random
import os
from datetime import datetime, timezone
import time

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "smart_greenhouse/24T_Nhat1/sensors")
DEVICE_INGEST_TOKEN = os.getenv("DEVICE_INGEST_TOKEN", "")

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)

print("Bắt đầu giả lập ESP32 gửi dữ liệu...")
try:
    while True:
        # Tạo dữ liệu ngẫu nhiên mô phỏng cảm biến
        payload = {
            "device_id": "NODE_01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_token": DEVICE_INGEST_TOKEN,
            "temp": round(random.uniform(25.0, 32.0), 1),
            "hum": round(random.uniform(60.0, 85.0), 1),
            "moisture": round(random.uniform(40.0, 75.0), 1),
            "pH": round(random.uniform(5.5, 7.5), 1),
            "N": random.randint(80, 150),
            "P": random.randint(30, 60),
            "K": random.randint(100, 200)
        }
        
        # Gửi gói tin lên MQTT
        client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"Đã gửi: {payload}")
        
        # Đợi 5 giây rồi gửi tiếp
        time.sleep(5)
except KeyboardInterrupt:
    print("Đã dừng giả lập.")
