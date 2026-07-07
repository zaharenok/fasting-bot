# Fasting Bot 🕐🍽

Telegram bot that tracks your fasting periods. Start / stop fasting with a tap, see your history, stats, and web dashboard.

## Stack

- **Bot:** Python + python-telegram-bot (async polling)
- **DB:** Supabase (PostgreSQL)
- **Web:** FastAPI + Jinja2 + Tailwind CDN
- **Deploy:** systemd on Linux VPS
- **Monetization:** Telegram Stars (freemium)

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + instructions |
| `/fast` | Start a new fasting period |
| `/eat` | End fasting, record duration |
| `/status` | How long since last meal |
| `/stats` | Your fasting stats |
| `/history` | Last 20 fasts |
| `/dashboard` | Link to web dashboard |
| `/premium` | Upgrade to premium |
| `/cancel` | Cancel active fast |

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill .env with your credentials
python -m bot.main
```

## Web Dashboard

```bash
uvicorn web.main:app --host 0.0.0.0 --port 8791
```

User dashboard: `http://localhost:8791/login?token=<token>`
Admin dashboard: `http://localhost:8791/admin/` (your Telegram ID only)

## Project Structure

```
fasting-bot/
├── bot/               # Telegram bot
│   ├── main.py        # Entry point (polling)
│   ├── config.py      # Config from env
│   ├── db.py          # Supabase client
│   ├── utils.py       # Formatting helpers
│   └── handlers/      # Command handlers
├── web/               # FastAPI web app
│   ├── main.py        # Routes
│   └── templates/     # Jinja2 HTML
├── supabase/
│   └── schema.sql     # DB migration
├── requirements.txt
└── .env.example
```
