@echo off
chcp 65001 >nul
title Smart Wallet - Cloudflare HTTPS Tunnel
echo ========================================================
echo         Cloudflare Tunnel Ishga Tushmoqda...
echo   (Hech qanday IP so'ramaydi, to'g'ridan-to'g'ri ochiladi)
echo ========================================================
echo.
echo Port 8000 uchun havola yaratilmoqda, iltimos kuting...
echo.
npx --yes cloudflared tunnel --url http://localhost:8000
pause
