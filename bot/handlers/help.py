"""Handler for /help command."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available commands."""
    text = (
        "🕐 <b>Fasting Bot — все команды</b>\n\n"
        "▸ /fast — начать голодание (с выбором времени)\n"
        "▸ /eat — закончить фаст (поел)\n"
        "▸ /status — сколько уже без еды\n"
        "▸ /stats — статистика\n"
        "▸ /history — история фастов\n"
        "▸ /cancel — отменить фаст (с подтверждением)\n\n"
        "▸ /goal — установить цель голодания\n"
        "▸ /mode — выбрать режим (16:8, OMAD, ...)\n"
        "▸ /reminder — утренние напоминания\n"
        "▸ /checkin — как самочувствие?\n\n"
        "▸ /dashboard — веб-дашборд\n"
        "▸ /miniapp — Mini App в Telegram\n"
        "▸ /help — эта справка\n"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast"),
         InlineKeyboardButton("🍽 Поел", callback_data="cmd_eat")],
        [InlineKeyboardButton("📊 Статистика", callback_data="cmd_stats"),
         InlineKeyboardButton("📋 История", callback_data="cmd_history")],
        [InlineKeyboardButton("🎯 Цель", callback_data="cmd_goal"),
         InlineKeyboardButton("⏰ Напоминания", callback_data="cmd_reminder")],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
