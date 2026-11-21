# NodeMCU v2.0.0 Firmware

Đặt mã nguồn Arduino/PlatformIO cho **NodeMCU v2.0.0** (DHT22 + Cảm biến ánh sáng Quang trở + Relay Bơm nước) tại thư mục này.

## Payload MQTT gửi lên Backend (`MQTT_TOPIC`)
```json
{
  "device_token": "<DEVICE_INGEST_TOKEN>",
  "device_id": "NODEMCU-CHILI-01",
  "timestamp": "2026-11-18T10:00:00Z",
  "temperature": 26.5,
  "humidity": 88.2,
  "light_level": 4200
}
```

## Topic nhận lệnh điều khiển Bơm nước
- `smart_garden/<greenhouse_id>/control`
