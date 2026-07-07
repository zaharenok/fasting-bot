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
    handle_custom_time,
)
from bot.handlers.status import cmd_status
from bot.handlers.stats import cmd_stats
from bot.handlers.history import cmd_history
from bot.handlers.dashboard import cmd_dashboard
from bot.db import get_active_fast, start_fast
from bot.handlers.fast import _parse_time, _action_keyboard

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
        "fast_selector": show_selector,
        "fast_more": show_more,
        "fast_back": show_selector,
        "fast_custom": handle_custom_time,
    }

    handler = cmd_map.get(query.data)
    if handler:
        await handler(update, context)


async def custom_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text time input (after tapping 'Своё время' or typing raw time)."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Only respond if looks like a time input
    time_patterns = [
        r'^\d{1,2}:\d{2}',                          # 14:30
        r'^\d{1,2}:\d{2}\s+вчера',                   # 14:30 вчера
        r'^\d+\s*(ч|час|часа|часов|h|м|мин|минут)',  # 2 часа, 30 минут
        r'^\d{4}-\d{2}-\d{2}'
    ]
    if not any(re.match(p, text.lower()) for p in time_patterns):
        return  # not a time input, ignore

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

    # Check for active fast
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

    from bot.utils import format_duration
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

    # Fast time presets (fast_set:N)
    app.add_handler(CallbackQueryHandler(handle_fast_set, pattern=r"^fast_set:\d+$"))

    # Other inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Free-text time input (e.g. "14:30", "2 часа назад")
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_time_text))

    logger.info("Bot started polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
