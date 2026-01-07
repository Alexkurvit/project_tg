import hashlib
import base64
import asyncio
import aiohttp
import logging
import os
from typing import Optional, Dict, Any
from config import VT_API_KEY

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
_API_KEY_MISSING_LOGGED = False

def _ensure_api_key() -> bool:
    global _API_KEY_MISSING_LOGGED
    if VT_API_KEY:
        return True
    if not _API_KEY_MISSING_LOGGED:
        logger.error("VT_API_KEY is not set. VirusTotal requests are disabled.")
        _API_KEY_MISSING_LOGGED = True
    return False

class VirusTotalScanner:
    """
    Класс для работы с API VirusTotal (файлы и ссылки).
    """
    @staticmethod
    def is_enabled() -> bool:
        return bool(VT_API_KEY)

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
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._calculate_sha256_sync, file_path)

    @staticmethod
    async def _make_request(url: str, method="GET", data=None, files=None) -> Optional[Dict[str, Any]]:
        """
        Универсальный метод для запросов к VT.
        """
        if not _ensure_api_key():
            return None
        headers = {
            "x-apikey": VT_API_KEY
        }
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 404:
                            return None # Объект не найден
                        else:
                            text = await response.text()
                            logger.error(f"VT API Error ({method} {url}): {response.status} - {text}")
                            return None
                elif method == "POST":
                    # Для загрузки файлов заголовки обрабатываются библиотекой (multipart),
                    # кроме x-apikey, который нужен.
                    async with session.post(url, headers=headers, data=data) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            text = await response.text()
                            logger.error(f"VT API Error ({method} {url}): {response.status} - {text}")
                            return None
            except Exception as e:
                logger.error(f"Connection Error VT: {e}")
                return None

    @classmethod
    async def check_file(cls, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет наличие отчета о файле в VirusTotal по его хешу.
        """
        url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
        return await cls._make_request(url)

    @classmethod
    async def upload_file(cls, file_path: str) -> Optional[str]:
        """
        Загружает файл на сканирование в VT.
        Возвращает ID анализа (analysis_id) или None.
        """
        url = "https://www.virustotal.com/api/v3/files"
        
        # aiohttp принимает файлы через FormData
        data = aiohttp.FormData()
        with open(file_path, "rb") as file_handle:
            data.add_field(
                "file",
                file_handle,
                filename=os.path.basename(file_path)
            )
            response = await cls._make_request(url, method="POST", data=data)
        if response and "data" in response:
            return response["data"]["id"]
        return None

    @classmethod
    async def get_analysis(cls, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает статус анализа.
        """
        url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
        return await cls._make_request(url)

    @classmethod
    async def check_url(cls, target_url: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет URL в VirusTotal.
        """
        try:
            url_id = base64.urlsafe_b64encode(target_url.encode()).decode().strip("=")
            url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
            return await cls._make_request(url)
        except Exception as e:
            logger.error(f"Error checking URL {target_url}: {e}")
            return None
