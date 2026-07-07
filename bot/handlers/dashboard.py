"""Handler for /dashboard command."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import DASHBOARD_BASE_URL
from bot.db import create_dashboard_token


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a one-time dashboard link."""
    user_id = update.effective_user.id
    token_data = create_dashboard_token(user_id)
    if not token_data:
        await update.message.reply_text("❌ Не удалось создать ссылку. Попробуй позже.")
        return

    token = token_data["token"]
    url = f"{DASHBOARD_BASE_URL}/login?token={token}"

    text = (
        "🌐 <b>Твой дашборд</b>\n\n"
        "Ссылка действует 24 часа, одноразовая:\n"
        f"{url}\n\n"
        "Там ты увидишь таймер, историю и графики."
    )

    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
