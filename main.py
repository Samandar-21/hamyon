import asyncio
import os
import sys
import threading
import uvicorn
from api import app as fastapi_app

DEFAULT_BOT_TOKEN = "9199753291:AAEKYuTXmn6moBejY9pvhydQtypv2cG0rQw"
DEFAULT_USER_ID = "5377564628"

os.environ["TELEGRAM_BOT_TOKEN"] = "9199753291:AAEKYuTXmn6moBejY9pvhydQtypv2cG0rQw"
os.environ["TELEGRAM_ALLOWED_USER_ID"] = DEFAULT_USER_ID

def run_fastapi():
    port = int(os.environ.get("PORT", 8000))
    print(f"FastAPI server port {port} da ishga tushmoqda...")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

def start_bot_process():
    try:
        import bot
        print("Telegram bot Render serverda muvaffaqiyatli ishga tushmoqda...")
        bot.main()
    except Exception as e:
        print(f"Bot ishga tushishda xatolik: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 1. Telegram botni alohida thread'da ishga tushiramiz
    bot_thread = threading.Thread(target=start_bot_process, daemon=True)
    bot_thread.start()

    # 2. FastAPI ni asosiy oqimda ishga tushiramiz
    run_fastapi()
