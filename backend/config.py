import os
from pathlib import Path

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBAPP_URL = os.getenv("TELEGRAM_WEBAPP_URL", "http://localhost:5173")


def validate_startup_config():
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"Missing required env vars: {', '.join(missing)}. Some features may be degraded.")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
DB_PATH = BASE_DIR / "vacancy_bot.db"

HH_API_BASE = "https://api.hh.ru"
HH_USER_AGENT = os.getenv(
    "HH_USER_AGENT",
    "VacancyAgent/1.0",
)
HH_PROXY = os.getenv("HH_PROXY", "")
HH_PROXY_LIST = os.getenv("HH_PROXY_LIST", "")

ALLOWED_ORIGINS = [
    TELEGRAM_WEBAPP_URL,
]
if "localhost" in TELEGRAM_WEBAPP_URL:
    ALLOWED_ORIGINS.extend(["http://localhost:5173", "http://localhost:3000"])

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

NOTIFICATION_INTERVAL = 300
MAX_SESSION_PAYLOAD_BYTES = MAX_UPLOAD_SIZE + 1024 * 1024  # slightly larger than upload limit to account for JSON overhead
ANALYSIS_CACHE_TTL = 3600
MAX_RETRIES = 3
BASE_DELAY = 1.0
ANALYSIS_MAX_VACANCIES = int(os.getenv("ANALYSIS_MAX_VACANCIES", "20"))

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))

AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "1"))
AGENT_TRACE_ENABLED = os.getenv("AGENT_TRACE_ENABLED", "true").lower() == "true"
AGENT_MEMORY_TTL_DAYS = int(os.getenv("AGENT_MEMORY_TTL_DAYS", "30"))
