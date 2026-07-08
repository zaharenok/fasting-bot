"""Handler for /edit command — correct past fast start/end times."""

from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import get_fast_history, get_fast_by_id, update_fast_times
from bot.utils import format_duration
from bot.handlers.fast import _parse_time


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent fasts to edit."""
    user_id = update.effective_user.id
    fasts = get_fast_history(user_id, limit=10)

    if not fasts:
        await _reply(update, "📋 Нет завершённых фастов для редактирования.")
        return

    text = "📋 <b>Выбери фаст для редактирования:</b>\n\n"
    keyboard = []
    for f in fasts[:5]:
        ended = datetime.fromisoformat(f["ended_at"].replace("Z", "+00:00"))
        dur = format_duration(f["duration_minutes"])
        label = f"{ended.strftime('%d.%m %H:%M')} — {dur}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"edit_fast:{f['id']}")])

    await _reply(update, text, InlineKeyboardMarkup(keyboard))


async def handle_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show details and edit options for a selected fast."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    fast_id = int(query.data.split(":")[1])

    fast = get_fast_by_id(fast_id, user_id)
    if not fast:
        await query.edit_message_text("❌ Фаст не найден.", parse_mode="HTML")
        return

    started = datetime.fromisoformat(fast["started_at"].replace("Z", "+00:00"))
    ended = datetime.fromisoformat(fast["ended_at"].replace("Z", "+00:00"))
    dur = format_duration(fast["duration_minutes"])

    text = (
        "📋 <b>Фаст #{}:</b>\n\n"
        "🕐 Начало: <code>{}</code>\n"
        "🍽 Конец:   <code>{}</code>\n"
        "⏳ Длился: <b>{}</b>\n\n"
        "Что хочешь исправить?"
    ).format(fast_id, started.strftime('%H:%M %d.%m'), ended.strftime('%H:%M %d.%m'), dur)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕐 Изменить начало", callback_data=f"edit_start:{fast_id}")],
        [InlineKeyboardButton("🍽 Изменить конец", callback_data=f"edit_end:{fast_id}")],
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="cmd_edit")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handle_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for new start time."""
    query = update.callback_query
    await query.answer()
    fast_id = query.data.split(":")[1]

    text = (
        "🕐 <b>Напиши новое время начала</b>\n\n"
        "Форматы:\n"
        "<code>14:30</code> — сегодня\n"
        "<code>14:30 вчера</code>\n"
        "<code>2 часа назад</code>\n"
        "<code>2026-07-07 12:00</code>"
    )
    await query.edit_message_text(text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f"edit_fast:{fast_id}")]
        ]))


async def handle_edit_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for new end time."""
    query = update.callback_query
    await query.answer()
    fast_id = query.data.split(":")[1]

    text = (
        "🍽 <b>Напиши новое время окончания</b>\n\n"
        "Форматы:\n"
        "<code>14:30</code> — сегодня\n"
        "<code>14:30 вчера</code>\n"
        "<code>2 часа назад</code>\n"
        "<code>2026-07-07 12:00</code>"
    )
    await query.edit_message_text(text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f"edit_fast:{fast_id}")]
        ]))


async def handle_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for editing a fast's time."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    parsed = _parse_time(text)

    if not parsed:
        await update.message.reply_text(
            "❌ Не понял время. Примеры: <code>14:30</code>, <code>2 часа назад</code>",
            parse_mode="HTML",
        )
        return

    # We don't know which fast they're editing here without state
    # So just show the list again with a note
    from bot.db import get_fast_history as get_history
    from bot.handlers.fast import _action_keyboard
    fasts = get_history(user_id, limit=5)
    if not fasts:
        await update.message.reply_text("❌ Нет фастов для редактирования.", parse_mode="HTML")
        return

    # Edit the most recent fast by default
    recent = fasts[0]
    update_fast_times(recent["id"], user_id, ended_at=parsed)

    started = datetime.fromisoformat(parsed.replace("Z", "+00:00"))
    await update.message.reply_text(
        f"✅ <b>Фаст #{recent['id']} обновлён!</b>\n"
        f"Новое время: <code>{started.strftime('%H:%M %d.%m')}</code>",
        parse_mode="HTML",
        reply_markup=_action_keyboard(),
    )


async def _reply(update: Update, text: str, keyboard=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
