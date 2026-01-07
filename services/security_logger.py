import html
import logging
from aiogram import Bot
from config import SECURITY_LOG_ID

logger = logging.getLogger(__name__)

class SecurityLogger:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.log_chat_id = SECURITY_LOG_ID

    async def log_threat(self, chat_name: str, user_name: str, user_id: int, threat_type: str, item_name: str, ai_analysis: str):
        """
        Отправляет детальный отчет об угрозе в админский канал.
        """
        if not self.log_chat_id:
            return

        safe_chat = html.escape(chat_name or "")
        safe_user = html.escape(user_name or "")
        safe_threat = html.escape(threat_type or "")
        safe_item = html.escape(item_name or "")
        safe_analysis = html.escape(ai_analysis or "")

        text = (
            f"🛡️ <b>ОТЧЕТ PhishGuard Group Sentinel</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Чат:</b> {safe_chat}\n"
            f"👤 <b>Нарушитель:</b> {safe_user} (ID: <code>{user_id}</code>)\n"
            f"🚨 <b>Тип угрозы:</b> {safe_threat}\n"
            f"📦 <b>Объект:</b> <code>{safe_item}</code>\n\n"
            f"🤖 <b>Анализ ИИ:</b>\n{safe_analysis}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <i>Сообщение удалено автоматически.</i>"
        )

        try:
            await self.bot.send_message(
                chat_id=self.log_chat_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить лог безопасности: {e}")
