"""Fasting Bot — main entry point.

Runs Telegram bot in polling mode.
Start: python -m bot.main
"""

import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from bot.config import BOT_TOKEN
from bot.handlers.start import start
from bot.handlers.fast import (
    cmd_fast,
    cmd_eat,
    cmd_cancel,
    show_selector,
    show_more,
    handle_fast_set,
    handle_custom_time as fast_handle_custom,
    handle_cancel_confirm,
    handle_cancel_abort,
    handle_eat_set,
    handle_eat_custom,
    show_eat_selector,
    show_eat_more,
)
from bot.handlers.status import cmd_status
from bot.handlers.stats import cmd_stats
from bot.handlers.history import cmd_history
from bot.handlers.dashboard import cmd_dashboard
from bot.handlers.miniapp import cmd_miniapp
from bot.handlers.help import cmd_help
from bot.handlers.goal import cmd_goal, handle_goal_set, handle_goal_off
from bot.config import BOT_TOKEN
from bot.handlers.reminders import cmd_reminder, handle_reminder_callback, handle_reminder_time_input
from bot.handlers.checkin import cmd_checkin, handle_feeling, handle_energy, feel_stats
from bot.handlers.mode import cmd_mode, handle_mode_set
from bot.handlers.electrolytes import cmd_electrolytes
from bot.handlers.edit import cmd_edit, handle_edit_select, handle_edit_start, handle_edit_end, handle_edit_text
from bot.scheduler import scheduler_tick
from bot.db import get_active_fast, start_fast, get_user
from bot.handlers.fast import _parse_time, _action_keyboard
from bot.utils import format_duration

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle general inline keyboard callback data."""
    query = update.callback_query
    await query.answer()

    cmd_map = {
        "cmd_fast": cmd_fast,
        "cmd_eat": cmd_eat,
        "cmd_cancel": cmd_cancel,
        "cmd_status": cmd_status,
        "cmd_stats": cmd_stats,
        "cmd_dashboard": cmd_dashboard,
        "cmd_history": cmd_history,
        "cmd_goal": cmd_goal,
        "cmd_reminder": cmd_reminder,
        "cmd_checkin": cmd_checkin,
        "cmd_mode": cmd_mode,
        "cmd_electrolytes": cmd_electrolytes,
        "cmd_edit": cmd_edit,
        "feel_stats": feel_stats,
        "fast_selector": show_selector,
        "fast_more": show_more,
        "fast_back": show_selector,
        "fast_custom": fast_handle_custom,
    }

    handler = cmd_map.get(query.data)
    if handler:
        await handler(update, context)


async def combined_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all non-command text: reminder settings OR fast time input."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ── First try: parse as reminder setting ───────────────
    # HH:MM → morning reminder setting
    if re.match(r'^\d{1,2}:\d{2}$', text):
        h, m = map(int, text.split(":"))
        if 0 <= h <= 23 and 0 <= m <= 59:
            from bot.db import set_morning_reminder
            set_morning_reminder(user_id, f"{h:02d}:{m:02d}")
            await update.message.reply_text(
                f"⏰ <b>Утреннее напоминание установлено</b> на {h:02d}:{m:02d} 🕐",
                parse_mode="HTML",
            )
            return

    # Plain number 5-120 → goal reminder interval setting
    try:
        mins = int(text)
        if 5 <= mins <= 120:
            from bot.db import set_goal_reminder_minutes
            set_goal_reminder_minutes(user_id, mins)
            await update.message.reply_text(
                f"⏰ <b>Напоминание о цели:</b> за {mins} мин до цели.",
                parse_mode="HTML",
            )
            return
    except ValueError:
        pass

    # ── Second try: parse as fast start time ──────────────
    time_patterns = [
        r'^\d{1,2}:\d{2}',                          # 14:30
        r'^\d{1,2}:\d{2}\s+вчера',                   # 14:30 вчера
        r'^\d+\s*(ч|час|часа|часов|h|м|мин|минут)',  # 2 часа, 30 минут
        r'^\d{4}-\d{2}-\d{2}',
    ]
    if any(re.match(p, text.lower()) for p in time_patterns):
        parsed = _parse_time(text)
        if not parsed:
            await update.message.reply_text(
                "❌ <b>Не понял время.</b>\n\n"
                "Попробуй:\n"
                "<code>14:30</code> — сегодня\n"
                "<code>2 часа назад</code>\n"
                "<code>вчера 18:00</code>",
                parse_mode="HTML",
            )
            return

        active = get_active_fast(user_id)
        if active:
            await update.message.reply_text(
                "⚠️ <b>Ты уже голодаешь!</b>\n"
                "Сначала заверши /eat или отмени /cancel.",
                parse_mode="HTML",
            )
            return

        record = start_fast(user_id, started_at=parsed)
        from datetime import datetime as dt2, timezone as tz2
        started = dt2.fromisoformat(record["started_at"].replace("Z", "+00:00"))
        now = dt2.now(tz2.utc)
        dur = int((now - started).total_seconds() / 60)

        reply = (
            "🕐 <b>Голодание начато!</b>\n\n"
            f"Последний приём пищи: <code>{started.strftime('%H:%M %d.%m')}</code>\n"
            f"⏳ <b>Ты уже {format_duration(dur)} без еды</b>\n\n"
            "Нажми /eat когда поешь."
        )
        await update.message.reply_text(reply, parse_mode="HTML", reply_markup=_action_keyboard())


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Create .env from .env.example")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fast", cmd_fast))
    app.add_handler(CommandHandler("eat", cmd_eat))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("goal", cmd_goal))
    app.add_handler(CommandHandler("reminder", cmd_reminder))
    app.add_handler(CommandHandler("checkin", cmd_checkin))
    app.add_handler(CommandHandler("mood", cmd_checkin))
    app.add_handler(CommandHandler("miniapp", cmd_miniapp))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("electrolytes", cmd_electrolytes))
    app.add_handler(CommandHandler("edit", cmd_edit))

    # Fast time presets (fast_set:N)
    app.add_handler(CallbackQueryHandler(handle_fast_set, pattern=r"^fast_set:\d+$"))

    # Eat time presets (eat_set:N)
    app.add_handler(CallbackQueryHandler(handle_eat_set, pattern=r"^eat_set:\d+$"))
    app.add_handler(CallbackQueryHandler(handle_eat_custom, pattern=r"^eat_custom$"))
    app.add_handler(CallbackQueryHandler(show_eat_selector, pattern=r"^eat_selector$|^eat_back$"))
    app.add_handler(CallbackQueryHandler(show_eat_more, pattern=r"^eat_more$"))

    # Goal callbacks
    app.add_handler(CallbackQueryHandler(handle_goal_set, pattern=r"^goal_set:\d+$"))
    app.add_handler(CallbackQueryHandler(handle_goal_off, pattern=r"^goal_off$"))

    # Reminder callbacks
    app.add_handler(CallbackQueryHandler(handle_reminder_callback, pattern=r"^rem_"))

    # Checkin callbacks
    app.add_handler(CallbackQueryHandler(handle_feeling, pattern=r"^feel:"))
    app.add_handler(CallbackQueryHandler(handle_energy, pattern=r"^energy:\d+$"))
    app.add_handler(CallbackQueryHandler(feel_stats, pattern=r"^feel_stats$"))

    # Mode callback
    app.add_handler(CallbackQueryHandler(handle_mode_set, pattern=r"^mode_set:"))

    # Cancel confirmation
    app.add_handler(CallbackQueryHandler(handle_cancel_confirm, pattern=r"^cancel_confirm$"))
    app.add_handler(CallbackQueryHandler(handle_cancel_abort, pattern=r"^cancel_abort$"))

    # Edit callbacks
    app.add_handler(CallbackQueryHandler(handle_edit_select, pattern=r"^edit_fast:\d+$"))
    app.add_handler(CallbackQueryHandler(handle_edit_start, pattern=r"^edit_start:\d+$"))
    app.add_handler(CallbackQueryHandler(handle_edit_end, pattern=r"^edit_end:\d+$"))

    # Other inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Non-command text: reminder settings + fast time input
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_text_handler))

    # ── Scheduler: check every 60 seconds ─────────────
    app.job_queue.run_repeating(scheduler_tick, interval=60, first=30)

    logger.info("Bot started polling with scheduler...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
