# THƯ MỤC PHẦN CỨNG IOT — SMART OUTDOOR GARDEN (PBL4)

Tài liệu này dành cho thành viên phụ trách phần cứng (nối dây và nạp code cho các mạch vi điều khiển ngoài vườn).

---

## 📁 Cấu trúc Thư mục

```
hardware/
│
├── nodemcu_v2/                           <-- DÀNH CHO VI ĐIỀU KHIỂN NODEMCU
│   ├── nodemcu_firmware.ino              Mã nguồn Arduino C++ nạp vào chip NodeMCU
│   └── HUONG_DAN_CHO_NGUOI_NOI_MACH.md   Hướng dẫn chi tiết nối chân DHT22, LDR, Relay & cách nạp code
│
└── esp32_cam/                            <-- DÀNH CHO CAMERA ESP32-CAM
    ├── esp32cam_firmware.ino             Mã nguồn Arduino C++ nạp vào chip ESP32-CAM
    └── HUONG_DAN_CHO_NGUOI_NOI_MACH.md   Hướng dẫn nối chân nạp code FTDI & cấu hình camera OV2640
```

---

## 🚀 Hướng dẫn Cho Bạn Phụ trách Phần cứng

1. **Mạch cảm biến & Relay bơm (NodeMCU v2.0.0):**
   - Đọc hướng dẫn nối dây: [HUONG_DAN_CHO_NGUOI_NOI_MACH.md](./nodemcu_v2/HUONG_DAN_CHO_NGUOI_NOI_MACH.md).
   - Nạp mã nguồn: [nodemcu_firmware.ino](./nodemcu_v2/nodemcu_firmware.ino).
   - *Sơ đồ chân tóm tắt:* DHT22 chân `D4`, Quang trở chân `A0`, Relay Bơm chân `D1`.

2. **Mạch Camera quét bệnh lá (ESP32-CAM AI-Thinker):**
   - Đọc hướng dẫn nạp code: [HUONG_DAN_CHO_NGUOI_NOI_MACH.md](./esp32_cam/HUONG_DAN_CHO_NGUOI_NOI_MACH.md).
   - Nạp mã nguồn: [esp32cam_firmware.ino](./esp32_cam/esp32cam_firmware.ino).
   - *Lưu ý quan trọng:* Khi nạp code qua mạch FTDI, cần nối chân `IO0` xuống `GND`. Nạp xong rút dây và bấm nút Reset.
