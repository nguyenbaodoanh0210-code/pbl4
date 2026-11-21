# HƯỚNG DẪN NỐI DÂY & NẠP CODE CHO VI ĐIỀU KHIỂN NODEMCU (V2.0.0)

> **Tài liệu này dành riêng cho thành viên phụ trách phần cứng.**  
> File code cần nạp: [nodemcu_firmware.ino](file:///d:/DUT/HK5/PBL4-HeThongThongMinh/pbl4/hardware/nodemcu_v2/nodemcu_firmware.ino)

---

## 1. Danh sách Linh kiện Phần cứng Cần chuẩn bị

1. **Board mạch:** NodeMCU v2.0.0 (ESP8266 ESP-12E / CP2102 hoặc CH340).
2. **Cảm biến:**
   - 01 Cảm biến nhiệt độ & độ ẩm **DHT22** (màu trắng).
   - 01 Cảm biến ánh sáng **Quang trở LDR** kèm 01 điện trở 10kΩ (hoặc Module quang trở 3 chân có sẵn phân áp).
3. **Bộ điều khiển bơm:**
   - 01 Module **Relay 5V 1 kênh** (hoặc 2 kênh) để đóng ngắt máy bơm mini.
   - 01 Máy bơm nước mini 5V/12V ngoài trời.
4. **Dây cắm test:** Dây cắm đực - cái, đực - đực.
5. **Dây cáp Micro-USB:** Loại có truyền dữ liệu (data).

---

## 2. Sơ đồ Nối Dây Chi Tiết (Pinout Table)

### A. Nối Cảm biến DHT22 (Nhiệt độ & Độ ẩm):
| Chân trên DHT22 | Chân trên NodeMCU | Chú thích |
| :--- | :--- | :--- |
| **VCC** (Chân 1) | **3V3** | Nguồn 3.3V (hoặc 5V nếu dùng module có sẵn trở) |
| **DATA** (Chân 2)| **D4 (GPIO2)** | Chân truyền tín hiệu dữ liệu |
| **NC** (Chân 3)  | *Bỏ trống* | Không dùng |
| **GND** (Chân 4) | **GND** | Chân nối đất |

*(Mẹo: Nếu dùng cảm biến DHT22 rời 4 chân, nối 1 trở 4.7kΩ hoặc 10kΩ giữa chân VCC và DATA để ổn định tín hiệu).*

---

### B. Nối Cảm biến Quang trở Ánh sáng (LDR):
* **Nếu bạn dùng Module Quang trở 3 chân (đã có sẵn biến trở và 3 chân VCC, GND, DO/AO):**
  - Chân **VCC** ➔ Nối chân **3V3** của NodeMCU.
  - Chân **GND** ➔ Nối chân **GND** của NodeMCU.
  - Chân **AO (Analog Out)** ➔ Nối chân **A0** của NodeMCU.

* **Nếu bạn dùng Quang trở LDR dạng 2 chân rời:**
  - 1 chân của LDR nối vào **3V3**.
  - Chân còn lại của LDR nối vào chân **A0** của NodeMCU, đồng thời nối qua 1 điện trở 10kΩ xuống **GND**.

---

### C. Nối Module Relay Điều Khiển Bơm Nước:
| Chân trên Relay | Chân trên NodeMCU | Chú thích |
| :--- | :--- | :--- |
| **VCC** | **Vin (5V)** | Cấp nguồn 5V cho cuộn hút relay |
| **GND** | **GND** | Nối đất chung |
| **IN**  | **D1 (GPIO5)** | Tín hiệu kích đóng/ngắt bơm từ NodeMCU |

*Đầu ra của Relay (Chân COM và NO): Nối tiếp vào nguồn cấp của máy bơm nước mini.*

---

## 3. Các bước Cài đặt & Nạp Code bằng Arduino IDE

### Bước 1: Cài đặt Board ESP8266 trong Arduino IDE (nếu chưa có)
1. Mở Arduino IDE ➔ Vào **File** ➔ **Preferences**.
2. Ở ô *Additional Boards Manager URLs*, dán link:
   ```
   http://arduino.esp8266.com/stable/package_esp8266com_index.json
   ```
3. Bấm **OK**.
4. Vào **Tools** ➔ **Board** ➔ **Boards Manager...**, tìm kiếm `esp8266` và bấm **Install**.

### Bước 2: Cài đặt 3 Thư viện cần thiết
Vào **Sketch** ➔ **Include Library** ➔ **Manage Libraries...**, tìm và cài đặt:
1. `DHT sensor library` (bởi Adafruit) — cài kèm *Adafruit Unified Sensor* khi được hỏi.
2. `PubSubClient` (bởi Nick O'Leary) — dùng giao tiếp MQTT.
3. `ArduinoJson` (bởi Benoit Blanchon) — dùng phiên bản **v6.x**.

### Bước 3: Cấu hình thông tin mạng trong file code
Mở file [nodemcu_firmware.ino](file:///d:/DUT/HK5/PBL4-HeThongThongMinh/pbl4/hardware/nodemcu_v2/nodemcu_firmware.ino):
- Điền đúng `WIFI_SSID` (Tên Wi-Fi) và `WIFI_PASSWORD` (Mật khẩu Wi-Fi).
- Điền `SERVER_IP` (Địa chỉ IP của máy đang bật Web Server, xem trong file `CHAY_WEB.bat`).

### Bước 4: Nạp Code vào NodeMCU
1. Cắm dây USB kết nối NodeMCU với máy tính.
2. Vào menu **Tools**:
   - **Board:** Chọn `NodeMCU 1.0 (ESP-12E Module)`.
   - **Upload Speed:** Chọn `115200` (hoặc `921600` để nạp nhanh).
   - **Port:** Chọn đúng cổng COM của mạch (Ví dụ: COM3, COM4,...).
3. Bấm nút **Upload (Mũi tên chỉ sang phải)** để nạp code.

---

## 4. Kiểm tra Kết quả Hoạt động
1. Sau khi nạp xong, bấm mở **Serial Monitor** (hình kính lúp góc trên bên phải) trong Arduino IDE.
2. Chọn tốc độ baud là **`115200`**.
3. Màn hình sẽ in ra:
   ```
   [WiFi] Dang ket noi vao mang...
   [WiFi] Ket noi THANH CONG! IP: 192.168.1.x
   [MQTT] Dang ket noi toi Broker... THANH CONG!
   [THONG SO DO DUOC] Nhiet do: 28.5 °C | Do am: 72.0 % | Anh sang: 35000 Lux
   [MQTT] Da gui du lieu len Web Server thanh cong!
   ```
4. Mở trình duyệt Web tại máy bạn (`http://localhost:8000`), thông số nhiệt ẩm ngoài vườn sẽ tự động nhảy số theo dữ liệu thật vừa đo!
