"""Handler for /miniapp command — opens Telegram Mini App."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from bot.config import DASHBOARD_BASE_URL


async def cmd_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the Mini App button to open in Telegram."""
    url = f"{DASHBOARD_BASE_URL}/miniapp"

    text = (
        "📱 <b>Fasting Mini App</b>\n\n"
        "Нажми кнопку ниже, чтобы открыть таймер, чекины "
        "и статистику прямо в Telegram 👇"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Открыть Mini App", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast"),
         InlineKeyboardButton("🍽 Поел", callback_data="cmd_eat")],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
