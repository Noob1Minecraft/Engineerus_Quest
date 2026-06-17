from aiogram import Router, types
from aiogram.filters import Command
import httpx
import os

router = Router()
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

@router.message(Command("daily"))
async def cmd_daily(message: types.Message):
    """Взять ежедневный квест"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_URL}/api/daily/quest",
                json={"telegram_id": message.from_user.id},
                timeout=10.0
            )
            res = resp.json()
        
        if res.get("status") == "already":
            await message.answer(res["message"])
            return
        
        quest = res["quest"]
        streak = res.get("streak", 0)
        
        await message.answer(
            f" **Ежедневный квест!**\n\n"
            f"{quest['text']}\n\n"
            f" Награда: **+{quest['xp']} XP**\n"
            f" Текущая серия: **{streak} дней**\n\n"
            f"Когда выполнишь — напиши /check_daily",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f" Ошибка: {str(e)}")

@router.message(Command("check_daily"))
async def cmd_check_daily(message: types.Message):
    """Проверить выполнение квеста"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_URL}/api/daily/check",
                json={"telegram_id": message.from_user.id},
                timeout=10.0
            )
            res = resp.json()
        
        if res.get("status") == "no_quest":
            await message.answer(res["message"])
            return
        
        if res.get("status") == "expired":
            await message.answer(res["message"])
            return
        
        # Квест выполнен!
        text = (
            f" **Квест выполнен!**\n\n"
            f" +{res['xp_reward']} XP\n"
            f" Серия: **{res['streak']} дней**\n"
            f" Всего XP: **{res['total_xp']}** | Уровень: **{res['level']}**"
        )
        
        if res.get("bonus") > 0:
            text += f"\n\n🏆 **БОНУС ЗА НЕДЕЛЮ!** +{res['bonus']} XP"
        
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f" Ошибка: {str(e)}")

@router.message(Command("streak"))
async def cmd_streak(message: types.Message):
    """Показать текущую серию"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API_URL}/api/daily/status/{message.from_user.id}",
                timeout=10.0
            )
            res = resp.json()
        
        if res.get("status") == "error":
            await message.answer(res["message"])
            return
        
        streak = res.get("streak", 0)
        xp = res.get("xp", 0)
        
        # Эмодзи в зависимости от серии
        if streak == 0:
            emoji = ""
            text = "Ты ещё не начал серию!"
        elif streak < 3:
            emoji = ""
            text = "Хорошее начало!"
        elif streak < 7:
            emoji = ""
            text = "Отличная работа!"
        else:
            emoji = ""
            text = "ТЫ ЛЕГЕНДА!"
        
        await message.answer(
            f"{emoji} **Твоя серия:** {streak} дней\n\n"
            f" **Всего XP:** {xp}\n"
            f"{text}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f" Ошибка: {str(e)}")