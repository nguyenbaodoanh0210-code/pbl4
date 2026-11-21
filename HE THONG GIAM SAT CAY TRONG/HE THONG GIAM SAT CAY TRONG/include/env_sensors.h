#ifndef ENV_SENSORS_H
#define ENV_SENSORS_H

#include <Arduino.h>

// Cấu trúc đóng gói toàn bộ dữ liệu cảm biến môi trường
struct EnvSensorData {
  float temperature;  // Nhiệt độ không khí đã bù sai số (°C)
  float humidity;     // Độ ẩm không khí (%)
  int soilRaw;        // Giá trị ADC 12-bit thô (0 - 4095)
  int soilPercent;    // Độ ẩm đất quy đổi (0 - 100%)
  bool dhtValid;      // Trạng thái đọc hợp lệ của cảm biến DHT22
};

// Khởi tạo các chân phần cứng cảm biến môi trường
void initEnvSensors();

// Đọc và cập nhật giá trị mới nhất từ DHT22 & Cảm biến độ ẩm đất
void updateEnvSensors();

// Lấy gói dữ liệu cảm biến hiện tại
EnvSensorData getEnvSensorData();

// Xuất danh sách cảnh báo nông học dạng mảng JSON
String buildEnvAlertsJson();

// In chi tiết thông số đo và cảnh báo ra Serial Monitor
void logEnvSensorsToSerial();

#endif // ENV_SENSORS_H