# Giao diện La Nhà

Giao diện ưu tiên thiết bị di động cho Smart Greenhouse API. Frontend không cần thư viện bên ngoài và được giữ riêng với backend Python trong `../api`.

## Cách khởi chạy

> Cần chạy **backend và frontend cùng lúc**. Hãy mở hai terminal trong VS Code (Terminal → New Terminal hai lần) hoặc mở hai cửa sổ PowerShell. Khởi động backend trước, giữ terminal đó mở; sau đó chạy frontend ở terminal thứ hai.

### Terminal 1 — Backend API

```powershell
cd D:\PBL4\api
.\venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql+psycopg2://USER:PASSWORD@localhost:5432/smart_greenhouse_db"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Thay `USER`, `PASSWORD` và tên database mẫu bằng thông tin PostgreSQL của bạn. Database/schema phải được tạo trước. `DATABASE_URL` là bắt buộc; backend hiện không tự đọc tệp `.env`. Khi API chạy, có thể mở `http://127.0.0.1:8000/health` để xem trạng thái.

### Terminal 2 — Frontend

Mở terminal mới, để terminal backend tiếp tục chạy:

```powershell
cd D:\PBL4\frontend
node .\server.mjs
```

Mở `http://127.0.0.1:5173` trên điện thoại hoặc dùng chế độ giả lập thiết bị của trình duyệt. Frontend chuyển tiếp `/api/*` và `/health` đến `http://127.0.0.1:8000`.

Để dừng mỗi tiến trình, nhấn `Ctrl+C` trong terminal tương ứng. Nếu chỉ muốn thử frontend, không có backend thì giao diện vẫn mở được, nhưng sẽ báo chưa kết nối API và không có dữ liệu thật.

Server frontend chuyển tiếp các đường dẫn `/api/*` và `/health` đến `http://127.0.0.1:8000`. Có thể đặt biến môi trường `API_ORIGIN` để dùng địa chỉ API khác, `FRONTEND_HOST` để đổi địa chỉ bind hoặc `FRONTEND_PORT` để đổi cổng.

## Kết nối API và giới hạn hiện tại

- Frontend đọc danh sách nhà kính, thiết bị, lịch sử/số đo cảm biến mới nhất và khuyến nghị từ các endpoint FastAPI hiện có.
- Biểu đồ lịch sử lọc các bản ghi API theo giờ, ngày, tuần hoặc tháng. Khi người dùng xác nhận, frontend gọi `PUT /api/recommendations/{rec_id}/apply` sau khi hiển thị hộp thoại xác nhận.
- Chức năng tạo nhà kính/thiết bị đang để chưa khả dụng vì các API này yêu cầu header `X-Admin-Token`. Frontend không lưu hoặc hiển thị token quản trị.
- Backend chưa có endpoint thông báo riêng. Màn hình thông báo chỉ tổng hợp trạng thái thiết bị ngoại tuyến và khuyến nghị đang chờ từ API.
- Backend hiện chưa cung cấp giai đoạn sinh trưởng, tài khoản người dùng, quyền sở hữu nhà kính, thời tiết hoặc ngưỡng dinh dưỡng đã được xác thực. Giao diện không tự đưa ra chẩn đoán canh tác hay liều lượng phân bón khi thiếu dữ liệu.
