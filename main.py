import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from handlers import file_analysis, text_analysis, common
from middlewares.throttling import ThrottlingMiddleware

# Настройка логирования
file_handler = RotatingFileHandler("bot.log", maxBytes=5*1024*1024, backupCount=2)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        file_handler
    ]
)
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
    
    # Подключение Middleware (Анти-спам: 1 сообщение в 2 секунды)
    dp.message.middleware(ThrottlingMiddleware(limit=2.0))
    
    # Регистрация роутеров
    # Порядок важен: специфичные команды -> общие обработчики
    dp.include_router(common.router)        # /help, /tips
    dp.include_router(file_analysis.router) # /start, документы
    dp.include_router(text_analysis.router) # Любой текст (должен быть последним)

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
