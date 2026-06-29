from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os, httpx, json, logging
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, timedelta
import random

import database
from prompts import AI_PROMPTS, MODULE_PROMPTS  

load_dotenv(Path(__file__).parent.parent / ".env")
logger = logging.getLogger(__name__)

# === СПИСОК КВЕСТОВ ===
QUESTS = {
    "first_contact": {
        "id": "first_contact",
        "name": "Первый контакт",
        "desc": "Отправь первый запрос к ИИ-репетитору",
        "xp": 20,
        "reward": "Бейдж Новичок",
        "condition": "first_request",
        "condition_desc": "Нужно задать хотя бы 1 вопрос ИИ"
    },
    "material_scout": {
        "id": "material_scout",
        "name": "Поиск материала",
        "desc": "Используй модуль MaterialSwap",
        "xp": 30,
        "reward": "Бейдж Исследователь",
        "condition": "use_material",
        "condition_desc": "Сделай 1 подбор в MaterialSwap"
    },
    "streak_master": {
        "id": "streak_master",
        "name": "Серия побед",
        "desc": "Набери стрик 3 дня",
        "xp": 50,
        "reward": "Бейдж Постоянец",
        "condition": "streak_3",
        "condition_desc": "Заходи 3 дня подряд"
    },
    "xp_hunter": {
        "id": "xp_hunter",
        "name": "Охотник за XP",
        "desc": "Набери 50 XP",
        "xp": 40,
        "reward": "Бейдж Опытный",
        "condition": "xp_50",
        "condition_desc": "Заработай 50 XP"
    },
    "module_explorer": {
        "id": "module_explorer",
        "name": "Вездеход",
        "desc": "Попробуй все модули",
        "xp": 100,
        "reward": "Бейдж Универсал",
        "condition": "use_all_modules",
        "condition_desc": "Используй все модули"
    }
}

# === СИСТЕМА АЧИВОК ===
ACHIEVEMENTS = {
    "first_step": {"name": "Первый шаг", "xp": 10, "desc": "Первый запрос к ИИ"},
    "material_master": {"name": "Материаловед", "xp": 50, "desc": "5 подборов в MaterialSwap"},
    "patent_crafter": {"name": "Патентный чертёжник", "xp": 30, "desc": "1 заявка в PatentCraft"},
    "streak_3": {"name": "3 дня в строю", "xp": 20, "desc": "Активность 3 дня подряд"},
    "streak_7": {"name": "Неделя в строю", "xp": 50, "desc": "Активность 7 дней подряд"},
    "xp_100": {"name": "Сотня", "xp": 30, "desc": "Достиг 100 XP"},
    "all_modules": {"name": "Инженер-универсал", "xp": 100, "desc": "Использовал все модули"}
}

# Декларативные правила ачивок
ACHIEVEMENT_RULES = {
    "first_step": lambda u: int(u.get("requests_count", 0) or 0) >= 1,
    "material_master": lambda u: int(u.get("material_count", 0) or 0) >= 5,
    "patent_crafter": lambda u: int(u.get("patent_count", 0) or 0) >= 1,
    "streak_3": lambda u: int(u.get("streak", 0) or 0) >= 3,
    "streak_7": lambda u: int(u.get("streak", 0) or 0) >= 7,
    "xp_100": lambda u: int(u.get("xp", 0) or 0) >= 100,
    "all_modules": lambda u: len(u.get("modules_used_list", [])) >= 4,
}

# === ПРОМПТЫ ДЛЯ РАЗНЫХ ЯЗЫКОВ ===
SYSTEM_PROMPTS = {
    "ru": """Ты — инженерный репетитор для студентов Казахстана. 
КРИТИЧЕСКИ ВАЖНО: Отвечай СТРОГО на РУССКОМ языке.
Даже если вопрос на другом языке — отвечай на русском.

Требования:
1. Объясняй просто, но с профессиональной терминологией
2. Приводи примеры из казахстанских реалий (Алматы, Астана, Шымкент)
3. Структура: теория → пример → вывод
4. Цены в тенге (₸), города Казахстана
5. Если решаешь задачу — показывай ВСЕ шаги подробно
6. Минимум 300-500 слов для сложных тем
7. Используй маркированные списки и заголовки для структуры""",
    
    "kk": """Сен — Қазақстан студенттеріне арналған инженерлік репетиторсың.
ЕҢ МАҢЫЗДЫСЫ: ҚАЗАҚ ТІЛІНДЕ ҒАНА ЖАУАП БЕР!
Сұрақ басқа тілде болса да — тек қазақша жауап бер.
Орысша, ағылшынша ЖАУАП БЕРМЕ!

Талаптар:
1. Қарапайым тілмен, бірақ кәсіби терминдермен түсіндір
2. Қазақстан шындығынан мысалдар келтір (Алматы, Астана, Шымкент)
3. Құрылым: теория → мысал → қорытынды
4. Бағалар теңгемен (₸), Қазақстан қалалары
5. Есеп шығарсаң — барлық қадамдарды толық көрсет
6. Кемінде 300-500 сөз күрделі тақырыптар үшін
7. Маркерленген тізімдер мен тақырыптарды қолдан

Жауаптың басында жаз: "Қазақша жауап:" деп баста.""",
    
    "en": """You are an engineering tutor for students in Kazakhstan.
CRITICAL: Answer STRICTLY in ENGLISH only.
Even if the question is in another language — answer in English.
DO NOT answer in Russian or Kazakh.

Requirements:
1. Explain simply but with professional terminology
2. Give examples adapted to Kazakhstan context (Almaty, Astana, Shymkent)
3. Structure: theory → example → conclusion
4. Prices in tenge (₸), Kazakhstan cities
5. If solving a problem — show ALL steps in detail
6. Minimum 300-500 words for complex topics
7. Use bullet points and headers for structure"""
}

# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ БЕЗОПАСНОГО INT ===
def safe_int(value, default=0):
    """Безопасная конвертация в int"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    print(" База данных инициализирована")
    yield

app = FastAPI(title="Engineerus Quest API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Раздача фронтенда
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Раздача PDF книг из frontend/books/
BOOKS_DIR = os.path.join(FRONTEND_DIR, "books")
if os.path.exists(BOOKS_DIR):
    app.mount("/books", StaticFiles(directory=BOOKS_DIR), name="books")
    
@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/app.html")
async def app_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.html"))

# === МОДЕЛИ ===
class AIRequest(BaseModel):
    telegram_id: int
    username: str = ""
    text: str
    lang: str = "ru"

class ModuleRequest(BaseModel):
    telegram_id: int
    username: str = ""
    module: str
    text: str
    lang: str = "ru"

class RegisterRequest(BaseModel):
    telegram_id: int
    username: str
    full_name: str = ""

class QuestCompleteRequest(BaseModel):
    telegram_id: int
    quest_id: str

class SetLangRequest(BaseModel):
    telegram_id: int
    lang: str

class WebRegisterRequest(BaseModel):
    email: str
    password: str
    username: str = ""

class WebLoginRequest(BaseModel):
    email: str
    password: str

class BindRequest(BaseModel):
    telegram_id: int
    email: str
    password: str

class UnbindRequest(BaseModel):
    telegram_id: int

# === ИИ ФУНКЦИЯ (МУЛЬТИЯЗЫЧНАЯ) ===
async def call_ai(prompt: str, lang: str = "ru") -> str:
    """Отвечает на выбранном языке ПОДРОБНО"""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3")
    
    system_prompt = SYSTEM_PROMPTS.get(lang, SYSTEM_PROMPTS["ru"])
    
    try:
        async with httpx.AsyncClient() as client:
            url = f"{ollama_url}/api/chat"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 2048}
            }
            
            resp = await client.post(url, json=payload, timeout=180.0)
            
            if resp.status_code != 200:
                return f"Ошибка Ollama ({resp.status_code})."
            
            data = resp.json()
            return data["message"]["content"]
            
    except httpx.ConnectError:
        return " Ollama не запущена! Открой приложение Ollama."
    except httpx.TimeoutException:
        return " AI думает слишком долго. Попробуй вопрос покороче."
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        return f" Ошибка соединения с AI: {str(e)}"

# === ФУНКЦИЯ АЧИВОК ===
async def check_and_award_achievements(user_data: dict) -> list:
    """Проверяет и выдаёт новые ачивки пользователю"""
    new_achievements = []
    
    try:
        # Парсим modules_used
        modules_used = user_data.get("modules_used", "[]")
        if isinstance(modules_used, str):
            try:
                modules_used = json.loads(modules_used)
            except:
                modules_used = []
        elif not isinstance(modules_used, list):
            modules_used = []
        user_data["modules_used_list"] = modules_used
        
        # Гарантируем что все числовые поля - это int
        user_data["xp"] = safe_int(user_data.get("xp"))
        user_data["requests_count"] = safe_int(user_data.get("requests_count"))
        user_data["material_count"] = safe_int(user_data.get("material_count"))
        user_data["patent_count"] = safe_int(user_data.get("patent_count"))
        user_data["streak"] = safe_int(user_data.get("streak"))
        
        # Получаем существующие ачивки
        try:
            existing = await database.get_achievements(user_data["telegram_id"])
            existing_codes = {ex[0] for ex in existing} if existing else set()
        except Exception as e:
            logger.error(f"Ошибка получения ачивок: {e}")
            existing_codes = set()
        
        total_xp_gained = 0
        
        for code, rule in ACHIEVEMENT_RULES.items():
            if code in existing_codes:
                continue
            
            try:
                if rule(user_data):
                    ach = ACHIEVEMENTS[code]
                    await database.add_achievement(user_data["telegram_id"], code)
                    total_xp_gained += ach["xp"]
                    new_achievements.append({
                        "code": code,
                        "name": ach["name"],
                        "xp": ach["xp"]
                    })
            except Exception as e:
                logger.error(f"Ошибка проверки правила {code}: {e}")
                continue
        
        if total_xp_gained > 0:
            await database.add_xp(user_data["telegram_id"], total_xp_gained)
            user_data["xp"] = user_data["xp"] + total_xp_gained
        
    except Exception as e:
        logger.error(f"Критическая ошибка в check_and_award_achievements: {e}", exc_info=True)
    
    return new_achievements

# === API: ИИ ===
@app.post("/api/ai")
async def handle_ai(req: AIRequest):
    user = await database.get_or_create_user(req.telegram_id, req.username)
    allowed, _ = await database.check_daily_limit(req.telegram_id, user["is_premium"])
    if not allowed:
        return {"status": "limit", "message": " Лимит 10 запросов/день."}
    
    # Берём язык из запроса или из БД
    lang = req.lang if req.lang else await database.get_preferred_lang(req.telegram_id)
    
    prompt = f"{AI_PROMPTS['tutor']}\n\nВопрос: {req.text}"
    ai_response = await call_ai(prompt, lang)
    
    await database.increment_daily_request(req.telegram_id)
    await database.increment_requests_count(req.telegram_id)
    await database.add_xp(req.telegram_id, 10)
    await database.update_streak(req.telegram_id)
    await database.save_request(req.telegram_id, "tutor", req.text, ai_response)
    
    updated_user = await database.get_user(req.telegram_id)
    user_data = {
        "telegram_id": req.telegram_id,
        "xp": safe_int(updated_user.get("xp")),
        "level": safe_int(updated_user.get("level"), 1),
        "streak": safe_int(updated_user.get("streak")),
        "requests_count": safe_int(updated_user.get("requests_count")),
        "material_count": safe_int(updated_user.get("material_count")),
        "patent_count": safe_int(updated_user.get("patent_count")),
        "modules_used": updated_user.get("modules_used", "[]")
    }
    new_achievements = await check_and_award_achievements(user_data)
    
    return {
        "status": "ok", "response": ai_response,
        "xp": user_data["xp"], "level": user_data["level"],
        "streak": user_data["streak"],
        "new_achievements": new_achievements, "lang": lang
    }

# === API: МОДУЛИ ===
@app.post("/api/module")
async def handle_module(req: ModuleRequest):
    if req.module not in MODULE_PROMPTS:
        raise HTTPException(status_code=400, detail="Неизвестный модуль")
    
    user = await database.get_or_create_user(req.telegram_id, req.username)
    
    # Берём язык из запроса или из БД
    lang = req.lang if req.lang else await database.get_preferred_lang(req.telegram_id)
    
    modules_used_raw = user.get("modules_used", "[]")
    if isinstance(modules_used_raw, str):
        try:
            modules_used = json.loads(modules_used_raw)
        except:
            modules_used = []
    elif isinstance(modules_used_raw, list):
        modules_used = modules_used_raw
    else:
        modules_used = []
    
    if req.module not in modules_used:
        modules_used.append(req.module)
    
    prompt = f"{MODULE_PROMPTS[req.module]}\n\nЗадача: {req.text}"
    ai_response = await call_ai(prompt, lang)
    
    await database.add_xp(req.telegram_id, 15)
    await database.increment_requests_count(req.telegram_id)
    await database.update_streak(req.telegram_id)
    await database.save_request(req.telegram_id, req.module, req.text, ai_response)
    
    # Безопасная работа с числовыми полями
    new_mat = safe_int(user.get("material_count")) + (1 if req.module == "material" else 0)
    new_pat = safe_int(user.get("patent_count")) + (1 if req.module == "patent" else 0)
    await database.update_module_counts(req.telegram_id, new_mat, new_pat, json.dumps(modules_used))
    
    updated_user = await database.get_user(req.telegram_id)
    user_data = {
        "telegram_id": req.telegram_id,
        "xp": safe_int(updated_user.get("xp")),
        "level": safe_int(updated_user.get("level"), 1),
        "streak": safe_int(updated_user.get("streak")),
        "requests_count": safe_int(updated_user.get("requests_count")),
        "material_count": new_mat,
        "patent_count": new_pat,
        "modules_used": modules_used
    }
    new_achievements = await check_and_award_achievements(user_data)
    
    return {
        "status": "ok", "response": ai_response,
        "xp": user_data["xp"], "level": user_data["level"],
        "new_achievements": new_achievements, "lang": lang
    }

# === API: РЕГИСТРАЦИЯ (Telegram) ===
@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    user = await database.get_or_create_user(req.telegram_id, req.username)
    if req.full_name:
        await database.update_username(req.telegram_id, req.full_name)
    return {"status": "ok", "user": user}

# === API: ВЕБ-АВТОРИЗАЦИЯ (Email + Password) ===
@app.post("/api/auth/web/register")
async def web_register(req: WebRegisterRequest):
    """Регистрация через сайт (email + пароль)"""
    if not req.email or len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Некорректные данные (пароль минимум 4 символа)")
    
    user = await database.register_user(req.email, req.password, req.username)
    if not user:
        raise HTTPException(status_code=400, detail="Такой email уже зарегистрирован")
    
    return {"status": "ok", "user": user}

@app.post("/api/auth/web/login")
async def web_login(req: WebLoginRequest):
    """Вход через сайт (email + пароль)"""
    user = await database.authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    return {"status": "ok", "user": user}

@app.post("/api/auth/bind")
async def bind_account(req: BindRequest):
    """Привязать Telegram к веб-аккаунту (с авто-регистрацией)"""
    logger.info(f" BIND запрос: email={req.email}, tg_id={req.telegram_id}")
    
    # 1. Сначала ищем пользователя по telegram_id
    existing_user = await database.get_user(req.telegram_id)
    logger.info(f" existing_user по telegram_id: {existing_user is not None}")
    
    if existing_user:
        # Пользователь уже существует (создан через бота)
        if existing_user.get("email"):
            logger.info(f" У пользователя уже есть email: {existing_user['email']}")
            if existing_user["email"] == req.email:
                # Обновляем пароль
                password_hash = __import__('hashlib').sha256(req.password.encode()).hexdigest()
                async with database.get_db() as db:
                    await db.execute(
                        "UPDATE users SET password_hash = ? WHERE telegram_id = ?",
                        (password_hash, req.telegram_id)
                    )
                    await db.commit()
                logger.info(f" Пароль обновлён")
                return {"status": "ok", "message": " Аккаунт привязан (пароль обновлён)"}
            else:
                logger.error(f" Email уже привязан: {existing_user['email']}")
                raise HTTPException(400, f"Этот Telegram уже привязан к email: {existing_user['email']}")
        
        # Добавляем email и пароль
        password_hash = __import__('hashlib').sha256(req.password.encode()).hexdigest()
        async with database.get_db() as db:
            await db.execute(
                "UPDATE users SET email = ?, password_hash = ? WHERE telegram_id = ?",
                (req.email, password_hash, req.telegram_id)
            )
            await db.commit()
        logger.info(f" Email и пароль добавлены к существующему пользователю")
        return {"status": "ok", "message": " Аккаунт привязан"}
    
    # 2. Если пользователь НЕ существует по telegram_id
    # Ищем по email
    user_by_email = await database.authenticate_user(req.email, req.password)
    logger.info(f" user_by_email: {user_by_email is not None}")
    
    if user_by_email:
        # Нашли по email - привязываем telegram_id
        if user_by_email.get("telegram_id") and user_by_email["telegram_id"] != req.telegram_id:
            logger.error(f" Email уже привязан к другому TG: {user_by_email['telegram_id']}")
            raise HTTPException(400, "Этот email уже привязан к другому Telegram-аккаунту")
        
        async with database.get_db() as db:
            await db.execute(
                "UPDATE users SET telegram_id = ? WHERE email = ?",
                (req.telegram_id, req.email)
            )
            await db.commit()
        logger.info(f" Telegram привязан к существующему email-аккаунту")
        return {"status": "ok", "message": " Аккаунт привязан"}
    
    # 3. Если вообще ничего не нашли - создаём нового
    logger.info(f" Создаём нового пользователя...")
    new_user = await database.register_user(req.email, req.password)
    logger.info(f" register_user вернул: {new_user is not None}")
    
    if not new_user:
        logger.error(f" Регистрация не удалась")
        raise HTTPException(401, "Не удалось создать аккаунт")
    
    # Привязываем telegram_id
    async with database.get_db() as db:
        await db.execute(
            "UPDATE users SET telegram_id = ? WHERE email = ?",
            (req.telegram_id, req.email)
        )
        await db.commit()
    
    logger.info(f" Создан новый аккаунт и привязан к Telegram")
    return {"status": "ok", "message": " Аккаунт создан и привязан"}

@app.post("/api/auth/unbind")
async def unbind_account(req: UnbindRequest):
    """Отвязать Telegram от веб-аккаунта"""
    async with database.get_db() as db:
        await db.execute(
            "UPDATE users SET telegram_id = NULL WHERE telegram_id = ?",
            (req.telegram_id,)
        )
        await db.commit()
    
    return {"status": "ok", "message": " Привязка удалена"}

# === API: ЛИДЕРБОРД ===
@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 20):
    users = await database.get_leaderboard(limit)
    return {"leaderboard": users, "total": len(users)}

# === API: КВЕСТЫ ===
@app.get("/api/quests")  
async def get_quests():
    return {"quests": QUESTS, "total": len(QUESTS)}

@app.post("/api/quests/complete")
async def complete_quest(req: QuestCompleteRequest):
    if req.quest_id not in QUESTS:
        raise HTTPException(400, "Квест не найден")
    
    quest = QUESTS[req.quest_id]
    user = await database.get_or_create_user(req.telegram_id, "")
    
    user["xp"] = safe_int(user.get("xp"))
    user["requests_count"] = safe_int(user.get("requests_count"))
    user["material_count"] = safe_int(user.get("material_count"))
    user["streak"] = safe_int(user.get("streak"))
    
    completed = await database.get_completed_quests(req.telegram_id)
    if req.quest_id in [c[0] for c in completed]:
        return {"status": "already", "message": "Квест уже выполнен"}
    
    condition_met = False
    if quest["condition"] == "first_request" and user["requests_count"] >= 1:
        condition_met = True
    elif quest["condition"] == "use_material" and user["material_count"] >= 1:
        condition_met = True
    elif quest["condition"] == "streak_3" and user["streak"] >= 3:
        condition_met = True
    elif quest["condition"] == "xp_50" and user["xp"] >= 50:
        condition_met = True
    elif quest["condition"] == "use_all_modules":
        modules_raw = user.get("modules_used", "[]")
        if isinstance(modules_raw, str):
            try:
                modules_list = json.loads(modules_raw)
            except:
                modules_list = []
        else:
            modules_list = modules_raw if isinstance(modules_raw, list) else []
        if len(modules_list) >= 4:
            condition_met = True
    
    if not condition_met:
        return {"status": "not_met", "message": f"Условие не выполнено: {quest['condition_desc']}"}
    
    await database.complete_quest(req.telegram_id, req.quest_id)
    await database.add_xp(req.telegram_id, quest["xp"])
    
    #  ОБНОВЛЯЕМ СТРИК при выполнении квеста!
    await database.update_streak(req.telegram_id)
    
    updated_user = await database.get_user(req.telegram_id)
    new_achievements = await check_and_award_achievements(updated_user)
    
    return {
        "status": "ok", 
        "message": f" Квест выполнен! +{quest['xp']} XP",
        "quest": quest,
        "new_xp": safe_int(updated_user.get("xp")),
        "new_level": safe_int(updated_user.get("level"), 1),
        "new_streak": safe_int(updated_user.get("streak")),
        "new_achievements": new_achievements
    }

@app.get("/api/quests/completed/{tg_id}")  
async def get_completed_quests(tg_id: int):
    completed = await database.get_completed_quests(tg_id)
    return {"completed": [c[0] for c in completed]}

# === API: ПРОФИЛЬ ===
@app.get("/api/user/by-email/{email}")
async def get_user_by_email(email: str):
    """Получить профиль пользователя по email"""
    logger.info(f" Поиск пользователя по email: {email}")
    
    async with database.get_db() as db:
        # Сначала ищем точное совпадение
        cur = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cur.fetchone()
        
        if not row:
            # Если не нашли — ищем по telegram_id (если email был сохранён как telegram_id)
            logger.warning(f" Пользователь с email={email} не найден")
            
            # Показываем всех пользователей для отладки
            cur = await db.execute("SELECT telegram_id, email, username FROM users")
            all_users = await cur.fetchall()
            logger.info(f" Все пользователи в БД: {all_users}")
            
            raise HTTPException(404, "Пользователь не найден. Сначала привяжи аккаунт через бота: /bind email пароль")
        
        user = database._row_to_dict(row)
        logger.info(f" Пользователь найден: id={user.get('id')}, tg_id={user.get('telegram_id')}")
    
    return {
        "id": user.get("id"),
        "telegram_id": user.get("telegram_id"),
        "username": user.get("username") or "Инженер",
        "email": user.get("email"),
        "xp": safe_int(user.get("xp")),
        "level": safe_int(user.get("level"), 1),
        "streak": safe_int(user.get("streak")),
        "is_premium": bool(user.get("is_premium")),
        "daily_requests": safe_int(user.get("daily_requests")),
        "last_request_date": user.get("last_request_date"),
        "requests_count": safe_int(user.get("requests_count")),
        "material_count": safe_int(user.get("material_count")),
        "patent_count": safe_int(user.get("patent_count")),
        "modules_used": user.get("modules_used", "[]"),
        "preferred_lang": user.get("preferred_lang", "ru"),
        "created_at": user.get("created_at")
    }

@app.get("/api/achievements/{tg_id}")
async def get_user_achievements(tg_id: int):
    rows = await database.get_achievements(tg_id)
    result = []
    for code, earned_at in rows:
        if code in ACHIEVEMENTS:
            result.append({"code": code, **ACHIEVEMENTS[code], "earned_at": earned_at})
    return {"achievements": result, "total": len(result)}

# === API: МУЛЬТИЯЗЫЧНОСТЬ ===
@app.post("/api/user/lang")
async def set_user_language(req: SetLangRequest):
    """Установить предпочитаемый язык пользователя"""
    if req.lang not in ["ru", "kk", "en"]:
        raise HTTPException(status_code=400, detail="Invalid language")
    await database.set_preferred_lang(req.telegram_id, req.lang)
    return {"status": "ok", "lang": req.lang}

@app.get("/api/user/lang/{tg_id}")
async def get_user_language(tg_id: int):
    """Получить предпочитаемый язык пользователя"""
    lang = await database.get_preferred_lang(tg_id)
    return {"lang": lang}

# === API: ЕЖЕДНЕВНЫЕ КВЕСТЫ ===
DAILY_QUESTS = [
    {"type": "sopromat", "text": " Реши 3 задачи по сопромату", "xp": 50},
    {"type": "termeh", "text": " Разберись с термехом (2 задачи)", "xp": 50},
    {"type": "module", "text": " Изучи новый модуль в боте", "xp": 30},
    {"type": "ai_question", "text": " Задай вопрос ИИ-помощнику", "xp": 20},
    {"type": "article", "text": " Прочитай научную статью", "xp": 40},
]

class DailyQuestRequest(BaseModel):
    telegram_id: int

@app.post("/api/daily/quest")
async def get_daily_quest(req: DailyQuestRequest):
    """Выдать ежедневный квест"""
    user = await database.get_user(req.telegram_id)
    if not user:
        user = await database.get_or_create_user(req.telegram_id, "")
    
    last_quest = user.get("last_daily_quest")
    today = str(date.today())
    
    if last_quest == today:
        return {
            "status": "already",
            "message": " Ты уже взял квест сегодня! Заходи завтра "
        }
    
    quest = random.choice(DAILY_QUESTS)
    await database.set_daily_quest(req.telegram_id, quest["type"], today)
    
    return {
        "status": "ok",
        "quest": quest,
        "streak": safe_int(user.get("streak"))
    }

@app.post("/api/daily/check")
async def check_daily_quest(req: DailyQuestRequest):
    """Проверить выполнение квеста"""
    user = await database.get_user(req.telegram_id)
    if not user:
        return {"status": "error", "message": "Пользователь не найден"}
    
    quest_type = user.get("active_quest_type")
    quest_date = user.get("last_daily_quest")
    today = str(date.today())
    
    if not quest_type or not quest_date:
        return {"status": "no_quest", "message": "У тебя нет активного квеста. Напиши /daily"}
    
    if quest_date != today:
        await database.reset_streak(req.telegram_id)
        await database.clear_daily_quest(req.telegram_id)
        return {
            "status": "expired",
            "message": " Квест просрочен. Серия сброшена. Бери новый: /daily"
        }
    
    xp_reward = 20
    for q in DAILY_QUESTS:
        if q["type"] == quest_type:
            xp_reward = q["xp"]
            break
    
    await database.add_xp(req.telegram_id, xp_reward)
    await database.increment_streak(req.telegram_id)
    await database.clear_daily_quest(req.telegram_id)
    
    updated_user = await database.get_user(req.telegram_id)
    new_streak = safe_int(updated_user.get("streak"), 1)
    
    bonus = 0
    if new_streak == 7:
        bonus = 100
        await database.add_xp(req.telegram_id, bonus)
        updated_user = await database.get_user(req.telegram_id)
    
    return {
        "status": "ok",
        "xp_reward": xp_reward,
        "bonus": bonus,
        "streak": new_streak,
        "total_xp": safe_int(updated_user.get("xp")),
        "level": safe_int(updated_user.get("level"), 1)
    }

@app.get("/api/daily/status/{tg_id}")
async def get_daily_status(tg_id: int):
    """Показать статус серии"""
    user = await database.get_user(tg_id)
    if not user:
        return {"status": "error", "message": "Пользователь не найден"}
    
    return {
        "streak": safe_int(user.get("streak")),
        "xp": safe_int(user.get("xp")),
        "level": safe_int(user.get("level"), 1),
        "has_active_quest": user.get("active_quest_type") is not None
    }

# === API: REFERENCES ===
@app.get("/api/references")
async def get_references(category: str = None):
    async with database.get_db() as db:
        if category:
            cur = await db.execute("SELECT * FROM research_refs WHERE category = ? ORDER BY year DESC", (category,))
        else:
            cur = await db.execute("SELECT * FROM research_refs ORDER BY year DESC")
        rows = await cur.fetchall()
        return {"references": [
            {"id": r[0], "title": r[1], "authors": r[2], "year": r[3], 
             "url": r[4], "pdf_path": r[5], "category": r[6]} for r in rows
        ]}

@app.post("/api/references")
async def add_reference(req: dict):
    async with database.get_db() as db:
        await db.execute(
            "INSERT INTO research_refs (title, authors, year, url, pdf_path, category) VALUES (?, ?, ?, ?, ?, ?)",
            (req.get("title"), req.get("authors", ""), req.get("year", 2026), 
             req.get("url", ""), req.get("pdf_path", ""), req.get("category", "general"))
        )
        await db.commit()
    return {"status": "ok", "message": "Research добавлен"}