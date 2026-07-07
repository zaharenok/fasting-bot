"""Handlers for /fast and /eat commands."""

import re
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import start_fast, end_fast, get_active_fast, get_stats
from bot.utils import format_duration


def _parse_time(text: str) -> str | None:
    """Parse user-friendly time string into ISO datetime.

    Supported formats:
      14:30              → today at 14:30 Vienna
      14:30 вчера        → yesterday at 14:30
      2 часа назад       → 2 hours ago
      30 минут назад     → 30 min ago
      2026-07-07 12:00   → specific datetime
    """
    if not text:
        return None

    now = datetime.now(timezone.utc)
    text = text.strip().lower()

    # "2 часа назад", "30 минут назад", "1ч назад"
    m = re.match(r'(\d+)\s*(?:ч|час|часа|часов|h)\s*(?:назад)?\s*$', text)
    if m:
        hours = int(m.group(1))
        return (now - timedelta(hours=hours)).isoformat()

    m = re.match(r'(\d+)\s*(?:м|мин|минут|минута|min)\s*(?:назад)?\s*$', text)
    if m:
        mins = int(m.group(1))
        return (now - timedelta(minutes=mins)).isoformat()

    # "14:30" or "14:30 вчера"
    m = re.match(r'(\d{1,2}):(\d{2})\s*(вчера|yesterday)?\s*$', text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        # Use Vienna time (UTC+2 in summer)
        vienna = now + timedelta(hours=2)  # approximate CEST
        dt = vienna.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if m.group(3):  # вчера
            dt -= timedelta(days=1)
        # Convert back to UTC
        utc_dt = dt - timedelta(hours=2)
        return utc_dt.isoformat()

    # "2026-07-07 12:00" or "2026-07-07T12:00"
    m = re.match(r'(\d{4}-\d{2}-\d{2})[\sT](\d{1,2}):(\d{2})', text)
    if m:
        try:
            dt = datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M")
            # Assume input is Vienna time
            utc_dt = dt - timedelta(hours=2)
            return utc_dt.isoformat()
        except ValueError:
            return None

    return None


async def cmd_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new fasting period. Optional: /fast 14:30"""
    user_id = update.effective_user.id
    active = get_active_fast(user_id)

    # Parse optional time argument
    args = context.args
    custom_time = _parse_time(" ".join(args)) if args else None

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
        record = start_fast(user_id, started_at=custom_time)
        started = datetime.fromisoformat(record["started_at"].replace("Z", "+00:00"))
        text = (
            "🕐 <b>Голодание начато!</b>\n"
            f"Время: {started.strftime('%H:%M %d.%m')}\n"
        )
        if custom_time:
            text += "⏪ <i>Время установлено вручную</i>\n"
        text += "\nНажми /eat когда начнёшь есть."

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
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
