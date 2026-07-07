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
        "Этот бот помогает отслеживать время без еды.\n"
        "Нажимай команды — я считаю.\n\n"
        "🕐 <b>Команды</b>\n"
        "▸ /fast — начать голодание\n"
        "▸ /eat — поел, закончить голод\n"
        "▸ /status — сколько уже без еды\n"
        "▸ /stats — статистика\n"
        "▸ /history — история фастов\n"
        "▸ /cancel — отменить текущий фаст\n\n"
        "Попробуй: нажми <b>/fast</b> когда последний раз поел 😉"
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
    ])

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
