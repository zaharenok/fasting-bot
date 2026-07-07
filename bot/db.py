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
    """)
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
    conn = _get_conn()
    active = get_active_fast(telegram_id)
    if not active:
        return None

    now = utcnow()
    started = datetime.fromisoformat(active["started_at"])
    duration = int((now - started).total_seconds() / 60)

    conn.execute(
        "UPDATE fasts SET ended_at = ?, duration_minutes = ? WHERE id = ?",
        (now.isoformat(), duration, active["id"]),
    )
    conn.commit()

    return {**active, "ended_at": now.isoformat(), "duration_minutes": duration}


def get_active_fast(telegram_id: int) -> Optional[dict]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT * FROM fasts WHERE user_id = ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
        (telegram_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


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

    # Current fasting?
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

    # Mark used
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
