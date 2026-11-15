@echo off
chcp 65001 >nul
title Smart Wallet - Telegram Bot
echo ========================================================
echo         Smart Wallet Telegram Botni Ishga Tushirish
echo ========================================================

REM Agar bot_config.env mavjud bo'lsa, o'qib olamiz
if exist "bot_config.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("bot_config.env") do (
        set "%%A=%%B"
    )
)

if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo.
    echo [DIQQAT] TELEGRAM_BOT_TOKEN kiritilmagan!
    echo Iltimos, Telegram @BotFather'dan olgan tokenni kiriting:
    set /p TELEGRAM_BOT_TOKEN="Bot Token: 9288305255:AAHilxcAa-YJC0bMRobL6e0sL24vybMXPbA "
)

if "%TELEGRAM_ALLOWED_USER_ID%"=="" (
    echo.
    echo [DIQQAT] TELEGRAM_ALLOWED_USER_ID kiritilmagan!
    echo Telegram @userinfobot'dan olingan raqamli ID'ingizni kiriting:
    set /p TELEGRAM_ALLOWED_USER_ID="Telegram ID (faqat raqam): 5377564628 "
)

REM Sozlamalarni bot_config.env ga saqlab qo'yamiz (keyingi safar so'ramasligi uchun)
(
echo TELEGRAM_BOT_TOKEN=%TELEGRAM_BOT_TOKEN%
echo TELEGRAM_ALLOWED_USER_ID=%TELEGRAM_ALLOWED_USER_ID%
echo TELEGRAM_WEBAPP_URL=%TELEGRAM_WEBAPP_URL%
) > "bot_config.env"

echo.
echo ========================================================
echo   Bot ishga tushmoqda... (To'xtatish uchun: Ctrl + C)
echo ========================================================
python bot.py
pause
