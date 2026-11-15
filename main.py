import asyncio
import os
import sys
import threading
import uvicorn
from api import app as fastapi_app

DEFAULT_BOT_TOKEN = "9288305255:AAHilxcAa-YJC0bMRobL6e0sL24vybMXPbA"
DEFAULT_USER_ID = "5377564628"

os.environ["TELEGRAM_BOT_TOKEN"] = os.environ.get("TELEGRAM_BOT_TOKEN") or DEFAULT_BOT_TOKEN
os.environ["TELEGRAM_ALLOWED_USER_ID"] = os.environ.get("TELEGRAM_ALLOWED_USER_ID") or DEFAULT_USER_ID

def run_fastapi():
    port = int(os.environ.get("PORT", 8000))
    print(f"FastAPI server port {port} da ishga tushmoqda...")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

def run_bot():
    try:
        # Alohida thread uchun yangi asyncio event loop yaratamiz
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        import bot
        print("Telegram bot Render serverda muvaffaqiyatli ishga tushmoqda...")
        bot.main()
    except Exception as e:
        print(f"Bot ishga tushishda xatolik: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 1. Telegram botni yangi event loop bilan alohida thread'da yoqamiz
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # 2. FastAPI ni asosiy oqimda ishga tushiramiz
    run_fastapi()
