"""Handler for /status command."""

from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

from bot.db import get_active_fast
from bot.utils import format_duration


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current fasting duration."""
    user_id = update.effective_user.id
    active = get_active_fast(user_id)

    if active:
        started = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        duration = int((now - started).total_seconds() / 60)
        hours, mins = divmod(duration, 60)
        days = 0
        if hours >= 24:
            days, hours = divmod(hours, 24)

        text = "⏳ <b>Ты без еды уже</b>\n"
        if days > 0:
            text += f"<b>{days}д {hours}ч {mins}м</b>\n"
        elif hours > 0:
            text += f"<b>{hours}ч {mins}м</b>\n"
        else:
            text += f"<b>{mins}м</b>\n"
        text += f"\nС <code>{started.strftime('%H:%M %d.%m')}</code>"

        # Milestone motivation
        milestones = [
            (12 * 60, "12ч — начало аутофагии 🔄"),
            (16 * 60, "16ч — жиросжигание 🔥"),
            (18 * 60, "18ч — пик аутофагии ⚡"),
            (24 * 60, "24ч — 1 сутки! 🏆"),
            (48 * 60, "48ч — глубокая перезагрузка 🧠"),
            (72 * 60, "72ч — 3 дня! 💪"),
        ]
        for m, label in milestones:
            if duration < m:
                remaining = m - duration
                text += f"\n🎯 <b>{label}</b> через {format_duration(remaining)}"
                break
    else:
        text = (
            "🍽 <b>Сейчас ты не голодаешь.</b>\n\n"
            "Нажми /fast, чтобы начать отсчёт."
        )

    await update.message.reply_text(text, parse_mode="HTML")
