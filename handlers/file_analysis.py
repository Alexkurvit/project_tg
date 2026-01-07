import os
import logging
import html
import asyncio
import secrets
import string
import base64
from pathlib import Path
from aiogram import Router, F, types
from aiogram.filters import CommandObject, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TEMP_DIR, MAX_FILE_SIZE
from services.vt_scanner import VirusTotalScanner
from services.ai_explainer import AIExplainer
from services.db import Database
from services.security_logger import SecurityLogger
# Импортируем функцию логики проверки текста
from handlers.text_analysis import run_text_check

router = Router()
vt_scanner = VirusTotalScanner()
ai_explainer = AIExplainer()
db = Database()

logger = logging.getLogger(__name__)

SAFE_FILENAME_CHARS = set(string.ascii_letters + string.digits + "._- ")

def _sanitize_filename(file_name: str, max_length: int = 120) -> str:
    base_name = os.path.basename(file_name or "")
    cleaned = "".join(ch for ch in base_name if ch in SAFE_FILENAME_CHARS)
    if not cleaned or cleaned in {".", ".."}:
        cleaned = "file"
    if len(cleaned) > max_length:
        root, ext = os.path.splitext(cleaned)
        cleaned = root[: max_length - len(ext)] + ext
    return cleaned

def _build_temp_path(file_name: str) -> str:
    safe_name = _sanitize_filename(file_name)
    unique_prefix = secrets.token_hex(8)
    return str(Path(TEMP_DIR) / f"{unique_prefix}_{safe_name}")

@router.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    """
    Приветственное сообщение. Поддерживает Deep Linking для Inline-режима.
    """
    args = command.args
    if args:
        # Обработка перехода из Inline-режима
        try:
            payload = args
            if args.startswith(("url_", "txt_")):
                payload = args[4:]

            if payload:
                padding = "=" * (-len(payload) % 4)
                decoded_text = base64.urlsafe_b64decode(payload + padding).decode(errors="replace")

                # Вместо хака с message.text вызываем выделенную функцию логики
                await run_text_check(message, decoded_text)
                return
        except Exception as e:
            logger.error(f"Error decoding deep link args: {e}")

    await message.answer(
        "👋 Привет! Я — <b>PhishGuard</b>.\n\n"
        "Отправь мне подозрительный файл, и я проверю его по мировой базе антивирусов, "
        "а затем объясню результаты простым языком.\n\n"
        "Также ты можешь переслать мне подозрительное сообщение или ссылку.",
        parse_mode="HTML"
    )

@router.message(F.document)
async def handle_document(message: types.Message):
    """
    Обработчик входящих файлов (документов).
    """
    bot = message.bot
    file_id = message.document.file_id
    file_name = message.document.file_name or "file"
    file_size = message.document.file_size
    user_id = message.from_user.id
    
    chat_type = message.chat.type
    is_group = chat_type in ("group", "supergroup")

    if file_size is not None and file_size > MAX_FILE_SIZE:
        if not is_group:
            await message.reply(
                f"❌ Файл слишком большой ({file_size / 1024 / 1024:.2f} MB).\n"
                "Я могу проверять файлы только до 20 MB из-за ограничений Telegram."
            )
        return

    if not vt_scanner.is_enabled():
        if not is_group:
            await message.reply("❌ VirusTotal недоступен: не настроен ключ VT_API_KEY.")
        return
    
    # Путь для сохранения файла
    file_path = _build_temp_path(file_name)

    status_msg = None
    if not is_group:
        status_msg = await message.reply("Проверяю файл по базам антивирусов... 🔍")

    try:
        # 1. Скачивание файла
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, file_path)
        
        # 2. Вычисление хеша
        file_hash = await vt_scanner.calculate_sha256(file_path)
        
        # 3. Проверка в VirusTotal
        vt_report = await vt_scanner.check_file(file_hash)
        await db.increment_api_stats(vt=1)
        
        # Если отчет не найден, загружаем файл на сканирование
        if not vt_report:
            if not is_group and status_msg:
                await status_msg.edit_text("ℹ️ Файл новый. Загружаю на сканирование в VirusTotal (это может занять время)... ⏳")
            
            analysis_id = await vt_scanner.upload_file(file_path)
            await db.increment_api_stats(vt=1)
            
            if not analysis_id:
                if status_msg: await status_msg.edit_text("❌ Ошибка при загрузке файла на сканирование.")
                return

            max_retries = 20
            for _ in range(max_retries):
                await asyncio.sleep(3)
                analysis_result = await vt_scanner.get_analysis(analysis_id)
                await db.increment_api_stats(vt=1)
                
                if not analysis_result:
                    continue
                
                status = analysis_result.get("data", {}).get("attributes", {}).get("status")
                
                if status == "completed":
                    vt_report = analysis_result 
                    break
            else:
                if status_msg: await status_msg.edit_text("⌛ Сканирование затянулось. Попробуйте проверить этот файл позже.")
                return

        # 4. Обработка результатов
        attributes = vt_report.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats") or attributes.get("stats") or {}
        malicious_count = stats.get("malicious", 0)
        
        await db.update_action_stats(user_id, file=True, threat=(malicious_count > 0))
        
        report_link = f"https://www.virustotal.com/gui/file/{file_hash}"
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🌐 Полный отчет (VirusTotal)", url=report_link))

        # Получаем настройки чата
        chat_settings = {"mode": "active", "strict": False}
        if is_group:
            chat_settings = await db.get_chat_settings(message.chat.id)

        if malicious_count == 0:
            if not is_group:
                if status_msg:
                    await status_msg.edit_text(
                        "✅ <b>Файл чист.</b> Угроз не найдено.",
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
            # В группе: Молчим, если чисто.
        else:
            total_engines = sum(stats.values())
            threat_names = []
            results = attributes.get("last_analysis_results") or attributes.get("results") or {}
            
            for engine, result in results.items():
                if result.get("category") == "malicious":
                    threat_name = result.get("result") or "Unknown"
                    threat_names.append(str(threat_name))
            
            threat_summary = ", ".join(set(threat_names[:10]))
            
            if status_msg:
                await status_msg.edit_text(f"⚠️ Найдено угроз: {malicious_count} из {total_engines}. Анализирую... 🤖")
            
            explanation = await ai_explainer.explain_threat(threat_summary)
            if ai_explainer.enabled:
                await db.increment_api_stats(ai=1)
            safe_explanation = html.escape(explanation)
            
            final_text = (
                f"🚨 <b>Обнаружена угроза!</b> ({malicious_count}/{total_engines})\n\n"
                f"{safe_explanation}"
            )
            
            if is_group:
                sender_name = html.escape(message.from_user.full_name or "")
                try:
                    await message.delete()
                except:
                    pass
                
                # Если режим НЕ Silent, пишем в чат
                if chat_settings["mode"] == "active":
                    await message.answer(
                        f"🚫 <b>ВРЕДОНОСНЫЙ ФАЙЛ УДАЛЕН</b>\nОтправитель: {sender_name}\n\n{final_text}",
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
                
                # Логируем в админ-канал ВСЕГДА
                sec_logger = SecurityLogger(message.bot)
                await sec_logger.log_threat(
                    chat_name=message.chat.title,
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    threat_type=f"Вредоносный файл ({malicious_count} детектов)",
                    item_name=file_name,
                    ai_analysis=explanation
                )
            else:
                if status_msg:
                    await status_msg.edit_text(final_text, parse_mode="HTML", reply_markup=builder.as_markup())
                else:
                    await message.reply(final_text, parse_mode="HTML", reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error handling file: {e}")
        if status_msg: await status_msg.edit_text("Произошла ошибка при анализе файла.")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"File {file_path} deleted.")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")
