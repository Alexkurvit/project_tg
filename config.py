import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# API Keys
BOT_TOKEN = os.getenv("BOT_TOKEN")
VT_API_KEY = os.getenv("VT_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Admin Config
admin_id_str = os.getenv("ADMIN_ID")
ADMIN_ID = int(admin_id_str) if admin_id_str else None

# Constants
TEMP_DIR = "temp_files"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB limit example (optional but good practice)

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
