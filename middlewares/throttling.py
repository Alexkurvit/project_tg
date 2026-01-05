import asyncio
import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

class ThrottlingMiddleware(BaseMiddleware):
    """
    Умный анти-спам. Если пользователь пишет слишком быстро, 
    бот просит подождать и сам обрабатывает сообщение после паузы.
    """
    def __init__(self, limit: float = 2.0):
        self.limit = limit
        self.users: Dict[int, Dict[str, float]] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)

        current_time = time.time()
        user_data = self.users.setdefault(user.id, {'last_request': 0.0, 'last_warned': 0.0})
        
        last_request = user_data['last_request']
        delta = current_time - last_request

        if delta < self.limit:
            wait_time = self.limit - delta
            
            # Предупреждаем пользователя, что мы "поставили его в очередь"
            # Но только если мы еще не предупреждали его за эту паузу
            wait_msg = None
            if current_time - user_data['last_warned'] > self.limit:
                wait_msg = await event.answer(f"⏳ Получил! Начну проверку через {wait_time:.1f} сек...")
                user_data['last_warned'] = current_time

            # Ждем нужное время
            await asyncio.sleep(wait_time)
            
            # Удаляем сообщение о ожидании, чтобы не захламлять чат
            if wait_msg:
                try:
                    await wait_msg.delete()
                except Exception:
                    pass

        # Обновляем время ПОСЛЕ ожидания, чтобы следующий запрос тоже ждал свой интервал
        user_data['last_request'] = time.time()
        return await handler(event, data)
