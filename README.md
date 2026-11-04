# PBL4 Smart Greenhouse

Dự án nhà kính thông minh gồm backend FastAPI, giao diện web và source ESP32.

## Cấu trúc repository

- api/app/: ứng dụng FastAPI, truy cập database và các adapter AI.
- api/data/: workbook cảm biến và bộ ảnh bệnh cây ớt dùng để train.
- api/models/: model đang dùng, báo cáo đánh giá và model legacy chưa xác minh.
- api/scripts/: script train model, giả lập MQTT và nhận dữ liệu Serial.
- api/firmware/esp32/: source firmware hiện có.
- frontend/: giao diện web và proxy API.

Hướng dẫn khởi chạy backend và các model nằm trong api/README.md. Frontend có hướng dẫn riêng trong frontend/README.md.

Cấu hình api/.env từ api/.env.example. Không commit api/.env, thông tin đăng nhập database hoặc token.