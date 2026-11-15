import asyncio
import os
import threading
import uvicorn
from api import app as fastapi_app
import bot

def run_fastapi():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 1. API ni alohida oqimda (thread) ishga tushiramiz
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()
    
    # 2. Telegram botni asosiy oqimda ishga tushiramiz (agar TOKEN berilgan bo'lsa)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        print("Telegram bot Render serverda ishga tushmoqda...")
        bot.main()
    else:
        print("TELEGRAM_BOT_TOKEN topilmadi, faqat Web API ishlamoqda.")
        # Thread to'xtab qolmasligi uchun kutamiz
        t.join()
