"""Handler for /history command."""

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import get_fast_history
from bot.utils import format_duration


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last 20 completed fasts."""
    user_id = update.effective_user.id
    fasts = get_fast_history(user_id)

    if not fasts:
        text = "📋 <b>История пуста.</b>\n\nЗаверши первый фаст командой /eat!"
    else:
        text = f"📋 <b>Последние {len(fasts)} фастов</b>\n\n"
        for f in fasts:
            ended = datetime.fromisoformat(f["ended_at"].replace("Z", "+00:00"))
            dur = format_duration(f["duration_minutes"])
            date = ended.strftime("%d.%m")
            text += f"▸ {date} — <b>{dur}</b>\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="cmd_stats"),
         InlineKeyboardButton("🌐 Дашборд", callback_data="cmd_dashboard")]
    ])

    await _reply(update, text, keyboard)


async def _reply(update: Update, text: str, keyboard=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
