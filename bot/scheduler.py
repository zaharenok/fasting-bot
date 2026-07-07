"""Scheduler — periodic checks for goal reminders and morning reminders.

Uses Application.job_queue. Run check every 60 seconds.
"""

import logging
from datetime import datetime, timezone, timedelta
from telegram.ext import ContextTypes

from bot.db import (
    get_active_users_with_goals,
    get_users_with_morning_reminder,
    get_goal_reminder_minutes,
    utcnow,
)
from bot.utils import format_duration

logger = logging.getLogger(__name__)

# In-memory set — tracking which reminders were already sent
# so we don't spam the same milestone. Resets on bot restart — fine for single user.
_sent_goal_reminders: set[str] = set()  # keys: "{telegram_id}:{fast_id}"
_sent_morning: set[str] = set()  # keys: "{telegram_id}:{date}"


async def scheduler_tick(context: ContextTypes.DEFAULT_TYPE):
    """Called every 60 seconds by JobQueue. Checks all conditions."""
    bot = context.bot
    now = utcnow()

    # ── 1. Goal reminders ──────────────────────────────────
    users = get_active_users_with_goals()
    for u in users:
        uid = u["telegram_id"]
        goal_min = u["goal_minutes"]
        reminder_offset = u["goal_reminder_minutes"] or 30
        fast_id = u["fast_id"]

        if not goal_min:
            continue

        started = datetime.fromisoformat(u["started_at"].replace("Z", "+00:00"))
        current_min = int((now - started).total_seconds() / 60)
        remaining = goal_min - current_min

        # Send at exactly the goal milestone
        if remaining <= 0:
            key = f"{uid}:{fast_id}:goal"
            if key not in _sent_goal_reminders:
                _sent_goal_reminders.add(key)
                try:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            f"🎯 <b>Цель достигнута!</b>\n"
                            f"Ты продержался {format_duration(goal_min)} без еды! 🏆\n\n"
                            "Можешь продолжать или поесть — ты молодец!"
                        ),
                        parse_mode="HTML",
                    )
                    logger.info(f"Goal reminder sent to {uid}: {format_duration(goal_min)}")
                except Exception as e:
                    logger.error(f"Failed to send goal reminder to {uid}: {e}")

        # Send pre-goal reminder (e.g., 30 min before goal)
        elif 0 < remaining <= reminder_offset:
            pre_key = f"{uid}:{fast_id}:pre"
            if pre_key not in _sent_goal_reminders:
                _sent_goal_reminders.add(pre_key)
                try:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            f"⏰ <b>Скоро достигнешь цели!</b>\n"
                            f"Осталось всего <b>{format_duration(remaining)}</b>\n"
                            f"Цель: {format_duration(goal_min)}\n\n"
                            "Держись, ты справишься! 💪"
                        ),
                        parse_mode="HTML",
                    )
                    logger.info(f"Pre-goal reminder sent to {uid}: {remaining} min to go")
                except Exception as e:
                    logger.error(f"Failed to send pre-goal reminder to {uid}: {e}")

    # ── 2. Morning reminders ───────────────────────────────
    users_morning = get_users_with_morning_reminder()
    for u in users_morning:
        uid = u["telegram_id"]
        reminder_time = u["morning_reminder"]
        if not reminder_time:
            continue

        # Parse reminder time into HH:MM
        try:
            rem_h, rem_m = map(int, reminder_time.split(":"))
        except (ValueError, AttributeError):
            continue

        # Vienna time approximate
        vienna_now = now + timedelta(hours=2)
        current_minutes = vienna_now.hour * 60 + vienna_now.minute
        target_minutes = rem_h * 60 + rem_m

        # Send within 2-minute window (prevent double-send)
        if abs(current_minutes - target_minutes) <= 1:
            today = vienna_now.strftime("%Y-%m-%d")
            key = f"{uid}:{today}"
            if key not in _sent_morning:
                _sent_morning.add(key)
                try:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            "☀️ <b>Доброе утро!</b>\n\n"
                            "Не забудь начать отсчёт голодания.\n"
                            "Нажми /fast, чтобы запустить таймер 🕐"
                        ),
                        parse_mode="HTML",
                    )
                    logger.info(f"Morning reminder sent to {uid}")
                except Exception as e:
                    logger.error(f"Failed to send morning reminder to {uid}: {e}")
