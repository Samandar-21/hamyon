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

from wallet_analytics import get_dashboard_metrics
from wallet_db import add_transaction, db, delete_transaction, load_data, update_transaction_category
from wallet_utils import parse_amount, parse_quick_entry

SELECT_TYPE, ENTER_AMOUNT, SELECT_CATEGORY, ENTER_NOTE = range(4)

EXPENSE_CATEGORIES = [
    "Oziq-ovqat", "Transport", "Uy", "Kommunal", "Xaridlar",
    "Sog‘liq", "Ta’lim", "Ko‘ngilochar", "Boshqa",
]
INCOME_CATEGORIES = ["Ish haqi", "Biznes", "Sovg‘a", "Qo‘shimcha daromad", "Boshqa"]


DEFAULT_BOT_TOKEN = "9199753291:AAEKYuTXmn6moBejY9pvhydQtypv2cG0rQw"
DEFAULT_USER_ID = "5377564628"


def _is_allowed(update: Update) -> bool:
    allowed_user_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip() or DEFAULT_USER_ID
    user = update.effective_user
    return bool(allowed_user_id and user and str(user.id) == allowed_user_id)


async def _deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "Botdan foydalanishga ruxsatingiz yo‘q. Telegram ID: "
            f"{update.effective_user.id if update.effective_user else 'aniqlanmadi'}"
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
            [KeyboardButton("➕ Xarajat qo‘shish"), KeyboardButton("📊 Oylik hisobot")],
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
    url = _webapp_url()
    if url:
        await app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Smart Wallet",
                web_app=WebAppInfo(url=url),
            )
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
    if not _is_allowed(update):
        await _deny(update)
        return

    text = update.effective_message.text.strip()
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

    if not tx_id:
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
            InlineKeyboardButton("✏️ Kategoriya", callback_data=f"editcat:{tx_id}:{tx_type}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"undo:{tx_id}"),
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
    conn = db()
    try:
        delete_transaction(conn, tx_id)
    finally:
        conn.close()
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
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or "9288305255:AAHilxcAa-YJC0bMRobL6e0sL24vybMXPbA"
    allowed_user_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip() or "5377564628"
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN muhit o‘zgaruvchisini o‘rnating.")
    if not allowed_user_id.isdigit():
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID ni raqamli Telegram ID bilan o‘rnating.")

    app = Application.builder().token(token).post_init(setup_webapp_menu).build()
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
    app.add_handler(CommandHandler("app", open_app))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("recent", recent))
    app.add_handler(MessageHandler(filters.Regex(r"^💰 Balans$"), balance))
    app.add_handler(MessageHandler(filters.Regex(r"^🧾 Oxirgi amallar$"), recent))
    app.add_handler(MessageHandler(filters.Regex(r"^📊 Oylik hisobot$"), balance))
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
