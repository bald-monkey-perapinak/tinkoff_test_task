import csv
import io
import json
import logging

from models import Vacancy
from services.security import has_minimum_vacancy_identity, sanitize_text, sanitize_url

logger = logging.getLogger(__name__)

MAX_FIELD_LEN = 1000
MAX_CSV_COLUMNS = 50
MAX_CSV_ROWS = 1000
MAX_JSON_ITEMS = 1000
MAX_JSON_DEPTH = 10


def _truncate(text: str) -> str:
    return sanitize_text(text, MAX_FIELD_LEN)


def _safe_salary(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        amount = int(value)
        if 0 <= amount <= 10_000_000:
            return amount
    return None


def _json_depth(value, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        return depth
    if isinstance(value, dict):
        return max([depth, *(_json_depth(v, depth + 1) for v in value.values())])
    if isinstance(value, list):
        return max([depth, *(_json_depth(v, depth + 1) for v in value)])
    return depth


def _csv_safe(value: str) -> str:
    if not value:
        return value
    dangerous_prefixes = ('=', '+', '-', '@', '\t', '\r')
    for i, ch in enumerate(value):
        if ch in dangerous_prefixes:
            return "'" + value
        if not ch.isspace():
            break
    return value


def parse_vacancies_json(content: str) -> list[Vacancy]:
    content = content.replace("\x00", "")
    if content.startswith("\ufeff"):
        content = content[1:]
    try:
        data = json.loads(content)
        if not isinstance(data, list):
            data = [data]
        if len(data) > MAX_JSON_ITEMS:
            logger.warning(f"JSON has {len(data)} items (max {MAX_JSON_ITEMS}), truncating")
            data = data[:MAX_JSON_ITEMS]
        if _json_depth(data) > MAX_JSON_DEPTH:
            logger.warning(f"JSON nesting exceeds max depth {MAX_JSON_DEPTH}, rejecting")
            return []
        vacancies = []
        for item in data:
            try:
                if not isinstance(item, dict):
                    continue
                skills_raw = item.get("skills", [])
                if isinstance(skills_raw, list):
                    skills = [_truncate(s) for s in skills_raw[:20] if isinstance(s, str)]
                else:
                    skills = []
                vacancy_id = _truncate(str(item.get("id", item.get("url", ""))))
                title = _truncate(item.get("title", item.get("name", "")))
                url = sanitize_url(item.get("url", ""))
                if not has_minimum_vacancy_identity(vacancy_id, title, url):
                    logger.warning("Skipping vacancy without id/title/url")
                    continue
                vacancies.append(Vacancy(
                    id=vacancy_id,
                    title=title,
                    company=_truncate(item.get("company", item.get("employer", ""))),
                    city=_truncate(item.get("city", item.get("area", ""))),
                    salary=_truncate(item.get("salary", "")),
                    salary_from=_safe_salary(item.get("salary_from")),
                    salary_to=_safe_salary(item.get("salary_to")),
                    schedule=_truncate(item.get("schedule", item.get("format", ""))),
                    experience=_truncate(item.get("experience", "")),
                    skills=skills,
                    url=url,
                    description=_truncate(item.get("description", "")),
                    published_at=_truncate(item.get("published_at", "")),
                    is_mock=True,
                ))
            except Exception as e:
                logger.warning(f"Skipping invalid vacancy entry: {e}")
        return _deduplicate(vacancies)
    except (json.JSONDecodeError, RecursionError) as e:
        logger.error(f"Invalid or malicious JSON structure: {e}")
        return []


def parse_vacancies_csv(content: str) -> list[Vacancy]:
    content = content.replace("\x00", "")
    if content.startswith("\ufeff"):
        content = content[1:]
    try:
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            logger.warning("CSV has no headers, rejecting")
            return []
        if len(reader.fieldnames) > MAX_CSV_COLUMNS:
            logger.warning(f"CSV has {len(reader.fieldnames)} columns (max {MAX_CSV_COLUMNS}), rejecting")
            return []
        vacancies = []
        for row_number, row in enumerate(reader, start=1):
            if row_number > MAX_CSV_ROWS:
                logger.warning(f"CSV has more than {MAX_CSV_ROWS} rows, truncating")
                break
            try:
                skills_raw = row.get("skills", row.get("key_skills", ""))
                if isinstance(skills_raw, str):
                    skills = [_truncate(s.strip()) for s in skills_raw.split(",") if s.strip()][:20]
                else:
                    skills = []

                salary_from = row.get("salary_from")
                salary_to = row.get("salary_to")
                try:
                    salary_from = int(salary_from) if salary_from else None
                except (ValueError, TypeError):
                    salary_from = None
                try:
                    salary_to = int(salary_to) if salary_to else None
                except (ValueError, TypeError):
                    salary_to = None

                vacancy_id = _truncate(str(row.get("id", row.get("url", ""))))
                title = _csv_safe(_truncate(row.get("title", row.get("name", ""))))
                url = sanitize_url(row.get("url", ""))
                if not has_minimum_vacancy_identity(vacancy_id, title, url):
                    logger.warning("Skipping CSV row without id/title/url")
                    continue
                vacancies.append(Vacancy(
                    id=vacancy_id,
                    title=title,
                    company=_csv_safe(_truncate(row.get("company", row.get("employer", "")))),
                    city=_truncate(row.get("city", row.get("area", ""))),
                    salary=_truncate(row.get("salary", "")),
                    salary_from=salary_from,
                    salary_to=salary_to,
                    schedule=_truncate(row.get("schedule", row.get("format", ""))),
                    experience=_truncate(row.get("experience", "")),
                    skills=skills,
                    url=url,
                    description=_truncate(row.get("description", "")),
                    published_at=_truncate(row.get("published_at", "")),
                    is_mock=True,
                ))
            except Exception as e:
                logger.warning(f"Skipping invalid CSV row: {e}")
        return _deduplicate(vacancies)
    except Exception as e:
        logger.error(f"CSV parse error: {e}")
        return []


def parse_uploaded_file(filename: str, content: str) -> list[Vacancy]:
    lower_name = filename.lower()
    if lower_name.endswith(".json"):
        return parse_vacancies_json(content)
    if lower_name.endswith(".csv"):
        return parse_vacancies_csv(content)

    content_stripped = content.strip()
    if content_stripped.startswith("{") or content_stripped.startswith("["):
        return parse_vacancies_json(content)
    elif "," in content_stripped or "\n" in content_stripped:
        return parse_vacancies_csv(content)
    else:
        logger.warning(f"Unrecognized file content for: {filename}")
        return []


def _deduplicate(vacancies: list[Vacancy]) -> list[Vacancy]:
    seen = set()
    unique = []
    for v in vacancies:
        key = v.id or (v.title + v.company)
        if key and key not in seen:
            seen.add(key)
            unique.append(v)
    return unique[:100]
