import os
from pathlib import Path

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBAPP_URL = os.getenv("TELEGRAM_WEBAPP_URL", "http://localhost:5173")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
DB_PATH = BASE_DIR / "vacancy_bot.db"

HH_API_BASE = "https://api.hh.ru"
HH_USER_AGENT = os.getenv(
    "HH_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)
HH_PROXY = os.getenv("HH_PROXY", "")
HH_PROXY_LIST = os.getenv("HH_PROXY_LIST", "")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    TELEGRAM_WEBAPP_URL,
]

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

MAX_VACANCIES_PER_SESSION = 100
SESSION_TTL_SECONDS = 3600 * 4  # 4 hours

RATE_LIMITS = {
    "search": "30/minute",
    "upload": "5/minute",
    "analyze": "10/minute",
    "default": "60/minute",
}

PROMPT_INPUT_MAX_LEN = 500

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))
