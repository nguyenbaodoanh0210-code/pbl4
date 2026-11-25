@echo off
chcp 65001 >nul
title Smart Outdoor Garden - Web Server
cd /d "%~dp0"

:: Xoa bien DATABASE_URL cu (neu co) de luon doc dung tu api\.env
set "DATABASE_URL="

echo =====================================================================
echo       HE THONG GIAM SAT KHU VUON NGOAI TROI THONG MINH (PBL4)
echo =====================================================================
echo.

:: Tim dia chi IP mang LAN / Wi-Fi
for /f "tokens=4" %%a in ('route print ^| findstr 0.0.0.0 ^| findstr /v "On-link" 2^>nul') do (
    set LOCAL_IP=%%a
    goto :ip_found
)
:ip_found

echo [1] MAY NAY TRUY CAP TAI:
echo     - Trinh duyet: http://localhost:8000
echo.
echo [2] MAY KHAC / DIEN THOAI (CUNG WI-FI / HOTSPOT):
if defined LOCAL_IP (
    echo     - Trinh duyet: http://%LOCAL_IP%:8000
) else (
    echo     - Trinh duyet: http://192.168.137.1:8000
)
echo.
echo [3] TAI KHOAN DANG NHAP DEMO:
echo     - Email:    demo@smartgreenhouse.local
echo     - Mat khau: Demo@12345678
echo =====================================================================
echo.

cd /d "%~dp0api"

echo Dang khoi dong MQTT Worker (ESP32-S3)...
start "Smart Garden - MQTT Worker" /D "%~dp0api" cmd /k "chcp 65001 >nul && .\venv\Scripts\python.exe -X utf8 -m app.mqtt_client"

:: Doi 3 giay roi tu dong mo trinh duyet
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

echo Dang khoi dong Web Server tren cong 8000 (0.0.0.0)...
echo Nhan Ctrl + C de dung server.
echo =====================================================================
echo.

.\venv\Scripts\python.exe -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause