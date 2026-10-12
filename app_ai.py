import os
import sys
import time
import json
import warnings

# Khống chế/Ẩn các cảnh báo lệch phiên bản scikit-learn để màn hình sạch sẽ
warnings.filterwarnings("ignore")

import serial
import serial.tools.list_ports
import joblib
import pandas as pd

# ==============================================================================
# 1. CẤU HÌNH THÔNG SỐ BAN ĐẦU
# ==============================================================================
MODEL_PATH = os.path.join("model", "model.pkl")  # Đường dẫn tới tệp mô hình AI
BAUD_RATE = 115200                              # Tốc độ Baud (khớp với main.cpp)
COM_PORT = 'COM6'                                # Cổng COM nối với ESP32-S3

# ==============================================================================
# 2. BẢNG ÁNH XẠ MÃ DỰ ĐOÁN (MÃ SỐ -> TÊN ĐỀ XUẤT PHÂN BÓN)
# ==============================================================================
# Bạn có thể chỉnh sửa lại các câu chữ dưới đây sao cho đúng với ý nghĩa tập dữ liệu train của bạn
RECOMMENDATION_MAP = {
    0: "Không cần bón phân (Đất đã đủ dinh dưỡng)",
    1: "Đề xuất: Bón bổ sung phân NPK cân bằng",
    2: "Đề xuất: Tăng cường bón phân Đạm (Nitrogen / Urê)",
    3: "Đề xuất: Bổ sung phân Lân (Phosphorus) cho rễ",
    4: "Đề xuất: Bổ sung phân Kali (Potassium) tăng sức đề kháng",
    5: "Đề xuất: Khử chua cho đất bằng Vôi bột (Tăng pH)"
}


# ==============================================================================
# 3. HÀM TẢI MÔ HÌNH AI (MODEL.PKL)
# ==============================================================================
def load_ai_model(path):
    if not os.path.exists(path):
        print(f"❌ [LỖI]: Không tìm thấy tệp mô hình tại '{path}'.")
        print(" -> Vui lòng kiểm tra lại thư mục và tên file 'model/model.pkl'.")
        return None

    try:
        model = joblib.load(path)
        print(f"✅ [THÀNH CÔNG]: Đã nạp thành công mô hình AI từ '{path}'.")
        return model
    except Exception as e:
        print(f"❌ [LỖI]: Không thể nạp mô hình AI. Chi tiết: {e}")
        return None


# ==============================================================================
# 4. LUỒNG CHÍNH ĐỌC DỮ LIỆU CẢM BIẾN & DỰ ĐOÁN AI
# ==============================================================================
def main():
    print("=" * 65)
    print(" 🌾 HỆ THỐNG DỰ ĐOÁN & ĐỀ XUẤT PHÂN BÓN THÔNG MINH IOT - AI 🌾")
    print("=" * 65)

    # 1. Nạp mô hình AI
    model = load_ai_model(MODEL_PATH)
    if model is None:
        return

    # 2. Mở kết nối Serial với ESP32-S3
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Đợi kết nối Serial ổn định
        print(f"🔌 Đã kết nối thành công tới cổng {COM_PORT} ở tốc độ {BAUD_RATE} baud.")
        print("⏳ Đang chờ nhận dữ liệu từ cảm biến IoT...\n" + "-" * 65)
    except Exception as e:
        print(f"❌ [LỖI KẾT NỐI]: Không thể mở cổng {COM_PORT}.")
        print(" -> Hãy đảm bảo bạn đã đóng Serial Monitor trong PlatformIO.")
        return

    # 3. Vòng lặp nhận dữ liệu và đưa ra đề xuất
    while True:
        try:
            if ser.in_waiting > 0:
                # Đọc từng dòng gửi từ ESP32
                raw_line = ser.readline().decode('utf-8', errors='ignore').strip()

                # Chỉ lọc và xử lý dòng dữ liệu chứa tiền tố 'JSON_DATA:'
                if raw_line.startswith("JSON_DATA:"):
                    json_str = raw_line.replace("JSON_DATA:", "").strip()
                    
                    try:
                        # Chuyển đổi chuỗi JSON thành Dictionary Python
                        sensor_data = json.loads(json_str)
                        
                        # Chuyển dữ liệu thành DataFrame chứa đúng 9 đặc trưng mô hình yêu cầu
                        input_df = pd.DataFrame([{
                            'Crop_Type': sensor_data.get('Crop_Type', 1),
                            'Growth_Stage': sensor_data.get('Growth_Stage', 1),
                            'Temperature': sensor_data.get('Temperature'),
                            'Humidity': sensor_data.get('Humidity'),
                            'Soil_Moisture': sensor_data.get('Soil_Moisture'),
                            'Soil_pH': sensor_data.get('Soil_pH', 6.5),
                            'Nitrogen': sensor_data.get('Nitrogen', 40),
                            'Phosphorus': sensor_data.get('Phosphorus', 20),
                            'Potassium': sensor_data.get('Potassium', 30)
                        }])

                        # Đưa vào mô hình AI để đưa ra dự đoán mã số
                        raw_pred = model.predict(input_df)[0]
                        
                        # Chuyển mã số dự đoán thành câu khuyến nghị bằng tiếng Việt
                        recommendation = RECOMMENDATION_MAP.get(
                            raw_pred, 
                            f"Mã đề xuất số {raw_pred} (Chưa được định nghĩa trong RECOMMENDATION_MAP)"
                        )
                        
                        # In kết quả phân tích ra màn hình
                        timestamp = time.strftime("%H:%M:%S")
                        print(f"[{timestamp}] 📊 Dữ liệu đo đạc: Nhiệt độ = {sensor_data.get('Temperature')}°C | Độ ẩm = {sensor_data.get('Humidity')}% | Độ ẩm đất = {sensor_data.get('Soil_Moisture')}%")
                        print(f"🤖 👉 KẾT QUẢ AI DỰ ĐOÁN : [ MÃ {raw_pred} ]")
                        print(f"💡 👉 ĐỀ XUẤT XỬ LÝ    : {recommendation}")
                        print("-" * 65)

                    except json.JSONDecodeError:
                        pass
                    except Exception as err:
                        print(f"⚠️ Lỗi khi dự đoán: {err}")

        except KeyboardInterrupt:
            print("\n🛑 Đã dừng chương trình Python thành công.")
            ser.close()
            break
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Serial: {e}")
            break

if __name__ == "__main__":
    main()