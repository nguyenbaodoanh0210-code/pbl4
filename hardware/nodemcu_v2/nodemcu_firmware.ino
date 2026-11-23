// NodeMCU ESP8266: bounded relay commands, replay rejection, feedback and fresh measurements.
// Copy config.example.h to config.h, wire/calibrate adapters, test with pump power disconnected.
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Ticker.h>
#include <time.h>
#include "config.h"
#include "sensor_adapter.h"

DHT dht(D4, DHT22);
WiFiClient network;
PubSubClient mqtt(network);
Ticker lease;
volatile bool pumpOn = false;
volatile bool stopFeedbackPending = false;
String lastCommand;
String recentCommands[8];
uint8_t commandCursor = 0;
unsigned long lastAttempt = 0, lastTelemetry = 0, lastFeedback = 0;
bool feedbackPending = false;

void stopRelay() {
  digitalWrite(D1, HIGH);
  pumpOn = false;
  stopFeedbackPending = true;
}

void publishFeedback() {
  if (!mqtt.connected() || lastCommand.length() == 0) return;
  StaticJsonDocument<512> msg;
  msg["device_id"] = DEVICE_ID;
  msg["device_token"] = DEVICE_TOKEN;
  msg["command_id"] = lastCommand;
  msg["is_on"] = bool(pumpOn);
  char buffer[512];
  serializeJson(msg, buffer, sizeof(buffer));
  feedbackPending = !mqtt.publish((String("smart_garden/") + GREENHOUSE_ID + "/pump/feedback").c_str(), buffer, false);
}

void onCommand(char* topic, byte* payload, unsigned int length) {
  if (length > 1000) return;
  StaticJsonDocument<1024> msg;
  if (deserializeJson(msg, payload, length)) return;
  if (String(msg["device_id"] | "") != DEVICE_ID ||
      String(msg["greenhouse_id"] | "") != GREENHOUSE_ID ||
      String(msg["command_token"] | "") != DEVICE_TOKEN ||
      String(msg["actuator_type"] | "") != "PUMP" || !msg["is_on"].is<bool>()) return;
  String id = msg["command_id"] | "";
  if (id.length() == 0 || id.length() > 50) return;
  if (id == lastCommand) { publishFeedback(); return; } // duplicate never extends lease
  for (const auto& seen : recentCommands) if (seen == id) return;
  long now = time(nullptr), issued = msg["issued_at"] | 0L, expires = msg["expires_at"] | 0L;
  if (now < 1700000000 || issued > now + 5 || expires < now || expires - issued > 10 || expires < issued) return;
  bool requested = msg["is_on"];
  int seconds = msg["run_seconds"] | 0;
  if (requested && (!HARDWARE_VERIFIED || pumpOn || seconds < 1 || seconds > 120)) return;
  lease.detach();
  lastCommand = id;
  recentCommands[commandCursor++ % 8] = id;
  if (requested) {
    pumpOn = true;
    stopFeedbackPending = false;
    digitalWrite(D1, LOW);
    lease.once(seconds, stopRelay);
  } else {
    stopRelay();
  }
  feedbackPending = true;
  publishFeedback();
}

void setup() {
  digitalWrite(D1, HIGH);
  pinMode(D1, OUTPUT);  // off before any network operation
  Serial.begin(115200);
  dht.begin();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setSocketTimeout(2);
  mqtt.setBufferSize(1200);
  mqtt.setCallback(onCommand);
}

void loop() {
  if (pumpOn && (WiFi.status() != WL_CONNECTED || !mqtt.connected())) stopRelay();
  if (stopFeedbackPending) { stopFeedbackPending = false; feedbackPending = true; }
  if (WiFi.status() == WL_CONNECTED && !mqtt.connected() && !pumpOn && millis() - lastAttempt >= 5000) {
    lastAttempt = millis();
    if (mqtt.connect(DEVICE_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
      mqtt.subscribe((String("smart_garden/") + GREENHOUSE_ID + "/control").c_str());
      publishFeedback();
    }
  }
  mqtt.loop();
  if (feedbackPending && millis() - lastFeedback > 1000) {
    lastFeedback = millis();
    publishFeedback();
  }
  if (mqtt.connected() && millis() - lastTelemetry >= 30000) {
    lastTelemetry = millis();
    float soil = readSoilMoisturePercent();
    float lux = readCalibratedLightLux();
    float temp = dht.readTemperature(), humidity = dht.readHumidity();
    time_t now = time(nullptr);
    // Missing hardware is missing data, never zero or guessed moisture.
    if (!isfinite(soil) || !isfinite(lux) || !isfinite(temp) || !isfinite(humidity) || now < 1700000000) return;
    char timestamp[30];
    struct tm value;
    gmtime_r(&now, &value);
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &value);
    StaticJsonDocument<512> msg;
    msg["device_id"] = DEVICE_ID;
    msg["device_token"] = DEVICE_TOKEN;
    msg["timestamp"] = timestamp;
    msg["temperature"] = temp;
    msg["humidity"] = humidity;
    msg["soil_moisture"] = soil;
    msg["light_level"] = lux;
    char buffer[512];
    serializeJson(msg, buffer, sizeof(buffer));
    mqtt.publish(SENSOR_TOPIC, buffer, false);
  }
  delay(5);
}
