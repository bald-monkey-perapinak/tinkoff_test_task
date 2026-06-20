import hashlib
import hmac
import os
import sys
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth import validate_telegram_init_data

BOT_TOKEN = "test-bot-token-12345"


def _make_init_data(user_id=12345, extra_params=None):
    auth_date = str(int(time.time()))
    params = {"auth_date": auth_date, "user": str(user_id)}
    if extra_params:
        params.update(extra_params)

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_val
    return urlencode(params)


class TestValidateTelegramInitData:
    def test_valid_data(self):
        init_data = _make_init_data(user_id=12345)
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is not None
        assert result["user"] == "12345"

    def test_wrong_hash(self):
        init_data = _make_init_data(user_id=12345)
        init_data = init_data.replace("hash=", "hash=0000")
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is None

    def test_wrong_bot_token(self):
        init_data = _make_init_data(user_id=12345)
        result = validate_telegram_init_data(init_data, "wrong-token")
        assert result is None

    def test_expired_data(self):
        params = {"auth_date": "1000000000", "user": "12345"}
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        hash_val = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        params["hash"] = hash_val
        init_data = urlencode(params)
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is None

    def test_empty_init_data(self):
        assert validate_telegram_init_data("", BOT_TOKEN) is None

    def test_none_init_data(self):
        assert validate_telegram_init_data(None, BOT_TOKEN) is None

    def test_empty_bot_token(self):
        init_data = _make_init_data(user_id=12345)
        assert validate_telegram_init_data(init_data, "") is None

    def test_malformed_data(self):
        assert validate_telegram_init_data("not-valid-url-data", BOT_TOKEN) is None

    def test_no_hash_field(self):
        auth_date = str(int(time.time()))
        init_data = urlencode({"auth_date": auth_date, "user": "12345"})
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is None
