"""Handler for /reminder command — configure notifications."""

import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import (
    get_morning_reminder,
    set_morning_reminder,
    get_goal_reminder_minutes,
    set_goal_reminder_minutes,
    get_goal,
)


async def cmd_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show / configure reminders.

    /reminder                     → show current settings
    /reminder morning 09:00       → set morning reminder
    /reminder morning off         → disable morning reminder
    /reminder goal 30             → remind 30 min before goal
    """
    user_id = update.effective_user.id
    args = context.args

    if args:
        cmd = args[0].lower()

        if cmd == "morning" and len(args) >= 2:
            time_val = args[1].lower()
            if time_val in ("off", "0", "none", "выкл", "нет"):
                set_morning_reminder(user_id, None)
                await _respond(update, "⏰ <b>Утреннее напоминание выключено.</b>")
            elif re.match(r'^\d{1,2}:\d{2}$', time_val):
                # Validate hour/minute
                h, m = map(int, time_val.split(":"))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    set_morning_reminder(user_id, f"{h:02d}:{m:02d}")
                    await _respond(
                        update,
                        f"⏰ <b>Утреннее напоминание установлено</b> на {h:02d}:{m:02d} 🕐\n\n"
                        "Каждый день в это время я буду напоминать начать голодание.",
                    )
                else:
                    await _respond(update, "❌ Неверное время. Используй формат HH:MM (например, 09:00).")
            else:
                await _respond(update, "❌ Формат: <code>/reminder morning 09:00</code>")
            return

        if cmd == "goal" and len(args) >= 2:
            try:
                mins = int(args[1])
                if mins < 0 or mins > 120:
                    await _respond(update, "❌ Напоминание должно быть от 0 до 120 минут до цели.")
                    return
                set_goal_reminder_minutes(user_id, mins)
                goal = get_goal(user_id)
                if goal:
                    await _respond(
                        update,
                        f"⏰ <b>Напоминание о цели:</b> за {mins} мин\n"
                        f"Предупрежу за {mins} мин до {mins // 60}ч цели.",
                    )
                else:
                    await _respond(
                        update,
                        f"⏰ <b>Напоминание установлено</b> за {mins} мин до цели.\n"
                        "Но цель пока не задана. Установи через /goal",
                    )
            except ValueError:
                await _respond(update, "❌ Формат: <code>/reminder goal 30</code> (минут до цели)")
            return

        await _respond(
            update,
            "❌ <b>Не понял.</b>\n\n"
            "<code>/reminder</code> — показать настройки\n"
            "<code>/reminder morning 09:00</code> — утреннее напоминание\n"
            "<code>/reminder morning off</code> — выключить\n"
            "<code>/reminder goal 30</code> — за сколько минут до цели напомнить",
        )
        return

    # Show current settings
    morning = get_morning_reminder(user_id)
    goal_rem = get_goal_reminder_minutes(user_id)
    goal = get_goal(user_id)

    text = "⏰ <b>Напоминания</b>\n\n"
    if morning:
        text += f"☀️ Утреннее: <b>{morning}</b>\n"
    else:
        text += "☀️ Утреннее: <i>выключено</i>\n"

    if goal:
        text += f"🎯 За {goal_rem} мин до цели ({goal // 60}ч): <b>включено</b>\n"
    else:
        text += "🎯 До цели: <i>цель не задана</i>\n"

    text += "\nВыбери, что настроить:"

    # Build keyboard based on state
    buttons = []
    if morning:
        buttons.append(InlineKeyboardButton("☀️ Убрать утро", callback_data="rem_morning_off"))
    else:
        buttons.append(InlineKeyboardButton("☀️ Вкл утро", callback_data="rem_morning_on"))

    buttons.append(InlineKeyboardButton("🎯 Интервал", callback_data="rem_goal_interval"))

    keyboard = InlineKeyboardMarkup([
        buttons,
        [InlineKeyboardButton("🎯 Установить цель", callback_data="cmd_goal")],
    ])

    await _respond(update, text, keyboard)


async def handle_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reminder inline button callbacks."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    data = query.data

    if data == "rem_morning_off":
        set_morning_reminder(user_id, None)
        await query.edit_message_text(
            "⏰ <b>Утреннее напоминание выключено.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="cmd_reminder")],
            ]),
        )

    elif data == "rem_morning_on":
        await query.edit_message_text(
            "⏰ <b>Напиши время для утреннего напоминания</b>\n\n"
            "Формат: <code>09:00</code>\n"
            "(просто напиши время в чат)",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="cmd_reminder")],
            ]),
        )

    elif data == "rem_goal_interval":
        await query.edit_message_text(
            "⏰ <b>За сколько минут до цели напомнить?</b>\n\n"
            "Сейчас: <code>30</code> мин\n\n"
            "Напиши число от 5 до 120 в чат.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="cmd_reminder")],
            ]),
        )


async def handle_reminder_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time text input for reminders (non-command text)."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Check if it looks like a time (HH:MM)
    import re
    if re.match(r'^\d{1,2}:\d{2}$', text):
        h, m = map(int, text.split(":"))
        if 0 <= h <= 23 and 0 <= m <= 59:
            set_morning_reminder(user_id, f"{h:02d}:{m:02d}")
            await update.message.reply_text(
                f"⏰ <b>Утреннее напоминание установлено</b> на {h:02d}:{m:02d} 🕐",
                parse_mode="HTML",
            )
            return

    # Check if it looks like a number (minutes for goal reminder)
    try:
        mins = int(text)
        if 5 <= mins <= 120:
            set_goal_reminder_minutes(user_id, mins)
            await update.message.reply_text(
                f"⏰ <b>Напоминание о цели:</b> за {mins} мин до цели.",
                parse_mode="HTML",
            )
            return
        elif 0 <= mins < 5:
            await update.message.reply_text("❌ Минимум 5 минут.")
            return
    except ValueError:
        pass

    # Not a valid input — ignore (could be a time for /fast)
    return


async def _respond(update: Update, text: str, keyboard=None):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
