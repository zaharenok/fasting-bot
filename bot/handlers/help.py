"""Handler for /help command."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available commands."""
    text = (
        "🕐 <b>Fasting Bot — все команды</b>\n\n"
        "🕐 <b>Основное</b>\n"
        "▸ /fast — начать голодание (с выбором времени)\n"
        "▸ /eat — закончить фаст (поел)\n"
        "▸ /status — сколько уже без еды\n"
        "▸ /cancel — отменить (с подтверждением)\n\n"
        "⚙️ <b>Настройки</b>\n"
        "▸ /mode — режим голодания (16:8, OMAD...)\n"
        "▸ /goal — цель голодания\n"
        "▸ /reminder — утренние напоминания\n\n"
        "📊 <b>Аналитика</b>\n"
        "▸ /stats — статистика\n"
        "▸ /history — история фастов\n"
        "▸ /edit — исправить время фаста\n"
        "▸ /checkin — как самочувствие?\n"
        "▸ /electrolytes — электролиты и советы\n\n"
        "🌐 <b>Веб</b>\n"
        "▸ /dashboard — веб-дашборд\n"
        "▸ /miniapp — Mini App в Telegram\n"
        "▸ /help — эта справка\n"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast"),
         InlineKeyboardButton("🍽 Поел", callback_data="cmd_eat")],
        [InlineKeyboardButton("📊 Статистика", callback_data="cmd_stats"),
         InlineKeyboardButton("📋 История", callback_data="cmd_history")],
        [InlineKeyboardButton("🎯 Режим", callback_data="cmd_mode"),
         InlineKeyboardButton("⏰ /reminder", callback_data="cmd_reminder")],
        [InlineKeyboardButton("🧂 Электролиты", callback_data="cmd_electrolytes"),
         InlineKeyboardButton("📝 Чекин", callback_data="cmd_checkin")],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
