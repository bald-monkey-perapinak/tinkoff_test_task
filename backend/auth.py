import hmac
import hashlib
import time
import logging
from urllib.parse import parse_qsl
from fastapi import Request, HTTPException
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

TELEGRAM_INIT_DATA_MAX_AGE = 3600  # 1 hour


def validate_telegram_init_data(init_data: str, bot_token: str, max_age: int = TELEGRAM_INIT_DATA_MAX_AGE) -> dict | None:
    if not init_data or not bot_token:
        return None

    try:
        parsed = dict(parse_qsl(init_data))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    auth_date_str = parsed.get("auth_date", "0")
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        return None

    if time.time() - auth_date > max_age:
        logger.warning("Telegram initData expired: auth_date=%s, now=%s", auth_date, int(time.time()))
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logger.warning("Telegram initData hash mismatch")
        return None

    return parsed


async def require_telegram_auth(request: Request) -> dict:
    init_data = request.headers.get("Telegram-Init-Data", "")
    result = validate_telegram_init_data(init_data, TELEGRAM_BOT_TOKEN)
    if result is None:
        if TELEGRAM_BOT_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid or missing Telegram initData")
        logger.debug("Telegram auth skipped (no bot token configured)")
        return {}
    return result
