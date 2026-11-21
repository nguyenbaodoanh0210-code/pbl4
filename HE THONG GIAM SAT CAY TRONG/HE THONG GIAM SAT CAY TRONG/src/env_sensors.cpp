#include "env_sensors.h"
#include "config.h"
#include <DHT.h>

static DHT dht(DHTPIN, DHTTYPE);
static EnvSensorData currentData = {NAN, NAN, 0, 0, false};
static uint8_t dhtFailCount = 0;

void initEnvSensors() {
  pinMode(DHTPIN, INPUT_PULLUP);
  dht.begin();

  analogReadResolution(12);
  pinMode(SOIL_PIN, INPUT);
}

void updateEnvSensors() {
  float rawTemp = dht.readTemperature();
  float rawHum = dht.readHumidity();

  if (!isnan(rawTemp) && !isnan(rawHum)) {
    currentData.temperature = rawTemp - TEMP_OFFSET;
    currentData.humidity = rawHum;
    currentData.dhtValid = true;
    dhtFailCount = 0;
  } else {
    // Chỉ báo lỗi nếu đọc hụt liên tiếp 3 chu kỳ (tránh báo giả do xung đột ngắt Wi-Fi)
    if (dhtFailCount < 3) {
      dhtFailCount++;
    } else {
      currentData.temperature = NAN;
      currentData.humidity = NAN;
      currentData.dhtValid = false;
    }
  }

  currentData.soilRaw = analogRead(SOIL_PIN);
  int mappedSoil = map(currentData.soilRaw, SOIL_DRY_ADC, SOIL_WET_ADC, 0, 100);
  currentData.soilPercent = constrain(mappedSoil, 0, 100);
}

EnvSensorData getEnvSensorData() {
  return currentData;
}

String buildEnvAlertsJson() {
  String alerts = "[";
  bool first = true;

  auto addAlert = [&](const String& msg) {
    if (!first) alerts += ",";
    alerts += "\"" + msg + "\"";
    first = false;
  };

  if (currentData.dhtValid) {
    if (currentData.temperature >= TEMP_HIGH_THRESHOLD) {
      addAlert("Nắng nóng (>32°C): Nguy cơ sốc nhiệt & héo lá");
    } else if (currentData.temperature <= TEMP_LOW_THRESHOLD) {
      addAlert("Rét đậm (<18°C): Cây chậm phát triển");
    }

    if (currentData.humidity <= HUM_LOW_THRESHOLD) {
      addAlert("Không khí khô hanh (<50%): Thoát hơi nước nhanh");
    }
  }

  if (currentData.soilPercent <= SOIL_LOW_THRESHOLD) {
    addAlert("Đất khô (<30%): Cần tưới nước khẩn cấp");
  } else if (currentData.soilPercent >= SOIL_HIGH_THRESHOLD) {
    addAlert("Đất ngập úng (>85%): Nguy cơ thiếu oxy & thối rễ");
  }

  alerts += "]";
  return alerts;
}

void logEnvSensorsToSerial() {
  Serial.println(F("------------------- DỮ LIỆU CẢM BIẾN MÔI TRƯỜNG -------------------"));
  if (!currentData.dhtValid) {
    Serial.println(F(" [LỖI DHT22]: Kiểm tra dây DATA tại GPIO 3 (hoặc thử đổi sang GPIO 2)."));
  } else {
    Serial.printf(" 🌡️ Nhiệt độ không khí : %.1f °C\n", currentData.temperature);
    Serial.printf(" 💧 Độ ẩm không khí   : %.1f %%\n", currentData.humidity);
  }
  Serial.printf(" 📊 Tín hiệu thô ADC   : %d\n", currentData.soilRaw);
  Serial.printf(" 🌱 Độ ẩm đất thực tế : %d %%\n", currentData.soilPercent);

  if (currentData.dhtValid) {
    if (currentData.temperature >= TEMP_HIGH_THRESHOLD) {
      Serial.println(F(" ⚠️ CẢNH BÁO [NẮNG NÓNG]: Tăng nguy cơ héo lá & sốc nhiệt."));
    } else if (currentData.temperature <= TEMP_LOW_THRESHOLD) {
      Serial.println(F(" ⚠️ CẢNH BÁO [RÉT ĐẬM]: Cây hãm tăng trưởng."));
    }
    if (currentData.humidity <= HUM_LOW_THRESHOLD) {
      Serial.println(F(" ⚠️ CẢNH BÁO [KHÔ HANH]: Tốc độ thoát nước qua lá rất nhanh."));
    }
  }

  if (currentData.soilPercent <= SOIL_LOW_THRESHOLD) {
    Serial.println(F(" ⚠️ CẢNH BÁO [ĐẤT KHÔ]: Cần bổ sung nước tưới khẩn cấp."));
  } else if (currentData.soilPercent >= SOIL_HIGH_THRESHOLD) {
    Serial.println(F(" ⚠️ CẢNH BÁO [NGẬP ÚNG]: Rễ thiếu oxy, nguy cơ thối rễ."));
  }
  Serial.println(F("-------------------------------------------------------------------\n"));
}