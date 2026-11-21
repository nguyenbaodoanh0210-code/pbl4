# HƯỚNG DẪN NỐI DÂY & NẠP CODE CHO MODULE ESP32-CAM (AI-THINKER)

> **Tài liệu này dành riêng cho thành viên phụ trách phần cứng.**  
> File code cần nạp: [esp32cam_firmware.ino](file:///d:/DUT/HK5/PBL4-HeThongThongMinh/pbl4/hardware/esp32_cam/esp32cam_firmware.ino)

---

## 1. Dụng cụ Phần cứng Cần chuẩn bị

1. **Board mạch:** Module **ESP32-CAM AI-Thinker** (có gắn sẵn camera OV2640).
2. **Mạch nạp:**
   - **Cách 1 (Dễ nhất):** Dùng đế nạp cắm sẵn **ESP32-CAM-MB** (có cổng Micro-USB, cắm trực tiếp là nạp được ngay).
   - **Cách 2:** Dùng mạch chuyển đổi USB-to-TTL (FTDI FT232RL hoặc CP2102).
3. **Dây cắm test:** Dây cắm cái - cái.
4. **Nguồn cấp:** Cổng USB 5V (tối thiểu dòng 1A–2A để camera không bị sụt áp khi chụp).

---

## 2. Sơ đồ Chân Nối để Nạp Code (Khi dùng Mạch nạp FTDI)

| Chân trên Mạch nạp FTDI | Chân trên ESP32-CAM | Chú thích quan trọng |
| :--- | :--- | :--- |
| **VCC** (Gạt jumper sang 5V) | **5V** | Bắt buộc cấp 5V, không dùng 3.3V vì camera dễ thiếu dòng |
| **GND** | **GND** | Nối đất chung |
| **TX** | **U0R (RX)** | Chân nhận dữ liệu |
| **RX** | **U0T (TX)** | Chân gửi dữ liệu |
| *(Dây cầu nối nội bộ)* | **Nối chân IO0 với chân GND** | **BẮT BUỘC để đưa chip vào chế độ nạp Code** |

> [!CAUTION]
> **LƯU Ý CỰC KỲ QUAN TRỌNG KHI NẠP:**
> 1. Trước khi bấm nút Upload trên máy tính: **Phải cắm dây nối chân `IO0` xuống `GND`**.
> 2. Bấm nút **Reset (RST)** nhỏ ở mặt sau ESP32-CAM một cái.
> 3. Bấm nút **Upload** trên Arduino IDE.
> 4. **Sau khi nạp xong 100%:** Hãy **RÚT DÂY NỐI `IO0` KHỎI `GND`**, rồi bấm nút Reset lại một lần nữa để ESP32-CAM chuyển sang chế độ chạy thật!

---

## 3. Các bước Cài đặt & Nạp Code bằng Arduino IDE

### Bước 1: Cài đặt Board ESP32 trong Arduino IDE
1. Vào **File** ➔ **Preferences**.
2. Ở ô *Additional Boards Manager URLs*, dán thêm link:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Vào **Tools** ➔ **Board** ➔ **Boards Manager...**, tìm kiếm `esp32` (bởi Espressif Systems) và bấm **Install**.

### Bước 2: Cài đặt Thư viện cần thiết
Vào **Sketch** ➔ **Include Library** ➔ **Manage Libraries...**, cài đặt:
1. `PubSubClient` (bởi Nick O'Leary)
2. `ArduinoJson` (phiên bản v6.x)

### Bước 3: Cấu hình thông số trên Arduino IDE
Vào menu **Tools** và chọn chính xác các mục sau:
- **Board:** Chọn `AI Thinker ESP32-CAM`
- **CPU Frequency:** `240MHz (WiFi/BT)`
- **Flash Frequency:** `40MHz`
- **Flash Mode:** `QIO`
- **Partition Scheme:** `Huge APP (3MB No OTA/1MB SPIFFS)` *(Rất quan trọng để đủ bộ nhớ chứa code camera)*
- **Upload Speed:** `115200`
- **Port:** Chọn đúng cổng COM của mạch nạp.

### Bước 4: Sửa thông tin Wi-Fi và nạp Code
1. Mở file [esp32cam_firmware.ino](file:///d:/DUT/HK5/PBL4-HeThongThongMinh/pbl4/hardware/esp32_cam/esp32cam_firmware.ino).
2. Điền tên Wi-Fi và mật khẩu ở 2 dòng `WIFI_SSID` và `WIFI_PASSWORD`.
3. Điền địa chỉ IP máy chạy Web Server ở dòng `SERVER_IP` (Xem IP in ra từ file `CHAY_WEB.bat`, ví dụ: `192.168.1.8`).
4. Nối chân `IO0` xuống `GND`, bấm nút Reset trên board, rồi bấm nút **Upload** trong Arduino IDE.

---

## 4. Kiểm tra Kết quả Hoạt động
1. Rút dây `IO0` khỏi `GND` và bấm nút Reset lại mạch.
2. Mở **Serial Monitor** (tốc độ baud **`115200`**).
3. Màn hình sẽ in ra:
   ```
   [CAMERA] Khoi tao camera OV2640 THANH CONG!
   [WiFi] Ket noi THANH CONG!
   [WiFi] Dia chi IP ESP32-CAM: 192.168.1.50
   [MQTT] Da lang nghe topic lenh: smart_garden/garden-outdoor-01/camera/cmd
   ```
4. Bây giờ, bạn hoặc người quản lý web chỉ cần vào trang **"Chẩn đoán sức khỏe cây"** trên trình duyệt, bấm nút **"CHỤP ẢNH & CHẨN ĐOÁN BỆNH LÁ"**:
   - Đèn flash trên ESP32-CAM sẽ chớp sáng 1 cái.
   - Ảnh chụp thật ngoài vườn sẽ tự động gửi lên server và kết quả nhận diện nấm bệnh sẽ xuất hiện tức thì trên màn hình web!
