@echo off
chcp 65001 >nul
title Smart Wallet - Backend API Server
echo ========================================================
echo         Smart Wallet API Server ishga tushirilmoqda...
echo ========================================================
cd /d D:\hamyon
python -m uvicorn api:app --host 127.0.0.1 --port 8000
if %errorlevel% neq 0 (
    echo.
    echo Xatolik yuz berdi. Iltimos xatolik matnini tekshiring.
)
pause
