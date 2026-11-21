@echo off
chcp 65001 >nul
title Smart Outdoor Garden - Web Server
cd /d "%~dp0"

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
echo [2] MAY KHAC / DIEN THOAI (CUNG WI-FI) TRUY CAP TAI:
if defined LOCAL_IP (
    echo     - Trinh duyet: http://%LOCAL_IP%:8000
) else (
    echo     - Trinh duyet: http://[DIA_CHI_IP_CUA_MAY]:8000
)
echo.
echo [3] TAI KHOAN DANG NHAP DEMO:
echo     - Email:    demo@smartgreenhouse.local
echo     - Mat khau: Demo@12345678
echo.
echo =====================================================================
echo Dang khoi dong Web Server tren cong 8000 (0.0.0.0)...
echo Nhan Ctrl + C de dung server.
echo =====================================================================
echo.

cd api
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
