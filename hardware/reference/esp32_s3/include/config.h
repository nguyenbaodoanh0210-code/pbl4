#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// =========================================================================
// 1. SƠ ĐỒ CHÂN CẢM BIẾN & NÚT BẤM (Không trùng chân Camera 4-13, 15-18)
// =========================================================================
#define DHTPIN          3       // GPIO 3: Cảm biến nhiệt độ & độ ẩm DHT22
#define DHTTYPE         DHT22   // Loại cảm biến DHT22
#define SOIL_PIN        1       // GPIO 1 (ADC1_CH0): Cảm biến độ ẩm đất v2.0
#define BOOT_PIN        0       // GPIO 0: Nút nhấn BOOT trên mạch

// =========================================================================
// 2. SƠ ĐỒ CHÂN CAMERA OV5640 (CHUẨN FREENOVE ESP32-S3 N16R8)
// =========================================================================
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     15
#define SIOD_GPIO_NUM     4
#define SIOC_GPIO_NUM     5
#define Y9_GPIO_NUM       16
#define Y8_GPIO_NUM       17
#define Y7_GPIO_NUM       18
#define Y6_GPIO_NUM       12
#define Y5_GPIO_NUM       10
#define Y4_GPIO_NUM       8
#define Y3_GPIO_NUM       9
#define Y2_GPIO_NUM       11
#define VSYNC_GPIO_NUM    6
#define HREF_GPIO_NUM     7
#define PCLK_GPIO_NUM     13

// =========================================================================
// 3. DANH SÁCH WI-FI DỰ PHÒNG MẶC ĐỊNH
// =========================================================================
struct WiFiCredential {
  const char* ssid;
  const char* password;
};

const WiFiCredential DEFAULT_WIFIS[] = {
  {"ESP32", "12345678"},
  {"iPhone", "12345678"}
};
const int DEFAULT_WIFI_COUNT = sizeof(DEFAULT_WIFIS) / sizeof(DEFAULT_WIFIS[0]);

// =========================================================================
// 4. HẰNG SỐ HIỆU CHỈNH & NGƯỠNG CẢNH BÁO NÔNG HỌC (XÀ LÁCH & ỚT)
// =========================================================================
const float TEMP_OFFSET = 4.3;  // Khử bù nhiệt lượng tỏa ra từ mạch ESP32-S3
const int SOIL_DRY_ADC  = 4095; // Giá trị ADC khi đất khô hoàn toàn
const int SOIL_WET_ADC  = 1300; // Giá trị ADC khi cắm vào nước

const float TEMP_HIGH_THRESHOLD = 32.0; // Nhiệt độ cao (>32°C)
const float TEMP_LOW_THRESHOLD  = 18.0; // Nhiệt độ thấp (<18°C)
const float HUM_LOW_THRESHOLD   = 50.0; // Độ ẩm không khí thấp (<50%)
const int SOIL_LOW_THRESHOLD    = 30;   // Độ ẩm đất thấp (<30%)
const int SOIL_HIGH_THRESHOLD   = 85;   // Độ ẩm đất ngập úng (>85%)

#endif // CONFIG_H