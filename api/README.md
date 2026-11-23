# Smart Greenhouse API

FastAPI backend for greenhouse telemetry and experimental plant recommendations. PostgreSQL is configured with `DATABASE_URL`; this project reuses its existing tables. SQL migrations are applied manually and never run automatically by the API.

## Project layout

```text
api/
├── app/                 FastAPI app, database models, and AI inference
├── data/                Source datasets used for training
├── ml_models/           Image models and isolated irrigation research artifacts
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
- The fertilizer models and training/loader code have been removed. The retired `POST /api/ai/fertilizer/predict` endpoint returns HTTP 410.
- Image model: `POST /api/ai/disease/predict`. Send raw JPEG or PNG bytes with the matching `Content-Type`; maximum body size is 10 MB and maximum image size is 20 megapixels. The image is not stored. Scores are softmax outputs, not calibrated confidence values. The API returns HTTP 503 if the model or TensorFlow runtime is unavailable.

Register/login requests use JSON with `full_name`, `email`, and `password` (plus optional `phone_number` on registration). Use the returned `access_token` as a bearer token:

```powershell
$body = @{ full_name = "Nông dân"; email = "farmer@example.com"; password = "a-long-demo-password-123" } | ConvertTo-Json
$session = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/register -ContentType application/json -Body $body
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/greenhouses -Headers @{ Authorization = "Bearer $($session.access_token)" }
```

Example image request:

```powershell
curl.exe -X POST -H "Content-Type: image/jpeg" --data-binary "@leaf.jpg" http://127.0.0.1:8000/api/ai/disease/predict
```

## MQTT and utilities

The MQTT subscriber validates the device token, device registration, timestamp, measurement ranges, and duplicate timestamps before storing telemetry. Configure `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`, optional username/password, and `MQTT_TLS` in `.env`. Each payload must carry `DEVICE_INGEST_TOKEN` as `device_token`. Use a private broker with TLS and ACLs outside demos.

From the `api` directory, run:

```powershell
.\venv\Scripts\python.exe -m app.irrigation_worker
.\venv\Scripts\python.exe -m scripts.simulate_esp32
.\venv\Scripts\python.exe -m scripts.serial_ai
```

Run exactly one irrigation worker: it receives telemetry/feedback and checks pump deadlines independently of new sensor packets. The simulator sends random demo readings; use it only with isolated demo devices and automatic control disabled. The bounded pump firmware is in `../hardware/nodemcu_v2`; copy `config.example.h` to ignored `config.h`, implement calibrated sensor adapters, and verify relay shutdown before enabling hardware control. The ESP32-S3 camera source in `../hardware/reference` is a separate reference, not a drop-in pump controller.

## Train models

Image inference uses `ml_models/plant_disease_model.keras`. CatBoost and Random Forest irrigation experiments are separate from live control; `ml_models/research` contains reproducible research weights and the API never loads them. See [the comparison report](../docs/reports/2026-11-23-irrigation/REPORT.md). The old fertilizer workbook is historical data and is not used by the API.

The chili image dataset is under `data/chili_plant_disease/{train,val,test}` with five balanced classes. TensorFlow is an optional CPU training dependency in `requirements-vision.txt`; install it into the existing project venv only when needed:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-vision.txt
.\venv\Scripts\python.exe -m scripts.train_disease_model --epochs 40
```

The image CNN trains from scratch without downloading pretrained weights. The model and per-class test report are saved under `ml_models/`. The test split contains ten images per class, so metrics are experimental and should be checked against independent field images. The retired fertilizer `.pkl` and `.joblib` artifacts have been removed.

## Current limitations

- Existing greenhouse records with a NULL `user_id` are intentionally hidden from farmer accounts until an administrator assigns ownership; `ADMIN` can still review them.
- The frontend login/register forms use the account routes and send bearer tokens through the frontend proxy. Login and account data require a configured PostgreSQL connection and the authentication migration.
- Disease predictions are experimental and are not validated field advice.
- Fertilizer models have been removed; MQTT ignores legacy pH/N-P-K fields and Serial firmware sends environmental measurements only.
- Camera uploads use local API storage; multi-instance shared image storage and FCM delivery are not implemented. SQL migrations are manual and never run automatically by the API.

## Học train AI hỗ trợ tưới — CatBoost và Random Forest

### 1. Hiểu bài toán trước khi chạy

CatBoost là thư viện thuật toán. Sau khi học từ dữ liệu, nó tạo ra file trọng số `.cbm` riêng của dự án. Bài đầu tiên ở đây dự báo **độ ẩm đất sau 30 phút**, không dự báo trực tiếp số giây bật bơm. Không dùng pH/N/P/K, không gọi database, không gửi lệnh tới phần cứng.

- **Feature/đầu vào:** những thông tin biết lúc quyết định tưới.
- **Target/nhãn:** độ ẩm đất thực sự đo sau 30 phút; đây là đáp án cho model học.
- **Train:** dữ liệu cho model học. **Validation:** chọn thời điểm dừng học. **Test:** dữ liệu giữ lại đến cuối để chấm điểm.

### 2. Cài đặt trên máy khác

Mở Terminal PowerShell trong VS Code. Các lệnh sau dùng đúng môi trường của API, không cần chạy Activate.ps1:

```powershell
Set-Location D:\PBL4\api
.\venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-irrigation.txt
.\venv\Scripts\python.exe -c "import catboost; print(catboost.__version__)"
```

Máy cần có `api/venv` trước. CatBoost chạy bằng CPU trong bài này, không cần card NVIDIA. Không tải lại TensorFlow hay clone toàn bộ mã nguồn CatBoost.

### 3. Chạy bài thực hành bằng dữ liệu giả

```powershell
Set-Location D:\PBL4\api
.\venv\Scripts\python.exe -m scripts.train_irrigation_model --demo
```

Script tạo 1.200 dòng mô phỏng cho bốn khu, train tối đa 400 vòng, dùng hai luồng CPU. Số vòng học có thể dừng sớm khi validation không cải thiện. Mỗi lần chạy tạo thư mục mới ở `ml_models/irrigation/demo/<thời-gian>/`, không ghi đè model ảnh.

Kết quả gồm `irrigation_model.cbm`, `random_forest.joblib`, `report.json`, `test_predictions.csv` và `synthetic_training_data.csv`. Hai model dùng cùng đầu vào và phân chia dữ liệu; bộ mã hóa Random Forest chỉ học từ tập train. Dữ liệu mô phỏng được sinh từ một công thức giả định, nên điểm số chỉ chứng minh chương trình chạy được, không chứng minh khả năng tưới cây. Không đổi `synthetic` thành `measured` để đưa dữ liệu giả vào bài train thật.

### 4. Chuẩn bị dữ liệu thật

Sao chép `data/irrigation/template.csv` thành `data/irrigation/observations.csv`. Mẫu chỉ có tiêu đề để không vô tình trộn ví dụ vào dữ liệu thật. Có thể nhập bằng Excel rồi lưu CSV UTF-8, dấu phẩy phân cách và dấu chấm thập phân. Mỗi dòng là **một khu tại một thời điểm quan sát**, không phải một cây riêng lẻ nếu cảm biến đại diện cho cả khu.

| Cột | Cần ghi gì? |
| --- | --- |
| `timestamp` | Thời điểm lấy số đo đầu vào, có múi giờ, ví dụ `2026-11-22T08:00:00+07:00` |
| `target_timestamp` | Thời điểm thực sự đo lại, khoảng 30 phút sau (cho phép lệch tối đa 3 phút) |
| `zone_id` | Mã khu cố định; dùng truy vết, không làm đầu vào model |
| `crop_type` | Loại cây, ví dụ `chili`, `lettuce`; dùng cách viết thống nhất |
| `growth_stage` | Giai đoạn sinh trưởng đã xác định tại thời điểm đo |
| `substrate` | Đất/giá thể, ví dụ `soil`, `coco` |
| `area_sqm` | Diện tích khu thực sự nhận lượng nước này, m² |
| `soil_moisture_pct` | Độ ẩm đất trước tưới, thang 0–100 đã hiệu chuẩn và thống nhất |
| `temperature_c` | Nhiệt độ hiện tại, °C |
| `air_humidity_pct` | Độ ẩm không khí hiện tại, % |
| `light_lux` | Ánh sáng hiện tại, lux; không nhập ADC thô rồi gọi là lux |
| `irrigation_liters` | Lượng nước đã quyết định cấp ngay sau số đo ban đầu, lít; không tưới thì 0 |
| `soil_moisture_30m_pct` | Độ ẩm đất đo lại sau 30 phút; không lấy từ quy tắc hay dự đoán |
| `data_source` | `measured` cho dữ liệu đo thực tế |

Quy trình thu một dòng: ghi trạng thái trước tưới → ghi mức nước đã quyết định → tưới và xác minh lượng nước thực cấp → chờ đến thời điểm đo lại → điền nhãn. Chỉ dùng dòng mà lượng nước thực cấp khớp kế hoạch trong sai số đo đã quy định. Loại khỏi bộ train ban đầu những khoảng có tưới bổ sung, hỏng bơm, đổi cảm biến hoặc mưa không được ghi nhận. Không tính tổng nước tương lai rồi giả vờ đó là thông tin đã biết lúc quyết định.

Thu cả các khoảng không tưới. Ưu tiên đo lưu lượng thực tế tại đường tưới; không suy ra lượng nước chỉ từ công suất ghi trên bơm. Không ép cây vào tình trạng quá khô hoặc tưới quá mức chỉ để tạo dữ liệu. Bài đầu nên giới hạn ở khu có điều kiện kiểm soát, cùng cách hiệu chuẩn và cấu hình vùng rễ/chậu; chưa áp dụng sang chậu, đất, cảm biến hoặc khu ngoài trời khác mà chưa kiểm định.

Database hiện có log cảm biến và bật/tắt bơm chưa đủ để tự động suy ra bộ CSV này: còn phải xác minh lưu lượng/lượng nước, ghép đúng khu và cặp số đo trước–sau. Script không tự xuất database hoặc tự tạo nhãn thay cho dữ liệu thật.

Script yêu cầu tối thiểu 200 dòng và 20 mốc thời gian để thực hiện chia tập. Đây chỉ là điều kiện kỹ thuật, không phải cam kết đủ dữ liệu: cần nhiều chu kỳ tưới, ngày, điều kiện và các giai đoạn cây; hàng nghìn dòng liên tiếp từ cùng một chu kỳ không tương đương nhiều quan sát độc lập.

### 5. Train từ dữ liệu thật

```powershell
Set-Location D:\PBL4\api
.\venv\Scripts\python.exe -m scripts.train_irrigation_model --csv .\data\irrigation\observations.csv
```

Kết quả nằm ở `ml_models/irrigation/experiments/<thời-gian>/`. Script dùng khoảng 70% mốc thời gian đầu để train, 15% tiếp theo validation, 15% cuối test. Những dòng có nhãn tương lai chồng qua ranh giới tập bị loại. Loại cây và giá thể được truyền trực tiếp cho CatBoost dưới dạng phân loại, không đổi tùy ý thành các số 1/2/3.

### 6. Đọc kết quả và quyết định có cải thiện hay không

Mở `report.json` và so sánh `test_metrics` với `persistence_baseline` — dự đoán đơn giản rằng độ ẩm sau 30 phút bằng độ ẩm hiện tại.

- `mae_percentage_points`: sai số tuyệt đối trung bình. Ví dụ MAE=3 nghĩa là lệch trung bình 3 điểm phần trăm độ ẩm; **không phải accuracy 97%**.
- `rmse_percentage_points`: nhạy hơn với những lần dự đoán lệch nhiều.
- `r2`: có thể âm; không phải độ chính xác phần trăm.
- `per_crop_test_mae`: kiểm tra từng loại cây, tránh một nhóm tốt che khuất nhóm kém.
- `beats_persistence_mae`: so sánh MAE với baseline, chưa phải giấy phép chạy bơm.

Nếu CatBoost không hơn baseline, kiểm tra dữ liệu, ghép thời gian, hiệu chuẩn, số chu kỳ và thông tin đầu vào trước khi tăng số vòng. Không chỉnh model liên tục theo test; khi đã dùng test để quyết định sửa, cần thu giai đoạn test mới. Kiểm tra thêm một khu chưa dùng để train trước khi tuyên bố dùng được cho khu mới; script hiện chỉ tự động chia theo thời gian.

### 7. Sau khi train

Script kiểm tra file `.cbm` bằng cách nạp lại và so kết quả với model trong bộ nhớ. Tất cả báo cáo đều đặt `automatic_control_approved=false`. Không có thay đổi nào vào API điều khiển bơm. Model từ dữ liệu quan sát chưa chứng minh được tác động nhân quả hoặc lượng nước tối ưu.

Bước triển khai tiếp theo là chạy dự báo song song với cách tưới hiện tại, ghi sai số thực tế. Chỉ sau kiểm định mới xây bộ chọn lượng nước và thời gian bơm, kèm giới hạn thời gian, thời gian nghỉ, kiểm tra cảm biến và dừng khi mất dữ liệu. Lưu cả file model, báo cáo và phiên bản dữ liệu để có thể đối chiếu lần train sau. Các quan sát và kết quả train đã được bỏ qua bởi Git để không tự đẩy dữ liệu lên repo.

Tài liệu chính thức: [Cài CatBoost](https://catboost.ai/docs/en/installation/python-installation-method-pip-install), [train bằng fit](https://catboost.ai/docs/en/concepts/python-reference_catboostregressor_fit), [lưu model](https://catboost.ai/docs/en/concepts/python-reference_catboostregressor_save_model).

### Thử bộ dữ liệu công khai SIO

Đã tải bản CSV từ [SIO của Abijith-U0245](https://github.com/Abijith-U0245/SIO---Smart-Irrigation-Optimization), commit `fb421ab52d070cb9dce6c2db28d0f95fcec96105`, vào `data/irrigation/external/sio/irrigation_dataset.csv`. `source.json` cùng thư mục ghi URL, checksum và thời điểm tải. Tác giả mô tả đây là dữ liệu tự tạo mô phỏng; không phải dữ liệu đo ở vườn của nhóm.

Bộ tải về có 2.000 dòng, tám cây (lúa, lúa mì, ngô, bông, mía, đậu tương, cà chua, khoai tây), bốn giai đoạn. Không có ớt hoặc xà lách. Bản gốc có cột pH; script chỉ dùng danh sách đầu vào cho phép, loại pH và không dùng N/P/K. Bản gốc được giữ nguyên để đối chiếu; mỗi lần train có file `dataset_without_ph.csv` riêng.

Đây là **bài toán khác**: phân loại tưới/không tưới và dự báo độ sâu nước tưới (mm). Không có thời gian quan sát, khu vườn, lượng nước thực cấp hay độ ẩm sau 30 phút, nên không thể ghép trực tiếp vào `train_irrigation_model.py` hoặc so độ chính xác với bài đó. Chi tiết cách tác giả sinh nhãn chưa được xác minh; bỏ pH khỏi đầu vào không chứng minh nhãn gốc độc lập với pH.

Chạy lại thử nghiệm tại máy đã tải dataset:

```powershell
Set-Location D:\PBL4\api
.\venv\Scripts\python.exe -m scripts.benchmark_sio_irrigation
```

Script cố định chia ngẫu nhiên có cân bằng nhãn 1.400 dòng train / 300 validation / 300 test, seed 42; dữ liệu không có thời gian để chia theo thời gian. Hai cấu hình dùng cùng tập kiểm tra: `available_inputs` chỉ dùng loại cây, giai đoạn, độ ẩm đất, nhiệt độ và độ ẩm không khí; `with_weather_context` thêm lượng mưa 7 ngày và bức xạ mặt trời. Không dùng ID hoặc nhãn đầu ra này làm đầu vào để dự đoán nhãn đầu ra kia.

Kết quả lưu trong `ml_models/irrigation/external_sio/<thời-gian>/`, gồm model CatBoost `.cbm` và Random Forest `.joblib`, báo cáo, phân chia dữ liệu và từng dự đoán. Tỷ lệ đúng quyết định tưới là accuracy phân loại; sai số lượng nước tính bằng mm, không phải phần trăm độ ẩm. Bức xạ mặt trời MJ/m² không được thay trực tiếp bằng số lux từ cảm biến ánh sáng.

Đây chỉ là đánh giá trên nhãn mô phỏng, chưa kiểm định tại vườn và chưa được API tải để điều khiển bơm. Không thấy giấy phép riêng ở thư mục gốc nguồn đã kiểm tra; giữ dữ liệu tải và kết quả ở máy, không tự đẩy lên GitHub. Script và mô tả nguồn có thể lưu cùng code dự án.
