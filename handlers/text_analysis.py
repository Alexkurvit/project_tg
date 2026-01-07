import logging
import re
import html
import base64
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.vt_scanner import VirusTotalScanner
from services.ai_explainer import AIExplainer
from services.db import Database

router = Router()
vt_scanner = VirusTotalScanner()
ai_explainer = AIExplainer()
db = Database()

logger = logging.getLogger(__name__)

# Регулярка для поиска ссылок (http/https)
URL_PATTERN = r"(https?://[^\s]+)"

async def run_text_check(message: types.Message, text: str):
    """
    Общая логика проверки текста/ссылок.
    Вынесена в отдельную функцию, чтобы можно было вызывать из Deep Linking (/start).
    """
    user_id = message.from_user.id
    found_urls = re.findall(URL_PATTERN, text)
    
    vt_stats = None
    report_link = None
    
    status_msg = await message.reply(f"🔎 Принято в работу: {html.escape(text[:50])}...\nПроверяю... 🕵️‍♂️", parse_mode="HTML")

    if found_urls:
        url_to_check = found_urls[0]
        # Проверяем URL в VT
        vt_report = await vt_scanner.check_url(url_to_check)
        await db.increment_api_stats(vt=1) # +1 запрос
        
        # Обновляем статистику (проверена ссылка)
        is_threat = False
        
        if vt_report:
            stats = vt_report.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            vt_stats = stats
            
            # Генерируем ссылку на отчет
            try:
                url_id = base64.urlsafe_b64encode(url_to_check.encode()).decode().strip("=")
                report_link = f"https://www.virustotal.com/gui/url/{url_id}"
            except:
                pass

            if stats.get("malicious", 0) > 0:
                is_threat = True
                await status_msg.edit_text(f"⚠️ Ссылка выглядит подозрительно! Изучаю детали... 🤖")
        
        # Записываем в БД
        await db.update_action_stats(user_id, link=True, threat=is_threat)
    
    # Отправляем текст и статистику VT (если есть) в ИИ
    ai_verdict = await ai_explainer.analyze_text(text, vt_stats)
    await db.increment_api_stats(ai=1) # +1 запрос
    safe_verdict = html.escape(ai_verdict)
    
    # Добавляем кнопку, если была ссылка
    markup = None
    if report_link:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="🌐 Отчет по ссылке (VirusTotal)", 
            url=report_link
        ))
        markup = builder.as_markup()
    
    await status_msg.edit_text(safe_verdict, parse_mode="HTML", reply_markup=markup)

@router.message(F.text)
async def handle_text_analysis(message: types.Message):
    """
    Хендлер для обычных текстовых сообщений.
    """
    await run_text_check(message, message.text)