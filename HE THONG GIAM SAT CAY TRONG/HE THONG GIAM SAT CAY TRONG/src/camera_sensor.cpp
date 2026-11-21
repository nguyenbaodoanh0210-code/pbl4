#include "camera_sensor.h"
#include "config.h"

static bool cameraReady = false;

bool initCameraSensor() {
  // BẮT BUỘC: Khởi tạo = {} để đưa toàn bộ trường ẩn (như sccb_i2c_port) về 0, tránh giá trị rác gây lỗi 0xffffffff
  camera_config_t config = {};

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_SVGA;     // 800x600: Truyền ảnh nhanh, vẫn rõ đốm bệnh & gân lá
  config.jpeg_quality = 16;
  config.fb_count = 2;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[LỖI CAMERA] Khởi tạo OV5640 thất bại! Mã lỗi esp_err: 0x%x\n", err);
    cameraReady = false;
    return false;
  }

  sensor_t* s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_whitebal(s, 1);       // Tự động cân bằng trắng
    s->set_awb_gain(s, 1);       // Bù lợi cân bằng trắng
    s->set_exposure_ctrl(s, 1);  // Tự động phơi sáng
  }

  cameraReady = true;
  return true;
}

bool isCameraSensorReady() {
  return cameraReady;
}

camera_fb_t* captureLeafFrame() {
  if (!cameraReady) {
    return nullptr;
  }
  return esp_camera_fb_get();
}

void releaseLeafFrame(camera_fb_t* fb) {
  if (fb != nullptr) {
    esp_camera_fb_return(fb);
  }
}