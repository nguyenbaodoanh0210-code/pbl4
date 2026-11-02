# Smart Greenhouse API

FastAPI backend for greenhouse telemetry and experimental plant recommendations. PostgreSQL is configured with `DATABASE_URL`; this project reuses the existing `greenhouses`, `devices`, `sensor_logs`, and `recommendations` tables and does not run schema migrations.

## Project layout

```text
api/
├── app/                 FastAPI app, database models, and AI inference
├── data/                Source datasets used for training
├── firmware/esp32/      ESP32 source currently present in the repository
├── models/              Active model artifacts and evaluation reports
│   └── legacy/           Unverified pickle files retained but never loaded
├── scripts/             Model training, simulation, and serial utilities
├── main.py              Compatibility entry point for Uvicorn
├── requirements.txt
└── requirements-vision.txt
```

## Run the API

Use the existing `api/venv` when present. Copy `.env.example` to `.env` and configure `DATABASE_URL`, `ADMIN_API_TOKEN`, and `DEVICE_INGEST_TOKEN`. `app/database.py` loads this local `.env` file; secrets are ignored by Git. Create the database and existing tables before starting the service.

From `D:\PBL4\api` in PowerShell:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Swagger/OpenAPI is at `/docs` and `/openapi.json`; liveness is at `/health`. The root `main.py` is a small compatibility shim for existing launch commands; the implementation is in `app/main.py`.

## Main API routes

- Greenhouses: `GET /api/greenhouses`, `GET /api/greenhouses/{greenhouse_id}`, `POST` and `PUT`/`DELETE` on a greenhouse. Writes require `X-Admin-Token`; deletion is refused while devices are linked.
- Devices: `GET /api/devices`, `POST /api/devices`, `PATCH /api/devices/{device_id}/status`. Writes require `X-Admin-Token`.
- Sensors: `GET /api/sensors/{device_id}/latest` and `GET /api/sensors/{device_id}?start=...&end=...&limit=...&offset=...`. Timestamps must include a timezone; page size is capped at 500.
- Recommendations: `GET /api/recommendations` with `device_id`, `status`, `limit`, and `offset` filters; `GET /api/recommendations/{rec_id}`; `PUT /api/recommendations/{rec_id}/apply`.
- Fertilizer model: `POST /api/ai/fertilizer/predict`. Send the nine model features: `Crop_Type`, `Growth_Stage`, `Temperature`, `Humidity`, `Soil_Moisture`, `Soil_pH`, `Nitrogen`, `Phosphorus`, `Potassium`. Unknown categories and numeric values outside the training range are rejected. The endpoint returns an experimental prediction and does not persist it.
- Image model: `POST /api/ai/disease/predict`. Send raw JPEG or PNG bytes with the matching `Content-Type`; maximum body size is 10 MB and maximum image size is 20 megapixels. The image is not stored. Scores are softmax outputs, not calibrated confidence values. The API returns HTTP 503 if the model or TensorFlow runtime is unavailable.

Example fertilizer request:

```json
{
  "Crop_Type": "Xa_Lach",
  "Growth_Stage": "2_Phat_Trien_Than_La",
  "Temperature": 25,
  "Humidity": 65,
  "Soil_Moisture": 60,
  "Soil_pH": 6.5,
  "Nitrogen": 100,
  "Phosphorus": 50,
  "Potassium": 120
}
```

Example image request:

```powershell
curl.exe -X POST -H "Content-Type: image/jpeg" --data-binary "@leaf.jpg" http://127.0.0.1:8000/api/ai/disease/predict
```

## MQTT and utilities

The MQTT subscriber validates the device token, device registration, timestamp, measurement ranges, and duplicate timestamps before storing telemetry. Configure `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`, optional username/password, and `MQTT_TLS` in `.env`. Each payload must carry `DEVICE_INGEST_TOKEN` as `device_token`. Use a private broker with TLS and ACLs outside demos.

From the `api` directory, run:

```powershell
.\venv\Scripts\python.exe -m app.mqtt_client
.\venv\Scripts\python.exe -m scripts.simulate_esp32
.\venv\Scripts\python.exe -m scripts.serial_ai
```

The simulator sends random demo readings and requires a registered device and configured token. The firmware file is in `firmware/esp32`; its current source expects an Arduino `config.h` and DHT library that are not included here.

## Train models

The greenhouse workbook is in `data/greenhouse/Greenhouse_Demo_Dataset.xlsx`. Train the sensor model using installed project dependencies:

```powershell
.\venv\Scripts\python.exe -m scripts.train_greenhouse_model
```

The trained artifact and evaluation report are saved under `models/`. The model is trained from demo data and does not produce validated agronomic prescriptions.

The chili image dataset is under `data/chili_plant_disease/{train,val,test}` with five balanced classes. TensorFlow is an optional CPU training dependency in `requirements-vision.txt`; install it into the existing project venv only when needed:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-vision.txt
.\venv\Scripts\python.exe -m scripts.train_disease_model --epochs 40
```

The image CNN trains from scratch without downloading pretrained weights. The model and per-class test report are saved under `models/`. The test split contains ten images per class, so metrics are experimental and should be checked against independent field images. Existing `.pkl` artifacts in `models/legacy/` have not been verified and are never loaded by the application.

## Current limitations

- The current frontend/backend setup has no user accounts or greenhouse ownership authorization.
- The fertilizer and disease models are experimental; neither output is validated field advice.
- MQTT continues to use configured demo N-P-K reference thresholds and does not run the fertilizer model.
- Firmware currently sends demo crop/stage and fixed pH/N-P-K values over Serial; these are not live measurements.
- Camera storage, FCM notifications, and database migrations are not implemented.
