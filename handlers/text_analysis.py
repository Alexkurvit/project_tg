import logging
import re
from aiogram import Router, F, types
from services.vt_scanner import VirusTotalScanner
from services.ai_explainer import AIExplainer

router = Router()
vt_scanner = VirusTotalScanner()
ai_explainer = AIExplainer()

logger = logging.getLogger(__name__)

# Регулярка для поиска ссылок (http/https)
URL_PATTERN = r"(https?://[^\s]+)"

@router.message(F.text)
async def handle_text_analysis(message: types.Message):
    """
    Анализирует текстовые сообщения.
    1. Ищет ссылки -> Проверяет в VT.
    2. Анализирует текст + результаты VT через ИИ.
    """
    text = message.text
    # Ищем первую ссылку (для MVP берем первую, можно расширить на все)
    found_urls = re.findall(URL_PATTERN, text)
    
    vt_stats = None
    status_msg = await message.reply("Проверяю текст и ссылки... 🕵️‍♂️")

    if found_urls:
        url_to_check = found_urls[0]
        # Проверяем URL в VT
        vt_report = await vt_scanner.check_url(url_to_check)
        
        if vt_report:
            stats = vt_report.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            vt_stats = stats
            # Если много детектов, сразу предупреждаем (опционально)
            if stats.get("malicious", 0) > 0:
                await status_msg.edit_text(f"⚠️ Ссылка выглядит подозрительно! Изучаю детали... 🤖")
    
    # Отправляем текст и статистику VT (если есть) в ИИ
    ai_verdict = await ai_explainer.analyze_text(text, vt_stats)
    
    await status_msg.edit_text(ai_verdict, parse_mode="Markdown")
