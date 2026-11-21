#ifndef CAMERA_SENSOR_H
#define CAMERA_SENSOR_H

#include <Arduino.h>
#include "esp_camera.h"

// Khởi tạo phần cứng Camera OV5640
bool initCameraSensor();

// Kiểm tra trạng thái sẵn sàng của Camera
bool isCameraSensorReady();

// Chụp và trả về con trỏ bộ đệm ảnh JPEG bề mặt lá
camera_fb_t* captureLeafFrame();

// Giải phóng bộ đệm ảnh trong PSRAM sau khi gửi xong
void releaseLeafFrame(camera_fb_t* fb);

#endif // CAMERA_SENSOR_H