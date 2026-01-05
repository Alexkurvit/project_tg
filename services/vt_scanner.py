import hashlib
import base64
import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from config import VT_API_KEY

logger = logging.getLogger(__name__)

class VirusTotalScanner:
    """
    Класс для работы с API VirusTotal (файлы и ссылки).
    """

    @staticmethod
    def _calculate_sha256_sync(file_path: str) -> str:
        """
        Синхронная версия хеширования (для запуска в executor).
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

    async def calculate_sha256(self, file_path: str) -> str:
        """
        Асинхронная обертка для хеширования.
        Запускает тяжелую задачу в отдельном потоке, не блокируя бота.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._calculate_sha256_sync, file_path)

    @staticmethod
    async def _make_request(url: str) -> Optional[Dict[str, Any]]:
        """
        Внутренний метод для выполнения запросов к VT.
        """
        headers = {
            "x-apikey": VT_API_KEY
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        return None
                    else:
                        logger.error(f"Ошибка VT API: статус {response.status}")
                        return None
            except Exception as e:
                logger.error(f"Ошибка соединения с VT: {e}")
                return None

    @classmethod
    async def check_file(cls, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет наличие отчета о файле в VirusTotal по его хешу.
        """
        url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
        return await cls._make_request(url)

    @classmethod
    async def check_url(cls, target_url: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет URL в VirusTotal.
        URL должен быть закодирован в base64 (url safe) без паддинга '='.
        """
        try:
            # Кодируем URL в base64 url-safe формат и убираем '='
            url_id = base64.urlsafe_b64encode(target_url.encode()).decode().strip("=")
            url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
            return await cls._make_request(url)
        except Exception as e:
            logger.error(f"Ошибка при проверке URL {target_url}: {e}")
            return None
