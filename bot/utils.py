"""Utility functions for formatting time and dates."""

from datetime import datetime, timedelta, timezone


def format_duration(minutes: int) -> str:
    """Format minutes into human-readable string.
    45m / 2h 15m / 16h 42m / 3d 5h
    """
    if minutes < 60:
        return f"{minutes}м"

    hours, mins = divmod(minutes, 60)
    if hours < 24:
        if mins == 0:
            return f"{hours}ч"
        return f"{hours}ч {mins}м"

    days, rem = divmod(hours, 24)
    if rem == 0:
        return f"{days}д"
    return f"{days}д {rem}ч"


def format_minutes_short(minutes: int) -> str:
    """Short format: '14h 32m' or '3d 2h'."""
    if minutes < 60:
        return f"{minutes}m"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {mins}m"
    days, rem = divmod(hours, 24)
    return f"{days}d {rem}h"


def format_datetime(dt_str: str) -> str:
    """Format ISO datetime for the user (Vienna timezone)."""
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    # Europe/Vienna is UTC+1/+2
    vienna_offset = timedelta(hours=2)  # CEST (summer)
    # Simple heuristic: detect summer time
    # In reality use pytz, but keeping deps light
    vienna = dt + timedelta(hours=1)
    if dt.month >= 3 and dt.month <= 10:
        vienna = dt + timedelta(hours=2)
    return vienna.strftime("%d.%m.%Y %H:%M")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
