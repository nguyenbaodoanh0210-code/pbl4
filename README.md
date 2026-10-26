# PBL4 Smart Greenhouse

Dự án gồm backend FastAPI, giao diện frontend tối ưu cho thiết bị di động và mã AI/firmware hiện có.

## Cấu trúc

- api/: backend FastAPI, kết nối PostgreSQL qua DATABASE_URL trong api/.env.
- api/pbl4/: mã AI/firmware đã có trong repository trước đây.
- frontend/: giao diện web, gọi backend qua proxy cục bộ.

## Chạy ứng dụng

Cấu hình api/.env từ api/.env.example, cài dependencies và khởi động API theo hướng dẫn trong api/README.md. Khởi động giao diện theo frontend/README.md.

Không commit api/.env hoặc thông tin xác thực database.
