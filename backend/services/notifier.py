import asyncio
import logging
import random

import httpx
from config import BASE_DELAY, MAX_RETRIES, TELEGRAM_BOT_TOKEN
from models import Vacancy

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
        "parse_mode": "HTML",
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
            elif resp.status_code in (502, 503, 504):
                delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, BASE_DELAY * 0.3)
                logger.warning(f"Telegram server error {resp.status_code}, attempt {attempt + 1}, retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
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


def _escape_html(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_vacancy_notification(v: Vacancy) -> str:
    salary = v.salary or "не указана"
    url_part = f'🔗 <a href="{v.url}">Открыть</a>' if v.url else ""
    return (
        f"🆕 <b>Новая вакансия!</b>\n\n"
        f"<b>{_escape_html(v.title)}</b>\n"
        f"🏢 {_escape_html(v.company)}\n"
        f"📍 {_escape_html(v.city)}\n"
        f"💰 {_escape_html(salary)}\n"
        f"📅 {_escape_html(v.schedule)}\n"
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


async def close_clients():
    global _shared_client
    if _shared_client:
        await _shared_client.aclose()
        _shared_client = None
