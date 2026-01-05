import logging
from groq import AsyncGroq
from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

class AIExplainer:
    """
    Класс для взаимодействия с Groq API (Llama 3) для объяснения угроз.
    """
    def __init__(self):
        # Инициализация клиента Groq
        self.client = AsyncGroq(api_key=GROQ_API_KEY)
        self.model = "llama-3.3-70b-versatile"
        self.system_prompt = (
            "Ты эксперт по кибербезопасности. Твоя аудитория — школьники и пожилые люди. "
            "Тебе пришел отчет антивируса. Твоя задача: "
            "1. Назвать тип угрозы (Троян, Майнер и т.д.). "
            "2. Объяснить, что он сделает с телефоном/компом. "
            "3. Дать четкий совет. "
            "Отвечай кратко, на русском языке, без воды."
        )

    async def explain_threat(self, threat_data: str) -> str:
        """
        Генерирует объяснение угрозы на основе данных от VirusTotal.
        """
        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": f"Вот данные об угрозе: {threat_data}",
                    }
                ],
                model=self.model,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка при запросе к Groq API: {e}")
            return "Не удалось получить объяснение от ИИ. Пожалуйста, будьте осторожны с этим файлом."

    async def analyze_text(self, text: str, vt_stats: dict = None) -> str:
        """
        Анализирует текст сообщения на предмет социальной инженерии и фишинга.
        Если есть данные VT (vt_stats), учитывает их.
        """
        vt_context = ""
        if vt_stats:
            vt_context = f"\nТехнический анализ ссылки (VirusTotal): {vt_stats}"
        
        prompt = (
            f"Текст сообщения: \"{text}\"{vt_context}\n\n"
            "Твоя задача: Проанализировать это сообщение на предмет мошенничества (скам, фишинг, социальная инженерия). "
            "Обрати внимание на: срочность, давление, просьбы денег, подозрительные ссылки.\n"
            "Структура ответа:\n"
            "1. ВЕРДИКТ: (СКАМ / ПОДОЗРИТЕЛЬНО / БЕЗОПАСНО)\n"
            "2. АНАЛИЗ: (Почему ты так решил?)\n"
            "3. СОВЕТ: (Что делать пользователю?)\n"
            "Отвечай кратко, четко, на русском языке."
        )

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по кибербезопасности. Ты защищаешь людей от мошенников.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка при анализе текста Groq API: {e}")
            return "Не удалось провести анализ текста. Будьте бдительны."
