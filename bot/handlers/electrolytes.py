"""Handler for /electrolytes — quick guide to surviving keto flu."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def cmd_electrolytes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the electrolyte survival guide."""
    text = (
        "🧂 <b>Электролиты: скорая помощь</b>\n\n"
        "Головная боль, слабость, раздражительность во время голодания — "
        "это почти всегда потеря электролитов.\n\n"
        "▸ <b>Соль (натрий)</b> — самое важное\n"
        "Щепотка гималайской или морской соли на стакан тёплой воды. "
        "Головная боль уходит за 30-40 мин.\n\n"
        "▸ <b>Магний</b> — от головной боли и сна\n"
        "Цитрат, малат или глицинат. Принять вечером — расслабляет сосуды "
        "и улучшает сон.\n\n"
        "▸ <b>Калий</b> — для сердца и мышц\n"
        "Огурцы, авокадо, зелень, минералка (Donat Mg, Sulinka).\n\n"
        "▸ <b>Вода</b> — но не пустая!\n"
        "Пустая вода без солей вымывает остатки минералов. Лучше: "
        "травяной чай, минералка, вода с лимоном и солью.\n\n"
        "🚫 <b>Чего НЕ делать:</b>\n"
        "▸ Пить литрами чистую воду — станет только хуже\n"
        "▸ Терпеть сильную головную боль — прерви фаст и поешь\n"
        "▸ Пить кофе на голодный желудок без соли — усилит обезвоживание\n\n"
        "💡 <b>Лайфхак:</b> если с утра выпиваешь стакан воды с солью "
        "и лимоном — адаптация проходит в 2 раза легче."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Чекин /checkin", callback_data="cmd_checkin"),
         InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast")],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
