"""SQLite database layer for Fasting Bot (single-user mode)."""

import sqlite3
import uuid
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from bot.config import DB_PATH


_local = threading.local()
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """Get thread-local connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _init_db(_local.conn)
    return _local.conn


def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            is_premium INTEGER DEFAULT 0,
            premium_until TEXT
        );

        CREATE TABLE IF NOT EXISTS fasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(telegram_id),
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_minutes INTEGER,
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_fasts_user ON fasts(user_id);
        CREATE INDEX IF NOT EXISTS idx_fasts_active ON fasts(user_id, ended_at);

        CREATE TABLE IF NOT EXISTS dashboard_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(telegram_id),
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            used_at TEXT
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(telegram_id),
            fast_id INTEGER REFERENCES fasts(id),
            created_at TEXT DEFAULT (datetime('now')),
            feeling TEXT NOT NULL,
            energy INTEGER DEFAULT 3,
            note TEXT DEFAULT ''
        );
    """)

    # Migration: add columns that may not exist yet
    migs = [
        "ALTER TABLE users ADD COLUMN goal_minutes INTEGER",
        "ALTER TABLE users ADD COLUMN morning_reminder TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN goal_reminder_minutes INTEGER DEFAULT 30",
        "ALTER TABLE users ADD COLUMN fasting_mode TEXT DEFAULT ''",
    ]
    for sql in migs:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.commit()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Users ───────────────────────────────────────────────────

def get_or_create_user(telegram_id: int, username: str = "", first_name: str = "") -> dict:
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    if row:
        return dict(row)

    conn.execute(
        "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
        (telegram_id, username, first_name),
    )
    conn.commit()
    return {"telegram_id": telegram_id, "username": username, "first_name": first_name}


def get_user(telegram_id: int) -> Optional[dict]:
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    return dict(row) if row else None


# ─── Goals & Reminders ───────────────────────────────────────

def get_goal(telegram_id: int) -> Optional[int]:
    """Get goal duration in minutes, or None if not set."""
    conn = _get_conn()
    cur = conn.execute("SELECT goal_minutes FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    if row and row["goal_minutes"]:
        return row["goal_minutes"]
    return None


def set_goal(telegram_id: int, minutes: Optional[int]):
    """Set fasting goal in minutes. Pass None or 0 to disable."""
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET goal_minutes = ? WHERE telegram_id = ?",
        (minutes, telegram_id),
    )
    conn.commit()


def get_morning_reminder(telegram_id: int) -> Optional[str]:
    """Get morning reminder time (HH:MM) or None."""
    conn = _get_conn()
    cur = conn.execute("SELECT morning_reminder FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    val = row["morning_reminder"] if row else ""
    return val if val else None


def set_morning_reminder(telegram_id: int, time_str: Optional[str]):
    """Set morning reminder time. HH:MM format or None/empty to disable."""
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET morning_reminder = ? WHERE telegram_id = ?",
        (time_str or "", telegram_id),
    )
    conn.commit()


def get_goal_reminder_minutes(telegram_id: int) -> int:
    """Get how many minutes before goal to remind (default 30)."""
    conn = _get_conn()
    cur = conn.execute("SELECT goal_reminder_minutes FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    return row["goal_reminder_minutes"] if row else 30


def set_goal_reminder_minutes(telegram_id: int, minutes: int):
    """Set how many minutes before goal to send reminder."""
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET goal_reminder_minutes = ? WHERE telegram_id = ?",
        (minutes, telegram_id),
    )
    conn.commit()


def get_reminder_info(telegram_id: int) -> dict:
    """Get all reminder/goal settings for display."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT goal_minutes, morning_reminder, goal_reminder_minutes FROM users WHERE telegram_id = ?",
        (telegram_id,),
    )
    row = cur.fetchone()
    if not row:
        return {"goal": None, "morning": None, "goal_reminder": 30}
    return {
        "goal": row["goal_minutes"],
        "morning": row["morning_reminder"] if row["morning_reminder"] else None,
        "goal_reminder": row["goal_reminder_minutes"],
    }


# ─── Fasting Modes ────────────────────────────────────────────

FASTING_MODES = [
    ("", 0, 0, "Без режима — просто считаю часы"),
    ("16:8", 16, 8, "16:8 — классика 🔥"),
    ("18:6", 18, 6, "18:6 — продвинутый ⚡"),
    ("20:4", 20, 4, "20:4 — хардкор 💪"),
    ("OMAD", 23, 1, "OMAD — один приём в день 🍽️"),
]


def get_fasting_mode(telegram_id: int) -> Optional[dict]:
    conn = _get_conn()
    cur = conn.execute("SELECT fasting_mode FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    mode_key = row["fasting_mode"] if row and row["fasting_mode"] else ""
    for key, fast_h, eat_h, label in FASTING_MODES:
        if key == mode_key:
            return {"key": key, "fast_hours": fast_h, "eat_hours": eat_h, "label": label}
    return None


def set_fasting_mode(telegram_id: int, mode_key: str):
    conn = _get_conn()
    conn.execute("UPDATE users SET fasting_mode = ? WHERE telegram_id = ?", (mode_key, telegram_id))
    conn.commit()


# ─── Scheduler helpers ───────────────────────────────────────

def get_active_users_with_goals() -> list[dict]:
    """Get all users with active fast + goal set (for scheduler)."""
    conn = _get_conn()
    cur = conn.execute("""
        SELECT u.telegram_id, u.goal_minutes, u.goal_reminder_minutes,
               f.started_at, f.id as fast_id
        FROM users u
        JOIN fasts f ON f.user_id = u.telegram_id AND f.ended_at IS NULL
        WHERE u.goal_minutes IS NOT NULL AND u.goal_minutes > 0
    """)
    return [dict(r) for r in cur.fetchall()]


def get_users_with_morning_reminder() -> list[dict]:
    """Get all users with morning reminder enabled."""
    conn = _get_conn()
    cur = conn.execute("""
        SELECT telegram_id, morning_reminder
        FROM users
        WHERE morning_reminder IS NOT NULL AND morning_reminder != ''
    """)
    return [dict(r) for r in cur.fetchall()]


# ─── Fasts ───────────────────────────────────────────────────

def start_fast(telegram_id: int, started_at: Optional[str] = None) -> dict:
    """Start a new fasting period. Returns the created fast record."""
    conn = _get_conn()
    ts = started_at or utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO fasts (user_id, started_at) VALUES (?, ?)",
        (telegram_id, ts),
    )
    conn.commit()
    return {"id": cur.lastrowid, "user_id": telegram_id, "started_at": ts}


def end_fast(telegram_id: int) -> Optional[dict]:
    """End current active fast. Returns updated fast or None."""
    return end_fast_at(telegram_id, utcnow())


def end_fast_at(telegram_id: int, ended_at: datetime) -> Optional[dict]:
    """End current active fast at a specific time. Returns updated fast or None."""
    conn = _get_conn()
    active = get_active_fast(telegram_id)
    if not active:
        return None

    started = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
    duration = int((ended_at - started).total_seconds() / 60)

    conn.execute(
        "UPDATE fasts SET ended_at = ?, duration_minutes = ? WHERE id = ?",
        (ended_at.isoformat(), duration, active["id"]),
    )
    conn.commit()

    return {**active, "ended_at": ended_at.isoformat(), "duration_minutes": duration}


def get_active_fast(telegram_id: int) -> Optional[dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM fasts WHERE user_id = ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
        (telegram_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_fast_by_id(fast_id: int, user_id: int) -> Optional[dict]:
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM fasts WHERE id = ? AND user_id = ?", (fast_id, user_id))
    row = cur.fetchone()
    return dict(row) if row else None


def update_fast_times(fast_id: int, user_id: int, started_at: Optional[str] = None, ended_at: Optional[str] = None) -> bool:
    fast = get_fast_by_id(fast_id, user_id)
    if not fast:
        return False
    new_start = started_at or fast["started_at"]
    new_end = ended_at or fast["ended_at"]
    if new_end:
        s = datetime.fromisoformat(new_start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(new_end.replace("Z", "+00:00"))
        duration = int((e - s).total_seconds() / 60)
    else:
        duration = None
    conn = _get_conn()
    conn.execute("UPDATE fasts SET started_at = ?, ended_at = ?, duration_minutes = ? WHERE id = ?",
                 (new_start, new_end, duration, fast_id))
    conn.commit()
    return True


def cancel_fast(telegram_id: int) -> bool:
    conn = _get_conn()
    active = get_active_fast(telegram_id)
    if not active:
        return False
    conn.execute("DELETE FROM fasts WHERE id = ?", (active["id"],))
    conn.commit()
    return True


def get_fast_history(telegram_id: int, limit: int = 20) -> list:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM fasts WHERE user_id = ? AND ended_at IS NOT NULL ORDER BY ended_at DESC LIMIT ?",
        (telegram_id, limit),
    )
    return [dict(r) for r in cur.fetchall()]


def get_all_completed_fasts(telegram_id: int) -> list:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM fasts WHERE user_id = ? AND ended_at IS NOT NULL ORDER BY ended_at DESC",
        (telegram_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def get_stats(telegram_id: int) -> dict:
    """Compute stats from local SQLite."""
    conn = _get_conn()

    cur = conn.execute(
        "SELECT COUNT(*) as total, COALESCE(SUM(duration_minutes),0) as total_dur, "
        "COALESCE(AVG(duration_minutes),0) as avg_dur, "
        "COALESCE(MAX(duration_minutes),0) as longest "
        "FROM fasts WHERE user_id = ? AND ended_at IS NOT NULL",
        (telegram_id,),
    )
    row = cur.fetchone()

    active = get_active_fast(telegram_id)
    current_min = 0
    if active:
        started = datetime.fromisoformat(active["started_at"])
        current_min = int((utcnow() - started).total_seconds() / 60)

    return {
        "total_fasts": row["total"],
        "total_duration_minutes": row["total_dur"],
        "avg_duration_minutes": round(row["avg_dur"], 1),
        "longest_duration_minutes": row["longest"],
        "current_fasting": active is not None,
        "current_fasting_minutes": current_min,
    }


# ─── Checkins ──────────────────────────────────────────────────

def save_checkin(user_id: int, fast_id: int, feeling: str, energy: int = 3, note: str = "") -> dict:
    """Save a mood/feeling checkin."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO checkins (user_id, fast_id, feeling, energy, note) VALUES (?, ?, ?, ?, ?)",
        (user_id, fast_id, feeling, energy, note),
    )
    conn.commit()
    return {"id": cur.lastrowid, "feeling": feeling, "energy": energy}


def get_recent_checkins(user_id: int, limit: int = 10) -> list:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM checkins WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    return [dict(r) for r in cur.fetchall()]


def get_checkin_stats(user_id: int) -> dict:
    conn = _get_conn()
    cur = conn.execute("""
        SELECT feeling, COUNT(*) as cnt FROM checkins
        WHERE user_id = ? AND created_at >= datetime('now', '-30 days')
        GROUP BY feeling ORDER BY cnt DESC
    """, (user_id,))
    rows = cur.fetchall()
    total = sum(r["cnt"] for r in rows)
    return {"total": total, "breakdown": {r["feeling"]: r["cnt"] for r in rows}}


def get_active_fast_id(user_id: int):
    """Get the ID of the active fast, if any."""
    fast = get_active_fast(user_id)
    return fast["id"] if fast else None


# ─── Dashboard Tokens ────────────────────────────────────────

def create_dashboard_token(telegram_id: int) -> dict:
    conn = _get_conn()
    token = str(uuid.uuid4())
    expires = (utcnow() + timedelta(hours=24)).isoformat()
    conn.execute(
        "INSERT INTO dashboard_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, telegram_id, expires),
    )
    conn.commit()
    return {"token": token, "user_id": telegram_id}


def use_dashboard_token(token: str) -> Optional[dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM dashboard_tokens WHERE token = ? AND used_at IS NULL",
        (token,),
    )
    row = cur.fetchone()
    if not row:
        return None

    expires = datetime.fromisoformat(row["expires_at"])
    if utcnow() > expires:
        return None

    conn.execute("UPDATE dashboard_tokens SET used_at = ? WHERE token = ?", (utcnow().isoformat(), token))
    conn.commit()

    return get_user(row["user_id"])


# ─── Admin ────────────────────────────────────────────────────

def get_all_users() -> list:
    conn = _get_conn()
    cur = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
    return [dict(r) for r in cur.fetchall()]


def get_admin_stats() -> dict:
    conn = _get_conn()
    today = utcnow().strftime("%Y-%m-%d")

    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_today = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM fasts WHERE started_at >= ?", (today,)
    ).fetchone()[0]
    fasts_today = conn.execute(
        "SELECT COUNT(*) FROM fasts WHERE created_at >= ?", (today,)
    ).fetchone()[0]
    premium = conn.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1").fetchone()[0]

    return {
        "total_users": total,
        "active_today": active_today,
        "fasts_today": fasts_today,
        "premium_users": premium,
    }
