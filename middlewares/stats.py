from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from services.db import Database

class StatsMiddleware(BaseMiddleware):
    """
    Middleware для сбора статистики активности пользователей.
    """
    def __init__(self, db: Database):
        self.db = db

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        
        if user:
            # Запускаем обновление БД (можно не ждать завершения, чтобы не тормозить бота, 
            # но aiosqlite работает быстро, так что await безопасен)
            await self.db.register_user(
                user_id=user.id,
                username=user.username,
                full_name=user.full_name
            )

        return await handler(event, data)
