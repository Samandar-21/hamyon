@echo off
chcp 65001 >nul
title Smart Wallet - Vercel Deploy
echo ========================================================
echo       Smart Wallet Mini Appni Vercel'ga yuklash
echo ========================================================
echo.
cd /d D:\hamyon\static
echo Vercel ishga tushmoqda, so'ralgan savollarga Enter bosing...
echo.
npx --yes vercel deploy --prod
pause
