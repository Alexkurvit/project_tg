import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

class ThrottlingMiddleware(BaseMiddleware):
    """
    Простой анти-спам. Ограничивает частоту запросов от одного пользователя.
    """
    def __init__(self, limit: float = 2.0):
        self.limit = limit
        self.users: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        
        # Если пользователя нет (маловероятно для Message), пропускаем
        if not user:
            return await handler(event, data)

        current_time = time.time()
        last_request_time = self.users.get(user.id, 0)

        # Если прошло меньше времени, чем limit
        if current_time - last_request_time < self.limit:
            # Можно отвечать пользователю, а можно просто игнорировать
            # Чтобы не спамить в ответ, лучше ответим один раз или промолчим.
            # Для примера просто вернем None (игнор) или отправим уведомление.
            # await event.answer("⏳ Пожалуйста, не так часто! Подождите немного.")
            return None
        
        # Обновляем время и пропускаем запрос дальше
        self.users[user.id] = current_time
        return await handler(event, data)
