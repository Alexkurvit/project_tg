from aiogram import Router, F, types
from aiogram.filters import Command
from config import ADMIN_ID
from services.db import Database

router = Router()
db = Database()

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """
    Показывает статистику бота. Доступно только админу.
    """
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        return

    stats = await db.get_statistics()
    
    text = (
        "📊 <b>Статистика PhishGuard</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"📅 Активных сегодня: <b>{stats['active_today']}</b>\n"
        f"🗓 Активных за неделю: <b>{stats['active_week']}</b>\n\n"
        "<b>🔎 Активность проверок:</b>\n"
        f"📁 Файлов проверено: <b>{stats['total_files']}</b>\n"
        f"🔗 Ссылок проверено: <b>{stats['total_links']}</b>\n"
        f"🦠 Угроз найдено: <b>{stats['total_threats']}</b>\n\n"
        "<b>📡 Использование API:</b>\n"
        f"🛡 VirusTotal запросов: <b>{stats['vt_api_calls']}</b>\n"
        f"🧠 AI (Groq) запросов: <b>{stats['ai_api_calls']}</b>"
    )
    
    await message.answer(text, parse_mode="HTML")