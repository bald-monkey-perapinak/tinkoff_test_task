import csv
import json
import io
import re
import logging
from models import Vacancy

logger = logging.getLogger(__name__)

MAX_FIELD_LEN = 1000
MAX_CSV_COLUMNS = 50


def _truncate(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'[^\w\s,.\-а-яА-ЯёЁa-zA-Z0-9;/:₽€$¥£@#%&*()+=<>{}[\]|\\!?]', '', text)
    return clean[:MAX_FIELD_LEN]


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
    try:
        data = json.loads(content)
        if not isinstance(data, list):
            data = [data]
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
                vacancies.append(Vacancy(
                    id=_truncate(str(item.get("id", item.get("url", "")))),
                    title=_truncate(item.get("title", item.get("name", ""))),
                    company=_truncate(item.get("company", item.get("employer", ""))),
                    city=_truncate(item.get("city", item.get("area", ""))),
                    salary=_truncate(item.get("salary", "")),
                    salary_from=item.get("salary_from") if isinstance(item.get("salary_from"), (int, float)) else None,
                    salary_to=item.get("salary_to") if isinstance(item.get("salary_to"), (int, float)) else None,
                    schedule=_truncate(item.get("schedule", item.get("format", ""))),
                    experience=_truncate(item.get("experience", "")),
                    skills=skills,
                    url=_truncate(item.get("url", "")),
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
    try:
        reader = csv.DictReader(io.StringIO(content))
        if reader.fieldnames and len(reader.fieldnames) > MAX_CSV_COLUMNS:
            logger.warning(f"CSV has {len(reader.fieldnames)} columns (max {MAX_CSV_COLUMNS}), rejecting")
            return []
        vacancies = []
        for row in reader:
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

                vacancies.append(Vacancy(
                    id=_truncate(str(row.get("id", row.get("url", "")))),
                    title=_csv_safe(_truncate(row.get("title", row.get("name", "")))),
                    company=_csv_safe(_truncate(row.get("company", row.get("employer", "")))),
                    city=_truncate(row.get("city", row.get("area", ""))),
                    salary=_truncate(row.get("salary", "")),
                    salary_from=salary_from,
                    salary_to=salary_to,
                    schedule=_truncate(row.get("schedule", row.get("format", ""))),
                    experience=_truncate(row.get("experience", "")),
                    skills=skills,
                    url=_truncate(row.get("url", "")),
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
