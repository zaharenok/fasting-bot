"""Fasting Bot — Web Dashboard (FastAPI).

Run: uvicorn web.main:app --host 0.0.0.0 --port 8791
"""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from bot.config import ADMIN_TELEGRAM_ID
from bot.db import (
    get_user,
    get_active_fast,
    get_stats,
    get_fast_history,
    get_all_completed_fasts,
    use_dashboard_token,
    get_all_users,
    get_admin_stats,
)
from bot.utils import format_minutes_short, format_datetime
from bot.db import save_checkin, get_goal


app = FastAPI(title="Fasting Bot Dashboard")

# Jinja2 templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=True,
)


def render(template_name: str, **kwargs) -> HTMLResponse:
    """Render Jinja2 template to HTML response."""
    html = templates.get_template(template_name).render(**kwargs)
    return HTMLResponse(html)


# ─── Auth helper ─────────────────────────────────────────────

def _get_user_from_request(request: Request) -> Optional[dict]:
    """Get user from session cookie or token query param."""
    telegram_id = request.cookies.get("telegram_id")
    if telegram_id:
        user = get_user(int(telegram_id))
        if user:
            return user
    return None


# ─── Public routes ───────────────────────────────────────────

@app.get("/login")
async def login(token: str = Query(...)):
    """One-time login via dashboard token."""
    user = use_dashboard_token(token)
    if not user:
        return HTMLResponse("❌ Ссылка недействительна или истекла", status_code=401)

    # Set cookie and redirect to dashboard
    resp = RedirectResponse(url="/dashboard", status_code=302)
    resp.set_cookie(
        key="telegram_id",
        value=str(user["telegram_id"]),
        max_age=86400 * 30,  # 30 days
        httponly=True,
        secure=False,  # False for local dev
        samesite="lax",
    )
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request):
    """User's personal dashboard."""
    user = _get_user_from_request(request)
    if not user:
        return HTMLResponse(
            "❌ Не авторизован. Нажми /dashboard в боте для входа.",
            status_code=401,
        )

    telegram_id = user["telegram_id"]
    active = get_active_fast(telegram_id)
    stats = get_stats(telegram_id)
    recent = get_fast_history(telegram_id, limit=10)

    now = datetime.now(timezone.utc)

    # Current fast info
    current_minutes = 0
    if active:
        started = datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
        current_minutes = int((now - started).total_seconds() / 60)

    return render(
        "dashboard.html",
        user=user,
        active=active,
        current_minutes=current_minutes,
        stats=stats,
        recent=recent,
        now_iso=now.isoformat(),
    )


@app.get("/history", response_class=HTMLResponse)
async def user_history(request: Request):
    """Full history page."""
    user = _get_user_from_request(request)
    if not user:
        return HTMLResponse("❌ Не авторизован", status_code=401)

    fasts = get_all_completed_fasts(user["telegram_id"])
    return render("history.html", user=user, fasts=fasts)


@app.get("/stats", response_class=HTMLResponse)
async def user_stats_page(request: Request):
    """Stats page."""
    user = _get_user_from_request(request)
    if not user:
        return HTMLResponse("❌ Не авторизован", status_code=401)

    stats = get_stats(user["telegram_id"])
    fasts = get_all_completed_fasts(user["telegram_id"])
    return render("stats.html", user=user, stats=stats, fasts=fasts)


# ─── Mini App ────────────────────────────────────────────────

@app.get("/miniapp", response_class=HTMLResponse)
async def miniapp(request: Request):
    """Serve Telegram Mini App page."""
    return render("miniapp.html")


# ─── Mini App API ────────────────────────────────────────────

from bot.db import get_active_fast_id, start_fast, end_fast, cancel_fast as db_cancel_fast


@app.get("/api/mini/{user_id}")
async def mini_data(user_id: int):
    """Get all data for mini app: active fast, stats, goal, recent."""
    user_id_int = int(user_id)
    active = get_active_fast(user_id_int)
    stats = get_stats(user_id_int)
    goal = get_goal(user_id_int)
    recent = get_fast_history(user_id_int, limit=10)

    return {
        "active_fast": active,
        "stats": stats,
        "goal_minutes": goal,
        "recent": recent,
    }


@app.post("/api/mini/{user_id}/start")
async def mini_start(user_id: int):
    uid = int(user_id)
    start_fast(uid)
    return {"ok": True}


@app.post("/api/mini/{user_id}/stop")
async def mini_stop(user_id: int):
    uid = int(user_id)
    end_fast(uid)
    return {"ok": True}


@app.post("/api/mini/{user_id}/cancel")
async def mini_cancel(user_id: int):
    uid = int(user_id)
    db_cancel_fast(uid)
    return {"ok": True}


@app.post("/api/mini/{user_id}/checkin")
async def mini_checkin(user_id: int, data: dict):
    uid = int(user_id)
    fast_id = get_active_fast_id(uid) or 0
    feeling = data.get("feeling", "")
    energy = data.get("energy", 3)
    save_checkin(uid, fast_id, feeling, energy)
    return {"ok": True}


@app.get("/api/mini/{user_id}/history")
async def mini_history(user_id: int):
    uid = int(user_id)
    fasts = get_all_completed_fasts(uid)
    return {"fasts": fasts}


# ─── Admin routes ────────────────────────────────────────────

def _require_admin(request: Request):
    """Check if user is admin."""
    user = _get_user_from_request(request)
    if not user or user["telegram_id"] != ADMIN_TELEGRAM_ID:
        raise HTTPException(status_code=403, detail="Access denied")
    return user


@app.get("/admin/", response_class=HTMLResponse)
async def admin_overview(request: Request):
    """Admin dashboard — overview."""
    try:
        _require_admin(request)
    except HTTPException:
        return HTMLResponse("🚫 Доступ только для администратора", status_code=403)

    stats = get_admin_stats()
    users = get_all_users()
    return render("admin/overview.html", stats=stats, users=users)


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    """Admin — all users list."""
    try:
        _require_admin(request)
    except HTTPException:
        return HTMLResponse("🚫 Доступ только для администратора", status_code=403)

    users = get_all_users()
    return render("admin/users.html", users=users)


@app.get("/admin/metrics", response_class=HTMLResponse)
async def admin_metrics(request: Request):
    """Admin — usage metrics & charts."""
    try:
        _require_admin(request)
    except HTTPException:
        return HTMLResponse("🚫 Доступ только для администратора", status_code=403)

    users = get_all_users()
    fasts = []

    # Collect all fast data for charting
    all_fasts = []
    for u in users[:50]:  # Limit for performance
        user_fasts = get_all_completed_fasts(u["telegram_id"])
        all_fasts.extend(user_fasts)

    return render("admin/metrics.html", users=users, all_fasts=all_fasts)


# ─── API for chart data ──────────────────────────────────────

from fastapi.responses import JSONResponse


@app.get("/api/history/{telegram_id}")
async def api_history(telegram_id: int):
    """JSON endpoint for chart data."""
    fasts = get_all_completed_fasts(telegram_id)
    data = [
        {
            "date": f["ended_at"],
            "duration_minutes": f["duration_minutes"],
            "duration_short": format_minutes_short(f["duration_minutes"]),
        }
        for f in fasts
        if f["duration_minutes"]
    ]
    return JSONResponse(data)


@app.get("/api/admin/stats")
async def api_admin_stats():
    """JSON endpoint for admin charts."""
    stats = get_admin_stats()
    users = get_all_users()

    # Users over time (daily registration)
    from collections import Counter
    daily_users = Counter()
    for u in users:
        day = u["created_at"][:10] if u.get("created_at") else "unknown"
        daily_users[day] += 1

    return JSONResponse({
        "stats": stats,
        "users_over_time": dict(sorted(daily_users.items())),
        "total_users": len(users),
    })


# ─── Startup ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from bot.config import WEB_HOST, WEB_PORT
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT)
