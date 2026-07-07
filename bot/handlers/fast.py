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
            InlineKeyboardButton("30 мин назад", callback_data="fast_set:30"),
            InlineKeyboardButton("1 час назад", callback_data="fast_set:60"),
        ],
        [
            InlineKeyboardButton("2 часа назад", callback_data="fast_set:120"),
            InlineKeyboardButton("4 часа назад", callback_data="fast_set:240"),
            InlineKeyboardButton("8 часов назад", callback_data="fast_set:480"),
        ],
        [
            InlineKeyboardButton("12 часов назад", callback_data="fast_set:720"),
            InlineKeyboardButton("▶️ Ещё →", callback_data="fast_more"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _selector_page2() -> InlineKeyboardMarkup:
    """Page 2: yesterday and earlier."""
    keyboard = [
        [
            InlineKeyboardButton("📅 Вчера", callback_data="fast_set:1440"),
            InlineKeyboardButton("2 дня назад", callback_data="fast_set:2880"),
            InlineKeyboardButton("3 дня назад", callback_data="fast_set:4320"),
        ],
        [
            InlineKeyboardButton("✏️ Своё время", callback_data="fast_custom"),
            InlineKeyboardButton("← Назад", callback_data="fast_back"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _action_keyboard() -> InlineKeyboardMarkup:
    """Standard post-start/eat keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽 Поел /eat", callback_data="cmd_eat"),
         InlineKeyboardButton("📊 Статус /status", callback_data="cmd_status")],
        [InlineKeyboardButton("📋 История /history", callback_data="cmd_history"),
         InlineKeyboardButton("📈 Статистика /stats", callback_data="cmd_stats")],
    ])


# ─── Time parsing ────────────────────────────────────────────

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


# ─── Commands ────────────────────────────────────────────────

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
            "⚠️ <b>Ты уже голодаешь!</b>\n"
            f"Начало: <code>{started.strftime('%H:%M %d.%m')}</code>\n"
            f"⏳ Длится: <b>{format_duration(duration)}</b>\n\n"
            "Нажми /eat когда поешь, или /cancel чтобы отменить."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍽 Поел /eat", callback_data="cmd_eat")],
            [InlineKeyboardButton("🗑 Отменить /cancel", callback_data="cmd_cancel")],
        ])
        await _reply(update, text, keyboard)
        return

    # Check if user passed a time argument (e.g. /fast 14:30)
    args = context.args
    if args:
        custom_time = _parse_time(" ".join(args))
        if custom_time:
            await _start_fast_and_reply(update, user_id, custom_time)
            return
        text = (
            "❌ <b>Не понял время</b>\n\n"
            "Примеры:\n"
            "<code>/fast 14:30</code> — сегодня в 14:30\n"
            "<code>/fast 2 часа назад</code>\n"
            "<code>/fast вчера 18:00</code>"
        )
        await _reply(update, text)
        return

    # Show time selector
    text = (
        "🕐 <b>Когда ты последний раз ел?</b>\n\n"
        "Нажми на кнопку — сколько времени прошло с тех пор.\n"
        "👇"
    )
    await _reply(update, text, _selector_page1())


async def cmd_eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End the current fasting period (user ate)."""
    user_id = update.effective_user.id
    record = end_fast(user_id)

    if not record:
        text = "❌ <b>Нет активного голодания.</b> Начни с /fast"
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
            f"⏳ Длился: <b>{format_duration(duration_min)}</b>\n"
        )
        if duration_min >= best and best > 0:
            text += "🏆 <b>Новый рекорд!</b> Ты никогда не был так долго без еды!\n"

        text += (
            f"\n📊 Средний фаст: <b>{format_duration(int(avg))}</b>\n"
            f"🏆 Рекорд: <b>{format_duration(best)}</b>"
        )
        keyboard = _action_keyboard()

    await _reply(update, text, keyboard)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current active fast — with confirmation."""
    from bot.db import cancel_fast as db_cancel

    user_id = update.effective_user.id
    active = get_active_fast(user_id)
    if not active:
        text = "❌ Нет активного фаста для отмены."
        await _reply(update, text)
        return

    text = (
        "🗑 <b>Точно отменить фаст?</b>\n\n"
        "Все данные текущего голодания будут удалены без сохранения."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, отменить", callback_data="cancel_confirm"),
         InlineKeyboardButton("🔙 Нет, оставить", callback_data="cancel_abort")],
    ])
    await _reply(update, text, keyboard)


async def handle_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm cancel — actually delete the fast."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    from bot.db import cancel_fast as db_cancel

    if db_cancel(user_id):
        await query.edit_message_text(
            "🗑 <b>Фаст отменён.</b> Данные не сохранены.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🕐 Начать новый фаст", callback_data="cmd_fast")],
            ]),
        )
    else:
        await query.edit_message_text("❌ Ошибка при отмене.", parse_mode="HTML")


async def handle_cancel_abort(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abort cancel — keep the fast going."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    active = get_active_fast(user_id)
    if active:
        from datetime import datetime as dt, timezone as tz
        started = dt.fromisoformat(active["started_at"].replace("Z", "+00:00"))
        duration = int((dt.now(tz.utc) - started).total_seconds() / 60)
        text = (
            "👍 <b>Продолжаем голодание!</b>\n"
            f"⏳ Длится: {format_duration(duration)}"
        )
    else:
        text = "👍 Продолжаем!"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍽 Поел /eat", callback_data="cmd_eat"),
         InlineKeyboardButton("📊 Статус /status", callback_data="cmd_status")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


# ─── Time selector callbacks ─────────────────────────────────

async def show_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show page 1 of time selector."""
    await update.callback_query.answer()
    text = (
        "🕐 <b>Когда ты последний раз ел?</b>\n\n"
        "Нажми на кнопку — сколько времени прошло с тех пор.\n"
        "👇"
    )
    await _edit(update, text, _selector_page1())


async def show_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show page 2 of time selector (earlier dates)."""
    await update.callback_query.answer()
    text = (
        "📅 <b>Вчера или раньше</b>\n\n"
        "Выбери, сколько дней назад был последний приём пищи:\n"
        "👇"
    )
    await _edit(update, text, _selector_page2())


async def handle_fast_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle fast_set:MINUTES callback — start fast N minutes ago."""
    query = update.callback_query
    await query.answer()
    minutes_ago = int(query.data.split(":")[1])
    user_id = update.effective_user.id

    now = datetime.now(timezone.utc)
    started_at = (now - timedelta(minutes=minutes_ago)).isoformat()

    await _start_fast_and_reply(update, user_id, started_at, edit=True)


async def handle_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to type their own time."""
    await update.callback_query.answer()
    text = (
        "✏️ <b>Напиши время начала голодания</b>\n\n"
        "Форматы (пиши прямо в чат):\n"
        "• <code>14:30</code> — сегодня в 14:30\n"
        "• <code>14:30 вчера</code> — вчера\n"
        "• <code>2 часа назад</code>\n"
        "• <code>30 минут назад</code>\n"
        "• <code>2026-07-07 12:00</code>\n\n"
        "👇"
    )
    await _edit(update, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("← К выбору времени", callback_data="fast_selector")]
    ]))


# ─── Core logic ──────────────────────────────────────────────

async def _start_fast_and_reply(update: Update, user_id: int, started_at: str, edit: bool = False):
    """Start fast and show confirmation."""
    active = get_active_fast(user_id)
    if active:
        started = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
        duration = int((datetime.now(timezone.utc) - started).total_seconds() / 60)
        text = (
            "⚠️ <b>Ты уже голодаешь!</b>\n"
            f"Начало: <code>{started.strftime('%H:%M %d.%m')}</code>\n"
            f"⏳ Длится: <b>{format_duration(duration)}</b>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍽 Поел /eat", callback_data="cmd_eat")],
        ])
    else:
        record = start_fast(user_id, started_at=started_at)
        started = datetime.fromisoformat(record["started_at"].replace("Z", "+00:00"))
        text = (
            "🕐 <b>Голодание начато!</b>\n\n"
            f"Последний приём пищи: <code>{started.strftime('%H:%M %d.%m')}</code>\n"
            f"⏳ <b>Ты уже {format_duration(int((datetime.now(timezone.utc) - started).total_seconds() / 60))} без еды</b>\n\n"
            "Нажми /eat когда поешь."
        )
        keyboard = _action_keyboard()

    if edit:
        await _edit(update, text, keyboard)
    else:
        await _reply(update, text, keyboard)


# ─── Reply helpers ───────────────────────────────────────────

async def _edit(update: Update, text: str, keyboard=None):
    """Edit the current inline message."""
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass


async def _reply(update: Update, text: str, keyboard=None):
    """Reply to message or callback query."""
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
    else:
        if update.message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
