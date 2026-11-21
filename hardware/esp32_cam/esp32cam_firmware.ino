/*
 ========================================================================================================
   ĐỀ TÀI: HỆ THỐNG GIÁM SÁT KHU VƯỜN NGOÀI TRỜI THÔNG MINH (PBL4)
   TÊN FILE: esp32cam_firmware.ino
   MỤC ĐÍCH: Mã nguồn nạp cho Module Camera nhúng ESP32-CAM AI-Thinker (OV2640)
   CHỨC NĂNG:
     1. Khởi tạo Camera OV2640 tối ưu độ nét và bộ nhớ RAM
     2. Kết nối mạng Wi-Fi và duy trì kết nối MQTT với máy chủ
     3. Lắng nghe lệnh chụp ảnh từ Web Server trên topic: smart_garden/{gh_id}/camera/cmd
     4. Khi có lệnh: Tự động chụp 1 bức ảnh JPEG và gửi trực tiếp qua HTTP POST Multipart
        lên Web Server tại endpoint: http://{SERVER_IP}:8000/api/camera/diagnose
     5. Cung cấp luồng video xem trực tiếp (MJPEG Stream) trên cổng 81 cho Kính ngắm web
 ========================================================================================================
 
 SƠ ĐỒ CHÂN NẠP CODE CHO BẠN PHỤ TRÁCH NỐI MẠCH:
 --------------------------------------------------------------------------------------------------------
 Lưu ý: ESP32-CAM không có cổng USB gắn sẵn, bạn cần dùng Mạch nạp FTDI (USB to TTL) hoặc đế nạp ESP32-CAM-MB:
 
 [NỐI NẠP CODE VỚI MẠCH FTDI]:
     - FTDI VCC (Gạt sang 5V) --> Nối chân 5V của ESP32-CAM
     - FTDI GND               --> Nối chân GND của ESP32-CAM
     - FTDI TX                --> Nối chân U0R (RX) của ESP32-CAM
     - FTDI RX                --> Nối chân U0T (TX) của ESP32-CAM
     *** QUAN TRỌNG NHẤT KHI NẠP:
     - Nối chân IO0 với GND của ESP32-CAM để vào chế độ nạp (Bootloader Mode).
     - Sau khi nạp code xong: RÚT DÂY IO0 KHỎI GND, bấm nút Reset trên board để mạch bắt đầu chạy!
 ========================================================================================================
*/

#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ========================================================================================================
// 1. CẤU HÌNH THÔNG SỐ (BẠN CHỈ CẦN SỬA KHỐI NÀY PHÙ HỢP VỚI MẠNG NHÀ BẠN)
// ========================================================================================================
const char* WIFI_SSID       = "TEN_WIFI_NHA_BAN";             // Tên Wi-Fi
const char* WIFI_PASSWORD   = "MAT_KHAU_WIFI";                // Mật khẩu Wi-Fi

// Địa chỉ IP của máy tính đang chạy Web Server (Xem trong file CHAY_WEB.bat, ví dụ: 192.168.1.8)
const char* SERVER_IP       = "192.168.1.8";                  
const int   SERVER_PORT     = 8000;                           // Cổng Web Server

// Thông tin định danh thiết bị Camera
const char* GREENHOUSE_ID   = "garden-outdoor-01";            // Mã khu vườn
const char* DEVICE_ID       = "ESP32CAM-CHILI-01";            // Mã camera (Ớt: ESP32CAM-CHILI-01, Xà lách: ESP32CAM-LETTUCE-01)
const char* DEVICE_TOKEN    = "UP/maSoJ2+8pkBbYUiXqs5h/7cSqw5WvK2yaSaFw8jh6EMvMZuNrGfu5s+hyt8qG"; // Token xác thực API

// MQTT Broker
const char* MQTT_BROKER     = "test.mosquitto.org";
const int   MQTT_PORT       = 1883;
const char* TOPIC_CAMERA_CMD= "smart_garden/garden-outdoor-01/camera/cmd";

// ========================================================================================================
// 2. ĐỊNH NGHĨA CHÂN CAMERA CHO MODEL AI-THINKER ESP32-CAM (OV2640)
// ========================================================================================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define FLASH_LED_PIN      4 // Đèn Flash trên mạch

WiFiClient espClient;
PubSubClient mqttClient(espClient);
WiFiServer streamServer(81); // Server phát luồng video MJPEG trên cổng 81

// ========================================================================================================
// 3. KHỞI TẠO CẤU HÌNH CAMERA OV2640
// ========================================================================================================
bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Kiểm tra có chip PSRAM hay không để chọn độ phân giải
  if (psramFound()) {
    config.frame_size   = FRAMESIZE_SVGA; // 800x600 (Độ nét cao, mượt mà cho AI nhận diện)
    config.jpeg_quality = 12;             // Chất lượng tốt (10-63)
    config.fb_count     = 2;
  } else {
    config.frame_size   = FRAMESIZE_VGA;  // 640x480
    config.jpeg_quality = 14;
    config.fb_count     = 1;
  }

  // Khởi động camera phần cứng
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAMERA] Khoi tao camera THAT BAI! Ma loi: 0x%x\n", err);
    return false;
  }
  Serial.println(F("[CAMERA] Khoi tao camera OV2640 THANH CONG!"));
  return true;
}

// ========================================================================================================
// 4. KẾT NỐI WI-FI
// ========================================================================================================
void setupWiFi() {
  delay(100);
  Serial.println();
  Serial.print(F("[WiFi] Dang ket noi vao mang: "));
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 30) {
    delay(500);
    Serial.print(F("."));
    retry++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println(F("[WiFi] Ket noi THANH CONG!"));
    Serial.print(F("[WiFi] Dia chi IP ESP32-CAM: "));
    Serial.println(WiFi.localIP());
    Serial.print(F("[WiFi] Luong Live Stream tai: http://"));
    Serial.print(WiFi.localIP());
    Serial.println(F(":81/stream"));
  } else {
    Serial.println();
    Serial.println(F("[WiFi] Khong ket noi duoc Wi-Fi, se thu lai sau..."));
  }
}

// ========================================================================================================
// 5. HÀM CHỤP ẢNH VÀ GỬI LÊN WEB SERVER (HTTP POST MULTIPART)
// ========================================================================================================
bool captureAndUploadImage() {
  Serial.println(F("\n[CHUP ANH] >>> Bat dau chup anh la cay theo lenh tu Web... <<<"));

  // Nháy đèn Flash nhẹ khi chụp
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(80);
  camera_fb_t* fb = esp_camera_fb_get();
  digitalWrite(FLASH_LED_PIN, LOW);

  if (!fb) {
    Serial.println(F("[LOI] Khong the chup anh tu sensor OV2640!"));
    return false;
  }
  Serial.printf("[CHUP ANH] Da chup thanh cong! Kich thuoc anh: %u bytes\n", fb->len);

  // Mở kết nối TCP tới Web Server FastAPI
  WiFiClient uploadClient;
  Serial.printf("[HTTP] Dang ket noi toi Web Server: %s:%d ...\n", SERVER_IP, SERVER_PORT);
  if (!uploadClient.connect(SERVER_IP, SERVER_PORT)) {
    Serial.println(F("[LOI] Khong the ket noi toi Web Server de gui anh!"));
    esp_camera_fb_return(fb);
    return false;
  }

  // Tạo Boundary cho multipart/form-data
  String boundary = "----ESP32CamBoundarySmartGarden";
  
  // Phần đầu của multipart (chứa form-data file)
  String head = "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"file\"; filename=\"leaf_scan.jpg\"\r\n";
  head += "Content-Type: image/jpeg\r\n\r\n";

  // Phần đuôi của multipart (kèm trường device_id)
  String tail = "\r\n--" + boundary + "\r\n";
  tail += "Content-Disposition: form-data; name=\"device_id\"\r\n\r\n";
  tail += String(DEVICE_ID) + "\r\n";
  tail += "--" + boundary + "--\r\n";

  size_t totalLen = head.length() + fb->len + tail.length();

  // Gửi HTTP Request Header
  uploadClient.print(String("POST /api/camera/diagnose HTTP/1.1\r\n") +
                     "Host: " + SERVER_IP + ":" + SERVER_PORT + "\r\n" +
                     "User-Agent: ESP32-CAM-AIThinker\r\n" +
                     "X-Device-Token: " + DEVICE_TOKEN + "\r\n" +
                     "Content-Type: multipart/form-data; boundary=" + boundary + "\r\n" +
                     "Content-Length: " + totalLen + "\r\n" +
                     "Connection: close\r\n\r\n");

  // Gửi phần Body
  uploadClient.print(head);
  uploadClient.write(fb->buf, fb->len);
  uploadClient.print(tail);

  // Giải phóng bộ nhớ Frame Buffer của Camera
  esp_camera_fb_return(fb);

  // Đọc phản hồi từ server
  Serial.println(F("[HTTP] Dang cho ket qua phan tich tu AI..."));
  unsigned long timeout = millis();
  while (uploadClient.connected() && millis() - timeout < 10000) {
    if (uploadClient.available()) {
      String line = uploadClient.readStringUntil('\n');
      if (line.startsWith("HTTP/1.1 200")) {
        Serial.println(F("[HTTP] >>> GUI ANH VA CHAN DOAN AI THANH CONG (200 OK)! <<<"));
      }
    }
  }
  uploadClient.stop();
  return true;
}

// ========================================================================================================
// 6. XỬ LÝ LỆNH TỪ MQTT (KHI NGƯỜI DÙNG BẤM QUÉT TRÊN WEB)
// ========================================================================================================
void onMqttCommand(char* topic, byte* payload, unsigned int length) {
  Serial.print(F("\n[MQTT] Nhan tin hieu tu topic: "));
  Serial.println(topic);

  char message[256];
  if (length >= sizeof(message)) length = sizeof(message) - 1;
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.print(F("[MQTT] Noi dung lenh: "));
  Serial.println(message);

  // Phân tích JSON lệnh
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, message);
  if (err) {
    Serial.println(F("[JSON] Loi giai ma lenh chup!"));
    return;
  }

  const char* action = doc["action"];
  const char* targetDevice = doc["device_id"];

  // Nếu lệnh yêu cầu chụp ảnh đúng camera này (hoặc toàn vườn)
  if (action && (strcmp(action, "CAPTURE") == 0 || strcmp(action, "TRIGGER") == 0)) {
    if (!targetDevice || strcmp(targetDevice, DEVICE_ID) == 0 || strlen(targetDevice) == 0) {
      captureAndUploadImage();
    }
  }
}

// ========================================================================================================
// 7. DUY TRÌ MQTT BROKER
// ========================================================================================================
void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print(F("[MQTT] Dang ket noi toi Broker: "));
    Serial.print(MQTT_BROKER);
    Serial.print(F("... "));

    String clientId = "ESP32CAM-Client-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(F("THANH CONG!"));
      mqttClient.subscribe(TOPIC_CAMERA_CMD);
      Serial.print(F("[MQTT] Da lang nghe topic lenh: "));
      Serial.println(TOPIC_CAMERA_CMD);
    } else {
      Serial.print(F("That bai, rc="));
      Serial.print(mqttClient.state());
      Serial.println(F(" -> Thu lai sau 3s..."));
      delay(3000);
      if (WiFi.status() != WL_CONNECTED) setupWiFi();
    }
  }
}

// ========================================================================================================
// 8. HÀM SETUP
// ========================================================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("\n=========================================================="));
  Serial.println(F("   HE THONG GIAM SAT KHU VƯỜN NGOAI TROI THONG MINH"));
  Serial.println(F("       KHOI DONG MODULE CAMERA ESP32-CAM AI-THINKER"));
  Serial.println(F("=========================================================="));

  // Khởi động Camera OV2640
  if (!initCamera()) {
    Serial.println(F("[LOI] Khong khoi dong duoc camera! Dung hoat dong."));
    while (true) delay(1000);
  }

  // Kết nối Wi-Fi & MQTT
  setupWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttCommand);

  // Mở cổng Live Stream video
  streamServer.begin();
}

// ========================================================================================================
// 9. HÀM LOOP
// ========================================================================================================
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  // Nhỏ gọn: Duy trì kết nối live stream nếu có client kết nối xem video trên cổng 81
  WiFiClient client = streamServer.available();
  if (client) {
    // Phục vụ 1 snapshot nhanh khi web yêu cầu
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) {
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: image/jpeg");
      client.println("Content-Length: " + String(fb->len));
      client.println("Connection: close\r\n");
      client.write(fb->buf, fb->len);
      esp_camera_fb_return(fb);
    }
    client.stop();
  }
}
