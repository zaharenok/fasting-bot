"""Scheduler — periodic checks for goal reminders, morning reminders, and tips.

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
from bot.tips import TIPS, format_tip

logger = logging.getLogger(__name__)

# In-memory tracking — prevents duplicate messages. Resets on restart.
_sent_goal_reminders: set[str] = set()  # keys: "{uid}:{fast_id}:goal" / "{uid}:{fast_id}:pre"
_sent_morning: set[str] = set()         # keys: "{uid}:{date}"
_sent_tips: set[str] = set()            # keys: "{uid}:{fast_id}:tip_{minutes}"


async def scheduler_tick(context: ContextTypes.DEFAULT_TYPE):
    """Called every 60 seconds by JobQueue. Checks all conditions."""
    bot = context.bot
    now = utcnow()

    # Get all users with active fasts (no goal required)
    from bot.db import _get_conn
    conn = _get_conn()
    cur = conn.execute("""
        SELECT u.telegram_id, u.goal_minutes, u.goal_reminder_minutes,
               f.started_at, f.id as fast_id
        FROM users u
        JOIN fasts f ON f.user_id = u.telegram_id AND f.ended_at IS NULL
    """)
    all_active = [dict(r) for r in cur.fetchall()]

    for u in all_active:
        uid = u["telegram_id"]
        goal_min = u["goal_minutes"]
        reminder_offset = u["goal_reminder_minutes"] or 30
        fast_id = u["fast_id"]

        started = datetime.fromisoformat(u["started_at"].replace("Z", "+00:00"))
        current_min = int((now - started).total_seconds() / 60)

        # ── A. Goal reminders ───────────────────────────────
        if goal_min:
            remaining = goal_min - current_min

            # Goal reached
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
                        logger.info(f"Goal reached for {uid}: {format_duration(goal_min)}")
                    except Exception as e:
                        logger.error(f"Goal msg failed for {uid}: {e}")

            # Pre-goal reminder
            elif 0 < remaining <= reminder_offset:
                pre_key = f"{uid}:{fast_id}:pre"
                if pre_key not in _sent_goal_reminders:
                    _sent_goal_reminders.add(pre_key)
                    try:
                        await bot.send_message(
                            chat_id=uid,
                            text=(
                                f"⏰ <b>Скоро достигнешь цели!</b>\n"
                                f"Осталось <b>{format_duration(remaining)}</b>\n"
                                f"Цель: {format_duration(goal_min)}\n\n"
                                "Держись, ты справишься! 💪"
                            ),
                            parse_mode="HTML",
                        )
                        logger.info(f"Pre-goal for {uid}: {remaining} min to go")
                    except Exception as e:
                        logger.error(f"Pre-goal msg failed for {uid}: {e}")

        # ── B. Periodic tips ─────────────────────────────────
        # Send tips at key milestones during the fast
        for tip_minutes, emoji, title, body in TIPS:
            # Send when within 2 minutes of milestone
            if abs(current_min - tip_minutes) <= 2:
                tip_key = f"{uid}:{fast_id}:tip_{tip_minutes}"
                if tip_key not in _sent_tips:
                    _sent_tips.add(tip_key)
                    try:
                        msg = format_tip((tip_minutes, emoji, title, body))
                        await bot.send_message(chat_id=uid, text=msg, parse_mode="HTML")
                        logger.info(f"Tip {tip_minutes}min sent to {uid}")
                    except Exception as e:
                        logger.error(f"Tip failed for {uid}: {e}")

    # ── C. Morning reminders ────────────────────────────────
    users_morning = get_users_with_morning_reminder()
    for u in users_morning:
        uid = u["telegram_id"]
        reminder_time = u["morning_reminder"]
        if not reminder_time:
            continue

        try:
            rem_h, rem_m = map(int, reminder_time.split(":"))
        except (ValueError, AttributeError):
            continue

        vienna_now = now + timedelta(hours=2)
        current_minutes = vienna_now.hour * 60 + vienna_now.minute
        target_minutes = rem_h * 60 + rem_m

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
                    logger.error(f"Morning reminder failed for {uid}: {e}")
