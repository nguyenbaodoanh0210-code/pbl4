# Smart Greenhouse API

FastAPI backend for greenhouse telemetry and experimental plant recommendations. PostgreSQL is configured with `DATABASE_URL`; this project reuses its existing tables. SQL migrations are applied manually and never run automatically by the API.

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

Use the existing `api/venv` when present. Copy `.env.example` to `.env` and configure `DATABASE_URL`, `AUTH_TOKEN_SECRET`, and `DEVICE_INGEST_TOKEN`. Set `AUTH_TOKEN_SECRET` to at least 32 random bytes; generate one in PowerShell with:

```powershell
$bytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
[Convert]::ToBase64String($bytes)
```

Put the resulting value in the local `.env` file. `app/database.py` loads it; secrets are ignored by Git. Create the database and existing tables before starting the service. Apply `migrations/20261102_authentication_and_greenhouse_ownership.sql` once before using account or owner-scoped routes:

```powershell
$databaseUrl = (Get-Content .\.env | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1).Substring(13)
$psqlUrl = $databaseUrl.Replace("postgresql+psycopg2://", "postgresql://")
psql $psqlUrl --set=ON_ERROR_STOP=1 --file .\migrations\20261102_authentication_and_greenhouse_ownership.sql
Remove-Variable databaseUrl, psqlUrl
```

The migration adds a nullable password hash and owner reference/index without deleting or assigning existing data. If legacy duplicate emails exist, resolve them before applying the unique case-insensitive email index. Existing greenhouses remain unassigned; an administrator should map them to the correct `user_id` after accounts are created.

Public registration always creates `FARMER`. To grant an account administrator access, a database administrator must set its role explicitly, for example: `UPDATE public.users SET role = 'ADMIN' WHERE lower(btrim(email)) = lower(btrim('admin@example.com'));`. Do not add an API that lets users promote their own role.

For a ready-to-use local demo account, apply the seed after the migration. Convert SQLAlchemy's driver URL for `psql`:

```powershell
$databaseUrl = (Get-Content .\.env | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1).Substring(13)
$psqlUrl = $databaseUrl.Replace("postgresql+psycopg2://", "postgresql://")
psql $psqlUrl --set=ON_ERROR_STOP=1 --file .\data\demo_user_seed.sql
Remove-Variable databaseUrl, psqlUrl
```

Sign in with **`demo@smartgreenhouse.local`** and **`Demo@12345678`**. The seed stores only a salted PBKDF2 password hash, creates a `FARMER`, and never updates a conflicting account. This credential is for local demo use only; replace it before using a shared or deployed environment.

For a local demo account, set `DEMO_MODE=true` in `.env`, optionally set `DEMO_USER_EMAIL`, apply the migration, then run:

```powershell
.\venv\Scripts\python.exe -m scripts.seed_demo_user
```

Without extra arguments, the interactive script creates a `FARMER` with your chosen password, stores only the hash, and refuses to replace an existing account.

### Complete synthetic dataset for the existing demo account

To populate every current database table for `DEMO_USER_EMAIL` (default `demo@smartgreenhouse.local`), reuse the same seed script. The account must already exist. Run from the `api` directory in the existing venv:

```powershell
$env:DEMO_MODE = "true"
.\venv\Scripts\python.exe -X utf8 -m scripts.seed_demo_user --with-data --dry-run
.\venv\Scripts\python.exe -X utf8 -m scripts.seed_demo_user --with-data
Remove-Item Env:DEMO_MODE
```

The dry run checks actual PostgreSQL constraints and rolls back. The real run writes the full dataset in one transaction. IDs are stable per demo user; rerunning inserts missing records without duplicating or overwriting existing records. Login credentials are preserved. Only missing phone/FCM fields on this demo account are filled with obvious, nonfunctional placeholders. No FCM or MQTT messages are sent.

| Table | Demo rows | Contents |
| --- | ---: | --- |
| `users` | 1 existing account | Full profile, existing password hash, fake phone/FCM placeholders |
| `crops` | 9 | 3 crops × 3 synthetic growth-stage reference configurations |
| `greenhouses` | 3 | Owned by the demo user, with area and fictional location |
| `greenhouse_areas` | 6 | 2 beds per greenhouse, total bed area equals greenhouse area |
| `devices` | 12 | 6 sensors and 6 cameras; active/offline examples, battery and send interval |
| `sensor_logs` | 2,016 | 336 samples per sensor: 7 days at 30-minute intervals, all 7 measurements |
| `recommendations` | 36 | PENDING, APPLIED and IGNORED examples linked to beds/devices |
| `camera_logs` | 18 | References to existing local chili dataset images |
| `notifications` | 36 | INFO/WARNING/CRITICAL examples with all related references filled |

Every column is populated for these fixtures, including nullable columns. Notifications use READ/RESOLVED so `read_at` is meaningful and filled. Records are marked `[DEMO]` or have deterministic `demo-...` IDs. Sensor values, crop references and recommendation statuses are synthetic; they are not training data or agronomic advice. `dosage=0` g/m² means no fertilizer dose has been prescribed. N/P/K examples use the frontend's mg/kg convention; device `send_interval` is in seconds.

Camera `image_url` values are URL-encoded paths relative to `api/`, pointing to existing dataset files; no new image-serving endpoint is added. These are reference photos, not captures from the simulated greenhouse. `ai_diagnosis` explicitly says no model was run; `confidence_score=0` is a placeholder, not a measured probability. The image records remain NEW. The fake FCM token cannot deliver notifications.

Timestamps are generated in UTC and adapted to the existing column types. Legacy timestamp-without-time-zone columns store UTC values; timezone-aware columns retain the offset. Repeated runs keep the original fixture timestamps and edited statuses. No schema, real records, passwords or owners are replaced.

From `D:\PBL4\api` in PowerShell:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Swagger/OpenAPI is at `/docs` and `/openapi.json`; liveness is at `/health`. The root `main.py` is a small compatibility shim for existing launch commands; the implementation is in `app/main.py`.

### Troubleshoot frontend API errors

If `DATABASE_URL` still contains placeholder credentials, run the interactive setup in the existing venv:

```powershell
.\venv\Scripts\python.exe -X utf8 -m scripts.configure_database
```

It reuses the PostgreSQL host, port, database and username from a non-placeholder `DATABASE_URL`, or the single PostgreSQL connection in workspace SQLTools settings. Enter the PostgreSQL password in the terminal; it is hidden and is never sent in command arguments or printed. The script checks `SELECT 1` before saving only `DATABASE_URL` in the local `.env`, safely encoding special characters in the password. Failed validation leaves `.env` unchanged. It does not create tables, change database passwords, or run migrations. Restart the API after success. In VS Code, use **Terminal → Run Task → Configure PostgreSQL** if the task is available. To check the current configuration without changing it, add `--check`.

The frontend server proxies `/api/*` and `/health` to `http://127.0.0.1:8000` by default and forwards the bearer token. Check both the process and the database:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod 'http://127.0.0.1:5173/health?check_database=true'
```

`/health` only checks the API process. Add `check_database=true` to execute `SELECT 1`; success includes `"database": "ok"`. HTTP 502 from the frontend means it cannot reach the API. HTTP 503 with `code=DATABASE_UNAVAILABLE` means the API cannot connect to PostgreSQL: configure real credentials/database in the local `.env` `DATABASE_URL` (do not leave `USER:PASSWORD`), check PostgreSQL is running, and restart the API after configuration changes. HTTP 503 with `code=DATABASE_SCHEMA_NOT_READY` means the connected database is missing a table/column/schema; review and apply the existing migrations. Database errors return a safe JSON `detail` that the frontend displays, without connection strings or SQL parameters. Seed demo credentials only after the database connection and authentication migration work.

## Main API routes

- Accounts: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, and `PATCH /api/auth/me`. Registration creates a `FARMER` account; it cannot grant the `ADMIN` role. Passwords are PBKDF2-HMAC-SHA256 hashes and are never returned by the API. Login returns a one-hour HS256 bearer token. Send it on protected requests as `Authorization: Bearer <access_token>`.
- Greenhouses: `GET /api/greenhouses`, `GET /api/greenhouses/{greenhouse_id}`, `POST`, and `PUT`/`DELETE` on a greenhouse require login. Farmers can see/manage their own records; database users with role `ADMIN` can access all. Newly created greenhouses belong to the logged-in user. Deletion is refused while devices are linked.
- Devices: `GET /api/devices`, `POST /api/devices`, and `PATCH /api/devices/{device_id}/status` require login and are scoped to the user's greenhouses; `ADMIN` can manage all.
- Sensors: `GET /api/sensors/{device_id}/latest` and `GET /api/sensors/{device_id}?start=...&end=...&limit=...&offset=...` require access to the device's greenhouse. Timestamps must include a timezone; page size is capped at 500.
- Recommendations: `GET /api/recommendations` with `device_id`, `status`, `limit`, and `offset` filters; `GET /api/recommendations/{rec_id}`; `PUT /api/recommendations/{rec_id}/apply` require login and only return/update recommendations linked to the user's greenhouse. `ADMIN` can access all records.
- Fertilizer model: `POST /api/ai/fertilizer/predict`. Send the nine model features: `Crop_Type`, `Growth_Stage`, `Temperature`, `Humidity`, `Soil_Moisture`, `Soil_pH`, `Nitrogen`, `Phosphorus`, `Potassium`. Unknown categories and numeric values outside the training range are rejected. The endpoint returns an experimental prediction and does not persist it.
- Image model: `POST /api/ai/disease/predict`. Send raw JPEG or PNG bytes with the matching `Content-Type`; maximum body size is 10 MB and maximum image size is 20 megapixels. The image is not stored. Scores are softmax outputs, not calibrated confidence values. The API returns HTTP 503 if the model or TensorFlow runtime is unavailable.

Register/login requests use JSON with `full_name`, `email`, and `password` (plus optional `phone_number` on registration). Use the returned `access_token` as a bearer token:

```powershell
$body = @{ full_name = "Nông dân"; email = "farmer@example.com"; password = "a-long-demo-password-123" } | ConvertTo-Json
$session = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/register -ContentType application/json -Body $body
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/greenhouses -Headers @{ Authorization = "Bearer $($session.access_token)" }
```

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

- Existing greenhouse records with a NULL `user_id` are intentionally hidden from farmer accounts until an administrator assigns ownership; `ADMIN` can still review them.
- The frontend login/register forms use the account routes and send bearer tokens through the frontend proxy. Login and account data require a configured PostgreSQL connection and the authentication migration.
- The fertilizer and disease models are experimental; neither output is validated field advice.
- MQTT continues to use configured demo N-P-K reference thresholds and does not run the fertilizer model.
- Firmware currently sends demo crop/stage and fixed pH/N-P-K values over Serial; these are not live measurements.
- Camera storage and FCM notifications are not implemented. The SQL migrations are manual and are never run automatically by the API.
