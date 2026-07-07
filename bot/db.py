"""Supabase database layer for Fasting Bot."""

from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client

from bot.config import SUPABASE_URL, SUPABASE_KEY


_supabase: Optional[Client] = None


def get_db() -> Client:
    """Get singleton Supabase client."""
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def utcnow():
    return datetime.now(timezone.utc)


# ─── Users ───────────────────────────────────────────────────

def get_or_create_user(telegram_id: int, username: str = "", first_name: str = "") -> dict:
    """Get user by telegram_id. Create if not exists."""
    db = get_db()
    result = db.table("users").select("*").eq("telegram_id", telegram_id).maybe_single().execute()
    if result.data:
        return result.data

    # Create new user
    user = {
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
    }
    db.table("users").insert(user).execute()
    return user


def get_user(telegram_id: int) -> Optional[dict]:
    """Get user by telegram_id."""
    db = get_db()
    result = db.table("users").select("*").eq("telegram_id", telegram_id).maybe_single().execute()
    return result.data


# ─── Fasts ───────────────────────────────────────────────────

def start_fast(telegram_id: int) -> dict:
    """Start a new fasting period. Returns the created fast record."""
    db = get_db()
    fast = {
        "user_id": telegram_id,
        "started_at": utcnow().isoformat(),
    }
    result = db.table("fasts").insert(fast).execute()
    return result.data[0]


def end_fast(telegram_id: int) -> Optional[dict]:
    """End the current active fast. Returns updated fast or None if no active fast."""
    db = get_db()
    active = get_active_fast(telegram_id)
    if not active:
        return None

    now = utcnow()
    started = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
    duration = int((now - started).total_seconds() / 60)

    result = (
        db.table("fasts")
        .update({
            "ended_at": now.isoformat(),
            "duration_minutes": duration,
        })
        .eq("id", active["id"])
        .execute()
    )
    return result.data[0] if result.data else None


def get_active_fast(telegram_id: int) -> Optional[dict]:
    """Get current active fast (ended_at IS NULL)."""
    db = get_db()
    result = (
        db.table("fasts")
        .select("*")
        .eq("user_id", telegram_id)
        .is_("ended_at", "null")
        .order("started_at", desc=True)
        .limit(1)
        .maybe_single()
        .execute()
    )
    return result.data


def cancel_fast(telegram_id: int) -> bool:
    """Cancel active fast without recording duration."""
    db = get_db()
    active = get_active_fast(telegram_id)
    if not active:
        return False
    db.table("fasts").delete().eq("id", active["id"]).execute()
    return True


def get_fast_history(telegram_id: int, limit: int = 20) -> list:
    """Get completed fasts, newest first."""
    db = get_db()
    result = (
        db.table("fasts")
        .select("*")
        .eq("user_id", telegram_id)
        .not_.is_("ended_at", "null")
        .order("ended_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_stats(telegram_id: int) -> dict:
    """Get fasting stats for a user."""
    db = get_db()
    result = db.rpc("get_user_stats", {"p_telegram_id": telegram_id}).execute()
    if result.data:
        return result.data[0]
    return {}


def get_all_completed_fasts(telegram_id: int) -> list:
    """Get ALL completed fasts for charts/stats."""
    db = get_db()
    result = (
        db.table("fasts")
        .select("*")
        .eq("user_id", telegram_id)
        .not_.is_("ended_at", "null")
        .order("ended_at", desc=True)
        .execute()
    )
    return result.data or []


# ─── Dashboard Tokens ────────────────────────────────────────

def create_dashboard_token(telegram_id: int) -> dict:
    """Create a one-time dashboard access token."""
    db = get_db()
    result = (
        db.table("dashboard_tokens")
        .insert({"user_id": telegram_id})
        .execute()
    )
    return result.data[0] if result.data else None


def use_dashboard_token(token: str) -> Optional[dict]:
    """Validate and consume a dashboard token. Returns user data or None."""
    db = get_db()
    result = (
        db.table("dashboard_tokens")
        .select("*")
        .eq("token", token)
        .is_("used_at", "null")
        .maybe_single()
        .execute()
    )
    if not result.data:
        return None

    token_data = result.data
    expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        return None

    # Mark as used
    db.table("dashboard_tokens").update({"used_at": utcnow().isoformat()}).eq("token", token).execute()

    # Return user
    user = db.table("users").select("*").eq("telegram_id", token_data["user_id"]).maybe_single().execute()
    return user.data


# ─── Admin queries ───────────────────────────────────────────

def get_all_users() -> list:
    """Get all users for admin dashboard."""
    db = get_db()
    result = db.table("users").select("*").order("created_at", desc=True).execute()
    return result.data or []


def get_admin_stats() -> dict:
    """Get overall bot stats for admin dashboard."""
    db = get_db()
    today = utcnow().strftime("%Y-%m-%d")

    # Total users
    total_users = db.table("users").select("telegram_id", count="exact").execute()
    # Active today
    active_today = (
        db.table("fasts")
        .select("id", count="exact")
        .gte("started_at", f"{today}T00:00:00Z")
        .execute()
    )
    # Fasts today
    fasts_today = (
        db.table("fasts")
        .select("id", count="exact")
        .gte("created_at", f"{today}T00:00:00Z")
        .execute()
    )
    # Premium users
    premium = (
        db.table("users")
        .select("telegram_id", count="exact")
        .eq("is_premium", True)
        .execute()
    )

    return {
        "total_users": total_users.count or 0,
        "active_today": active_today.count or 0,
        "fasts_today": fasts_today.count or 0,
        "premium_users": premium.count or 0,
    }
