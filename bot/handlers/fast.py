"""Handlers for /fast and /eat commands."""

from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import start_fast, end_fast, get_active_fast, get_stats
from bot.utils import format_duration


async def cmd_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new fasting period."""
    user_id = update.effective_user.id
    active = get_active_fast(user_id)

    if active:
        started = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
        duration = int((datetime.now(timezone.utc) - started).total_seconds() / 60)
        text = (
            "⚠️ Ты уже голодаешь!\n"
            f"Начало: {started.strftime('%H:%M %d.%m')}\n"
            f"Длительность: {format_duration(duration)}\n\n"
            "Нажми /eat когда поешь, или /cancel чтобы отменить."
        )
    else:
        record = start_fast(user_id)
        started = datetime.fromisoformat(record["started_at"].replace("Z", "+00:00"))
        text = (
            "🕐 <b>Голодание начато!</b>\n"
            f"Время: {started.strftime('%H:%M %d.%m')}\n\n"
            "Нажми /eat когда начнёшь есть."
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽 /eat — Поел", callback_data="cmd_eat")],
        [InlineKeyboardButton("📊 /status — Статус", callback_data="cmd_status")],
    ])

    await _reply(update, text, keyboard)


async def cmd_eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End the current fasting period (user ate)."""
    user_id = update.effective_user.id
    record = end_fast(user_id)

    if not record:
        text = "❌ Нет активного голодания. Начни с /fast"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast")]
        ])
    else:
        duration_min = record["duration_minutes"]
        ended = datetime.fromisoformat(record["ended_at"].replace("Z", "+00:00"))
        started = datetime.fromisoformat(record["started_at"].replace("Z", "+00:00"))

        stats = get_stats(user_id)
        best = stats.get("longest_duration_minutes", 0) or 0
        avg = stats.get("avg_duration_minutes", 0) or 0

        text = (
            "🍽 <b>Фаст завершён!</b>\n"
            f"Длительность: <b>{format_duration(duration_min)}</b>\n"
            f"Начало: {started.strftime('%H:%M %d.%m')}\n"
            f"Конец: {ended.strftime('%H:%M %d.%m')}\n\n"
        )

        if duration_min >= best and best > 0:
            text += "🏆 <b>Новый рекорд!</b> Ты никогда не был так долго без еды!\n"
        else:
            text += f"🏆 Лучший результат: {format_duration(best)}\n"

        text += f"📊 Средний фаст: {format_duration(int(avg))}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🕐 Начать новый фаст", callback_data="cmd_fast")],
            [InlineKeyboardButton("📊 Статистика", callback_data="cmd_stats")],
        ])

    await _reply(update, text, keyboard)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current active fast."""
    from bot.db import cancel_fast as db_cancel

    user_id = update.effective_user.id
    if db_cancel(user_id):
        text = "🗑 Текущий фаст отменён. Данные не сохранены."
    else:
        text = "❌ Нет активного фаста для отмены."

    await _reply(update, text)


async def _reply(update: Update, text: str, keyboard=None):
    """Reply to message or callback query."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
