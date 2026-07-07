"""Fasting Bot — main entry point.

Runs Telegram bot in polling mode.
Start: python -m bot.main
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from bot.config import BOT_TOKEN
from bot.handlers.start import start
from bot.handlers.fast import cmd_fast, cmd_eat, cmd_cancel
from bot.handlers.status import cmd_status
from bot.handlers.stats import cmd_stats
from bot.handlers.history import cmd_history
from bot.handlers.dashboard import cmd_dashboard

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callback data."""
    query = update.callback_query
    await query.answer()

    cmd_map = {
        "cmd_fast": cmd_fast,
        "cmd_eat": cmd_eat,
        "cmd_status": cmd_status,
        "cmd_stats": cmd_stats,
        "cmd_dashboard": cmd_dashboard,
        "cmd_history": cmd_history,
    }

    handler = cmd_map.get(query.data)
    if handler:
        await handler(update, context)


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

    # Inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot started polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
