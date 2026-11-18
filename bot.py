import os
import sqlite3
from datetime import date
from urllib.parse import urlparse

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from wallet_analytics import build_daily_digest, get_dashboard_metrics
from wallet_db import (
    add_transaction,
    db,
    delete_transaction,
    get_all_users,
    get_user,
    load_data,
    register_or_update_user,
    update_transaction_category,
)
from wallet_utils import parse_amount, parse_quick_entry

SELECT_TYPE, ENTER_AMOUNT, SELECT_CATEGORY, ENTER_NOTE = range(4)

EXPENSE_CATEGORIES = [
    "Oziq-ovqat", "Transport", "Uy", "Kommunal", "Xaridlar",
    "Sog‘liq", "Ta’lim", "Ko‘ngilochar", "Boshqa",
]
INCOME_CATEGORIES = ["Ish haqi", "Biznes", "Sovg‘a", "Qo‘shimcha daromad", "Boshqa"]


DEFAULT_BOT_TOKEN = "9199753291:AAEKYuTXmn6moBejY9pvhydQtypv2cG0rQw"
DEFAULT_USER_ID = "5377564628"
ALLOWED_USER_IDS = {"5377564628", "8004299236"}


def _is_allowed(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    # Agar ruxsat berilgan ID larda bo'lsa
    if str(user.id) in ALLOWED_USER_IDS:
        return True
    # Yoki ma'lumotlar bazasida ro'yxatdan o'tgan bo'lsa
    conn = db()
    try:
        u = get_user(conn, str(user.id))
        return bool(u and u.get("phone_number"))
    finally:
        conn.close()


def _request_phone_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📞 Telefon raqamni ulashish", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def _deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "🔒 *Smart Wallet'dan foydalanish uchun ro‘yxatdan o‘tishingiz kerak.*\n\n"
            "Iltimos, pastdagi **«📞 Telefon raqamni ulashish»** tugmasini bosing yoki telefon raqamingizni yozib yuboring (masalan: `+998901234567`).",
            reply_markup=_request_phone_keyboard(),
            parse_mode="Markdown",
        )


DEFAULT_WEBAPP_URL = "https://hamyon-tan.vercel.app"


def _webapp_url() -> str:
    url = os.environ.get("TELEGRAM_WEBAPP_URL", "").strip() or DEFAULT_WEBAPP_URL
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return DEFAULT_WEBAPP_URL
    return url


def _main_reply_keyboard():
    url = _webapp_url()
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📱 Smart Wallet (Mini App)", web_app=WebAppInfo(url=url))],
            [KeyboardButton("💰 Balans"), KeyboardButton("🧾 Oxirgi amallar")],
            [KeyboardButton("➕ Xarajat qo‘shish"), KeyboardButton("🌙 Kunlik hisobot")],
        ],
        resize_keyboard=True,
    )


def _start_keyboard():
    webapp_url = _webapp_url()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Smart Wallet’ni ochish", web_app=WebAppInfo(url=webapp_url))],
        [
            InlineKeyboardButton("💰 Balans", callback_data="btn:balance"),
            InlineKeyboardButton("🧾 Oxirgi amallar", callback_data="btn:recent"),
        ],
    ])


async def setup_webapp_menu(app: Application) -> None:
    try:
        url = _webapp_url()
        if url:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Smart Wallet",
                    web_app=WebAppInfo(url=url),
                )
            )
    except Exception as e:
        print(f"Menu button o'rnatishda ogohlantirish (e'tiborsiz qoldirsa bo'ladi): {e}")


async def handle_contact_or_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not user or not msg:
        return

    phone = None
    if msg.contact:
        phone = msg.contact.phone_number
    elif msg.text:
        text = msg.text.strip().replace(" ", "").replace("-", "")
        if (text.startswith("+998") or text.startswith("998") or text.startswith("8")) and len(text) >= 9:
            phone = text

    if not phone:
        if not _is_allowed(update):
            await _deny(update)
        return

    if not phone.startswith("+"):
        phone = "+" + phone

    conn = db()
    try:
        register_or_update_user(
            conn,
            telegram_id=str(user.id),
            phone_number=phone,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
        )
        ALLOWED_USER_IDS.add(str(user.id))
    finally:
        conn.close()

    # Render API'ga ham foydalanuvchini yuboramiz
    try:
        import urllib.request
        import json
        req_data = json.dumps({
            "telegram_id": str(user.id),
            "phone_number": phone,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
        }).encode("utf-8")
        render_url = f"{RENDER_API_URL}/api/users/register"
        req = urllib.request.Request(
            render_url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        print(f"Render user sync warning: {e}")

    await msg.reply_text(
        f"🎉 *Tabriklaymiz, {user.first_name or 'qadrdon'}!*\n\n"
        f"Siz muvaffaqiyatli ro‘yxatdan o‘tdingiz.\n"
        f"📱 Telefon: `{phone}`\n\n"
        "Endi botdan va **Smart Wallet (Mini App)** dan to‘liq foydalanishingiz mumkin. "
        "Ilovaga kirganingizda ushbu akkauntingiz avtomatik ulanadi! 🚀",
        reply_markup=_main_reply_keyboard(),
        parse_mode="Markdown",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _deny(update)
        return
    await update.effective_message.reply_text(
        "👋 *Smart Wallet botiga xush kelibsiz!*\n\n"
        "⚡ *Tezkor kiritish:*\n"
        "Shunchaki xabar yuboring:\n"
        "• `45000 tushlik` (chiqim)\n"
        "• `25k taksi` (chiqim)\n"
        "• `+3.5m oylik` (kirim)\n"
        "• Yoki Click/Payme SMS xabarlarini yuboring.\n\n"
        "👇 *Quyidagi tugmalar orqali boshqaring:*",
        reply_markup=_main_reply_keyboard(),
        parse_mode="Markdown",
    )


async def open_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _deny(update)
        return
    keyboard = _start_keyboard()
    if keyboard is None:
        await update.effective_message.reply_text(
            "Mobil dashboard hali sozlanmagan. TELEGRAM_WEBAPP_URL ga HTTPS manzil kiriting."
        )
        return
    await update.effective_message.reply_text(
        "Smart Wallet mobil dashboardini oching:",
        reply_markup=keyboard,
    )


async def daily_digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _deny(update)
        return
    conn = db()
    try:
        df = load_data(conn)
        digest_text = build_daily_digest(df)
    finally:
        conn.close()

    webapp_url = _webapp_url()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Ilovada to‘liq ko‘rish", web_app=WebAppInfo(url=webapp_url))]
    ])

    await update.effective_message.reply_text(
        digest_text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def send_evening_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = db()
    try:
        df = load_data(conn)
        digest_text = build_daily_digest(df)
        users = get_all_users(conn)
    finally:
        conn.close()

    user_ids = set(ALLOWED_USER_IDS)
    for u in users:
        if u.get("telegram_id"):
            user_ids.add(str(u["telegram_id"]))

    webapp_url = _webapp_url()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Ilovada to‘liq ko‘rish", web_app=WebAppInfo(url=webapp_url))]
    ])

    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"🌙 *Kechki kunlik xulosa*\n\n{digest_text}",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"User {uid} ga kunlik hisobot yuborishda xatolik: {e}")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _deny(update)
        return
    conn = db()
    try:
        metrics = get_dashboard_metrics(load_data(conn))
    finally:
        conn.close()
    await update.effective_message.reply_text(
        "💰 Umumiy balans\n"
        f"Balans: {metrics['balance']:,.0f} so‘m\n"
        f"Jami kirim: {metrics['total_income']:,.0f} so‘m\n"
        f"Jami chiqim: {metrics['total_expense']:,.0f} so‘m\n\n"
        "📅 Joriy oy\n"
        f"Kirim: {metrics['month_income']:,.0f} so‘m\n"
        f"Chiqim: {metrics['month_expense']:,.0f} so‘m"
    )


async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _deny(update)
        return
    conn = db()
    try:
        df = load_data(conn).head(5)
    finally:
        conn.close()
    if df.empty:
        await update.effective_message.reply_text("Hozircha operatsiyalar mavjud emas.")
        return

    lines = ["🧾 Oxirgi operatsiyalar"]
    for _, row in df.iterrows():
        if row["income"] > 0:
            amount = f"+{row['income']:,.0f} so‘m"
        else:
            amount = f"−{row['expense']:,.0f} so‘m"
        description = str(row["description"] or row["category"] or "Operatsiya")
        lines.append(f"{row['tx_date']} · {description} · {amount}")
    await update.effective_message.reply_text("\n".join(lines))


async def begin_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        await _deny(update)
        return ConversationHandler.END
    keyboard = [[
        InlineKeyboardButton("↘ Chiqim", callback_data="type:expense"),
        InlineKeyboardButton("↗ Kirim", callback_data="type:income"),
    ]]
    await update.effective_message.reply_text(
        "Qaysi turdagi operatsiyani kiritamiz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SELECT_TYPE


async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not _is_allowed(update):
        await query.answer()
        await query.message.reply_text("Botdan foydalanishga ruxsatingiz yo‘q.")
        return ConversationHandler.END
    await query.answer()
    context.user_data["type"] = query.data.split(":", 1)[1]
    label = "chiqim" if context.user_data["type"] == "expense" else "kirim"
    await query.edit_message_text(f"{label.capitalize()} summasini so‘mda yuboring:")
    return ENTER_AMOUNT


async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        await _deny(update)
        return ConversationHandler.END
    amount = parse_amount(update.effective_message.text)
    if amount <= 0 or amount > 9_000_000_000_000_000:
        await update.effective_message.reply_text("Summani noldan katta qilib, raqamda kiriting. Masalan: 125000")
        return ENTER_AMOUNT
    context.user_data["amount"] = amount
    categories = EXPENSE_CATEGORIES if context.user_data["type"] == "expense" else INCOME_CATEGORIES
    context.user_data["categories"] = categories
    keyboard = [
        [InlineKeyboardButton(category, callback_data=f"category:{index}")]
        for index, category in enumerate(categories)
    ]
    await update.effective_message.reply_text(
        "Kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SELECT_CATEGORY


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not _is_allowed(update):
        await query.answer()
        await query.message.reply_text("Botdan foydalanishga ruxsatingiz yo‘q.")
        return ConversationHandler.END
    await query.answer()
    index = int(query.data.split(":", 1)[1])
    context.user_data["category"] = context.user_data["categories"][index]
    await query.edit_message_text(
        f"Kategoriya: {context.user_data['category']}\n"
        "Izoh yuboring yoki izohsiz saqlash uchun tugmani bosing.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Izohsiz saqlash", callback_data="note:skip")
        ]]),
    )
    return ENTER_NOTE


async def _save_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str) -> int:
    tx_type = context.user_data["type"]
    amount = context.user_data["amount"]
    category = context.user_data["category"]
    conn = db()
    try:
        saved = add_transaction(
            conn,
            date.today(),
            description,
            category,
            amount if tx_type == "income" else 0,
            amount if tx_type == "expense" else 0,
            "Telegram",
        )
    finally:
        conn.close()

    if saved:
        await update.effective_message.reply_text(
            f"✅ Operatsiya saqlandi\n{category} · {amount:,.0f} so‘m"
        )
    else:
        await update.effective_message.reply_text("Bu operatsiya avval kiritilgan bo‘lishi mumkin.")
    context.user_data.clear()
    return ConversationHandler.END


async def enter_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        await _deny(update)
        return ConversationHandler.END
    description = update.effective_message.text.strip()[:120]
    return await _save_transaction(update, context, description)


async def skip_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not _is_allowed(update):
        await query.answer()
        await query.message.reply_text("Botdan foydalanishga ruxsatingiz yo‘q.")
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await _save_transaction(update, context, "")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        await _deny(update)
        return ConversationHandler.END
    context.user_data.clear()
    await update.effective_message.reply_text("Operatsiya kiritish bekor qilindi.")
    return ConversationHandler.END


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _deny(update)
        return
    await update.effective_message.reply_text("Buyruq topilmadi. Buyruqlar ro‘yxati uchun /start yuboring.")


async def quick_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text.strip() if update.effective_message and update.effective_message.text else ""
    
    # Agar telefon raqam kiritgan bo'lsa va hali ruxsati bo'lmasa, ro'yxatdan o'tkazish
    cleaned_digits = text.replace(" ", "").replace("-", "")
    if (cleaned_digits.startswith("+998") or cleaned_digits.startswith("998") or cleaned_digits.startswith("8")) and len(cleaned_digits) >= 9:
        await handle_contact_or_phone(update, context)
        return

    if not _is_allowed(update):
        await _deny(update)
        return
    parsed = parse_quick_entry(text)
    if not parsed or parsed["amount"] <= 0:
        await update.effective_message.reply_text(
            "Kiritish formatini tushunmadim 🤔\n\n"
            "Tezkor kiritish uchun masalan:\n"
            "• `45000 tushlik` (chiqim)\n"
            "• `25k taksi` (chiqim)\n"
            "• `+3.5m oylik` (kirim)\n"
            "• Click / Payme SMS xabarini yuboring.\n\n"
            "Yoki bosqichma-bosqich: /add",
            parse_mode="Markdown",
        )
        return

    tx_type = parsed["type"]
    amount = parsed["amount"]
    category = parsed["category"]
    description = parsed["description"]

    # 1. Avval Render Backend API ga yuboramiz (Mini App shu serverdan o'qiydi)
    api_url = os.environ.get("RENDER_API_URL", "https://hamyon-ocfv.onrender.com").rstrip("/")
    api_success = False
    remote_tx_id = None
    try:
        import urllib.request
        import json
        req_data = json.dumps({
            "amount": float(amount),
            "type": tx_type,
            "category": category,
            "description": description,
            "tx_date": date.today().isoformat(),
            "source": "Telegram Bot"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url}/api/transactions",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                api_success = True
                res_body = json.loads(resp.read().decode("utf-8"))
                remote_tx_id = res_body.get("id")
    except Exception as e:
        print(f"Render API ga yuborishda xatolik: {e}")

    # 2. Shuningdek lokal hamyon.db ga ham nusxasini saqlab qo'yamiz
    conn = db()
    try:
        tx_id = add_transaction(
            conn,
            date.today(),
            description,
            category,
            amount if tx_type == "income" else 0,
            amount if tx_type == "expense" else 0,
            "Telegram SMS" if parsed.get("is_sms") else "Telegram Quick",
        )
    finally:
        conn.close()

    effective_tx_id = remote_tx_id or tx_id
    if not tx_id and not api_success:
        await update.effective_message.reply_text("⚠️ Bu operatsiya avval kiritilgan bo‘lishi mumkin (takroriy).")
        return

    sign = "↗ Kirim" if tx_type == "income" else "↘ Chiqim"
    reply_text = (
        f"✅ *Operatsiya saqlandi!*\n\n"
        f"🔹 *Turi:* {sign}\n"
        f"💰 *Summa:* {amount:,.0f} so‘m\n"
        f"🏷 *Kategoriya:* {category}\n"
        f"📝 *Izoh:* {description}"
    )
    keyboard = [
        [
            InlineKeyboardButton("✏️ Kategoriya", callback_data=f"editcat:{effective_tx_id}:{tx_type}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"undo:{effective_tx_id}"),
        ]
    ]
    await update.effective_message.reply_text(
        reply_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def undo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_allowed(update):
        await query.answer()
        return
    await query.answer()
    tx_id = int(query.data.split(":", 1)[1])

    # 1. Lokal bazadan o'chirish
    conn = db()
    try:
        delete_transaction(conn, tx_id)
    finally:
        conn.close()

    # 2. Render backend bazasidan ham o'chirish (Mini App sinxron bo'lishi uchun)
    try:
        import urllib.request
        api_url = os.environ.get("RENDER_API_URL", "https://hamyon-ocfv.onrender.com").rstrip("/")
        req = urllib.request.Request(f"{api_url}/api/transactions/{tx_id}", method="DELETE")
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Render delete tx warning: {e}")

    await query.edit_message_text("❌ Operatsiya bekor qilindi va bazadan o‘chirildi.")


async def edit_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_allowed(update):
        await query.answer()
        return
    await query.answer()
    _, tx_id, tx_type = query.data.split(":")
    categories = EXPENSE_CATEGORIES if tx_type == "expense" else INCOME_CATEGORIES
    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"setcat:{tx_id}:{idx}:{tx_type}")]
        for idx, cat in enumerate(categories)
    ]
    await query.edit_message_text(
        "Yangi kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def set_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_allowed(update):
        await query.answer()
        return
    await query.answer()
    _, tx_id, cat_idx, tx_type = query.data.split(":")
    categories = EXPENSE_CATEGORIES if tx_type == "expense" else INCOME_CATEGORIES
    new_cat = categories[int(cat_idx)]
    conn = db()
    try:
        update_transaction_category(conn, int(tx_id), new_cat)
    finally:
        conn.close()

    keyboard = [[
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"undo:{tx_id}"),
    ]]
    await query.edit_message_text(
        f"✅ Kategoriya yangilandi: *{new_cat}*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


def _load_env_file() -> None:
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k and v and k not in os.environ:
                        os.environ[k] = v


def main() -> None:
    _load_env_file()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or DEFAULT_BOT_TOKEN
    allowed_user_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip() or DEFAULT_USER_ID
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN muhit o‘zgaruvchisini o‘rnating.")
    if not allowed_user_id.isdigit():
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID ni raqamli Telegram ID bilan o‘rnating.")

    app = Application.builder().token(token).post_init(setup_webapp_menu).build()

    # Kechki soat 21:00 da avtomatik kunlik xulosa yuborish (JobQueue)
    if app.job_queue:
        from datetime import time
        import zoneinfo
        try:
            tashkent_tz = zoneinfo.ZoneInfo("Asia/Tashkent")
            evening_time = time(hour=21, minute=0, tzinfo=tashkent_tz)
        except Exception:
            evening_time = time(hour=21, minute=0)
        app.job_queue.run_daily(send_evening_digest_job, time=evening_time)
    conversation = ConversationHandler(
        entry_points=[CommandHandler("add", begin_add)],
        states={
            SELECT_TYPE: [CallbackQueryHandler(choose_type, pattern=r"^type:(income|expense)$")],
            ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)],
            SELECT_CATEGORY: [CallbackQueryHandler(choose_category, pattern=r"^category:\d+$")],
            ENTER_NOTE: [
                CallbackQueryHandler(skip_note, pattern=r"^note:skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_note),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact_or_phone))
    app.add_handler(CommandHandler("app", open_app))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("recent", recent))
    app.add_handler(CommandHandler("digest", daily_digest_command))
    app.add_handler(CommandHandler("today", daily_digest_command))
    app.add_handler(MessageHandler(filters.Regex(r"^💰 Balans$"), balance))
    app.add_handler(MessageHandler(filters.Regex(r"^🧾 Oxirgi amallar$"), recent))
    app.add_handler(MessageHandler(filters.Regex(r"^(📊 Oylik hisobot|🌙 Kunlik hisobot)$"), daily_digest_command))
    app.add_handler(MessageHandler(filters.Regex(r"^➕ Xarajat qo‘shish$"), begin_add))
    app.add_handler(conversation)
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(undo_callback, pattern=r"^undo:\d+$"))
    app.add_handler(CallbackQueryHandler(edit_category_callback, pattern=r"^editcat:\d+:(income|expense)$"))
    app.add_handler(CallbackQueryHandler(set_category_callback, pattern=r"^setcat:\d+:\d+:(income|expense)$"))
    app.add_handler(CallbackQueryHandler(balance, pattern=r"^btn:balance$"))
    app.add_handler(CallbackQueryHandler(recent, pattern=r"^btn:recent$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, quick_entry))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    print("Smart Wallet Telegram bot ishga tushdi. To‘xtatish uchun Ctrl+C bosing.")
    app.run_polling()


if __name__ == "__main__":
    main()
