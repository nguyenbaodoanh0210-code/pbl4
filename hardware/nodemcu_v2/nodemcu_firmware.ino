/*
 ========================================================================================================
   ĐỀ TÀI: HỆ THỐNG GIÁM SÁT KHU VƯỜN NGOÀI TRỜI THÔNG MINH (PBL4)
   TÊN FILE: nodemcu_firmware.ino
   MỤC ĐÍCH: Mã nguồn nạp cho Vi điều khiển NodeMCU v2.0.0 (ESP8266)
   CHỨC NĂNG:
     1. Đọc dữ liệu nhiệt độ & độ ẩm không khí từ cảm biến DHT22
     2. Đọc cường độ ánh sáng từ cảm biến Quang trở (LDR)
     3. Đóng gói chuỗi JSON và gửi định kỳ lên Web Server qua MQTT
     4. Lắng nghe lệnh từ Web để đóng/ngắt Relay điều khiển Bơm nước tưới ngoài trời
 ========================================================================================================
 
 SƠ ĐỒ CHÂN CẮM CHO BẠN PHỤ TRÁCH NỐI MẠCH:
 --------------------------------------------------------------------------------------------------------
 [1] CẢM BIẾN NHIỆT ĐỘ & ĐỘ ẨM DHT22:
     - Chân VCC  --> Nối vào chân 3V3 của NodeMCU
     - Chân GND  --> Nối vào chân GND của NodeMCU
     - Chân DATA --> Nối vào chân D4 (GPIO2) của NodeMCU (Khuyến nghị gắn thêm điện trở kéo 10k lên 3V3)
 
 [2] CẢM BIẾN QUANG TRỞ ÁNH SÁNG (LDR):
     - Dùng mạch phân áp: 1 chân LDR nối 3V3, chân còn lại nối trở 10k xuống GND.
     - Điểm giữa (chân tín hiệu) --> Nối vào chân A0 (Analog ADC) của NodeMCU.
 
 [3] MẠCH RELAY ĐIỀU KHIỂN BƠM NƯỚC NGOÀI TRỜI:
     - Chân VCC  --> Nối vào chân Vin (5V) của NodeMCU
     - Chân GND  --> Nối vào chân GND của NodeMCU
     - Chân IN   --> Nối vào chân D1 (GPIO5) của NodeMCU
 ========================================================================================================
*/

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ========================================================================================================
// 1. CẤU HÌNH THÔNG SỐ (BẠN CHỈ CẦN CHỈNH SỬA KHỐI NÀY PHÙ HỢP VỚI MẠNG NHÀ BẠN)
// ========================================================================================================
const char* WIFI_SSID       = "TEN_WIFI_NHA_BAN";             // Tên mạng Wi-Fi
const char* WIFI_PASSWORD   = "MAT_KHAU_WIFI";                // Mật khẩu Wi-Fi

// Địa chỉ IP của máy tính đang chạy Web Server (Ví dụ: 192.168.1.8)
const char* SERVER_IP       = "192.168.1.8";                  
const int   MQTT_PORT       = 1883;                           // Cổng MQTT Broker (Mặc định: 1883)
const char* MQTT_BROKER     = "test.mosquitto.org";           // Hoặc dùng Broker đám mây / IP máy chủ

// Thông tin định danh thiết bị trong hệ thống Smart Garden
const char* GREENHOUSE_ID   = "garden-outdoor-01";            // Mã khu vườn
const char* DEVICE_ID       = "NODEMCU-CHILI-01";             // Mã thiết bị (Ớt: NODEMCU-CHILI-01, Xà lách: NODEMCU-LETTUCE-01)
const char* DEVICE_TOKEN    = "UP/maSoJ2+8pkBbYUiXqs5h/7cSqw5WvK2yaSaFw8jh6EMvMZuNrGfu5s+hyt8qG"; // Token xác thực bảo mật

// Các Topic MQTT gửi nhận
const char* TOPIC_SENSORS   = "smart_greenhouse/24T_Nhat1/sensors";
const char* TOPIC_PUMP_CMD  = "smart_garden/garden-outdoor-01/control";

// Chu kỳ gửi dữ liệu đo (Mili-giây, ví dụ: 30000ms = 30 giây)
const unsigned long SEND_INTERVAL_MS = 30000;

// Định nghĩa chân phần cứng
#define PIN_DHT             D4    // Chân tín hiệu DHT22 (GPIO2)
#define PIN_LDR             A0    // Chân Analog đọc Quang trở (ADC0)
#define PIN_RELAY_PUMP      D1    // Chân điều khiển Relay Bơm (GPIO5)
#define DHT_TYPE            DHT22 // Loại cảm biến: DHT22

// ========================================================================================================
// 2. KHỞI TẠO ĐỐI TƯỢNG VÀ BIẾN TOÀN CỤC
// ========================================================================================================
DHT dht(PIN_DHT, DHT_TYPE);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastSendTime = 0;
bool isPumpOn = false;

// ========================================================================================================
// 3. HÀM KẾT NỐI WI-FI
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
    Serial.print(F("[WiFi] Dia chi IP cua NodeMCU: "));
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println(F("[WiFi] Khong the ket noi Wi-Fi, se thu lai sau..."));
  }
}

// ========================================================================================================
// 4. HÀM XỬ LÝ KHI NHẬN LỆNH TỪ WEB (ĐIỀU KHIỂN BƠM NƯỚC)
// ========================================================================================================
void onMqttMessageReceived(char* topic, byte* payload, unsigned int length) {
  Serial.print(F("\n[MQTT] Nhan lenh tu topic: "));
  Serial.println(topic);

  // Chuyển payload byte sang chuỗi
  char message[256];
  if (length >= sizeof(message)) length = sizeof(message) - 1;
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.print(F("[MQTT] Noi dung lenh: "));
  Serial.println(message);

  // Phân tích chuỗi JSON
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, message);
  if (err) {
    Serial.print(F("[JSON] Loi giai ma lenh: "));
    Serial.println(err.c_str());
    return;
  }

  // Đọc trường action (ON / OFF) hoặc state (1 / 0)
  const char* action = doc["action"];
  if (action != nullptr) {
    if (strcmp(action, "ON") == 0 || strcmp(action, "TURN_ON") == 0) {
      digitalWrite(PIN_RELAY_PUMP, LOW); // Relay kich LOW: Bật bơm
      isPumpOn = true;
      Serial.println(F("[BOM NUOC] >>> DA BAT BOM NUOC TUOI NGOAI TROI <<<"));
    } else if (strcmp(action, "OFF") == 0 || strcmp(action, "TURN_OFF") == 0) {
      digitalWrite(PIN_RELAY_PUMP, HIGH); // Relay ngắt HIGH: Tắt bơm
      isPumpOn = false;
      Serial.println(F("[BOM NUOC] >>> DA TAT BOM NUOC <<<"));
    }
  }
}

// ========================================================================================================
// 5. HÀM KẾT NỐI VÀ DUY TRÌ MQTT BROKER
// ========================================================================================================
void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print(F("[MQTT] Dang ket noi toi Broker: "));
    Serial.print(MQTT_BROKER);
    Serial.print(F("... "));

    String clientId = "NodeMCU-Client-" + String(ESP.getChipId(), HEX);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(F("THANH CONG!"));
      // Đăng ký nhận lệnh điều khiển máy bơm
      mqttClient.subscribe(TOPIC_PUMP_CMD);
      Serial.print(F("[MQTT] Da lang nghe topic lenh: "));
      Serial.println(TOPIC_PUMP_CMD);
    } else {
      Serial.print(F("That bai, ma loi rc="));
      Serial.print(mqttClient.state());
      Serial.println(F(" -> Thu lai sau 3 giay..."));
      delay(3000);
      if (WiFi.status() != WL_CONNECTED) setupWiFi();
    }
  }
}

// ========================================================================================================
// 6. HÀM ĐỌC CẢM BIẾN & GỬI DỮ LIỆU LÊN WEB SERVER
// ========================================================================================================
void readAndSendSensorData() {
  // Đọc nhiệt độ và độ ẩm từ DHT22
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature(); // Độ C

  // Kiểm tra lỗi cảm biến DHT22
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println(F("[CANH BAO] Khong doc duoc du lieu tu cam bien DHT22! Kiem tra day cam chan D4."));
    return;
  }

  // Đọc giá trị quang trở (LDR) từ chân A0 (Khoảng giá trị ADC: 0 - 1023)
  int rawLdr = analogRead(PIN_LDR);
  // Quy đổi ước tính sang đơn vị Lux ngoài trời (0 đến 60000 Lux)
  float lightLux = (float)rawLdr * (60000.0 / 1023.0);

  Serial.println(F("\n----------------------------------------------------------"));
  Serial.print(F("[THONG SO DO DUOC] Nhiet do: "));
  Serial.print(temperature, 1);
  Serial.print(F(" °C | Do am: "));
  Serial.print(humidity, 1);
  Serial.print(F(" % | Anh sang: "));
  Serial.print((int)lightLux);
  Serial.println(F(" Lux"));

  // Đóng gói JSON gửi lên Web Server
  StaticJsonDocument<300> doc;
  doc["device_token"] = DEVICE_TOKEN;
  doc["device_id"]    = DEVICE_ID;
  doc["temperature"]  = serialized(String(temperature, 1));
  doc["humidity"]     = serialized(String(humidity, 1));
  doc["light_level"]  = (int)lightLux;

  char jsonBuffer[300];
  serializeJson(doc, jsonBuffer);

  // Xuất bản gói tin MQTT lên Topic cảm biến
  if (mqttClient.publish(TOPIC_SENSORS, jsonBuffer)) {
    Serial.println(F("[MQTT] Da gui du lieu len Web Server thanh cong!"));
  } else {
    Serial.println(F("[MQTT] Loi gui du lieu MQTT!"));
  }
  Serial.println(F("----------------------------------------------------------"));
}

// ========================================================================================================
// 7. HÀM SETUP (CHẠY 1 LẦN KHI KHỞI ĐỘNG MẠCH)
// ========================================================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("\n=========================================================="));
  Serial.println(F("   HE THONG GIAM SAT KHU VUON NGOAI TROI THONG MINH"));
  Serial.println(F("          KHOI DONG VI DIEU KHIEN NODEMCU"));
  Serial.println(F("=========================================================="));

  // Cấu hình chân Relay: ngắt ban đầu (Relay 5V thường kích mức LOW)
  pinMode(PIN_RELAY_PUMP, OUTPUT);
  digitalWrite(PIN_RELAY_PUMP, HIGH); // Mặc định tắt máy bơm khi mới bật nguồn

  // Khởi động cảm biến DHT22
  dht.begin();

  // Kết nối Wi-Fi và cấu hình MQTT
  setupWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMqttMessageReceived);
}

// ========================================================================================================
// 8. HÀM LOOP (CHẠY LẶP VÔ TẬN)
// ========================================================================================================
void loop() {
  // Duy trì kết nối Wi-Fi & MQTT
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  // Kiểm tra chu kỳ để gửi dữ liệu định kỳ
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS || lastSendTime == 0) {
    lastSendTime = now;
    readAndSendSensorData();
  }
}
