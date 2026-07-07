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

        text = "⏳ <b>Ты без еды</b>\n"
        if days > 0:
            text += f"<b>{days}д {hours}ч {mins}м</b>\n"
        elif hours > 0:
            text += f"<b>{hours}ч {mins}м</b>\n"
        else:
            text += f"<b>{mins}м</b>\n"
        text += f"С {started.strftime('%H:%M %d.%m')}"

        # Milestone motivation
        milestones = [12 * 60, 16 * 60, 18 * 60, 24 * 60, 48 * 60, 72 * 60]
        for m in milestones:
            if duration < m:
                remaining = m - duration
                text += f"\n🎯 До {m//60}ч: {format_duration(remaining)}"
                break
    else:
        text = "🍽 Сейчас ты не голодаешь.\nНажми /fast, чтобы начать."

    await update.message.reply_text(text, parse_mode="HTML")
