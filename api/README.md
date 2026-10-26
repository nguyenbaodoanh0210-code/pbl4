# Smart Greenhouse API

Backend hiện dùng FastAPI, SQLAlchemy và PostgreSQL theo schema trong `models.py`. Chưa có migration framework trong source, vì vậy API không tự sửa schema hoặc xóa dữ liệu. Bản triển khai này tái sử dụng các bảng hiện có (`greenhouses`, `devices`, `sensor_logs`, `recommendations`).

## Môi trường và khởi chạy

1. Dùng môi trường ảo Python có sẵn trong dự án nếu có; không tạo môi trường thứ hai.
2. Cài dependencies vào đúng môi trường ảo từ `requirements.txt`.
3. Sao chép `.env.example` thành `.env` và cấu hình các biến ở terminal/launcher. Backend hiện không tự đọc file `.env`.
4. Chạy `uvicorn main:app --reload`. OpenAPI/Swagger: `/docs`; kiểm tra liveness: `/health`.

`DATABASE_URL` là bắt buộc. Tạo database/schema hiện có trước khi chạy. `ADMIN_API_TOKEN` bảo vệ thao tác đăng ký nhà kính/thiết bị; gửi qua header `X-Admin-Token`. Không có tài khoản người dùng hoặc phân quyền theo chủ sở hữu trong source hiện tại.

## API chính

- `GET /api/greenhouses`, `GET /api/greenhouses/{greenhouse_id}`, `POST /api/greenhouses` và `PUT`/`DELETE /api/greenhouses/{greenhouse_id}` (ghi cần `X-Admin-Token`; xóa bị từ chối nếu còn thiết bị liên kết).
- `GET /api/devices`, `POST /api/devices`, `PATCH /api/devices/{device_id}/status` (ghi cần `X-Admin-Token`; status ACTIVE/INACTIVE).
- `GET /api/sensors/{device_id}/latest` và `GET /api/sensors/{device_id}?start=...&end=...&limit=...&offset=...`.
- `GET /api/recommendations` (lọc `device_id`, `status`, phân trang), `GET /api/recommendations/{rec_id}` và `PUT /api/recommendations/{rec_id}/apply`.
- `GET /health`; tài liệu API tự sinh ở `/docs` và `/openapi.json`.

Thời gian truy vấn dùng ISO 8601 có múi giờ. Lịch sử giới hạn tối đa 500 bản ghi mỗi trang. Khuyến nghị không còn trả dữ liệu mock khi database trống.

## MQTT

Subscriber giữ topic mặc định cũ, có thể cấu hình bằng `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, `MQTT_PASSWORD`; đặt `MQTT_TLS=true` để bật TLS. Mỗi payload phải có `device_token` khớp `DEVICE_INGEST_TOKEN`, `device_id` đã đăng ký, timestamp ISO 8601 có múi giờ và các số đo `temp`, `hum`, `moisture`, `pH`, `N`, `P`, `K` (hoặc tên đầy đủ được backend hỗ trợ). Payload lặp cùng `device_id` và timestamp bị bỏ qua. Dữ liệu pH/NPK trong firmware hiện tại đang gán cứng/mô phỏng, không phải phép đo phần cứng.

Để chạy subscriber trong tiến trình riêng: `python -c "from mqtt_client import start_mqtt; start_mqtt(); input('Press Enter to stop')"`. Chỉ chạy trên broker riêng có TLS/ACL trong triển khai thật; topic broker công cộng mặc định chỉ phục vụ demo.

`simulate_esp32.py` là bộ phát dữ liệu demo ngẫu nhiên, cần cấu hình token và thiết bị/nhà kính trong database trước. Không dùng nó làm nguồn dữ liệu production.

## Giới hạn AI/phần cứng

Backend không tự nạp các file pickle có sẵn vì chưa xác minh nguồn, schema đặc trưng hoặc phiên bản tương thích. Khi chưa cấu hình đủ các ngưỡng `REF_N_MIN`, `REF_P_MIN`, `REF_K_MIN`, hệ thống chỉ ghi rằng chưa đủ căn cứ và không đề xuất loại/liều phân bón. Nếu bật các ngưỡng này, chúng vẫn là tham chiếu demo cần chuyên gia xác nhận theo cây và giai đoạn.

Firmware `pbl4/main.cpp` hiện gửi dữ liệu qua Serial và gán cứng crop/NPK/pH; nó chưa gửi MQTT trực tiếp. Camera, người dùng, cây trồng/giai đoạn, FCM và migration chưa có trong source nên API chưa giả lập các chức năng đó.
