import os
import logging
from aiogram import Router, F, types
from aiogram.types import FSInputFile

from config import TEMP_DIR
from services.vt_scanner import VirusTotalScanner
from services.ai_explainer import AIExplainer

router = Router()
vt_scanner = VirusTotalScanner()
ai_explainer = AIExplainer()

logger = logging.getLogger(__name__)

@router.message(F.text == "/start")
async def cmd_start(message: types.Message):
    """
    Приветственное сообщение.
    """
    await message.answer(
        "👋 Привет! Я — *PhishGuard*.\n\n"
        "Отправь мне подозрительный файл, и я проверю его по мировой базе антивирусов, "
        "а затем объясню результаты простым языком.",
        parse_mode="Markdown"
    )

@router.message(F.document)
async def handle_document(message: types.Message):
    """
    Обработчик входящих файлов (документов).
    """
    bot = message.bot
    file_id = message.document.file_id
    file_name = message.document.file_name
    
    # Путь для сохранения файла
    file_path = os.path.join(TEMP_DIR, f"{file_id}_{file_name}")

    status_msg = await message.reply("Проверяю файл по базам антивирусов... 🔍")

    try:
        # 1. Скачивание файла
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, file_path)
        
        # 2. Вычисление хеша (теперь асинхронно)
        file_hash = await vt_scanner.calculate_sha256(file_path)
        
        # 3. Проверка в VirusTotal
        vt_report = await vt_scanner.check_file(file_hash)
        
        if not vt_report:
            # Файл не найден в базе VT (скорее всего новый или неизвестный)
            # Для MVP считаем, что если нет в базе - нужно предупредить, но пока просто скажем "Unknown"
            await status_msg.edit_text("ℹ️ Этот файл мне пока неизвестен. Будьте осторожны.")
            return

        # Получаем статистику обнаружений
        stats = vt_report.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        malicious_count = stats.get("malicious", 0)
        
        if malicious_count == 0:
            # 4. Файл чист
            await status_msg.edit_text("✅ Файл чист. Угроз не найдено.")
        else:
            # 5. Файл заражен
            total_engines = sum(stats.values())
            
            # Собираем названия угроз для ИИ
            # Берем результаты сканирования
            results = vt_report.get("data", {}).get("attributes", {}).get("last_analysis_results", {})
            threat_names = []
            for engine, result in results.items():
                if result.get("category") == "malicious":
                    threat_names.append(result.get("result", "Unknown"))
            
            # Ограничим список угроз, чтобы не перегружать промпт (первые 10)
            threat_summary = ", ".join(set(threat_names[:10]))
            
            await status_msg.edit_text(f"⚠️ Найдено угроз: {malicious_count} из {total_engines} антивирусов считают этот файл опасным.\nСпрашиваю у ИИ, что это значит... 🤖")
            
            # 6. Генерация объяснения ИИ
            explanation = await ai_explainer.explain_threat(threat_summary)
            
            final_text = (
                f"🚨 *Обнаружена угроза!* ({malicious_count}/{total_engines})\n\n"
                f"{explanation}"
            )
            # Используем Markdown для форматирования
            await status_msg.edit_text(final_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error handling file: {e}")
        await status_msg.edit_text("Произошла ошибка при анализе файла.")
    finally:
        # 7. Очистка (удаление файла)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"File {file_path} deleted.")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")