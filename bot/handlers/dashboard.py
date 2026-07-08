"""Handler for /dashboard command — sends permanent direct link."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import DASHBOARD_BASE_URL


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a permanent dashboard link based on user's telegram_id."""
    user_id = update.effective_user.id
    url = f"{DASHBOARD_BASE_URL}/dashboard/{user_id}"

    text = (
        "🌐 <b>Твой дашборд</b>\n\n"
        f"Постоянная ссылка (никогда не сгорает):\n"
        f"{url}\n\n"
        "Там ты увидишь таймер, историю и графики."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Открыть дашборд", url=url)]
    ])

    await _reply(update, text, keyboard)


async def _reply(update: Update, text: str, keyboard=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            pass
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
