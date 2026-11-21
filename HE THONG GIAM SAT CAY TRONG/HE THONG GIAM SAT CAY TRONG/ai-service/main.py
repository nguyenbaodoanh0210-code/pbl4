import io
import keras
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Khởi tạo ứng dụng API
app = FastAPI(title="Image Classification AI Service")

# Cho phép Frontend (Web/App) từ domain khác gọi tới API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Khi đưa lên thực tế, hãy thay "*" bằng domain web của bạn
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Tải mô hình một lần duy nhất khi khởi động server
MODEL_PATH = "plant_disease_model.keras"
model = keras.models.load_model(MODEL_PATH)

# 2. Thay thế danh sách này bằng tên 5 nhãn thực tế lúc bạn huấn luyện mô hình (đúng thứ tự 0 -> 4)
CLASS_NAMES = [
    "Bacterial",
    "fungal",
    "healthy",
    "ot_dom_vi_khuan",
    "ot_khoe_manh"
]

def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Chuyển đổi dữ liệu ảnh thô thành định dạng chuẩn của MobileNetV2 (224x224, dải 0-255)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((224, 224))
    
    # Lưu ý: Giữ nguyên dải giá trị [0, 255] vì bên trong model.keras đã có sẵn lớp Rescaling
    img_array = np.array(img, dtype=np.float32)
    img_array = np.expand_dims(img_array, axis=0)  # Shape: (1, 224, 224, 3)
    return img_array

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # Kiểm tra định dạng tệp gửi lên
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Tệp tải lên phải là hình ảnh.")
    
    try:
        # Đọc ảnh và tiền xử lý
        image_bytes = await file.read()
        processed_img = preprocess_image(image_bytes)
        
        # Chạy dự đoán
        predictions = model.predict(processed_img)
        scores = predictions[0]
        
        predicted_index = int(np.argmax(scores))
        confidence = float(np.max(scores))
        
        # Trả về kết quả JSON
        return {
            "status": "success",
            "predicted_class": CLASS_NAMES[predicted_index],
            "confidence_percent": round(confidence * 100, 2),
            "details": {
                CLASS_NAMES[i]: round(float(scores[i]) * 100, 2) 
                for i in range(len(CLASS_NAMES))
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý mô hình: {str(e)}")