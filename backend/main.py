import os
import json
import logging
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

import jwt
import httpx
from fastapi import FastAPI, HTTPException, Response, Cookie, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from dotenv import load_dotenv

import database
from prompts import AI_PROMPTS, MODULE_PROMPTS  

load_dotenv(Path(__file__).parent.parent / ".env")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === НАСТРОЙКИ БЕЗОПАСНОСТИ ===
SECRET_KEY = os.getenv("JWT_SECRET", "ENGINEERUS_SUPER_SECRET_KEY_2026")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

ACHIEVEMENT_RULES = {
    "first_step": lambda u: u.get("requests_count", 0) >= 1,
    "material_master": lambda u: u.get("material_count", 0) >= 5,
    "patent_crafter": lambda u: u.get("patent_count", 0) >= 1,
    "streak_3": lambda u: u.get("streak", 0) >= 3,
    "streak_7": lambda u: u.get("streak", 0) >= 7,
    "xp_100": lambda u: u.get("xp", 0) >= 100,
    "all_modules": lambda u: len(u.get("modules_used_list", [])) >= 4,
}

SYSTEM_PROMPTS = {
    "ru": "Ты — инженерный репетитор для студентов Казахстана. Отвечай кратко, чётко, структурировано.",
    "kk": "Сен — Қазақстан студенттеріне арналған инженерлік репетиторсың. Қысқа, нұсқа және құрылымды жауап бер.",
    "en": "You are an engineering tutor for students in Kazakhstan. Be concise, clear, and structured."
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    print(" База данных инициализирована")
    yield

app = FastAPI(title="Engineerus Quest API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ БЕЗОПАСНОСТИ ---
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(telegram_id: int) -> str:
    payload = {
        "sub": str(telegram_id),
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user_id(engineerus_session: str = Cookie(None)) -> int:
    if not engineerus_session:
        raise HTTPException(status_code=401, detail="Вы не авторизованы")
    try:
        payload = jwt.decode(engineerus_session, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Сессия устарела. Войдите заново")

# --- ВСПЛЫВАЮЩАЯ ФУНКЦИЯ ДЛЯ ВЫДАЧИ АЧИВОК (ДОБАВЛЕНО) ---
async def check_and_award_achievements(user_data: dict) -> list:
    """Проверяет условия достижений и начисляет их"""
    new_achievements = []
    try:
        modules_used = user_data.get("modules_used", "[]")
        if isinstance(modules_used, str):
            try:
                modules_used = json.loads(modules_used)
            except:
                modules_used = []
        elif not isinstance(modules_used, list):
            modules_used = []
        user_data["modules_used_list"] = modules_used
        
        try:
            existing = await database.get_achievements(user_data["telegram_id"])
            existing_codes = {ex[0] for ex in existing} if existing else set()
        except Exception as e:
            logger.error(f"Ошибка получения ачивок из БД: {e}")
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
            user_data["xp"] += total_xp_gained
            
    except Exception as e:
        logger.error(f"Критическая ошибка в ачивках: {e}", exc_info=True)
        
    return new_achievements

# Вспомогательная функция фейк-ИИ (если у тебя нет реального вызова API)
async def call_ai(prompt: str, lang: str) -> str:
    return f"[Ответ ИИ на языке {lang}]: На основе анализа вашего запроса, инженерные спецификации требуют соблюдения стандартов ГОСТ/ISO."

# === ОБНОВЛЕННЫЕ МОДЕЛИ ===
class WebRegisterRequest(BaseModel):
    telegram_id: int
    username: str
    password: str
    full_name: str = ""

class WebLoginRequest(BaseModel):
    telegram_id: int  
    password: str

class AIRequest(BaseModel):
    text: str
    lang: str = "ru"

class ModuleRequest(BaseModel):
    module: str
    text: str
    lang: str = "ru"

class QuestCompleteRequest(BaseModel):
    quest_id: str

# === API: АУТЕНТИФИКАЦИЯ ===

@app.post("/api/auth/web-register")
async def web_register(req: WebRegisterRequest):
    existing_user = await database.get_user(req.telegram_id)
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким Telegram ID уже зарегистрирован")
    
    hashed_pwd = get_password_hash(req.password)
    await database.get_or_create_user(req.telegram_id, req.username)
    
    if req.full_name:
        await database.update_username(req.telegram_id, req.full_name)
    
    await database.save_password_hash(req.telegram_id, hashed_pwd) 
    return {"status": "ok", "message": "Регистрация успешна!"}

@app.post("/api/auth/web-login")
async def web_login(req: WebLoginRequest, response: Response):
    user = await database.get_user(req.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    hashed_pwd = await database.get_password_hash(req.telegram_id)
    if not hashed_pwd or not verify_password(req.password, hashed_pwd):
        raise HTTPException(status_code=400, detail="Неверный пароль")
    
    token = create_access_token(req.telegram_id)
    response.set_cookie(
        key="engineerus_session",
        value=token,
        httponly=True,   
        max_age=604800,  
        samesite="lax"
    )
    return {"status": "ok", "username": user["username"]}

@app.post("/api/auth/web-logout")
async def web_logout(response: Response):
    response.delete_cookie("engineerus_session")
    return {"status": "ok", "message": "Вы успешно вышли"}

# === API: ИИ ===
@app.post("/api/ai")
async def handle_ai(req: AIRequest, tg_id: int = Depends(get_current_user_id)):
    user = await database.get_user(tg_id)
    allowed, _ = await database.check_daily_limit(tg_id, user["is_premium"])
    if not allowed:
        return {"status": "limit", "message": " Лимит 10 запросов/день."}
    
    lang = req.lang if req.lang else await database.get_preferred_lang(tg_id)
    prompt = f"{SYSTEM_PROMPTS.get(lang, SYSTEM_PROMPTS['ru'])}\n\nВопрос: {req.text}"
    ai_response = await call_ai(prompt, lang)
    
    await database.increment_daily_request(tg_id)
    await database.increment_requests_count(tg_id)
    await database.add_xp(tg_id, 10)
    await database.update_streak(tg_id)
    await database.save_request(tg_id, "tutor", req.text, ai_response)
    
    updated_user = await database.get_user(tg_id)
    user_data = {
        "telegram_id": tg_id, "xp": updated_user["xp"], "level": updated_user["level"],
        "streak": updated_user["streak"], "requests_count": updated_user["requests_count"],
        "material_count": updated_user["material_count"], "patent_count": updated_user["patent_count"],
        "modules_used": updated_user["modules_used"]
    }
    new_achievements = await check_and_award_achievements(user_data)
    
    return {
        "status": "ok", "response": ai_response, "xp": user_data["xp"], 
        "level": user_data["level"], "streak": user_data["streak"], 
        "new_achievements": new_achievements, "lang": lang
    }

# === API: ИНЖЕНЕРНЫЕ МОДУЛИ ===
@app.post("/api/module")
async def handle_module(req: ModuleRequest, tg_id: int = Depends(get_current_user_id)):
    user = await database.get_user(tg_id)
    allowed, _ = await database.check_daily_limit(tg_id, user["is_premium"])
    if not allowed:
        return {"status": "limit", "message": "Лимит запросов исчерпан."}
        
    lang = req.lang if req.lang else await database.get_preferred_lang(tg_id)
    
    # Парсим список использованных модулей
    try:
        modules_used = json.loads(user["modules_used"])
    except:
        modules_used = []
        
    if req.module not in modules_used:
        modules_used.append(req.module)
        
    # Считаем счётчики по модулям
    mat_count = user["material_count"] + 1 if req.module == "MaterialSwap" else user["material_count"]
    pat_count = user["patent_count"] + 1 if req.module == "PatentCraft" else user["patent_count"]
    
    # Системный промпт модуля
    module_system = MODULE_PROMPTS.get(req.module, "Ты — специализированный инженерный ИИ-помощник.")
    prompt = f"{module_system}\n\nЗапрос пользователя: {req.text}"
    ai_response = await call_ai(prompt, lang)
    
    # Обновляем БД
    await database.increment_daily_request(tg_id)
    await database.update_module_counts(tg_id, mat_count, pat_count, json.dumps(modules_used))
    await database.save_request(tg_id, req.module, req.text, ai_response)
    
    updated_user = await database.get_user(tg_id)
    user_data = {
        "telegram_id": tg_id, "xp": updated_user["xp"], "level": updated_user["level"],
        "streak": updated_user["streak"], "requests_count": updated_user["requests_count"],
        "material_count": updated_user["material_count"], "patent_count": updated_user["patent_count"],
        "modules_used": updated_user["modules_used"]
    }
    new_achievements = await check_and_award_achievements(user_data)
    
    return {
        "status": "ok", "response": ai_response, "xp": user_data["xp"],
        "level": user_data["level"], "new_achievements": new_achievements
    }

# === API: КВЕСТЫ ===
@app.post("/api/quests/complete")
async def complete_quest(req: QuestCompleteRequest, tg_id: int = Depends(get_current_user_id)):
    if req.quest_id not in QUESTS:
        raise HTTPException(status_code=404, detail="Квест не найден")
        
    await database.complete_quest(tg_id, req.quest_id)
    quest = QUESTS[req.quest_id]
    await database.add_xp(tg_id, quest["xp"])
    
    return {"status": "ok", "message": f"Квест '{quest['name']}' выполнен!", "xp_reward": quest["xp"]}

# === СТАТИКА И ФРОНТЕНД ===
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/app.html")
async def app_page(): 
    return FileResponse(os.path.join(FRONTEND_DIR, "app.html"))