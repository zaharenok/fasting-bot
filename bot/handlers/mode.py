"""Handler for /mode command — set fasting schedule."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import FASTING_MODES, get_fasting_mode, set_fasting_mode, get_goal, set_goal


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show/select fasting mode."""
    user_id = update.effective_user.id
    current = get_fasting_mode(user_id)

    text = "⏱ <b>Режим голодания</b>\n\n"
    if current and current["key"]:
        text += f"Текущий: <b>{current['label']}</b>\n"
        text += f"Голод: <b>{current['fast_hours']}ч</b> — Окно: <b>{current['eat_hours']}ч</b>\n\n"
    else:
        text += "Сейчас: <i>без режима</i>\n\n"

    text += "Выбери режим:"

    keyboard = []
    for key, fast_h, eat_h, label in FASTING_MODES:
        prefix = "✅ " if (current and current["key"] == key) else ""
        btn = InlineKeyboardButton(
            f"{prefix}{label}" if not prefix else f"✅ {label}",
            callback_data=f"mode_set:{key}",
        )
        keyboard.append([btn])

    await _reply(update, text, InlineKeyboardMarkup(keyboard))


async def handle_mode_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mode_set:KEY callback."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    key = query.data.split(":", 1)[1]
    mode = None
    for k, fh, eh, label in FASTING_MODES:
        if k == key:
            mode = (k, fh, eh, label)
            break

    if not mode:
        await query.edit_message_text("❌ Режим не найден.", parse_mode="HTML")
        return

    set_fasting_mode(user_id, mode[0])

    # Also auto-set goal to match the fast duration if it's not a free mode
    if mode[0] and mode[1] > 0:
        set_goal(user_id, mode[1] * 60)
        goal_text = f"\n\n🎯 Цель автоустановлена: <b>{mode[1]}ч</b>"
    else:
        set_goal(user_id, None)
        goal_text = ""

    text = (
        f"✅ <b>Режим установлен:</b> {mode[3]}\n\n"
        f"⏳ Голодать: <b>{mode[1]}ч</b>\n"
        f"🍽 Окно еды: <b>{mode[2]}ч</b>{goal_text}\n\n"
        "Когда начнёшь фаст — я буду считать и напомню, "
        "когда придёт время поесть."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _reply(update: Update, text: str, keyboard=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
