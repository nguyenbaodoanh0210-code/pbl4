#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include "config.h"
#include "web_ui.h"
#include "camera_sensor.h"
#include "env_sensors.h"

// --- ĐỐI TƯỢNG & BIẾN TOÀN CỤC ---
WebServer server(80);
Preferences prefs;

unsigned long lastSensorReadTime = 0;
unsigned long lastWiFiRetryTime = 0;
const unsigned long SENSOR_INTERVAL = 10000;     // Chu kỳ đọc cảm biến: 10 giây
const unsigned long WIFI_RETRY_INTERVAL = 15000; // Tự quét lại Wi-Fi sau 15 giây nếu mất mạng

const int MAX_SAVED_WIFIS = 5;
String scannedSSIDs[25];
int scannedCount = 0;

// --- NGUYÊN MẪU HÀM ---
void saveWiFiToFlash(const String& ssid, const String& pass);
bool connectToSpecificWiFi(const String& ssid, const String& pass, unsigned long timeoutMs = 12000);
bool scanAndAutoConnectWiFi();
void printNearbyWiFiToSerial();
void handleSerialCommands();
void checkBootButtonScan();
void sendCorsHeaders();
void setupApiRoutes();

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("\n=========================================================="));
  Serial.println(F("   HỆ THỐNG GIÁM SÁT CÂY TRỒNG IOT - ESP32-S3 N16R8"));
  Serial.println(F("==========================================================\n"));

  if (psramFound()) {
    Serial.printf("[OK] PSRAM sẵn sàng: %d bytes (~%.2f MB)\n", 
                  ESP.getPsramSize(), ESP.getPsramSize() / (1024.0 * 1024.0));
  } else {
    Serial.println(F("[CẢNH BÁO] Không tìm thấy PSRAM! Kiểm tra lại platformio.ini."));
  }

  // 1. Khởi tạo nút BOOT & Mô-đun cảm biến môi trường
  pinMode(BOOT_PIN, INPUT_PULLUP);
  initEnvSensors();
  Serial.println(F("[OK] Đã khởi tạo mô-đun cảm biến môi trường (DHT22 & Độ ẩm đất)."));

  // 2. Khởi tạo Mô-đun Camera OV5640
  if (initCameraSensor()) {
    Serial.println(F("[OK] Đã khởi tạo mô-đun Camera OV5640 (UXGA 1600x1200)."));
  } else {
    Serial.println(F("[CẢNH BÁO] Camera chưa phản hồi, hệ thống vẫn duy trì đo cảm biến."));
  }

  // 3. Kết nối Wi-Fi chế độ STA (tiết kiệm RAM)
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(100);

  if (!scanAndAutoConnectWiFi()) {
    Serial.println(F("\n⚠️ Chưa tìm thấy mạng Wi-Fi quen ở khu vực này."));
    printNearbyWiFiToSerial();
  } else {
    Serial.println(F(" 💡 Gõ \"scan\" vào ô bên dưới bất cứ lúc nào để đổi sang Wi-Fi khác.\n"));
  }

  // 4. Khởi động REST API Server phục vụ Web phân tích
  setupApiRoutes();
  server.begin();

  updateEnvSensors();
  logEnvSensorsToSerial();
  lastSensorReadTime = millis();
  lastWiFiRetryTime = millis();
}

void loop() {
  handleSerialCommands();
  checkBootButtonScan();

  if (WiFi.status() == WL_CONNECTED) {
    server.handleClient();
  } else if (millis() - lastWiFiRetryTime >= WIFI_RETRY_INTERVAL) {
    lastWiFiRetryTime = millis();
    Serial.println(F("[WIFI] Đang tự động quét tìm mạng Wi-Fi..."));
    scanAndAutoConnectWiFi();
  }

  if (millis() - lastSensorReadTime >= SENSOR_INTERVAL) {
    lastSensorReadTime = millis();
    updateEnvSensors();
    logEnvSensorsToSerial();
  }
}

// =========================================================================
// KHỐI REST API KẾT NỐI VỚI WEB PHÂN TÍCH & AI
// =========================================================================

void sendCorsHeaders() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void setupApiRoutes() {
  // Giao diện kiểm tra nhanh cục bộ (include/web_ui.h)
  server.on("/", HTTP_GET, []() {
    server.send_P(200, "text/html; charset=utf-8", htmlPage);
  });

  // API 1: Lấy dữ liệu cảm biến môi trường dạng JSON
  server.on("/sensors", HTTP_GET, []() {
    updateEnvSensors();
    EnvSensorData data = getEnvSensorData();
    sendCorsHeaders();

    String json = "{";
    json += "\"temp\":" + (data.dhtValid ? String(data.temperature, 1) : String("null")) + ",";
    json += "\"hum\":" + (data.dhtValid ? String(data.humidity, 1) : String("null")) + ",";
    json += "\"soil\":" + String(data.soilPercent) + ",";
    json += "\"soil_raw\":" + String(data.soilRaw) + ",";
    json += "\"camera_ready\":" + String(isCameraSensorReady() ? "true" : "false") + ",";
    json += "\"wifi_ssid\":\"" + WiFi.SSID() + "\",";
    json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
    json += "\"alerts\":" + buildEnvAlertsJson();
    json += "}";

    server.send(200, "application/json; charset=utf-8", json);
  });

  // API 2: Chụp và xuất ảnh JPEG UXGA bề mặt lá
  server.on("/capture", HTTP_GET, []() {
    sendCorsHeaders();
    if (!isCameraSensorReady()) {
      server.send(503, "text/plain", "Camera not initialized");
      return;
    }

    camera_fb_t* fb = captureLeafFrame();
    if (!fb) {
      server.send(500, "text/plain", "Camera capture failed");
      return;
    }

    server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
    server.sendHeader("Pragma", "no-cache");
    server.sendHeader("Expires", "-1");
    server.setContentLength(fb->len);
    server.send(200, "image/jpeg", "");

    WiFiClient client = server.client();
    client.write(fb->buf, fb->len);
    releaseLeafFrame(fb);
  });

  // API 3: Quét danh sách Wi-Fi xung quanh
  server.on("/scan-wifi", HTTP_GET, []() {
    sendCorsHeaders();
    int n = WiFi.scanNetworks();
    scannedCount = min(n, 25);
    String json = "[";
    for (int i = 0; i < scannedCount; i++) {
      scannedSSIDs[i] = WiFi.SSID(i);
      if (i > 0) json += ",";
      String s = scannedSSIDs[i];
      s.replace("\"", "\\\"");
      json += "{\"ssid\":\"" + s + "\",\"rssi\":" + String(WiFi.RSSI(i)) + ",\"secure\":" + String(WiFi.encryptionType(i) != WIFI_AUTH_OPEN ? "true" : "false") + "}";
    }
    json += "]";
    WiFi.scanDelete();
    server.send(200, "application/json; charset=utf-8", json);
  });

  // API 4: Đổi sang mạng Wi-Fi mới
  server.on("/connect-wifi", HTTP_GET, []() {
    sendCorsHeaders();
    if (!server.hasArg("ssid")) {
      server.send(400, "text/plain", "Missing SSID");
      return;
    }
    String newSsid = server.arg("ssid");
    String newPass = server.hasArg("pass") ? server.arg("pass") : "";

    server.send(200, "text/plain; charset=utf-8", "Switching WiFi...");
    delay(300);

    if (connectToSpecificWiFi(newSsid, newPass)) {
      saveWiFiToFlash(newSsid, newPass);
      Serial.println(F("[OK] Đã chuyển sang mạng Wi-Fi mới và lưu vào Flash!\n"));
    } else {
      scanAndAutoConnectWiFi();
    }
  });
}

// =========================================================================
// KHỐI QUẢN LÝ WI-FI STA & LỆNH SERIAL MONITOR
// =========================================================================

void saveWiFiToFlash(const String& ssid, const String& pass) {
  if (ssid.length() == 0) return;
  prefs.begin("wifi_list", false);
  for (int i = 0; i < MAX_SAVED_WIFIS; i++) {
    if (prefs.getString(("s" + String(i)).c_str(), "") == ssid) {
      prefs.putString(("p" + String(i)).c_str(), pass);
      prefs.end();
      return;
    }
  }
  for (int i = MAX_SAVED_WIFIS - 1; i > 0; i--) {
    String prevS = prefs.getString(("s" + String(i - 1)).c_str(), "");
    String prevP = prefs.getString(("p" + String(i - 1)).c_str(), "");
    if (prevS.length() > 0) {
      prefs.putString(("s" + String(i)).c_str(), prevS);
      prefs.putString(("p" + String(i)).c_str(), prevP);
    }
  }
  prefs.putString("s0", ssid);
  prefs.putString("p0", pass);
  prefs.end();
}

bool connectToSpecificWiFi(const String& ssid, const String& pass, unsigned long timeoutMs) {
  Serial.printf(" 🔄 Đang kết nối tới Wi-Fi: [%s] ", ssid.c_str());
  WiFi.disconnect(true);
  delay(100);
  WiFi.begin(ssid.c_str(), pass.c_str());

  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - startAttempt < timeoutMs)) {
    delay(400);
    Serial.print(F("."));
  }

  if (WiFi.status() == WL_CONNECTED) {
    WiFi.setSleep(false);
    Serial.println(F(" THÀNH CÔNG!"));
    Serial.print(F(" 🌐 ĐỊA CHỈ IP THIẾT BỊ IOT : http://"));
    Serial.println(WiFi.localIP());
    Serial.println(F("=========================================================="));
    return true;
  }

  Serial.println(F(" THẤT BẠI."));
  WiFi.disconnect(true);
  return false;
}

bool scanAndAutoConnectWiFi() {
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    WiFi.scanDelete();
    return false;
  }

  String savedSsid[MAX_SAVED_WIFIS], savedPass[MAX_SAVED_WIFIS];
  prefs.begin("wifi_list", true);
  for (int i = 0; i < MAX_SAVED_WIFIS; i++) {
    savedSsid[i] = prefs.getString(("s" + String(i)).c_str(), "");
    savedPass[i] = prefs.getString(("p" + String(i)).c_str(), "");
  }
  prefs.end();

  int bestIdx = -1, bestRssi = -999;
  String matchedPass = "";

  for (int i = 0; i < n; i++) {
    String foundSsid = WiFi.SSID(i);
    int rssi = WiFi.RSSI(i);

    for (int j = 0; j < MAX_SAVED_WIFIS; j++) {
      if (savedSsid[j].length() > 0 && foundSsid == savedSsid[j] && rssi > bestRssi) {
        bestIdx = i; bestRssi = rssi; matchedPass = savedPass[j];
      }
    }
    for (int k = 0; k < DEFAULT_WIFI_COUNT; k++) {
      if (foundSsid == String(DEFAULT_WIFIS[k].ssid) && rssi > bestRssi) {
        bestIdx = i; bestRssi = rssi; matchedPass = String(DEFAULT_WIFIS[k].password);
      }
    }
  }

  String targetSsid = (bestIdx != -1) ? WiFi.SSID(bestIdx) : "";
  WiFi.scanDelete();

  return (targetSsid.length() > 0) ? connectToSpecificWiFi(targetSsid, matchedPass) : false;
}

void printNearbyWiFiToSerial() {
  Serial.println(F("\n----------------- DANH SÁCH WI-FI XUNG QUANH -----------------"));
  int n = WiFi.scanNetworks();
  scannedCount = min(n, 25);

  if (scannedCount <= 0) {
    Serial.println(F(" Không tìm thấy mạng Wi-Fi nào."));
  } else {
    for (int i = 0; i < scannedCount; i++) {
      scannedSSIDs[i] = WiFi.SSID(i);
      Serial.printf("  [%d] %-25s (%d dBm) %s\n", i + 1, scannedSSIDs[i].c_str(), WiFi.RSSI(i),
                    (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "[Mở]" : "[Có mật khẩu]");
    }
    Serial.println(F("--------------------------------------------------------------"));
    Serial.println(F(" 👉 Gõ: <Số_thứ_tự> <Mật_khẩu> (VD: 1 12345678) hoặc gõ: scan"));
  }
  WiFi.scanDelete();
  Serial.println(F("--------------------------------------------------------------\n"));
}

void handleSerialCommands() {
  if (!Serial.available()) return;
  String input = Serial.readStringUntil('\n');
  input.trim();
  if (input.length() == 0) return;

  if (input.equalsIgnoreCase("scan")) {
    printNearbyWiFiToSerial();
    return;
  }

  int spaceIdx = input.indexOf(' ');
  String firstPart = (spaceIdx == -1) ? input : input.substring(0, spaceIdx);
  String passPart  = (spaceIdx == -1) ? ""    : input.substring(spaceIdx + 1);

  int choice = firstPart.toInt();
  String targetSsid = (choice >= 1 && choice <= scannedCount) ? scannedSSIDs[choice - 1] : firstPart;

  if (connectToSpecificWiFi(targetSsid, passPart)) {
    saveWiFiToFlash(targetSsid, passPart);
    Serial.println(F("[OK] Đã lưu mạng Wi-Fi mới vào bộ nhớ Flash!\n"));
  }
}

void checkBootButtonScan() {
  if (digitalRead(BOOT_PIN) == LOW) {
    unsigned long pressStart = millis();
    while (digitalRead(BOOT_PIN) == LOW) {
      if (millis() - pressStart >= 2000) {
        printNearbyWiFiToSerial();
        while (digitalRead(BOOT_PIN) == LOW) delay(50);
        return;
      }
      delay(50);
    }
  }
}