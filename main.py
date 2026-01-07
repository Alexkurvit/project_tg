import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, ADMIN_ID
from handlers import file_analysis, text_analysis, common, admin
from middlewares.throttling import ThrottlingMiddleware
from middlewares.stats import StatsMiddleware
from utils.logging_handler import TelegramAlertHandler
from services.db import Database

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

    # Инициализация базы данных
    db = Database()
    await db.create_tables()

    # Настройка сессии с увеличенным тайм-аутом (для нестабильного интернета)
    session = AiohttpSession(timeout=60)

    # Инициализация бота с DefaultBotProperties и кастомной сессией
    bot = Bot(
        token=BOT_TOKEN, 
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Подключаем отправку алертов админу
    if ADMIN_ID:
        alert_handler = TelegramAlertHandler(bot, ADMIN_ID)
        # Используем тот же формат, что и везде
        alert_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(alert_handler)
        logger.info(f"Admin alerts enabled for ID: {ADMIN_ID}")
    else:
        logger.warning("ADMIN_ID not set. Alerts disabled.")
    
    # Инициализация диспетчера
    dp = Dispatcher()
    
    # Подключение Middleware
    dp.message.middleware(ThrottlingMiddleware(limit=2.0)) # Анти-спам
    dp.message.middleware(StatsMiddleware(db))             # Сбор статистики
    
    # Регистрация роутеров
    # Порядок важен: специфичные команды -> общие обработчики
    dp.include_router(admin.router)         # /stats (только админ)
    dp.include_router(common.router)        # /help, /tips
    dp.include_router(file_analysis.router) # /start, документы
    dp.include_router(text_analysis.router) # Любой текст (должен быть последним)

    logger.info("Starting bot polling...")
    
    # Удаляем вебхук и сбрасываем старые обновления (чтобы не было конфликтов при старте)
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
