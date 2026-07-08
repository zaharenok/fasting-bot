"""Handler for /checkin command — track mood and energy during a fast."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.db import save_checkin, get_active_fast_id, get_recent_checkins, get_checkin_stats, get_active_fast
from bot.utils import format_duration
from datetime import datetime, timezone


FEELINGS = [
    ("🔥", "отлично", "Прекрасное самочувствие, энергия бьёт ключом!"),
    ("💪", "хорошо", "Чувствуешь себя хорошо — лёгкость и бодрость."),
    ("🙂", "нормально", "Стабильно, ничего не мешает."),
    ("😴", "устал", "Чувствуешь усталость или сонливость."),
    ("🤤", "голоден", "Хочется есть — и это нормально, скоро пройдёт!"),
    ("😵", "слабость", "Кружится голова или слабость — возможно, нужна соль/вода."),
    ("🥴", "раздражает", "Раздражительность — тоже симптом перестройки организма."),
]

ENERGY_LABELS = {1: "🪫", 2: "🔋", 3: "⚡", 4: "🔥", 5: "💫"}


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check in: how are you feeling right now during your fast?"""
    user_id = update.effective_user.id
    fast = get_active_fast(user_id)

    if not fast:
        text = (
            "📝 <b>Ты сейчас не голодаешь.</b>\n\n"
            "Чек-ины доступны только во время голодания.\n"
            "Начни с /fast и возвращайся!"
        )
        await _respond(update, text)
        return

    started = datetime.fromisoformat(fast["started_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    duration = int((now - started).total_seconds() / 60)

    text = (
        f"📝 <b>Как ты себя чувствуешь?</b>\n"
        f"⏳ Голодаешь: {format_duration(duration)}\n\n"
        "Выбери своё состояние 👇"
    )

    # Build feeling buttons
    keyboard = []
    row = []
    for emoji, label, _ in FEELINGS:
        btn = InlineKeyboardButton(f"{emoji} {label}", callback_data=f"feel:{label}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("📊 Мои чекины", callback_data="feel_stats")])

    await _respond(update, text, InlineKeyboardMarkup(keyboard))


async def handle_feeling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feeling selection callback."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    feeling = query.data.split(":")[1]
    fast_id = get_active_fast_id(user_id)

    if not fast_id:
        await query.edit_message_text(
            "❌ Нет активного голодания. Начни с /fast",
            parse_mode="HTML",
        )
        return

    # Find the description
    desc = ""
    tip = ""
    for emoji, label, d in FEELINGS:
        if label == feeling:
            desc = d
            break

    # Save checkin
    save_checkin(user_id, fast_id, feeling, energy=3)

    # Response based on feeling
    feel_texts = {
        "отлично": "🔥 Круто! Организм адаптируется, кетоны дают энергию. Продолжай в том же духе!",
        "хорошо": "💪 Отлично, стабильное состояние — признак того, что организм перестроился на жиросжигание.",
        "нормально": "🙂 Стабильность — признак мастерства. Всё идёт по плану.",
        "устал": "😴 Это норма на фазе адаптации. Сделай это:\n"
                 "1️⃣ Стакан воды с щепоткой соли — восстановит электролиты\n"
                 "2️⃣ Если есть — магний (цитрат/глицинат) расслабит сосуды\n"
                 "3️⃣ Прогуляйся на свежем воздухе\n\n"
                 "Первые 3-5 дней может быть вялость — проходит, когда организм перестроится на кетоны.",
        "голоден": "🤤 Чувство голода приходит волнами. Обычно хватает 15-20 минут и оно отступает.\n\n"
                   "🥤 Выпей воды — часто мозг путает жажду с голодом.\n"
                   "☕ Кофе или зелёный чай без сахара тоже притупляют голод.",
        "слабость": "😵 <b>Это классический «кето-грипп».</b>\n\n"
                    "Организм перестраивается, теряет воду и соль. Вот что поможет:\n\n"
                    "🧂 <b>Соль — самое важное.</b> Щепотка гималайской или морской соли "
                    "на стакан тёплой воды. Головная боль уходит за 30-40 мин.\n\n"
                    "💧 <b>Не пей пустую воду</b> — она вымывает остатки минералов. "
                    "Лучше минералка (Donat/Sulinka) или травяной чай.\n\n"
                    "🥬 В окно еды: салат из огурцов, зелени, авокадо — это калий.\n"
                    "💊 Магний на ночь — расслабляет сосуды и улучшает сон.\n\n"
                    "Если слабость сильная — прерви голодание и поешь лёгкого белка с жирами.",
        "раздражает": "🥴 Раздражительность — признак перестройки нервной системы на кетоны. "
                      "Поможет:\n"
                      "🧂 Вода с солью\n"
                      "🚶 Прогулка на воздухе\n"
                      "💊 Магний вечером\n\n"
                      "Через 3-5 дней это пройдёт.",
    }
    advice = feel_texts.get(feeling, "")

    text = (
        f"✅ <b>Записал:</b> {desc}\n\n"
        f"{advice}\n\n"
        "Как у тебя с энергией по шкале от 1 до 5? 👇"
    )

    # Energy level buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🪫 1 — совсем нет сил", callback_data=f"energy:1")],
        [InlineKeyboardButton("🔋 2 — вялость", callback_data=f"energy:2")],
        [InlineKeyboardButton("⚡ 3 — нормально", callback_data=f"energy:3")],
        [InlineKeyboardButton("🔥 4 — бодро", callback_data=f"energy:4")],
        [InlineKeyboardButton("💫 5 — суперэнергия", callback_data=f"energy:5")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handle_energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle energy level callback."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    level = int(query.data.split(":")[1])

    # Update the last checkin with energy level
    checkins = get_recent_checkins(user_id, limit=1)
    if checkins:
        fast_id = get_active_fast_id(user_id)
        # Just re-save with energy included to keep it simple
        last = checkins[0]
        save_checkin(user_id, fast_id or 0, last["feeling"], energy=level)

    icon = ENERGY_LABELS.get(level, "⚡")
    if level >= 4:
        mood = "Бодрячком! 🔥 Жиросжигание на полную."
    elif level >= 3:
        mood = "Нормальный уровень — всё в порядке."
    elif level >= 2:
        mood = "Маловато энергии. Попробуй добавку соли или выйди на прогулку."
    else:
        mood = "Совсем нет сил. Возможно, стоит прервать голодание и поесть лёгкой пищи."

    text = (
        f"✅ <b>Чекин сохранён!</b>\n"
        f"Энергия: {icon} {level}/5\n"
        f"Состояние: {mood}\n\n"
        "Отслеживай своё самочувствие каждый час, чтобы лучше понять свой организм! 📊"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Ещё чекин", callback_data="cmd_checkin"),
         InlineKeyboardButton("📊 Статистика", callback_data="feel_stats")],
        [InlineKeyboardButton("🍽 Поел /eat", callback_data="cmd_eat")],
    ])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def feel_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show checkin statistics."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    stats = get_checkin_stats(user_id)
    checkins = get_recent_checkins(user_id, limit=10)

    text = "📊 <b>Твои чекины (30 дней)</b>\n\n"

    if stats["total"] == 0:
        text += "Пока нет данных. Начни с /checkin во время фаста!"
    else:
        text += f"Всего: <b>{stats['total']}</b>\n\n"
        for feeling, cnt in stats["breakdown"].items():
            emoji = ""
            for e, label, _ in FEELINGS:
                if label == feeling:
                    emoji = e
                    break
            bar = "█" * cnt + "░" * (10 - min(cnt, 10))
            text += f"{emoji} {feeling}: {bar} {cnt}\n"

        text += "\n<b>Последние:</b>\n"
        for c in checkins[:5]:
            from datetime import datetime as dt2
            energy_icon = ENERGY_LABELS.get(c.get("energy", 3), "⚡")
            text += f"• {c['feeling']} {energy_icon} ({c['created_at'][:16]})\n"

    await query.edit_message_text(text, parse_mode="HTML")


async def _respond(update: Update, text: str, keyboard=None):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
