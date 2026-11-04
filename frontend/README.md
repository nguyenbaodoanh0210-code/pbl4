# Giao diện La Nhà

Giao diện ưu tiên thiết bị di động cho Smart Greenhouse API. Frontend không cần thư viện bên ngoài và được giữ riêng với backend Python trong `../api`.

## Cách khởi chạy

> Cần chạy **backend và frontend cùng lúc**. Hãy mở hai terminal trong VS Code (Terminal → New Terminal hai lần) hoặc mở hai cửa sổ PowerShell. Khởi động backend trước, giữ terminal đó mở; sau đó chạy frontend ở terminal thứ hai.

### Terminal 1 — Backend API

```powershell
cd D:\PBL4\api
.\venv\Scripts\python.exe -X utf8 -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend dùng venv hiện có và đọc `DATABASE_URL` từ [api/.env](../api/.env). Nếu cần cấu hình kết nối, chạy `.\venv\Scripts\python.exe -X utf8 -m scripts.configure_database` tại thư mục `api` rồi nhập mật khẩu PostgreSQL trong terminal. Công cụ kiểm tra kết nối trước khi lưu. Không đặt lại `DATABASE_URL` bằng giá trị mẫu trong terminal; biến môi trường này có ưu tiên cao hơn `.env`. Nếu terminal đang giữ cấu hình cũ, bỏ biến đó trong terminal bằng `Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue` rồi khởi động lại API. Áp dụng các migration theo [hướng dẫn backend](../api/README.md). Kiểm tra cả API và database tại `http://127.0.0.1:5173/health?check_database=true` sau khi frontend đã chạy.

### Terminal 2 — Frontend

Mở terminal mới, để terminal backend tiếp tục chạy:

```powershell
cd D:\PBL4\frontend
node .\server.mjs
```

Mở `http://127.0.0.1:5173` trên điện thoại hoặc dùng chế độ giả lập thiết bị của trình duyệt. Frontend chuyển tiếp `/api/*` và `/health` đến `http://127.0.0.1:8000`.

Để dừng mỗi tiến trình, nhấn `Ctrl+C` trong terminal tương ứng. Nếu chỉ muốn thử frontend, không có backend thì giao diện vẫn mở được, nhưng sẽ báo chưa kết nối API và không có dữ liệu thật.

Sau khi sửa `server.mjs`, khởi động lại tiến trình Node để nạp thay đổi proxy; chỉ tải lại trang sẽ không nạp lại mã server.

Server frontend chuyển tiếp các đường dẫn `/api/*` và `/health` đến `http://127.0.0.1:8000`. Có thể đặt biến môi trường `API_ORIGIN` để dùng địa chỉ API khác, `FRONTEND_HOST` để đổi địa chỉ bind hoặc `FRONTEND_PORT` để đổi cổng.

## Kết nối API và giới hạn hiện tại

- Frontend đọc danh sách nhà kính, thiết bị, lịch sử/số đo cảm biến mới nhất và khuyến nghị từ các endpoint FastAPI hiện có.
- Biểu đồ lịch sử lọc các bản ghi API theo giờ, ngày, tuần hoặc tháng. Khi người dùng xác nhận, frontend gọi `PUT /api/recommendations/{rec_id}/apply` sau khi hiển thị hộp thoại xác nhận.
- Đăng nhập/đăng ký dùng các endpoint `/api/auth/*`. Frontend lưu token trong `sessionStorage` và gửi header `Authorization: Bearer ...`; proxy chuyển tiếp header này tới API. Form tạo nhà kính/thiết bị chưa được tích hợp trên giao diện; các API quản lý hiện dùng tài khoản đăng nhập và kiểm tra quyền sở hữu.
- Backend chưa có endpoint thông báo riêng. Màn hình thông báo chỉ tổng hợp trạng thái thiết bị ngoại tuyến và khuyến nghị đang chờ từ API.
- Backend đã có tài khoản người dùng và lọc nhà kính theo chủ sở hữu. Giao diện chưa tích hợp dữ liệu giai đoạn sinh trưởng, thời tiết hoặc ngưỡng dinh dưỡng đã được xác thực; không tự đưa ra chẩn đoán canh tác hay liều lượng phân bón khi thiếu dữ liệu.
