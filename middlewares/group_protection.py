import re
import logging
import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.enums import ChatType, ChatMemberStatus

logger = logging.getLogger(__name__)

class GroupProtectionMiddleware(BaseMiddleware):
    def __init__(self):
        self.admin_cache = {} # (chat_id, user_id) -> (is_admin, timestamp)
        self.cache_ttl = 300  # 5 minutes cache

        # Rough filter settings
        self.suspicious_extensions = {'.exe', '.scr', '.bat', '.com', '.zip', '.rar', '.7z', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.py', '.js', '.vbs'}
        self.trigger_words = {
            'схема', 'заработок', 'crypto', 'usdt', 'airdrop', 'private', 'hack', 'cheat', 
            'пассивный доход', 'арбитраж', 'темка', 'карта', 'номер', 'скинь', 'деньги', 
            'банк', 'перевод', 'номер телефона', 'личные данные'
        }
        self.url_pattern = re.compile(r"(https?://[^\s]+)|(t\.me/[^\s]+)|(tg://[^\s]+)")

    async def _is_admin(self, message: Message) -> bool:
        if message.chat.type == ChatType.PRIVATE:
            return False
            
        # Если отправителя нет (например, пост от имени канала), считаем его админом (безопасно)
        if message.from_user is None:
            return True

        chat_id = message.chat.id
        user_id = message.from_user.id
        key = (chat_id, user_id)
        
        # Check cache
        if key in self.admin_cache:
            is_admin, timestamp = self.admin_cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return is_admin
        
        # API Call
        try:
            member = await message.chat.get_member(user_id)
            is_admin = member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
            self.admin_cache[key] = (is_admin, time.time())
            return is_admin
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
        
        # 1. Skip checks for Private chats
        if event.chat.type == ChatType.PRIVATE:
            return await handler(event, data)
            
        # 2. Check Service Messages (New members, etc.) - aiogram handlers usually ignore them unless specific, 
        # but good to be safe.
        if event.content_type not in {'text', 'caption', 'document', 'photo'}:
             # Allow logic to proceed? Usually service messages like 'new_chat_members' are handled by specific handlers.
             # If we return None here, those handlers won't trigger.
             # But our bot focuses on "text/file analysis".
             # Let's check if it's a content type we care about.
             pass

        # 3. Whitelist Admins (Ignore their messages)
        # Note: We might want to allow commands from admins, e.g. /settings
        is_command = event.text and event.text.startswith('/')
        if await self._is_admin(event):
            if is_command:
                return await handler(event, data) # Allow commands
            return # Ignore regular messages from admins
            
        # 4. Rough Filter (The Funnel Step 1)
        
        text_content = event.text or event.caption or ""
        
        # Check 1: Files
        if event.document:
            file_name = event.document.file_name or ""
            ext = "." + file_name.split(".")[-1].lower() if "." in file_name else ""
            if ext in self.suspicious_extensions:
                # Suspicious File -> PASS
                return await handler(event, data)
            # If document but not suspicious extension?
            # Maybe pass anyway to be safe? Or ignore?
            # Plan says: "If file (.exe, .scr...) -> Step 2".
            # Implies other files are ignored? 
            # "Если есть файл (.exe...) или ссылка -> Переход".
            # Let's only pass suspicious extensions or if user wants all files scanned.
            # For now, adhering to plan: pass specific extensions.
            pass

        # Check 2: Links
        if self.url_pattern.search(text_content):
            # Suspicious Link -> PASS
            return await handler(event, data)
            
        # Check 3: Trigger Words
        if any(word in text_content.lower() for word in self.trigger_words):
             # Suspicious Text -> PASS
             return await handler(event, data)
        
        # Check 4: Commands (from non-admins)
        if is_command:
            # Maybe allow /scan or /report?
            # For now allow all commands to reach handlers (they handle permissions internally)
            return await handler(event, data)

        # If we reached here:
        # Message is NOT admin, NOT suspicious file, NO link, NO trigger word.
        # Action: IGNORE
        return
