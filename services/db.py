import aiosqlite
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = "database.db"

class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def create_tables(self):
        """Создает таблицы, если их нет."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    joined_date TIMESTAMP,
                    last_active TIMESTAMP,
                    interaction_count INTEGER DEFAULT 0
                )
            """)
            await db.commit()

    async def register_user(self, user_id: int, username: str, full_name: str):
        """
        Регистрирует пользователя или обновляет время последней активности.
        Увеличивает счетчик взаимодействий.
        """
        now = datetime.now()
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, есть ли пользователь
            async with db.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()

            if not user:
                # Новый пользователь
                await db.execute("""
                    INSERT INTO users (id, username, full_name, joined_date, last_active, interaction_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (user_id, username, full_name, now, now))
                logger.info(f"New user registered: {user_id} ({username})")
            else:
                # Старый пользователь - обновляем активность и счетчик
                await db.execute("""
                    UPDATE users 
                    SET username = ?, full_name = ?, last_active = ?, interaction_count = interaction_count + 1
                    WHERE id = ?
                """, (username, full_name, now, user_id))
            
            await db.commit()

    async def get_statistics(self):
        """Собирает статистику для админа."""
        async with aiosqlite.connect(self.db_path) as db:
            # Всего пользователей
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]

            # Активные за сегодня
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            async with db.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (today_start,)) as cursor:
                active_today = (await cursor.fetchone())[0]

            # Активные за неделю
            week_start = today_start - timedelta(days=7)
            async with db.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (week_start,)) as cursor:
                active_week = (await cursor.fetchone())[0]
            
            # Топ 5 активных (для примера)
            # async with db.execute("SELECT username, interaction_count FROM users ORDER BY interaction_count DESC LIMIT 5") as cursor:
            #     top_users = await cursor.fetchall()

            return {
                "total_users": total_users,
                "active_today": active_today,
                "active_week": active_week
            }
