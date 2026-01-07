import logging
import re
import html
import base64
from aiogram import Router, F, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from services.vt_scanner import VirusTotalScanner

router = Router()
vt_scanner = VirusTotalScanner()
logger = logging.getLogger(__name__)

URL_PATTERN = r"(https?://[^\s]+)"

@router.inline_query()
async def handle_inline_query(inline_query: types.InlineQuery):
    """
    Обрабатывает inline-запросы.
    Пример: @bot_name google.com
    """
    query_text = inline_query.query.strip()
    
    # Если запрос пустой - показываем заглушку
    if not query_text:
        await inline_query.answer(
            results=[],
            cache_time=300,
            is_personal=True,
            switch_pm_text="🔎 Введите ссылку для проверки",
            switch_pm_parameter="help"
        )
        return

    # Ищем ссылку
    found_urls = re.findall(URL_PATTERN, query_text)
    
    results = []
    
    if found_urls:
        url = found_urls[0]
        # Пробуем быстро проверить в VT (только если есть в кэше/базе)
        # ВАЖНО: Inline запросы должны быть быстрыми.
        
        # Генерируем ID для результата
        result_id = base64.urlsafe_b64encode(url.encode()).decode()[:64]
        
        # Формируем красивое сообщение, которое отправится в чат
        message_content = InputTextMessageContent(
            message_text=f"🛡 <b>PhishGuard Check</b>\n\nПроверяю ссылку: {html.escape(url)}\n\n👇 Нажмите кнопку ниже для полного отчета.",
            parse_mode="HTML"
        )
        
        # Кнопка, которая ведет в бота с deep-link параметром
        # Параметр start=url_... позволит нам сразу запустить проверку в ЛС
        # Но URL может быть длинным, поэтому лучше просто start
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔎 Проверить в боте", url=f"https://t.me/phishing_guart_bot?start=check")]
        ])

        item = InlineQueryResultArticle(
            id=result_id,
            title="🔍 Проверить ссылку",
            description=f"Отправить '{url}' на проверку безопасности.",
            input_message_content=message_content,
            reply_markup=keyboard,
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python_icon_notext.svg/1200px-Python_icon_notext.svg.png", # Заглушка или лого бота
        )
        results.append(item)
    
    else:
        # Если это просто текст
        results.append(InlineQueryResultArticle(
            id="text_check",
            title="📝 Проверить текст",
            description="Отправить текст на анализ (скам/мошенничество).",
            input_message_content=InputTextMessageContent(
                message_text=f"🛡 <b>Анализ текста</b>\n\nТекст отправлен на проверку:\n<i>{html.escape(query_text[:100])}...</i>",
                parse_mode="HTML"
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔎 Анализировать", url=f"https://t.me/phishing_guart_bot?start=check")]
            ])
        ))

    await inline_query.answer(
        results=results,
        cache_time=5, # Кэшируем ненадолго, чтобы не спамить
        is_personal=True 
    )
