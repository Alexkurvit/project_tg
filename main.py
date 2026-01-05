import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from handlers import file_analysis, text_analysis
from middlewares.throttling import ThrottlingMiddleware

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

async def main():
    """
    Точка входа. Запуск бота.
    """
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in .env")
        return

    # Инициализация бота с DefaultBotProperties (для parse_mode)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Инициализация диспетчера
    dp = Dispatcher()
    
    # Подключение Middleware (Анти-спам: 1 сообщение в 5 секунд)
    dp.message.middleware(ThrottlingMiddleware(limit=5.0))
    
    # Регистрация роутеров
    # Важно: file_analysis содержит обработку /start (F.text == "/start"), 
    # поэтому он должен быть первым, чтобы команда не ушла в общий анализ текста.
    dp.include_router(file_analysis.router)
    dp.include_router(text_analysis.router)

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
