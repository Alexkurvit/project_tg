import os
import logging
import html
import asyncio
import secrets
import string
from pathlib import Path
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TEMP_DIR, MAX_FILE_SIZE
from services.vt_scanner import VirusTotalScanner
from services.ai_explainer import AIExplainer
from services.db import Database

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

@router.message(F.text == "/start")
async def cmd_start(message: types.Message):
    """
    Приветственное сообщение.
    """
    await message.answer(
        "👋 Привет! Я — <b>PhishGuard</b>.\n\n"
        "Отправь мне подозрительный файл, и я проверю его по мировой базе антивирусов, "
        "а затем объясню результаты простым языком.",
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

    if file_size > MAX_FILE_SIZE:
        await message.reply(
            f"❌ Файл слишком большой ({file_size / 1024 / 1024:.2f} MB).\n"
            "Я могу проверять файлы только до 20 MB из-за ограничений Telegram."
        )
        return
    
    # Путь для сохранения файла
    file_path = _build_temp_path(file_name)

    status_msg = await message.reply("Проверяю файл по базам антивирусов... 🔍")

    try:
        # 1. Скачивание файла
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, file_path)
        
        # 2. Вычисление хеша
        file_hash = await vt_scanner.calculate_sha256(file_path)
        
        # 3. Проверка в VirusTotal
        vt_report = await vt_scanner.check_file(file_hash)
        await db.increment_api_stats(vt=1) # +1 запрос
        
        # Если отчет не найден, загружаем файл на сканирование
        if not vt_report:
            await status_msg.edit_text("ℹ️ Файл новый. Загружаю на сканирование в VirusTotal (это может занять время)... ⏳")
            
            analysis_id = await vt_scanner.upload_file(file_path)
            await db.increment_api_stats(vt=1) # +1 запрос (upload)
            
            if not analysis_id:
                await status_msg.edit_text("❌ Ошибка при загрузке файла на сканирование.")
                return

            # Полллинг результатов (ждем завершения анализа)
            max_retries = 20  # 20 * 3 сек = 1 минута ожидания (можно увеличить)
            for _ in range(max_retries):
                await asyncio.sleep(3) # Ждем перед проверкой
                analysis_result = await vt_scanner.get_analysis(analysis_id)
                await db.increment_api_stats(vt=1) # +1 запрос (polling)
                
                if not analysis_result:
                    continue
                
                status = analysis_result.get("data", {}).get("attributes", {}).get("status")
                
                if status == "completed":
                    vt_report = analysis_result 
                    break
            else:
                await status_msg.edit_text("⌛ Сканирование затянулось. Попробуйте проверить этот файл позже.")
                return

        # 4. Обработка результатов
        attributes = vt_report.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats") or attributes.get("stats") or {}
        malicious_count = stats.get("malicious", 0)
        
        # Обновляем статистику пользователя
        await db.update_action_stats(user_id, file=True, threat=(malicious_count > 0))
        
        # Формируем ссылку на отчет
        report_link = f"https://www.virustotal.com/gui/file/{file_hash}"
        
        # Создаем кнопку
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="🌐 Полный отчет (VirusTotal)", 
            url=report_link
        ))

        if malicious_count == 0:
            await status_msg.edit_text(
                "✅ <b>Файл чист.</b> Угроз не найдено.\n\n"
                "Вы можете посмотреть технический отчет по кнопке ниже.",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        else:
            total_engines = sum(stats.values())
            
            # Сбор названий угроз
            threat_names = []
            results = attributes.get("last_analysis_results") or attributes.get("results") or {}
            
            for engine, result in results.items():
                if result.get("category") == "malicious":
                    threat_names.append(result.get("result", "Unknown"))
            
            threat_summary = ", ".join(set(threat_names[:10]))
            
            await status_msg.edit_text(f"⚠️ Найдено угроз: {malicious_count} из {total_engines}. Анализирую... 🤖")
            
            # Генерация объяснения ИИ
            explanation = await ai_explainer.explain_threat(threat_summary)
            await db.increment_api_stats(ai=1) # +1 запрос к AI
            safe_explanation = html.escape(explanation)
            
            final_text = (
                f"🚨 <b>Обнаружена угроза!</b> ({malicious_count}/{total_engines})\n\n"
                f"{safe_explanation}"
            )
            await status_msg.edit_text(
                final_text, 
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )

    except Exception as e:
        logger.error(f"Error handling file: {e}")
        await status_msg.edit_text("Произошла ошибка при анализе файла.")
    finally:
        # Очистка
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"File {file_path} deleted.")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")