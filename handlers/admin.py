from aiogram import Router, F, types
from aiogram.filters import Command
from config import ADMIN_ID
from services.db import Database

router = Router()
# Мы передадим экземпляр DB в main.py, но чтобы получить его здесь,
# проще создать новый экземпляр, так как он stateless (хранит только путь),
# либо передать через data. Для простоты создадим здесь.
db = Database()

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """
    Показывает статистику бота. Доступно только админу.
    """
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        # Игнорируем чужаков, чтобы не палить, что такая команда есть
        return

    stats = await db.get_statistics()
    
    text = (
        "📊 <b>Статистика PhishGuard</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"📅 Активных сегодня: <b>{stats['active_today']}</b>\n"
        f"🗓 Активных за неделю: <b>{stats['active_week']}</b>\n"
    )
    
    await message.answer(text, parse_mode="HTML")