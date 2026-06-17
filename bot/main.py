import os, asyncio, httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

# Импортируем роутер ежедневных квестов
from bot.daily_quest import router as daily_quest_router

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Подключаем роутер
dp.include_router(daily_quest_router)

# === МУЛЬТИЯЗЫЧНОСТЬ ===
TEXTS = {
    "ru": {
        "choose_lang": " Привет! Выбери язык:",
        "lang_set": " Отлично! Теперь я буду отвечать на русском.\n\nИспользуй /lang чтобы сменить язык.",
        "welcome": " Привет! Выбери модуль:",
        "ask_question": " Отправь вопрос для модуля",
        "limit_msg": " Лимит: 10 запросов/день. Подключи Premium ($5/мес).",
        "error": " Ошибка. Попробуй через минуту.",
        "current_lang": " Текущий язык: Русский\n\nВыбери новый:",
        "lang_changed": " Язык изменён на русский!",
        "no_achievements": " У тебя пока нет ачивок. Начни использовать модули!",
        "achievements_header": " Твои ачивки:\n\n",
        "thinking": " Думаю...",
        "help": (
            " **Команды бота:**\n\n"
            "/start — начать заново\n"
            "/lang — сменить язык\n"
            "/profile — твой профиль\n"
            "/achievements — ачивки\n"
            "/daily — ежедневный квест\n"
            "/check_daily — проверить квест\n"
            "/streak — твоя серия\n"
            "/help — помощь"
        )
    },
    "kk": {
        "choose_lang": " Сәлем! Тілді таңда:",
        "lang_set": " Керемет! Енді қазақша жауап беремін.\n\nТілді өзгерту үшін /lang пайдалан.",
        "welcome": " Сәлем! Модульді таңда:",
        "ask_question": " Модульге сұрақ жібер",
        "limit_msg": " Лимит: 10 сұрау/күн. Premium қос ($5/ай).",
        "error": " Қате. Бір минуттан кейін қайтала.",
        "current_lang": " Ағымдағы тіл: Қазақша\n\nЖаңа тілді таңда:",
        "lang_changed": " Тіл қазақшаға өзгертілді!",
        "no_achievements": " Жетістіктер жоқ. Модульдерді қолдана баста!",
        "achievements_header": " Сенің жетістіктерің:\n\n",
        "thinking": " Ойлануда...",
        "help": (
            " **Бот пәрмендері:**\n\n"
            "/start — қайта бастау\n"
            "/lang — тілді өзгерту\n"
            "/profile — профилің\n"
            "/achievements — жетістіктер\n"
            "/daily — күнделікті квест\n"
            "/check_daily — квестті тексеру\n"
            "/streak — серияң\n"
            "/help — көмек"
        )
    },
    "en": {
        "choose_lang": " Hello! Select language:",
        "lang_set": " Great! Now I'll answer in English.\n\nUse /lang to change language.",
        "welcome": " Hello! Choose a module:",
        "ask_question": " Send a question for the module",
        "limit_msg": " Limit: 10 requests/day. Get Premium ($5/mo).",
        "error": " Error. Try again in a minute.",
        "current_lang": " Current language: English\n\nChoose new:",
        "lang_changed": " Language changed to English!",
        "no_achievements": " No achievements yet. Start using modules!",
        "achievements_header": " Your achievements:\n\n",
        "thinking": " Thinking...",
        "help": (
            " **Bot commands:**\n\n"
            "/start — restart\n"
            "/lang — change language\n"
            "/profile — your profile\n"
            "/achievements — achievements\n"
            "/daily — daily quest\n"
            "/check_daily — check quest\n"
            "/streak — your streak\n"
            "/help — help"
        )
    }
}

# Кэш языков (чтобы не дёргать API каждый раз)
user_langs_cache = {}

async def get_user_lang(tg_id: int) -> str:
    """Получить язык пользователя (из кэша или API)"""
    if tg_id in user_langs_cache:
        return user_langs_cache[tg_id]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/api/user/lang/{tg_id}", timeout=5.0)
            if resp.status_code == 200:
                lang = resp.json().get("lang", "ru")
                user_langs_cache[tg_id] = lang
                return lang
    except:
        pass
    return "ru"

async def set_user_lang(tg_id: int, lang: str):
    """Установить язык пользователя через API"""
    user_langs_cache[tg_id] = lang
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{API_URL}/api/user/lang",
                json={"telegram_id": tg_id, "lang": lang},
                timeout=5.0
            )
    except:
        pass

class ModuleState(StatesGroup):
    waiting_input = State()

# === /start — СРАЗУ ВЫБОР ЯЗЫКА ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="start_lang:ru")],
        [types.InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="start_lang:kk")],
        [types.InlineKeyboardButton(text="🇬🇧 English", callback_data="start_lang:en")]
    ])
    await message.answer(TEXTS["ru"]["choose_lang"], reply_markup=kb)

# === ВЫБОР ЯЗЫКА ПРИ СТАРТЕ ===
@dp.callback_query(lambda c: c.data.startswith("start_lang:"))
async def start_lang_callback(callback: types.CallbackQuery):
    lang = callback.data.split(":")[1]
    
    # Сохраняем язык
    await set_user_lang(callback.from_user.id, lang)
    
    # Подтверждение на выбранном языке
    await callback.message.edit_text(TEXTS[lang]["lang_set"])
    
    # Через 1.5 секунды показываем модули
    await asyncio.sleep(1.5)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=" TUTOR AI", callback_data="mod:tutor")],
        [types.InlineKeyboardButton(text=" MaterialSwap", callback_data="mod:material")],
        [types.InlineKeyboardButton(text=" PatentCraft", callback_data="mod:patent")],
        [types.InlineKeyboardButton(text=" EngiLegal", callback_data="mod:legal")],
        [types.InlineKeyboardButton(text=" EngiMatch", callback_data="mod:match")]
    ])
    await callback.message.answer(TEXTS[lang]["welcome"], reply_markup=kb)
    await callback.answer()

# === /lang — СМЕНА ЯЗЫКА ===
@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
        [types.InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kk")],
        [types.InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")]
    ])
    lang = await get_user_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["current_lang"], reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("lang:"))
async def lang_callback(callback: types.CallbackQuery):
    new_lang = callback.data.split(":")[1]
    await set_user_lang(callback.from_user.id, new_lang)
    await callback.message.edit_text(TEXTS[new_lang]["lang_changed"])
    await callback.answer()

# === ВЫБОР МОДУЛЯ ===
@dp.callback_query(lambda c: c.data.startswith("mod:"))
async def select_module(callback: types.CallbackQuery, state: FSMContext):
    module = callback.data.split(":")[1]
    lang = await get_user_lang(callback.from_user.id)
    await state.update_data(module=module)
    await callback.message.answer(f"{TEXTS[lang]['ask_question']} `{module.upper()}`:")
    await callback.answer()
    await state.set_state(ModuleState.waiting_input)

# === ОБРАБОТКА ВОПРОСА ===
@dp.message(ModuleState.waiting_input)
async def process_query(message: types.Message, state: FSMContext):
    data = await state.get_data()
    module = data.get("module", "tutor")
    lang = await get_user_lang(message.from_user.id)
    
    await message.answer(TEXTS[lang]["thinking"])
    
    try:
        async with httpx.AsyncClient() as client:
            if module == "tutor":
                endpoint = f"{API_URL}/api/ai"
                payload = {
                    "telegram_id": message.from_user.id,
                    "username": message.from_user.username or "",
                    "text": message.text,
                    "lang": lang  #  Передаём язык
                }
            else:
                endpoint = f"{API_URL}/api/module"
                payload = {
                    "telegram_id": message.from_user.id,
                    "username": message.from_user.username or "",
                    "module": module,
                    "text": message.text,
                    "lang": lang  #  Передаём язык
                }
            
            resp = await client.post(endpoint, json=payload, timeout=180.0)
            res = resp.json()
        
        if res.get("status") == "limit":
            await message.answer(TEXTS[lang]["limit_msg"])
        else:
            # Ответ ИИ на выбранном языке
            text = f" {res['response']}\n\n💎 +XP | 📊 {res['xp']} | 🎯 Lvl {res['level']}"
            
            if res.get("streak"):
                streak_word = {"ru": "дн.", "kk": "күн", "en": "days"}[lang]
                text += f" |  {res['streak']} {streak_word}"
            
            if res.get("new_achievements"):
                ach_header = {
                    "ru": " Новые ачивки:",
                    "kk": " Жаңа жетістіктер:",
                    "en": " New achievements:"
                }[lang]
                text += f"\n\n{ach_header}\n"
                for ach in res["new_achievements"]:
                    text += f"  • {ach['name']} (+{ach['xp']} XP)\n"
            
            await message.answer(text)
    except Exception as e:
        await message.answer(f"{TEXTS[lang]['error']}: {str(e)}")
    
    await state.clear()

# === /profile ===
@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    try:
        async with httpx.AsyncClient() as client:
            user_resp = await client.get(f"{API_URL}/api/user/{message.from_user.id}")
            ach_resp = await client.get(f"{API_URL}/api/achievements/{message.from_user.id}")
            user = user_resp.json()
            ach = ach_resp.json()
        
        labels = {
            "ru": {"level": "Уровень", "streak": "Стрик", "days": "дн.", 
                   "requests": "Запросов сегодня", "ach": "Ачивок", "premium": "Да/Нет"},
            "kk": {"level": "Деңгей", "streak": "Стрик", "days": "күн",
                   "requests": "Бүгінгі сұраулар", "ach": "Жетістіктер", "premium": "Иә/Жоқ"},
            "en": {"level": "Level", "streak": "Streak", "days": "days",
                   "requests": "Requests today", "ach": "Achievements", "premium": "Yes/No"}
        }
        L = labels[lang]
        prem = {"ru": "Да" if user['is_premium'] else "Нет",
                "kk": "Иә" if user['is_premium'] else "Жоқ",
                "en": "Yes" if user['is_premium'] else "No"}[lang]
        
        text = (
            f" {message.from_user.username or 'Инженер'}\n"
            f" XP: {user['xp']} |  {L['level']}: {user['level']}\n"
            f" {L['streak']}: {user.get('streak', 0)} {L['days']}\n"
            f" Premium: {prem}\n"
            f" {L['requests']}: {user['daily_requests']}/10\n"
            f" {L['ach']}: {ach['total']}"
        )
        await message.answer(text)
    except Exception as e:
        await message.answer(f" {str(e)}")

# === /achievements ===
@dp.message(Command("achievements"))
async def cmd_achievements(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/api/achievements/{message.from_user.id}")
            ach = resp.json()
        
        if not ach["achievements"]:
            await message.answer(TEXTS[lang]["no_achievements"])
            return
        
        text = TEXTS[lang]["achievements_header"]
        for a in ach["achievements"]:
            text += f"• {a['name']} — {a['desc']} (+{a['xp']} XP)\n"
        await message.answer(text)
    except Exception as e:
        await message.answer(f" {str(e)}")

# === /help ===
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["help"], parse_mode="Markdown")

# === ЗАПУСК ===
async def main():
    print(f" Бот запущен. API: {API_URL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())