#include <Arduino.h>
#include "DHT.h"
#include "config.h"

// Khởi tạo đối tượng cảm biến DHT22
DHT dht(DHTPIN, DHTTYPE);

// Khai báo các hàm xử lý
void processAndDisplayData(float temp, float hum, int soilRaw, int soilPercent);
void checkWeatherAlerts(float temp, float hum, int soilPercent);
void sendDataToPython(float temp, float hum, int soilPercent);

void setup() {
  // Khởi tạo Serial Debug
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("\n=========================================================="));
  Serial.println(F(" PHÂN TÍCH VÀ ĐỀ XUẤT PHÂN BÓN CHO CÂY TRỒNG DỰA TRÊN DỮ LIỆU THỰC TẾ"));
  Serial.println(F("==========================================================\n"));

  // Khởi động cảm biến DHT22
  dht.begin();

  // Đặt độ phân giải bộ đọc Analog ADC của ESP32-S3 lên 12-bit (0 - 4095)
  analogReadResolution(12);
}

void loop() {
  // 1. Đọc thông số nhiệt độ và độ ẩm không khí từ DHT22
  float temp_air = dht.readTemperature();
  float hum_air = dht.readHumidity();

  // 2. Đọc giá trị tín hiệu Analog thô từ Cảm biến độ ẩm đất V2.0.0
  int soil_raw = analogRead(SOIL_PIN);

  // 3. Quy đổi giá trị ADC thô sang phần trăm độ ẩm đất (%)
  int soil_percent = map(soil_raw, SOIL_DRY_ADC, SOIL_WET_ADC, 0, 100);
  soil_percent = constrain(soil_percent, 0, 100); // Giới hạn giá trị từ 0% đến 100%

  // 4. Kiểm tra xem cảm biến DHT22 có đọc dữ liệu thành công hay không
  if (isnan(temp_air) || isnan(hum_air)) {
    Serial.println(F("[LỖI PHẦN CỨNG]: Không thể đọc dữ liệu từ cảm biến DHT22!"));
    Serial.println(F(" -> Vui lòng kiểm tra lại dây cắm chân DHTPIN và dải nguồn 3.3V/5V/GND.\n"));
    delay(2000);
    return;
  }

  // 5. In kết quả đo đạc thực tế lên Serial Monitor (Dành cho con người xem)
  processAndDisplayData(temp_air, hum_air, soil_raw, soil_percent);

  // 6. Phân tích kịch bản và đưa ra cảnh báo thời tiết khắc nghiệt
  checkWeatherAlerts(temp_air, hum_air, soil_percent);

  // 7. Gửi dữ liệu định dạng JSON qua Serial để Script Python (Mô hình AI) tiếp nhận
  sendDataToPython(temp_air, hum_air, soil_percent);

  // Đọc lại dữ liệu định kỳ mỗi 3 giây
  delay(3000);
}

/**
 * In dữ liệu đã thu thập ra màn hình Serial Monitor
 */
void processAndDisplayData(float temp, float hum, int soilRaw, int soilPercent) {
  Serial.println(F("------------------- DỮ LIỆU ĐO ĐẠC THỰC TẾ -------------------"));
  Serial.printf(" 🌡️ Nhiệt độ không khí (DHT22) : %.1f °C\n", temp);
  Serial.printf(" 💧 Độ ẩm không khí  (DHT22) : %.1f %%\n", hum);
  Serial.printf(" 📊 Tín hiệu thô ADC (V2.0.0)  : %d\n", soilRaw);
  Serial.printf(" 🌱 Độ ẩm đất thực tế (V2.0.0) : %d %%\n", soilPercent);
  Serial.println(F("-------------------------------------------------------------"));
}

/**
 * Đánh giá điều kiện môi trường và đưa ra cảnh báo khắc nghiệt đối với cây trồng
 */
void checkWeatherAlerts(float temp, float hum, int soilPercent) {
  bool isAlertTriggered = false;

  // Cảnh báo Nhiệt độ
  if (temp >= TEMP_HIGH_THRESHOLD) {
    Serial.println(F("   🔥 CẢNH BÁO [NẮNG NÓNG]: Nguy cơ héo lá & sốc nhiệt."));
    isAlertTriggered = true;
  } else if (temp <= TEMP_LOW_THRESHOLD) {
    Serial.println(F("   ❄️ CẢNH BÁO [RÉT ĐẬM]: Cây ngừng phát triển, còi cọc."));
    isAlertTriggered = true;
  }

  // Cảnh báo Độ ẩm không khí
  if (hum <= HUM_LOW_THRESHOLD) {
    Serial.println(F("   🍂 CẢNH BÁO [KHÔ HANH]: Tốc độ thoát nước qua lá rất nhanh."));
    isAlertTriggered = true;
  }

  // Cảnh báo Độ ẩm đất
  if (soilPercent <= SOIL_LOW_THRESHOLD) {
    Serial.println(F("   🏜️ CẢNH BÁO [ĐẤT KHÔ]: Cây héo gốc, cần tưới khẩn cấp."));
    isAlertTriggered = true;
  } else if (soilPercent >= SOIL_HIGH_THRESHOLD) {
    Serial.println(F("   🌊 CẢNH BÁO [NGẬP ÚNG]: Rễ thiếu oxy, nguy cơ thối rễ."));
    isAlertTriggered = true;
  }

  // Tổng kết trạng thái chung
  if (!isAlertTriggered) {
    Serial.println(F("   ✅ TRẠNG THÁI: Điều kiện môi trường đạt chuẩn, an toàn."));
  }
  
  Serial.println(F("=============================================================\n"));
}

/**
 * Gửi dữ liệu định dạng JSON để Python đọc và đưa vào mô hình AI
 */
void sendDataToPython(float temp, float hum, int soilPercent) {
  // Chuỗi JSON chứa đúng 9 biến mà mô hình AI yêu cầu
  // Giá trị N, P, K, pH, Crop_Type, Growth_Stage có thể điều chỉnh giá trị mặc định tùy dự án
  Serial.print("JSON_DATA:{\"Crop_Type\":1,\"Growth_Stage\":2,\"Temperature\":");
  Serial.print(temp, 1);
  Serial.print(",\"Humidity\":");
  Serial.print(hum, 1);
  Serial.print(",\"Soil_Moisture\":");
  Serial.print(soilPercent);
  Serial.print(",\"Soil_pH\":6.5,\"Nitrogen\":40,\"Phosphorus\":20,\"Potassium\":30}\n");
}