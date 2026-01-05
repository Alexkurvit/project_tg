import hashlib
import aiohttp
import logging
from typing import Optional, Dict, Any
from config import VT_API_KEY

logger = logging.getLogger(__name__)

class VirusTotalScanner:
    """
    Класс для работы с API VirusTotal и вычисления хешей файлов.
    """

    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        """
        Вычисляет SHA256 хеш файла, читая его частями по 4096 байт.
        Экономит оперативную память.
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Читаем файл кусками по 4 КБ
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Ошибка при хешировании файла {file_path}: {e}")
            raise e

    @staticmethod
    async def check_file(file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет наличие отчета о файле в VirusTotal по его хешу.
        Использует API v3.
        """
        url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
        headers = {
            "x-apikey": VT_API_KEY
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    elif response.status == 404:
                        # Файл не найден в базе VT
                        return None
                    else:
                        logger.error(f"Ошибка VT API: статус {response.status}")
                        return None
            except Exception as e:
                logger.error(f"Ошибка соединения с VT: {e}")
                return None
