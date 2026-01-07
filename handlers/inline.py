import logging
import re
import html
import base64
from typing import Optional
from aiogram import Bot, Router, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from services.vt_scanner import VirusTotalScanner

router = Router()
vt_scanner = VirusTotalScanner()
logger = logging.getLogger(__name__)
_BOT_USERNAME: Optional[str] = None

URL_PATTERN = r"(https?://[^\s]+)"

async def _get_bot_username(bot: Bot) -> Optional[str]:
    global _BOT_USERNAME
    if _BOT_USERNAME:
        return _BOT_USERNAME
    cached = getattr(bot, "username", None)
    if cached:
        _BOT_USERNAME = cached
        return _BOT_USERNAME
    try:
        me = await bot.get_me()
    except Exception as e:
        logger.error(f"Failed to fetch bot username: {e}")
        return None
    _BOT_USERNAME = me.username
    return _BOT_USERNAME

@router.inline_query()
async def handle_inline_query(inline_query: types.InlineQuery):
    """
    Обрабатывает inline-запросы.
    Пример: @bot_name google.com
    """
    query_text = inline_query.query.strip()
    logger.info(f"INLINE QUERY RECEIVED: '{query_text}' from user {inline_query.from_user.id}")
    
    bot_username = await _get_bot_username(inline_query.bot)
    if not bot_username:
        await inline_query.answer(results=[], cache_time=5, is_personal=True)
        return

    results = []

    # Ищем ссылку
    found_urls = re.findall(URL_PATTERN, query_text)
    
    if found_urls:
        url = found_urls[0]
        # Кодируем URL в base64 (urlsafe), чтобы передать в параметре start
        encoded_url = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        
        # Генерируем ID для результата
        result_id = f"url_{encoded_url}"[:64]
        
        message_content = InputTextMessageContent(
            message_text=f"🛡 <b>PhishGuard Check</b>\n\nПроверяю ссылку: {html.escape(url)}\n\n👇 Нажмите кнопку ниже для получения вердикта ИИ.",
            parse_mode="HTML"
        )
        
        # Кнопка с параметром start=url_...
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text="🔎 Получить результат", 
                url=f"https://t.me/{bot_username}?start=url_{encoded_url}"
            )]
        ])

        item = InlineQueryResultArticle(
            id=result_id,
            title="🔍 Проверить ссылку",
            description=f"Нажмите, чтобы проанализировать {url}",
            input_message_content=message_content,
            reply_markup=keyboard,
        )
        results.append(item)
    
    # Если это просто текст или пустой запрос
    if not results and query_text:
        # Кодируем текст (до 30 символов для безопасности длины URL)
        encoded_text = base64.urlsafe_b64encode(query_text[:50].encode()).decode().strip("=")
        
        results.append(InlineQueryResultArticle(
            id="text_check",
            title="📝 Проверить текст",
            description="Отправить этот текст на анализ ИИ",
            input_message_content=InputTextMessageContent(
                message_text=f"🛡 <b>Анализ текста</b>\n\nТекст отправлен на проверку:\n<i>{html.escape(query_text[:100])}...</i>",
                parse_mode="HTML"
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="🔎 Анализировать", 
                    url=f"https://t.me/{bot_username}?start=txt_{encoded_text}"
                )]
            ])
        ))

    try:
        await inline_query.answer(
            results=results,
            cache_time=5, 
            is_personal=True 
        )
    except Exception as e:
        logger.error(f"Error answering inline query: {e}")
