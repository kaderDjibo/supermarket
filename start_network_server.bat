@echo off
title Supermarket App - Network Server (Phones + PCs)
color 0B

echo.
echo ============================================================
echo   SUPERMARKET APP - LOCAL NETWORK SERVER
echo   (for Smartphones and other PCs on the same WiFi)
echo ============================================================
echo.

:: Find local IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    set LOCAL_IP=%%a
)
set LOCAL_IP=%LOCAL_IP: =%

echo   Your Network IP:  %LOCAL_IP%
echo.
echo   On your PHONE (must be on same WiFi):
echo   Open browser and go to:  http://%LOCAL_IP%:8501
echo.
echo   On another PC:
echo   Open browser and go to:  http://%LOCAL_IP%:8501
echo.
echo   Press Ctrl+C to stop the server.
echo ============================================================
echo.

:: Activate venv and start server
call venv\Scripts\activate.bat
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false

pause
