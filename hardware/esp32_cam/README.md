# ESP32-CAM Firmware

Đặt mã nguồn Arduino/PlatformIO cho **ESP32-CAM** tại thư mục này.

## Cơ chế hoạt động
1. Chụp định kỳ (`SCHEDULED`), hoặc khi nhận lệnh MQTT trên topic `smart_garden/<greenhouse_id>/camera/cmd` (`MANUAL` / `ENV_ALERT`).
2. Gửi ảnh JPEG lên `POST /api/camera/diagnose` kèm header `X-Device-Token: <DEVICE_INGEST_TOKEN>`.
