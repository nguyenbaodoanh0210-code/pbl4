
#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <time.h>

// ========================================================================================================
// 1. CẤU HÌNH MẠNG & ĐỊNH DANH THIẾT BỊ
// ========================================================================================================
const char* WIFI_SSID        = "ESP32";
const char* WIFI_PASSWORD    = "12345678";

const char* SERVER_IP        = "192.168.137.1";
const int   SERVER_PORT      = 8000;

const char* GREENHOUSE_ID    = "garden-outdoor-01";
const char* SENSOR_DEVICE_ID = "NODEMCU-CHILI-01";
const char* CAMERA_DEVICE_ID = "ESP32CAM-CHILI-01";
const char* DEVICE_TOKEN     = "UP/maSoJ2+8pkBbYUiXqs5h/7cSqw5WvK2yaSaFw8jh6EMvMZuNrGfu5s+hyt8qG";

// MQTT Broker & Topics
const char* MQTT_BROKER      = "test.mosquitto.org";
const int   MQTT_PORT        = 1883;
const char* TOPIC_SENSORS    = "smart_greenhouse/24T_Nhat1/sensors";
const char* TOPIC_CAMERA_CMD = "smart_garden/garden-outdoor-01/camera/cmd";
const char* TOPIC_PUMP_CMD   = "smart_garden/garden-outdoor-01/control";

const unsigned long SEND_INTERVAL_MS   = 15000; // Gửi cảm biến mỗi 15 giây
const unsigned long STREAM_INTERVAL_MS = 100;   // ~10 FPS cho Live Stream mượt mà

// ========================================================================================================
// 2. SƠ ĐỒ CHÂN PHẦN CỨNG (ESP32-S3 N16R8)
// ========================================================================================================
#define PIN_DHT              21     // Có thể đổi sang 14, 21, 47 hoặc 48 (tránh GPIO 4 của Camera)
#define DHT_TYPE             DHT22  // Đổi thành DHT11 nếu dùng cảm biến màu xanh dương
#define PIN_SOIL             1      // Cảm biến độ ẩm đất (ADC1_CH0)
#define PIN_LDR              2      // Cảm biến ánh sáng LDR (ADC1_CH1)

const int SOIL_DRY_ADC       = 4095;
const int SOIL_WET_ADC       = 1300;

// Chân Camera ESP32-S3 N16R8 (chiếm GPIO 4-13 và 15-18)
#define PWDN_GPIO_NUM        -1
#define RESET_GPIO_NUM       -1
#define XCLK_GPIO_NUM        15
#define SIOD_GPIO_NUM        4
#define SIOC_GPIO_NUM        5
#define Y9_GPIO_NUM          16
#define Y8_GPIO_NUM          17
#define Y7_GPIO_NUM          18
#define Y6_GPIO_NUM          12
#define Y5_GPIO_NUM          10
#define Y4_GPIO_NUM          8
#define Y3_GPIO_NUM          9
#define Y2_GPIO_NUM          11
#define VSYNC_GPIO_NUM       6
#define HREF_GPIO_NUM        7
#define PCLK_GPIO_NUM        13

#define FLASH_LED_PIN        -1     // Tắt Flash LED để nhường GPIO 2 cho cảm biến ánh sáng

// ========================================================================================================
// 3. BIẾN TOÀN CỤC
// ========================================================================================================
DHT dht(PIN_DHT, DHT_TYPE);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

WiFiServer streamServer(81);
WiFiClient activeStreamClient;      // Giữ kết nối MJPEG không chặn (non-blocking)

unsigned long lastSendTime   = 0;
unsigned long lastFrameTime  = 0;
bool cameraReady = false;
bool ntpSynced   = false;

// ========================================================================================================
// 4. ĐỒNG BỘ THỜI GIAN THỰC NTP (ISO 8601 UTC)
// ========================================================================================================
void syncTimeNTP() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov", "time.google.com");
  Serial.print(F("[NTP] Dang dong bo thoi gian UTC"));
  struct tm timeinfo;
  for (int i = 0; i < 15; i++) {
    if (getLocalTime(&timeinfo, 500)) {
      ntpSynced = true;
      Serial.println(F(" -> THANH CONG!"));
      return;
    }
    Serial.print(F("."));
  }
  Serial.println(F(" -> Chua dong bo duoc, se thu lai sau."));
}

bool getIsoTimestamp(char* outBuf, size_t bufSize) {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 200)) return false;
  strftime(outBuf, bufSize, "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return true;
}

// ========================================================================================================
// 5. KHỞI TẠO CAMERA
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

  if (psramFound()) {
    config.frame_size   = FRAMESIZE_SVGA;    
    config.jpeg_quality = 10;
    config.fb_count     = 2;
    config.grab_mode    = CAMERA_GRAB_LATEST;
  } else {
    config.frame_size   = FRAMESIZE_VGA;
    config.jpeg_quality = 16;
    config.fb_count     = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAMERA] Khoi tao THAT BAI! Ma loi: 0x%x\n", err);
    return false;
  }
  Serial.println(F("[CAMERA] Khoi tao camera THANH CONG!"));
  return true;
}

// ========================================================================================================
// 6. KẾT NỐI WI-FI
// ========================================================================================================
void setupWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

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
    Serial.print(F("[WiFi] IP ESP32-S3: "));
    Serial.println(WiFi.localIP());
    Serial.print(F("[LIVE STREAM] Dan dia chi nay vao Web: http://"));
    Serial.print(WiFi.localIP());
    Serial.println(F(":81/stream"));
    if (!ntpSynced) syncTimeNTP();
  } else {
    Serial.println(F("\n[WiFi] Khong ket noi duoc Wi-Fi, se thu lai sau..."));
  }
}

// ========================================================================================================
// 7. LIVE STREAM MJPEG KHÔNG CHẶN (NON-BLOCKING) TRÊN CỔNG 81
// ========================================================================================================
void handleLiveStream() {
  if (!cameraReady) return;

  // Chấp nhận trình duyệt mới kết nối vào cổng 81
  WiFiClient incoming = streamServer.available();
  if (incoming) {
    if (activeStreamClient && activeStreamClient.connected()) {
      activeStreamClient.stop();
    }
    activeStreamClient = incoming;
    activeStreamClient.setTimeout(1);

    // Đọc bỏ HTTP request header từ trình duyệt
    unsigned long t0 = millis();
    while (activeStreamClient.connected() && millis() - t0 < 200) {
      if (activeStreamClient.available()) {
        String line = activeStreamClient.readStringUntil('\n');
        if (line == "\r" || line.length() == 0) break;
      }
    }

    // Trả header chuẩn MJPEG Stream (multipart/x-mixed-replace)
    activeStreamClient.print(
      "HTTP/1.1 200 OK\r\n"
      "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
      "Access-Control-Allow-Origin: *\r\n"
      "Cache-Control: no-cache, no-store, must-revalidate\r\n"
      "Connection: close\r\n\r\n"
    );
    Serial.println(F("[STREAM] Trinh duyet da ket noi xem video truc tiep!"));
  }

  // Gửi đều đặn từng khung hình (~10 FPS) mà không chặn loop()
  if (activeStreamClient && activeStreamClient.connected()) {
    unsigned long now = millis();
    if (now - lastFrameTime >= STREAM_INTERVAL_MS) {
      lastFrameTime = now;
      camera_fb_t* fb = esp_camera_fb_get();
      if (fb) {
        String partHeader =
          "--frame\r\n"
          "Content-Type: image/jpeg\r\n"
          "Content-Length: " + String(fb->len) + "\r\n\r\n";
        size_t w1 = activeStreamClient.print(partHeader);
        size_t w2 = activeStreamClient.write(fb->buf, fb->len);
        size_t w3 = activeStreamClient.print("\r\n");
        esp_camera_fb_return(fb);
        if (w1 == 0 || w2 == 0 || w3 == 0) {
          activeStreamClient.stop();
        }
      }
    }
  } else if (activeStreamClient) {
    activeStreamClient.stop();
  }
}

// ========================================================================================================
// 8. CHỤP ẢNH & GỬI HTTP POST LÊN FASTAPI (/api/camera/diagnose)
// ========================================================================================================
bool captureAndUploadImage() {
  if (!cameraReady) {
    Serial.println(F("[CAMERA] Bo qua lenh chup vi camera chua san sang."));
    return false;
  }

  Serial.println(F("\n[CHUP ANH] >>> Bat dau chup anh theo lenh tu Web... <<<"));

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println(F("[LOI] Khong lay duoc frame anh tu camera!"));
    return false;
  }
  Serial.printf("[CHUP ANH] Da chup xong! Kich thuoc: %u bytes\n", fb->len);

  WiFiClient uploadClient;
  Serial.printf("[HTTP] Ket noi toi Web Server %s:%d ...\n", SERVER_IP, SERVER_PORT);
  if (!uploadClient.connect(SERVER_IP, SERVER_PORT)) {
    Serial.println(F("[LOI] Khong ket noi duoc Web Server!"));
    esp_camera_fb_return(fb);
    return false;
  }

  String boundary = "----ESP32CamBoundarySmartGarden";

  String head = "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"file\"; filename=\"leaf_scan.jpg\"\r\n";
  head += "Content-Type: image/jpeg\r\n\r\n";

  String tail = "\r\n--" + boundary + "\r\n";
  tail += "Content-Disposition: form-data; name=\"device_id\"\r\n\r\n";
  tail += String(CAMERA_DEVICE_ID) + "\r\n";
  tail += "--" + boundary + "--\r\n";

  size_t totalLen = head.length() + fb->len + tail.length();

  uploadClient.print(String("POST /api/camera/diagnose HTTP/1.1\r\n") +
                     "Host: " + SERVER_IP + ":" + SERVER_PORT + "\r\n" +
                     "User-Agent: ESP32-S3-AllInOne\r\n" +
                     "X-Device-Token: " + DEVICE_TOKEN + "\r\n" +
                     "Content-Type: multipart/form-data; boundary=" + boundary + "\r\n" +
                     "Content-Length: " + totalLen + "\r\n" +
                     "Connection: close\r\n\r\n");

  uploadClient.print(head);
  uploadClient.write(fb->buf, fb->len);
  uploadClient.print(tail);

  esp_camera_fb_return(fb);

  Serial.println(F("[HTTP] Dang cho phan hoi tu AI..."));
  unsigned long timeout = millis();
  while (uploadClient.connected() && millis() - timeout < 10000) {
    if (uploadClient.available()) {
      String line = uploadClient.readStringUntil('\n');
      if (line.startsWith("HTTP/1.1 200") || line.startsWith("HTTP/1.1 201")) {
        Serial.println(F("[HTTP] >>> GUI ANH & CHAN DOAN AI THANH CONG! <<<"));
        break;
      }
    }
  }
  uploadClient.stop();
  return true;
}

// ========================================================================================================
// 9. ĐỌC CẢM BIẾN (DHT22 + ĐỘ ẨM ĐẤT + ÁNH SÁNG) & GỬI MQTT
// ========================================================================================================
void readAndSendSensorData() {
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();

  if (isnan(humidity) || isnan(temperature)) {
    Serial.printf("[CANH BAO] Khong doc duoc DHT22 tren GPIO %d! Kiem tra day cam.\n", PIN_DHT);
    return;
  }

  int rawSoil = analogRead(PIN_SOIL);
  float soilMoisture = ((float)(SOIL_DRY_ADC - rawSoil) * 100.0f) / (float)(SOIL_DRY_ADC - SOIL_WET_ADC);
  soilMoisture = constrain(soilMoisture, 0.0f, 100.0f);

  int rawLdr = analogRead(PIN_LDR);
  float lightLux = (float)rawLdr * (60000.0f / 4095.0f);

  char isoTs[32];
  if (!getIsoTimestamp(isoTs, sizeof(isoTs))) {
    syncTimeNTP();
    if (!getIsoTimestamp(isoTs, sizeof(isoTs))) {
      Serial.println(F("[NTP] Chua co thoi gian UTC nen tam bo qua goi tin nay."));
      return;
    }
  }

  Serial.printf("[CAM BIEN] T: %.1f C | H: %.1f %% | Dat: %.1f %% (ADC=%d) | Sang: %d Lux (ADC=%d)\n",
                temperature, humidity, soilMoisture, rawSoil, (int)lightLux, rawLdr);

  StaticJsonDocument<384> doc;
  doc["device_token"]  = DEVICE_TOKEN;
  doc["device_id"]     = SENSOR_DEVICE_ID;
  doc["timestamp"]     = isoTs;
  doc["temperature"]   = serialized(String(temperature, 1));
  doc["humidity"]      = serialized(String(humidity, 1));
  doc["soil_moisture"] = serialized(String(soilMoisture, 1));
  doc["light_level"]   = (int)lightLux;

  char jsonBuffer[384];
  serializeJson(doc, jsonBuffer);

  if (mqttClient.publish(TOPIC_SENSORS, jsonBuffer)) {
    Serial.println(F("[MQTT] Da gui du lieu cam bien thanh cong!"));
  } else {
    Serial.println(F("[MQTT] Loi gui du lieu cam bien!"));
  }
}

// ========================================================================================================
// 10. XỬ LÝ LỆNH NHẬN TỪ MQTT
// ========================================================================================================
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  char message[320];
  if (length >= sizeof(message)) length = sizeof(message) - 1;
  memcpy(message, payload, length);
  message[length] = '\0';

  StaticJsonDocument<320> doc;
  if (deserializeJson(doc, message)) return;

  if (strcmp(topic, TOPIC_CAMERA_CMD) == 0) {
    const char* action = doc["command"] | doc["action"];
    const char* targetDevice = doc["device_id"];
    if (action && (strcmp(action, "CAPTURE") == 0 || strcmp(action, "TRIGGER") == 0)) {
      if (!targetDevice || strlen(targetDevice) == 0 || strcmp(targetDevice, CAMERA_DEVICE_ID) == 0) {
        captureAndUploadImage();
      }
    }
    return;
  }

  if (strcmp(topic, TOPIC_PUMP_CMD) == 0) {
    bool isOn = doc["is_on"] | false;
    const char* mode = doc["control_mode"] | "UNKNOWN";
    Serial.printf("[BOM NUOC - MO PHONG] mode=%s, trang thai=%s\n", mode, isOn ? "BAT" : "TAT");
  }
}

void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print(F("[MQTT] Dang ket noi toi Broker... "));
    String clientId = "ESP32S3-AllInOne-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(F("THANH CONG!"));
      mqttClient.subscribe(TOPIC_CAMERA_CMD);
      mqttClient.subscribe(TOPIC_PUMP_CMD);
    } else {
      Serial.printf("That bai (rc=%d) -> Thu lai sau 3s...\n", mqttClient.state());
      delay(3000);
      if (WiFi.status() != WL_CONNECTED) setupWiFi();
    }
  }
}

// ========================================================================================================
// 11. SETUP & LOOP
// ========================================================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("\n=========================================================="));
  Serial.println(F("   ESP32-S3 ALL-IN-ONE: LIVE STREAM + AI + CAM BIEN"));
  Serial.println(F("=========================================================="));

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  dht.begin();

  cameraReady = initCamera();

  setupWiFi();
  mqttClient.setBufferSize(512);
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttMessage);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) setupWiFi();
  if (!mqttClient.connected()) reconnectMQTT();
  mqttClient.loop();


  // Gửi cảm biến định kỳ mỗi 15 giây
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS || lastSendTime == 0) {
    lastSendTime = now;
    readAndSendSensorData();
  }
}
