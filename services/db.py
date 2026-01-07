import aiosqlite
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = "database.db"

class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def create_tables(self):
        """Создает таблицы и обновляет структуру БД."""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    joined_date TIMESTAMP,
                    last_active TIMESTAMP,
                    interaction_count INTEGER DEFAULT 0,
                    files_checked INTEGER DEFAULT 0,
                    links_checked INTEGER DEFAULT 0,
                    threats_found INTEGER DEFAULT 0
                )
            """)
            
            # Таблица системной статистики (хранит одну строку)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS system_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    vt_api_calls INTEGER DEFAULT 0,
                    ai_api_calls INTEGER DEFAULT 0
                )
            """)
            # Инициализируем строку статистики, если её нет
            await db.execute("INSERT OR IGNORE INTO system_stats (id, vt_api_calls, ai_api_calls) VALUES (1, 0, 0)")
            
            # Миграции для users
            async with db.execute("PRAGMA table_info(users)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            
            if "files_checked" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN files_checked INTEGER DEFAULT 0")
            if "links_checked" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN links_checked INTEGER DEFAULT 0")
            if "threats_found" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN threats_found INTEGER DEFAULT 0")
                
            await db.commit()

    async def register_user(self, user_id: int, username: str, full_name: str):
        """Регистрирует пользователя / обновляет активность."""
        now = datetime.now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (id, username, full_name, joined_date, last_active, interaction_count)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    last_active = excluded.last_active,
                    interaction_count = users.interaction_count + 1
            """, (user_id, username, full_name, now, now))
            await db.commit()

    async def update_action_stats(self, user_id: int, file: bool = False, link: bool = False, threat: bool = False):
        """Обновляет статистику действий пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            query_parts = []
            if file:
                query_parts.append("files_checked = files_checked + 1")
            if link:
                query_parts.append("links_checked = links_checked + 1")
            if threat:
                query_parts.append("threats_found = threats_found + 1")
            
            if query_parts:
                query = f"UPDATE users SET {', '.join(query_parts)} WHERE id = ?"
                await db.execute(query, (user_id,))
                await db.commit()

    async def increment_api_stats(self, vt: int = 0, ai: int = 0):
        """Увеличивает счетчики использования API."""
        if vt == 0 and ai == 0:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE system_stats 
                SET vt_api_calls = vt_api_calls + ?, 
                    ai_api_calls = ai_api_calls + ?
                WHERE id = 1
            """, (vt, ai))
            await db.commit()

    async def get_statistics(self):
        """Собирает полную статистику."""
        async with aiosqlite.connect(self.db_path) as db:
            # Users stats
            async with db.execute("SELECT COUNT(*), SUM(files_checked), SUM(links_checked), SUM(threats_found) FROM users") as cursor:
                row = await cursor.fetchone()
                total_users = row[0]
                total_files = row[1] or 0
                total_links = row[2] or 0
                total_threats = row[3] or 0

            # Active users
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            
            async with db.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (today_start,)) as cursor:
                active_today = (await cursor.fetchone())[0]
            
            async with db.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (week_start,)) as cursor:
                active_week = (await cursor.fetchone())[0]

            # System stats (API usage)
            async with db.execute("SELECT vt_api_calls, ai_api_calls FROM system_stats WHERE id = 1") as cursor:
                sys_row = await cursor.fetchone()
                vt_calls = sys_row[0] if sys_row else 0
                ai_calls = sys_row[1] if sys_row else 0

            return {
                "total_users": total_users,
                "active_today": active_today,
                "active_week": active_week,
                "total_files": total_files,
                "total_links": total_links,
                "total_threats": total_threats,
                "vt_api_calls": vt_calls,
                "ai_api_calls": ai_calls
            }
