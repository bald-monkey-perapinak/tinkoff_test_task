from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from models import CriteriaInput

MAX_TEXT_LEN = 1000
MAX_CRITERIA_FIELD_LEN = 200
MAX_SKILLS = 20
ALLOWED_URL_SCHEMES = {"http", "https"}

PROMPT_INJECTION_PATTERNS = (
    r"ignore (all )?(previous|above) instructions?",
    r"system prompt",
    r"you are now",
    r"new instructions?",
    r"forget (everything|all)",
    r"developer message",
    r"tool calls?",
    r"reveal (the )?(prompt|secret|token|key)",
    r"send (me )?(the )?(prompt|secret|token|key)",
)


def sanitize_text(text: object, max_len: int = MAX_TEXT_LEN) -> str:
    if text is None:
        return ""
    value = str(text)
    value = value.replace("\x00", "")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    for pattern in PROMPT_INJECTION_PATTERNS:
        value = re.sub(pattern, "[removed]", value, flags=re.IGNORECASE)
    value = re.sub(r"<script.*?</script>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[^\w\s,.\-а-яА-ЯёЁa-zA-Z0-9;/:₽€$¥£@#%&*()+=<>{}[\]|\\!?]", "", value)
    return value[:max_len]


def sanitize_url(url: object, max_len: int = 500) -> str:
    value = sanitize_text(url, max_len=max_len)
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return ""
    if parsed.scheme and not parsed.netloc:
        return ""
    return value


def is_valid_date(value: str) -> bool:
    if not value:
        return True
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def sanitize_criteria(criteria: CriteriaInput) -> CriteriaInput:
    date_from = sanitize_text(criteria.date_from, 20) if criteria.date_from else None
    if date_from and not is_valid_date(date_from):
        date_from = None

    min_salary = criteria.min_salary
    if min_salary is not None and (min_salary < 0 or min_salary > 10_000_000):
        min_salary = None

    return CriteriaInput(
        direction=sanitize_text(criteria.direction, MAX_CRITERIA_FIELD_LEN),
        city=sanitize_text(criteria.city, MAX_CRITERIA_FIELD_LEN),
        remote_only=bool(criteria.remote_only),
        min_salary=min_salary,
        experience_level=sanitize_text(criteria.experience_level, MAX_CRITERIA_FIELD_LEN),
        key_skills=[
            sanitize_text(skill, 50)
            for skill in criteria.key_skills[:MAX_SKILLS]
            if sanitize_text(skill, 50)
        ],
        date_from=date_from,
    )


def has_minimum_vacancy_identity(vacancy_id: str, title: str, url: str) -> bool:
    return bool(vacancy_id or title or url)
