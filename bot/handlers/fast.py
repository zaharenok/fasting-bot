"""Handlers for /fast and /eat commands."""

import re
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import start_fast, end_fast, get_active_fast, get_stats
from bot.utils import format_duration


# ─── Time selector keyboard pages ────────────────────────────

def _selector_page1() -> InlineKeyboardMarkup:
    """Page 1: quick time presets."""
    keyboard = [
        [
            InlineKeyboardButton("⚡ Сейчас", callback_data="fast_set:0"),
            InlineKeyboardButton("30 мин", callback_data="fast_set:30"),
            InlineKeyboardButton("1 час", callback_data="fast_set:60"),
        ],
        [
            InlineKeyboardButton("2 часа", callback_data="fast_set:120"),
            InlineKeyboardButton("4 часа", callback_data="fast_set:240"),
            InlineKeyboardButton("8 часов", callback_data="fast_set:480"),
        ],
        [
            InlineKeyboardButton("12 часов", callback_data="fast_set:720"),
            InlineKeyboardButton("▶️ Ещё →", callback_data="fast_more"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _selector_page2() -> InlineKeyboardMarkup:
    """Page 2: yesterday and earlier."""
    keyboard = [
        [
            InlineKeyboardButton("📅 Вчера", callback_data="fast_set:1440"),
            InlineKeyboardButton("2 дня", callback_data="fast_set:2880"),
            InlineKeyboardButton("3 дня", callback_data="fast_set:4320"),
        ],
        [
            InlineKeyboardButton("✏️ Своё время", callback_data="fast_custom"),
            InlineKeyboardButton("← Назад", callback_data="fast_back"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


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
        vienna = now + timedelta(hours=2)  # approximate CEST
        dt = vienna.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if m.group(3):  # вчера
            dt -= timedelta(days=1)
        utc_dt = dt - timedelta(hours=2)
        return utc_dt.isoformat()

    # "2026-07-07 12:00" or "2026-07-07T12:00"
    m = re.match(r'(\d{4}-\d{2}-\d{2})[\sT](\d{1,2}):(\d{2})', text)
    if m:
        try:
            dt = datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M")
            utc_dt = dt - timedelta(hours=2)
            return utc_dt.isoformat()
        except ValueError:
            return None

    return None


# ─── Handlers ────────────────────────────────────────────────

async def cmd_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new fasting period.

    /fast           → show time selector
    /fast 14:30     → start at specific time
    """
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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍽 /eat — Поел", callback_data="cmd_eat")],
            [InlineKeyboardButton("📊 /status — Статус", callback_data="cmd_status")],
        ])
    else:
        # Check if user passed a time argument (e.g. /fast 14:30)
        args = context.args
        if args:
            custom_time = _parse_time(" ".join(args))
            if custom_time:
                await _start_fast_with_time(update, user_id, custom_time)
                return
            else:
                text = "❌ Не понял время. Примеры:\n/fast 14:30\n/fast 2 часа назад\n/fast вчера 18:00"
                await _reply(update, text)
                return

        # Show time selector
        text = "🕐 Когда ты последний раз ел?\nВыбери время начала голодания:"
        keyboard = _selector_page1()

    await _reply(update, text, keyboard)


async def show_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show page 1 of time selector (called from 'fast_selector')."""
    text = "🕐 Когда ты последний раз ел?\nВыбери время начала голодания:"
    await _edit(update, text, _selector_page1())


async def show_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show page 2 of time selector (earlier dates)."""
    text = "📅 Вчера или раньше:"
    await _edit(update, text, _selector_page2())


async def handle_fast_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle fast_set:MINUTES callback — start fast N minutes ago."""
    query = update.callback_query
    minutes_ago = int(query.data.split(":")[1])
    user_id = update.effective_user.id

    now = datetime.now(timezone.utc)
    started_at = (now - timedelta(minutes=minutes_ago)).isoformat()

    await _start_fast_with_time(update, user_id, started_at, edit=True)


async def handle_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to type their own time."""
    text = (
        "✏️ Напиши время начала голодания.\n\n"
        "Форматы:\n"
        "<code>14:30</code> — сегодня в 14:30\n"
        "<code>14:30 вчера</code>\n"
        "<code>2 часа назад</code>\n"
        "<code>30 минут назад</code>\n"
        "<code>2026-07-07 12:00</code>"
    )
    await _edit(update, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("← К выбору времени", callback_data="fast_selector")]
    ]))


async def _start_fast_with_time(update: Update, user_id: int, started_at: str, edit: bool = False):
    """Start fast and show confirmation."""
    # Check again (race condition)
    active = get_active_fast(user_id)
    if active:
        started = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
        duration = int((datetime.now(timezone.utc) - started).total_seconds() / 60)
        text = (
            "⚠️ Ты уже голодаешь!\n"
            f"Начало: {started.strftime('%H:%M %d.%m')}\n"
            f"Длительность: {format_duration(duration)}"
        )
    else:
        record = start_fast(user_id, started_at=started_at)
        started = datetime.fromisoformat(record["started_at"].replace("Z", "+00:00"))
        text = (
            "🕐 <b>Голодание начато!</b>\n"
            f"Время: {started.strftime('%H:%M %d.%m')}\n"
        )
        if started_at:
            text += "⏪ <i>Время установлено вручную</i>\n"
        text += "\nНажми /eat когда начнёшь есть."

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽 /eat — Поел", callback_data="cmd_eat")],
        [InlineKeyboardButton("📊 /status — Статус", callback_data="cmd_status")],
    ])

    if edit:
        await _edit(update, text, keyboard)
    else:
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


# ─── Reply helpers ───────────────────────────────────────────

async def _edit(update: Update, text: str, keyboard=None):
    """Edit the current inline message."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _reply(update: Update, text: str, keyboard=None):
    """Reply to message or callback query."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
