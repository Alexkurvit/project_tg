import logging
import re
import html
import base64
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.vt_scanner import VirusTotalScanner
from services.ai_explainer import AIExplainer
from services.db import Database
from services.security_logger import SecurityLogger

router = Router()
vt_scanner = VirusTotalScanner()
ai_explainer = AIExplainer()
db = Database()

logger = logging.getLogger(__name__)

# Регулярка для поиска ссылок (http/https)
URL_PATTERN = r"(https?://[^\s]+)"

async def run_text_check(message: types.Message, text_to_check: str):
    """
    Общая логика проверки текста/ссылок.
    text_to_check: Текст для анализа (может отличаться от message.text при Deep Linking)
    """
    user_id = message.from_user.id
    chat_type = message.chat.type
    is_group = chat_type in ("group", "supergroup")
    
    # Используем переданный текст, а не message.text
    found_urls = re.findall(URL_PATTERN, text_to_check)
    
    vt_stats = None
    report_link = None
    vt_disabled_note = ""
    is_vt_threat = False
    
    # 1. Начальное сообщение (только в ЛС)
    status_msg = None
    if not is_group:
        status_msg = await message.reply(f"🔎 Принято в работу: {html.escape(text_to_check[:50])}...\nПроверяю... 🕵️‍♂️", parse_mode="HTML")

    # 2. Проверка ссылок (VirusTotal)
    if found_urls:
        url_to_check = found_urls[0]
        if vt_scanner.is_enabled():
            vt_report = await vt_scanner.check_url(url_to_check)
            await db.increment_api_stats(vt=1) 

            if vt_report:
                stats = vt_report.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                vt_stats = stats

                # Генерируем ссылку на отчет
                try:
                    url_id = base64.urlsafe_b64encode(url_to_check.encode()).decode().strip("=")
                    report_link = f"https://www.virustotal.com/gui/url/{url_id}"
                except Exception:
                    pass

                if stats.get("malicious", 0) > 0:
                    is_vt_threat = True
                    if status_msg:
                        await status_msg.edit_text("⚠️ Ссылка выглядит подозрительно! Изучаю детали... 🤖")
        else:
            vt_disabled_note = "⚠️ VirusTotal недоступен: анализ ссылки выполнен без VT.\n\n"
        
        # Записываем в БД
        await db.update_action_stats(user_id, link=True, threat=is_vt_threat)
    
    # 3. Интеллектуальный анализ (AI)
    # Передаем статистику VT в промпт
    ai_verdict = await ai_explainer.analyze_text(text_to_check, vt_stats)
    if ai_explainer.enabled:
        await db.increment_api_stats(ai=1)
    
    safe_verdict = html.escape(ai_verdict)
    
    # Парсинг вердикта
    is_ai_safe = "🟢 БЕЗОПАСНО" in ai_verdict
    is_ai_suspicious = "🟡 ПОДОЗРИТЕЛЬНО" in ai_verdict
    is_ai_danger = "🔴 ОПАСНО" in ai_verdict

    # Формирование ответа
    markup = None
    if report_link:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="🌐 Отчет по ссылке (VirusTotal)", 
            url=report_link
        ))
        markup = builder.as_markup()

    final_text = f"{vt_disabled_note}{safe_verdict}"

    # Получаем настройки чата
    chat_settings = {"mode": "active", "strict": False}
    if is_group:
        chat_settings = await db.get_chat_settings(message.chat.id)

    # ЛОГИКА ОТВЕТА
    if is_group:
        # В ГРУППЕ: Молчим, если безопасно. Действуем, если угроза.
        
        # Режим Silent: Бот пишет только об устранении угрозы, не предупреждает о подозрениях?
        # Или Silent значит, что он вообще ничего не пишет в общий чат, только удаляет?
        # Согласно плану: "Silent Mode: бот ТОЛЬКО удаляет сообщение и тихо пишет админу".
        
        # Критическая угроза (VT > 0 или AI = ОПАСНО)
        if is_vt_threat or is_ai_danger:
            try:
                await message.delete()
            except Exception:
                pass # Нет прав или уже удалено
            
            # Если режим НЕ Silent, пишем в чат
            if chat_settings["mode"] == "active":
                alert_text = f"🚫 <b>УГРОЗА УСТРАНЕНА</b>\n\n{final_text}"
                await message.answer(alert_text, parse_mode="HTML", reply_markup=markup)
            
            # Логируем в админ-канал ВСЕГДА
            sec_logger = SecurityLogger(message.bot)
            await sec_logger.log_threat(
                chat_name=message.chat.title,
                user_name=message.from_user.full_name,
                user_id=message.from_user.id,
                threat_type="Фишинг/Скам" if is_ai_danger else "Вредоносная ссылка (VT)",
                item_name=text_to_check[:50] + "...",
                ai_analysis=ai_verdict
            )
            
        # Подозрение (AI = ПОДОЗРИТЕЛЬНО)
        elif is_ai_suspicious:
            # В режиме Strict удаляем даже подозрительные
            if chat_settings["strict"]:
                try:
                    await message.delete()
                except:
                    pass
                if chat_settings["mode"] == "active":
                    await message.answer(f"⚠️ <b>Удалено подозрительное сообщение</b>\n\n{final_text}", parse_mode="HTML")
            else:
                # Не строгий режим: просто предупреждаем, если не Silent
                if chat_settings["mode"] == "active":
                    warn_text = f"⚠️ <b>ВНИМАНИЕ: ПОДОЗРИТЕЛЬНО</b>\n\n{final_text}"
                    await message.reply(warn_text, parse_mode="HTML", reply_markup=markup)
            
        # Если безопасно (is_ai_safe) -> RETURN (Silent)
        
    else:
        # В ЛС: Всегда показываем результат
        if status_msg:
            await status_msg.edit_text(final_text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.reply(final_text, parse_mode="HTML", reply_markup=markup)


@router.message(F.text)
async def handle_text_analysis(message: types.Message):
    """
    Хендлер для обычных текстовых сообщений.
    """
    # Здесь передаем message.text как текст для проверки
    await run_text_check(message, message.text)
