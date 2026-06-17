import aiosqlite
import os
from datetime import date, timedelta
from contextlib import asynccontextmanager

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "engineerus.db")
os.makedirs(DB_DIR, exist_ok=True)

@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout=5000;")
        yield db

async def init_db():
    async with get_db() as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
            streak INTEGER DEFAULT 0, last_active DATE, is_premium BOOLEAN DEFAULT 0,
            daily_requests INTEGER DEFAULT 0, last_request_date DATE,
            requests_count INTEGER DEFAULT 0, material_count INTEGER DEFAULT 0,
            patent_count INTEGER DEFAULT 0, modules_used TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
            module TEXT NOT NULL, input_text TEXT, ai_response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
            achievement_code TEXT NOT NULL, earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, achievement_code))""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS research_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            authors TEXT, year INTEGER, url TEXT, pdf_path TEXT,
            category TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        
        await db.execute("""CREATE TABLE IF NOT EXISTS completed_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
            quest_id TEXT NOT NULL, completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, quest_id))""")
        
        # === АВТОМАТИЧЕСКИЕ АЛЬТЕРЫ (НАКАТЫВАЕМ НОВЫЕ КОЛОНКИ) ===
        try:
            await db.execute("ALTER TABLE users ADD COLUMN active_quest_type TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_daily_quest TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN preferred_lang TEXT DEFAULT 'ru'")
        except:
            pass
        
        #  НАКАТЫВАЕМ КОЛОНКУ ДЛЯ ХЭША ПАРОЛЯ
        try:
            await db.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            print(" Колонка password_hash успешно добавлена в таблицу users")
        except:
            pass
        
        await db.commit()
    print(" База данных инициализирована:", DB_PATH)

async def get_or_create_user(tg_id: int, username: str = ""):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,))
        row = await cur.fetchone()
        if not row:
            await db.execute("INSERT INTO users (telegram_id, username, last_active) VALUES (?, ?, date('now'))", (tg_id, username))
            await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,))
            row = await cur.fetchone()
        return _row_to_dict(row)

async def get_user(tg_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,))
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None

def _row_to_dict(row):
    """ ОБНОВЛЕНО: Полная проверка длины кортежа во избежание IndexErrors """
    return {
        "id": row[0], 
        "telegram_id": row[1],  
        "username": row[2], 
        "xp": row[3],
        "level": row[4], 
        "streak": row[5], 
        "last_active": row[6],
        "is_premium": bool(row[7]), 
        "daily_requests": row[8],
        "last_request_date": row[9], 
        "requests_count": row[10],
        "material_count": row[11], 
        "patent_count": row[12],
        "modules_used": row[13], 
        "created_at": row[14],
        "active_quest_type": row[15] if len(row) > 15 else None,
        "last_daily_quest": row[16] if len(row) > 16 else None,
        "preferred_lang": row[17] if len(row) > 17 else "ru",
        "password_hash": row[18] if len(row) > 18 else None  #  ДОБАВЛЕНО
    }

#  НОВЫЕ ФУНКЦИИ ДЛЯ ПОДДЕРЖКИ ВЕБ-АУТЕНТИФИКАЦИИ

async def save_password_hash(tg_id: int, hashed_password: str):
    """Сохраняет хэшированный пароль для пользователя"""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET password_hash = ? WHERE telegram_id = ?", 
            (hashed_password, tg_id)
        )
        await db.commit()

async def get_password_hash(tg_id: int) -> str:
    """Получает хэш пароля пользователя для проверки при логине"""
    async with get_db() as db:
        cur = await db.execute("SELECT password_hash FROM users WHERE telegram_id = ?", (tg_id,))
        row = await cur.fetchone()
        return row[0] if row else None

# === ОСТАЛЬНЫЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ ===

async def update_username(tg_id: int, username: str):
    async with get_db() as db:
        await db.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, tg_id))
        await db.commit()

async def add_xp(tg_id: int, amount: int):
    async with get_db() as db:
        cur = await db.execute("SELECT xp FROM users WHERE telegram_id = ?", (tg_id,))
        row = await cur.fetchone()
        if not row:
            return
        
        current_xp = row[0]
        new_xp = current_xp + amount
        new_level = (new_xp // 100) + 1
        
        await db.execute(
            "UPDATE users SET xp = ?, level = ? WHERE telegram_id = ?",
            (new_xp, new_level, tg_id)
        )
        await db.commit()

async def update_streak(tg_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT streak, last_active FROM users WHERE telegram_id = ?", (tg_id,))
        row = await cur.fetchone()
        if not row: 
            return
        streak, last = row
        today = date.today()
        if last == str(today): 
            return
        new_streak = streak + 1 if last == str(today - timedelta(days=1)) else 1
        await db.execute("UPDATE users SET streak = ?, last_active = ? WHERE telegram_id = ?", (new_streak, str(today), tg_id))
        await db.commit()

async def check_daily_limit(tg_id: int, is_premium: bool):
    async with get_db() as db:
        today = str(date.today())
        cur = await db.execute("SELECT daily_requests, last_request_date FROM users WHERE telegram_id = ?", (tg_id,))
        row = await cur.fetchone()
        if not row: 
            return True, 0
        reqs, last_date = row
        if last_date != today: 
            reqs = 0
        if not is_premium and reqs >= 10: 
            return False, reqs
        return True, reqs + 1

async def increment_daily_request(tg_id: int):
    async with get_db() as db:
        await db.execute("UPDATE users SET daily_requests = daily_requests + 1, last_request_date = date('now') WHERE telegram_id = ?", (tg_id,))
        await db.commit()

async def increment_requests_count(tg_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET requests_count = requests_count + 1 WHERE telegram_id = ?",
            (tg_id,)
        )
        await db.commit()

async def save_request(tg_id: int, module: str, text: str, response: str):
    async with get_db() as db:
        await db.execute("INSERT INTO requests (telegram_id, module, input_text, ai_response) VALUES (?, ?, ?, ?)", (tg_id, module, text, response))
        await db.commit()

async def update_module_counts(tg_id: int, mat: int, pat: int, modules_json: str):
    async with get_db() as db:
        await db.execute("UPDATE users SET material_count = ?, patent_count = ?, modules_used = ? WHERE telegram_id = ?", (mat, pat, modules_json, tg_id))
        await db.commit()

async def add_achievement(tg_id: int, code: str):
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO user_achievements (telegram_id, achievement_code) VALUES (?, ?)", (tg_id, code))
        await db.commit()

async def get_achievements(tg_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT achievement_code, earned_at FROM user_achievements WHERE telegram_id = ? ORDER BY earned_at DESC", (tg_id,))
        return await cur.fetchall()

async def get_leaderboard(limit: int = 20):
    async with get_db() as db:
        cur = await db.execute("""
            SELECT telegram_id, username, xp, level, streak 
            FROM users 
            ORDER BY xp DESC 
            LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
        return [
            {"telegram_id": r[0], "username": r[1] or f"User_{r[0]}", 
             "xp": r[2], "level": r[3], "streak": r[4]}
            for r in rows
        ]

async def complete_quest(tg_id: int, quest_id: str):
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO completed_quests (telegram_id, quest_id) VALUES (?, ?)",
            (tg_id, quest_id)
        )
        await db.commit()

async def get_completed_quests(tg_id: int):
    async with get_db() as db:
        cur = await db.execute(
            "SELECT quest_id, completed_at FROM completed_quests WHERE telegram_id = ? ORDER BY completed_at DESC",
            (tg_id,)
        )
        return await cur.fetchall()

async def set_daily_quest(tg_id: int, quest_type: str, date_str: str):
    async with get_db() as db:
        await db.execute(
            """UPDATE users 
               SET active_quest_type = ?, 
                   last_daily_quest = ? 
               WHERE telegram_id = ?""",
            (quest_type, date_str, tg_id)
        )
        await db.commit()

async def clear_daily_quest(tg_id: int):
    async with get_db() as db:
        await db.execute(
            """UPDATE users 
               SET active_quest_type = NULL,
                   last_daily_quest = NULL 
               WHERE telegram_id = ?""",
            (tg_id,)
        )
        await db.commit()

async def increment_streak(tg_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET streak = streak + 1 WHERE telegram_id = ?",
            (tg_id,)
        )
        await db.commit()

async def reset_streak(tg_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET streak = 0 WHERE telegram_id = ?",
            (tg_id,)
        )
        await db.commit()

async def set_preferred_lang(tg_id: int, lang: str):
    if lang not in ["ru", "kk", "en"]:
        lang = "ru"
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET preferred_lang = ? WHERE telegram_id = ?",
            (lang, tg_id)
        )
        await db.commit()

async def get_preferred_lang(tg_id: int) -> str:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT preferred_lang FROM users WHERE telegram_id = ?",
            (tg_id,)
        )
        row = await cur.fetchone()
        if row and row[0]:
            return row[0]
        return "ru"