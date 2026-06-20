import httpx
import asyncio
import logging
import random
from config import TELEGRAM_BOT_TOKEN, MAX_RETRIES, BASE_DELAY
from models import Subscription, Vacancy

logger = logging.getLogger(__name__)

_shared_client: httpx.AsyncClient | None = None


async def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None):
    global _shared_client
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("No TELEGRAM_BOT_TOKEN, skipping notification")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    for attempt in range(MAX_RETRIES):
        try:
            if _shared_client is None:
                _shared_client = httpx.AsyncClient(timeout=10)
            resp = await _shared_client.post(url, json=payload)
            if resp.status_code == 200:
                return True
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", BASE_DELAY * (2 ** attempt)))
                logger.warning(f"Telegram rate limited, waiting {retry_after}s")
                await asyncio.sleep(retry_after)
                continue
            else:
                logger.error(f"Telegram API error: status={resp.status_code}")
                return False
        except httpx.TimeoutException:
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, BASE_DELAY * 0.3)
            logger.warning(f"Telegram timeout, attempt {attempt + 1}, retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"Telegram send failed: {type(e).__name__}")
            return False

    logger.error(f"Telegram send failed after {MAX_RETRIES} retries")
    return False


def format_vacancy_notification(v: Vacancy) -> str:
    salary = v.salary or "не указана"
    url_part = f"🔗 [Открыть]({v.url})" if v.url else ""
    return (
        f"🆕 *Новая вакансия!*\n\n"
        f"*{v.title}*\n"
        f"🏢 {v.company}\n"
        f"📍 {v.city}\n"
        f"💰 {salary}\n"
        f"📅 {v.schedule}\n"
        f"{url_part}"
    )


async def notify_new_vacancies(chat_id: int, vacancies: list[Vacancy]) -> int:
    count = 0
    for v in vacancies[:5]:
        text = format_vacancy_notification(v)
        reply_markup = None
        if v.url:
            reply_markup = {
                "inline_keyboard": [[{"text": "Открыть", "url": v.url}]]
            }
        success = await send_telegram_message(chat_id, text, reply_markup)
        if success:
            count += 1
        await asyncio.sleep(0.5)
    return count
