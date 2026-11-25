# KỊCH BẢN & HƯỚNG DẪN DEMO HỆ THỐNG SMART OUTDOOR GARDEN (PBL4)

**Đề tài:** Hệ thống giám sát khu vườn ngoài trời thông minh & chẩn đoán bệnh cây bằng AI Đa phương thức (Multimodal Fusion)  
**Kiến trúc:** MVC 3 tầng (FastAPI + PostgreSQL 11 bảng · Web Dashboard "La Nhà" · ESP32-S3 All-in-One)

---

## 1. Phần cứng & Sơ đồ kết nối thực tế (1 mạch ESP32-S3 All-in-One)

Toàn bộ cảm biến và camera được gộp chạy đồng thời trên **01 vi điều khiển ESP32-S3 N16R8** (tối ưu gọn mạch và nguồn cấp):

| Thành phần | Chân cắm trên ESP32-S3 | Giao thức / Chức năng |
| --- | --- | --- |
| **Camera tích hợp** | GPIO 4–13, 15–18 (nội bộ) | Nhận lệnh MQTT `camera/cmd` → HTTP POST ảnh JPEG lên `/api/camera/diagnose`; snapshot cổng `81` |
| **Cảm biến nhiệt độ & độ ẩm (DHT22)** | **GPIO 3** *(dời từ GPIO 4 để tránh trùng `SIOD` Camera)* | Đọc nhiệt độ (°C) & độ ẩm không khí (%) gửi MQTT mỗi 15 giây |
| **Cảm biến độ ẩm đất** | **GPIO 1** (`ADC1_CH0`) | Đọc ADC 12-bit quy đổi 0–100% độ ẩm đất |
| **Cảm biến ánh sáng (LDR)** | **GPIO 2** (`ADC1_CH1`) | Đọc ADC 12-bit ước tính cường độ ánh sáng (Lux); đã tắt Flash LED để không xung đột |
| **Điều khiển Bơm nước** | *Chưa gắn Relay/Bơm vật lý* | Mạch vẫn đăng ký topic `control`, nhận lệnh bật/tắt từ Web và in log `[BOM NUOC - MO PHONG]` trên Serial Monitor |

**Cấu hình mạng chuẩn khi báo cáo (tránh Wi-Fi trường chặn LAN/MQTT):**
- Bật **Windows Mobile Hotspot** trên laptop (băng tần **2.4 GHz**): SSID `ESP32`, mật khẩu `12345678`.
- IP máy chủ Web Server cố định trên Hotspot Windows: **`192.168.137.1:8000`**.

---

## 2. Quy trình khởi động hệ thống trong 60 giây trước giờ báo cáo

### Bước 1: Bật mạng & cấp nguồn mạch
1. Bật **Mobile Hotspot 2.4 GHz** (`ESP32` / `12345678`) trên laptop (vẫn giữ mạng dây LAN hoặc 4G để có Internet kết nối MQTT Broker & đồng bộ giờ NTP).
2. Cắm nguồn USB cho **ESP32-S3** (có thể mở sẵn Serial Monitor tốc độ `115200` để hội đồng thấy log trực tiếp khi cảm biến gửi dữ liệu và nhận lệnh).

### Bước 2: Khởi chạy Web Server & MQTT Worker
- Nhấp đúp file **`CHAY_WEB.bat`** tại thư mục gốc dự án (hoặc mở 2 cửa sổ PowerShell tại `D:\PBL4\api`):
  - **Cửa sổ 1 (Web + API):** `.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - **Cửa sổ 2 (MQTT Worker):** `.\venv\Scripts\python.exe -m app.mqtt_client`

### Bước 3: Kiểm tra nhanh trước khi trình chiếu
- Mở trình duyệt vào `http://localhost:8000/health?check_database=true` → xác nhận trả về `{"status": "ok", "database": "ok"}`.
- Mở giao diện chính tại **`http://localhost:8000`** (máy khác/điện thoại cùng Hotspot truy cập `http://192.168.137.1:8000`).

---

## 3. Kịch bản Demo 5–7 phút trước Hội đồng

### Màn hình 1 — Đăng nhập & Phân quyền (`Authentication`)
- **Thao tác:** Đăng nhập bằng tài khoản demo `demo@smartgreenhouse.local` / `Demo@12345678`.
- **Thuyết minh:** Xác thực bằng Bearer Token (HS256, hiệu lực 1 giờ), mật khẩu băm PBKDF2-HMAC-SHA256 (600.000 vòng lặp); dữ liệu khu vườn được lọc chặt theo quyền sở hữu (`user_id`).

### Màn hình 2 — Tổng quan khu vườn & Điều khiển Bơm (`Dashboard & Actuators`)
- **Thao tác:**
  1. Quan sát các thông số thời gian thực (**Nhiệt độ**, **Độ ẩm không khí**, **Cường độ ánh sáng**) cập nhật mỗi 15 giây từ ESP32-S3 (có thể hà hơi vào DHT22 hoặc lấy tay che cảm biến ánh sáng để thấy số liệu thay đổi trực tiếp).
  2. Chuyển chế độ Bơm từ **Tự động (`AUTO`)** sang **Thủ công (`MANUAL`)**, bấm **Bật Bơm** rồi **Tắt Bơm** — chỉ cho hội đồng thấy log `[BOM NUOC - MO PHONG]` nhảy tức thì trên Serial Monitor của ESP32-S3 và lịch sử lưu trong bảng `actuator_logs`.
- **Thuyết minh:** Ở chế độ `AUTO`, hệ thống khóa nút bật/tắt tay (API trả HTTP 409) và tự điều khiển theo ngưỡng (bật khi ẩm ≤ 50% hoặc nhiệt ≥ 33°C, ngắt khi ẩm ≥ 75% để tránh úng rễ và phát sinh nấm). Phần cứng máy bơm dễ dàng đấu thêm qua 1 module Relay 5V ở bước triển khai thực tế.

### Màn hình 3 — Lịch sử & Xu hướng (`History Analytics`)
- **Thao tác:** Chuyển sang tab **Lịch sử & Xu hướng**, đổi qua lại giữa các chỉ số (Nhiệt độ / Độ ẩm / Ánh sáng) và khung thời gian (Giờ / Ngày / Tuần).
- **Thuyết minh:** Dữ liệu chuỗi thời gian từ PostgreSQL (`sensor_logs`) giúp phát hiện giai đoạn ẩm cao kéo dài (≥ 85%) kết hợp thiếu sáng (≤ 8.000 Lux) — nguyên nhân chính gây nấm bệnh ngoài trời.

### Màn hình 4 — Chẩn đoán bệnh bằng AI Đa phương thức (`Multimodal Camera AI` — Trọng tâm)
- **Thao tác:**
  1. Chuyển sang tab **Chẩn đoán sức khỏe cây**, hướng ống kính ESP32-S3 vào lá cây (hoặc ảnh lá bệnh) rồi bấm **CHỤP ẢNH & CHẨN ĐOÁN BỆNH LÁ**.
  2. Quan sát luồng chạy thực tế: Web gửi lệnh MQTT → ESP32-S3 chụp ảnh JPEG (`VGA`, `CAMERA_GRAB_LATEST`) → POST lên `/api/camera/diagnose` → ảnh mới nhất hiện lên kính ngắm kèm kết quả phân tích.
- **Thuyết minh:**
  - Nếu chỉ dùng CNN đơn lẻ (tập dữ liệu 500 ảnh lá ớt, 5 lớp, độ chính xác 70%), mô hình dễ nhầm lẫn đốm lá với cháy nắng hoặc vết bẩn.
  - **Tầng Multimodal Fusion (`multimodal_service.py`)** đối chiếu kết quả CNN với dữ liệu môi trường 60 phút gần nhất:
    - Khi CNN nghi nấm (`leaf spot` / `fungal`) kèm độ ẩm ≥ 85% kéo dài và ánh sáng yếu (≤ 8.000 Lux) → **củng cố độ tin cậy +12%** (chỉ ẩm cao tăng **+7%**).
    - Khi môi trường ngoài vườn khô thoáng, đủ sáng → **giảm độ tin cậy −8%** để hạn chế báo động giả.
    - Khi lá vẫn `healthy` nhưng trời ẩm ướt thiếu sáng kéo dài → **phát cảnh báo phòng ngừa sớm** khuyên tạm ngưng tưới chiều tối.

### Màn hình 5 — Cảnh báo, Khuyến nghị & Quản lý luống (`Alerts, Advice & Gardens`)
- **Thao tác:**
  1. Mở tab **Thông báo & Cảnh báo** và **Hướng dẫn chăm sóc**: xem cảnh báo tự động sinh ra khi phát hiện bệnh (độ tin cậy sau hợp nhất ≥ 65%, mức `CRITICAL` nếu ≥ 80%), bấm **Áp dụng khuyến nghị** (`PENDING` → `APPLIED`).
  2. Lướt nhanh tab **Khu vườn & Cây trồng** để cho thấy khả năng quản lý riêng từng luống (**Cây ớt**, **Cây xà lách**) và tùy chỉnh ngưỡng sinh thái.

---

## 4. Phương án dự phòng (Plan B) khi mạng hoặc cảm biến gặp sự cố

### Phương án A — Giả lập dữ liệu cảm biến khi mất tín hiệu mạch
Mở PowerShell tại `D:\PBL4\api` và chạy:
```powershell
.\venv\Scripts\python.exe -m scripts.simulate_esp32
```

### Phương án B — Upload trực tiếp 3 ảnh mẫu trên tab Chẩn đoán
Bấm mục **Hoặc tải ảnh từ tệp máy tính (Dự phòng kiểm thử)** và chọn sẵn 1 trong 3 ảnh có độ nhận diện cao nhất:

1. **Lá ớt khỏe mạnh (`healthy`):** `api\data\chili_plant_disease\test\healthy\Cabai sehat003.jpg`
2. **Lá ớt vàng lá (`yellowish` — F1 95,2%):** `api\data\chili_plant_disease\test\unhealthy\yellowish\yellowish01.jpg`
3. **Lá ớt xoăn lá (`leaf curl` — F1 80,0%):** `api\data\chili_plant_disease\test\unhealthy\leaf curl\download (11).jpg`

*(Nếu máy báo cáo chưa cài TensorFlow, đảm bảo `ALLOW_DEMO_VISION_FALLBACK=true` đang bật trong `api/.env` để tránh lỗi HTTP 503).*

---

## 5. Gợi ý trả lời nhanh các câu hỏi phản biện thường gặp

| Câu hỏi của Hội đồng | Hướng trả lời ngắn gọn, trúng trọng tâm |
| --- | --- |
| **Tại sao gộp cả Camera và 3 cảm biến trên 1 mạch ESP32-S3?** | ESP32-S3 N16R8 có chip lõi kép, 8 MB PSRAM và bộ ADC 12-bit độc lập nên dư sức xử lý đồng thời Camera + DHT22 + độ ẩm đất + ánh sáng, giúp giảm chi phí phần cứng, đơn giản hóa cấp nguồn và đồng bộ dữ liệu tập trung hơn. |
| **Chưa có máy bơm thật thì chứng minh điều khiển tự động thế nào?** | Toàn bộ kiến trúc điều khiển 2 chiều (API kiểm tra chế độ `AUTO`/`MANUAL`, lưu vết `actuator_logs`, gửi lệnh MQTT xuống mạch) đã hoàn chỉnh 100% và minh chứng trực tiếp qua Serial Monitor của ESP32-S3; khi triển khai thực tế chỉ cần nối thêm 1 module Relay 5V vào chân GPIO trống. |
| **Tại sao chọn PostgreSQL thay vì MySQL?** | PostgreSQL mã nguồn mở, hỗ trợ mạnh kiểu `JSONB` (lưu `cnn_scores`, `env_window_summary`, `auto_rules`) và ràng buộc `CHECK` chặt chẽ cho 11 bảng quan hệ IoT + AI. |
| **Độ chính xác CNN mới 70% thì có đáng tin không?** | Tập dữ liệu lá ớt hiện có 500 ảnh và huấn luyện từ đầu nên lớp `leaf spot` còn hạn chế; đó là lý do nhóm xây dựng tầng **Multimodal Fusion** kết hợp độ ẩm và ánh sáng thực tế để lọc báo động giả, đồng thời có thể nâng cấp trọng số model mà không cần sửa kiến trúc hệ thống. |
   