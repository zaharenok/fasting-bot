"""Handler for /start command."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import get_or_create_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and register user."""
    user = update.effective_user
    get_or_create_user(
        telegram_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
    )

    text = (
        f"👋 <b>Привет, {user.first_name or 'друг'}!</b>\n\n"
        "Я помогаю отслеживать время без еды.\n"
        "Нажимай кнопки или пиши команды.\n\n"
        "🕐 <b>Основное</b>\n"
        "▸ /fast — начать голодание\n"
        "▸ /eat — закончить фаст\n"
        "▸ /status — сколько без еды\n"
        "▸ /cancel — отменить (с подтверждением)\n\n"
        "⚙️ <b>Настройки</b>\n"
        "▸ /mode — режим (16:8, OMAD...)\n"
        "▸ /goal — цель голодания\n"
        "▸ /reminder — напоминания\n\n"
        "📊 <b>Аналитика</b>\n"
        "▸ /stats — статистика\n"
        "▸ /history — история фастов\n"
        "▸ /edit — исправить время фаста\n"
        "▸ /checkin — самочувствие\n"
        "▸ /electrolytes — электролиты, советы\n\n"
        "🌐 <b>Веб</b>\n"
        "▸ /dashboard — дашборд в браузере\n"
        "▸ /miniapp — Mini App в Telegram\n"
        "▸ /help — все команды\n\n"
        "Попробуй: нажми <b>/fast</b> 😉"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast"),
            InlineKeyboardButton("🍽 Поел", callback_data="cmd_eat"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="cmd_stats"),
            InlineKeyboardButton("📋 История", callback_data="cmd_history"),
        ],
        [
            InlineKeyboardButton("🎯 Режим /mode", callback_data="cmd_mode"),
            InlineKeyboardButton("⏰ /reminder", callback_data="cmd_reminder"),
        ],
        [
            InlineKeyboardButton("🧂 Электролиты", callback_data="cmd_electrolytes"),
            InlineKeyboardButton("📝 Чекин", callback_data="cmd_checkin"),
        ],
    ])

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
