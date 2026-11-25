# PBL4 — Hệ thống Giám sát Khu vườn Ngoài trời & Chẩn đoán Bệnh Đa phương thức

Hệ thống IoT + AI Đa phương thức (CNN + DHT22 + Cảm biến ánh sáng) dành cho **khu vườn trồng ngoài trời** (Cây ớt, Cây xà lách), tổ chức theo mô hình **MVC**.

## Cấu trúc thư mục (MVC)

```text
pbl4/
├── api/                         # Backend FastAPI theo mô hình MVC
│   ├── app/
│   │   ├── core/                # Hạ tầng dùng chung (database.py, auth.py)
│   │   ├── models/              # [M] 11 bảng SQLAlchemy ORM
│   │   ├── schemas/             # [M] Pydantic Request/Response DTO
│   │   ├── controllers/         # [C] FastAPI Routers (REST API)
│   │   ├── services/            # Nghiệp vụ lõi (MQTT, Bơm nước, AI Đa phương thức)
│   │   ├── ai/                  # Adapter suy luận mô hình CNN / ML
│   │   └── main.py              # Khởi tạo FastAPI & gắn Controllers
│   ├── migrations/              # SQL migration khởi tạo & nâng cấp PostgreSQL
│   ├── ml_models/               # Trọng số AI (.keras, .joblib) và báo cáo đánh giá
│   ├── data/                    # Dataset huấn luyện & seed SQL
│   ├── scripts/                 # apply_migrations, seed_outdoor_garden, train, simulate
│   ├── uploads/camera/          # Ảnh chụp lưu từ ESP32-CAM (ignored bởi Git)
│   └── tests/                   # Bộ kiểm thử Backend
│
├── frontend/                    # [V] Web Dashboard (HTML/CSS/ES Modules MVC)
│   ├── index.html               # Khung giao diện chính
│   ├── server.mjs               # Proxy /api -> Backend & phục vụ tệp tĩnh
│   ├── app.js                   # Entrypoint ứng dụng
│   ├── styles/                  # CSS (base, workspace, editorial, auth)
│   ├── js/
│   │   ├── models/              # State & API client
│   │   ├── views/               # Giao diện 1 (Môi trường), 2 (AI Camera), 3 (Khu vườn)
│   │   └── controllers/         # Router & điều phối sự kiện
│   ├── assets/                  # Ảnh tĩnh & icon
│   └── tests/                   # Bộ kiểm thử Frontend
│
└── hardware/                    # Firmware phần cứng IoT
    ├── nodemcu_v2/              # NodeMCU v2.0.0 (DHT22 + Quang trở + Relay Bơm nước)
    └── esp32_cam/               # ESP32-CAM chụp & truyền ảnh về Backend
```

## Chạy nhanh

1. Cấu hình `api/.env` từ `api/.env.example` (không commit thông tin đăng nhập/token).
2. Áp dụng migration & seed dữ liệu mẫu:
   ```powershell
   cd api
   .\venv\Scripts\python.exe -X utf8 -m scripts.apply_migrations
   .\venv\Scripts\python.exe -X utf8 -m scripts.seed_outdoor_garden
   ```
3. Khởi chạy API:
   ```powershell
   .\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```
4. Khởi chạy Frontend:
   ```powershell
   cd frontend
   node server.mjs
   ```
