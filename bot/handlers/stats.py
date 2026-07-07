"""Handler for /stats command."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.db import get_stats
from bot.utils import format_duration


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show personal fasting statistics."""
    user_id = update.effective_user.id
    stats = get_stats(user_id)

    if not stats or stats.get("total_fasts", 0) == 0:
        text = "📊 <b>Пока нет данных.</b>\n\nЗаверши первый фаст — и статистика появится!"
    else:
        total = stats.get("total_fasts", 0)
        avg = int(stats.get("avg_duration_minutes", 0) or 0)
        longest = int(stats.get("longest_duration_minutes", 0) or 0)
        total_dur = int(stats.get("total_duration_minutes", 0) or 0)
        current = stats.get("current_fasting", False)
        current_min = int(stats.get("current_fasting_minutes", 0) or 0)

        text = (
            "📊 <b>Твоя статистика</b>\n\n"
            f"📌 Всего фастов:      <b>{total}</b>\n"
            f"⏱ Общее время:       <b>{format_duration(total_dur)}</b>\n"
            f"📏 Средняя длина:    <b>{format_duration(avg)}</b>\n"
            f"🏆 Рекорд:            <b>{format_duration(longest)}</b>\n"
        )

        if current:
            text += f"\n🕐 <i>Текущий фаст: {format_duration(current_min)}</i>"

    await update.message.reply_text(text, parse_mode="HTML")
