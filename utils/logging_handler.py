import logging
import asyncio
from aiogram import Bot

class TelegramAlertHandler(logging.Handler):
    """
    Кастомный обработчик логов.
    Перехватывает записи уровня ERROR/CRITICAL и отправляет их админу в Telegram.
    """
    def __init__(self, bot: Bot, admin_id: int):
        super().__init__()
        self.bot = bot
        self.admin_id = admin_id
        # Устанавливаем уровень, чтобы не слать обычные INFO сообщения
        self.setLevel(logging.ERROR)

    def emit(self, record):
        try:
            # Если цикла событий нет (например, старт бота), мы не можем отправить сообщение
            # (или если ошибка произошла в другом потоке без loop)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return

            # Форматируем сообщение об ошибке
            log_entry = self.format(record)
            
            # Обрезаем, если слишком длинное (Telegram limit 4096)
            if len(log_entry) > 3500:
                log_entry = log_entry[:3500] + "... (truncated)"
            
            text = f"🚨 **SYSTEM ERROR DETECTED**\n\n```\n{log_entry}\n```"
            
            # Создаем задачу в текущем цикле
            loop.create_task(self._send_alert(text))
            
        except Exception:
            self.handleError(record)

    async def _send_alert(self, text: str):
        try:
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception:
            # Если не удалось отправить алерт (например, Telegram упал), 
            # мы ничего не можем сделать, кроме как промолчать.
            pass
