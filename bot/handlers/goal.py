"""Handler for /goal command — set and view fasting goals."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import get_goal, set_goal, get_reminder_info
from bot.utils import format_duration


PRESET_GOALS = [
    (12 * 60, "12ч — начало аутофагии"),
    (14 * 60, "14ч — хороший старт"),
    (16 * 60, "16:8 — классика 🔥"),
    (18 * 60, "18:6 — продвинутый"),
    (20 * 60, "20:4 — хардкор"),
    (24 * 60, "24ч — сутки 🏆"),
    (48 * 60, "48ч — эксперт 💪"),
    (72 * 60, "72ч — монах 🧘"),
]


async def cmd_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View or set fasting goal.

    /goal        → show current goal + preset buttons
    /goal 16     → set 16-hour goal
    /goal off    → disable goal
    """
    user_id = update.effective_user.id
    args = context.args

    # Handle setting goal via text argument
    if args:
        text = " ".join(args).lower().strip()
        if text in ("off", "0", "none", "no", "убрать", "нет", "выкл"):
            set_goal(user_id, None)
            await _respond(update, "🎯 <b>Цель убрана.</b> Голодай без ограничений!")
            return

        # Parse hours
        try:
            hours = int(text)
            if hours < 1 or hours > 168:
                await _respond(update, "❌ Цель должна быть от 1 до 168 часов.")
                return
            set_goal(user_id, hours * 60)
            await _respond(
                update,
                f"🎯 <b>Цель установлена:</b> {format_duration(hours * 60)}\n\n"
                "Я напомню, когда будешь близок к цели!"
            )
            return
        except ValueError:
            await _respond(
                update,
                "❌ <b>Не понял.</b>\n\n"
                "Примеры:\n"
                "<code>/goal 16</code> — цель 16 часов\n"
                "<code>/goal off</code> — убрать цель",
            )
            return

    # Show current goal + presets
    goal = get_goal(user_id)
    info = get_reminder_info(user_id)

    if goal:
        text = (
            f"🎯 <b>Твоя цель:</b> {format_duration(goal)}\n"
            f"⏰ Напоминание за {info['goal_reminder']} мин до цели\n\n"
            "<b>Выбери новую цель или нажми снизу:</b>"
        )
    else:
        text = (
            "🎯 <b>Цель не установлена.</b>\n\n"
            "Выбери продолжительность голодания ниже.\n"
            "Я пришлю напоминание, когда будешь близок к цели."
        )

    # Build preset keyboard
    keyboard = []
    row = []
    for minutes, label in PRESET_GOALS:
        btn = InlineKeyboardButton(label, callback_data=f"goal_set:{minutes}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🗑 Убрать цель", callback_data="goal_off"),
        InlineKeyboardButton("⏰ Напоминания", callback_data="cmd_reminder"),
    ])

    await _respond(update, text, InlineKeyboardMarkup(keyboard))


async def handle_goal_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle goal_set:MINUTES callback."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    minutes = int(query.data.split(":")[1])
    set_goal(user_id, minutes)

    text = (
        f"🎯 <b>Цель установлена:</b> {format_duration(minutes)}\n\n"
        "Я пришлю напоминание, когда будешь близок к цели!"
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад к целям", callback_data="cmd_goal")],
        [InlineKeyboardButton("🍽 Поел /eat", callback_data="cmd_eat")],
    ]))


async def handle_goal_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'goal_off' callback."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    set_goal(user_id, None)
    await query.edit_message_text(
        "🎯 <b>Цель убрана.</b> Голодай без ограничений!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🕐 Начать фаст", callback_data="cmd_fast")],
        ]),
    )


async def _respond(update: Update, text: str, keyboard=None):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
