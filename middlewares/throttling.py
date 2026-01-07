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
    def __init__(self, limit: float = 2.0, cleanup_interval: float = 300.0, max_idle: float = 600.0):
        self.limit = limit
        self.users: Dict[int, Dict[str, float]] = {}
        self.cleanup_interval = cleanup_interval
        self.max_idle = max_idle
        self._last_cleanup = time.time()

    def _cleanup(self, current_time: float) -> None:
        stale_ids = [
            user_id
            for user_id, data in self.users.items()
            if current_time - data.get("last_request", 0.0) > self.max_idle
            and current_time - data.get("last_warned", 0.0) > self.max_idle
        ]
        for user_id in stale_ids:
            del self.users[user_id]
        self._last_cleanup = current_time

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
        if current_time - self._last_cleanup > self.cleanup_interval:
            self._cleanup(current_time)
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
