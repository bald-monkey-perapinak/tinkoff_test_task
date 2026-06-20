import json
import httpx
import asyncio
import logging
import random
from typing import Optional
from config import HH_API_BASE, HH_USER_AGENT, HH_PROXY, HH_PROXY_LIST, DATA_DIR
from models import Vacancy, SearchParams

logger = logging.getLogger(__name__)

_areas_cache: dict = {}
_roles_cache: dict = {}
_cache_loaded = False
_cache_lock = asyncio.Lock()
_proxy_list: list[str] = []
_proxy_index = 0

MAX_RETRIES = 3
BASE_DELAY = 1.0

HEADERS = {
    "User-Agent": HH_USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _load_proxy_list():
    global _proxy_list
    if _proxy_list:
        return
    if HH_PROXY_LIST:
        try:
            path = DATA_DIR.parent / HH_PROXY_LIST
            if path.exists():
                _proxy_list = [
                    line.strip()
                    for line in path.read_text().splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                logger.info(f"Loaded {len(_proxy_list)} proxies from {HH_PROXY_LIST}")
        except Exception as e:
            logger.warning(f"Failed to load proxy list: {e}")


def _get_proxy() -> Optional[str]:
    global _proxy_index
    if HH_PROXY:
        return HH_PROXY
    if _proxy_list:
        proxy = _proxy_list[_proxy_index % len(_proxy_list)]
        _proxy_index += 1
        return proxy
    return None


def _get_mock_vacancies(query: str) -> list[Vacancy]:
    try:
        sample_path = DATA_DIR / "sample_vacancies.json"
        if not sample_path.exists():
            return []
        data = json.loads(sample_path.read_text(encoding="utf-8"))
        vacancies = []
        q_lower = query.lower() if query else ""
        for item in data:
            if q_lower and q_lower not in item.get("title", "").lower() and q_lower not in item.get("company", "").lower():
                continue
            vacancies.append(Vacancy(
                id=str(item.get("id", "")),
                title=item.get("title", ""),
                company=item.get("company", ""),
                city=item.get("city", ""),
                salary=item.get("salary", ""),
                salary_from=item.get("salary_from"),
                salary_to=item.get("salary_to"),
                schedule=item.get("schedule", ""),
                experience=item.get("experience", ""),
                skills=item.get("skills", []),
                url=item.get("url", ""),
                description=item.get("description", ""),
                is_mock=True,
            ))
        return vacancies[:20]
    except Exception as e:
        logger.error(f"Failed to load mock vacancies: {e}")
        return []


async def _load_dictionaries():
    global _cache_loaded
    if _cache_loaded:
        return
    async with _cache_lock:
        if _cache_loaded:
            return
        _load_proxy_list()
        proxy = _get_proxy()
        try:
            async with httpx.AsyncClient(proxy=proxy) as client:
                for attempt in range(MAX_RETRIES):
                    try:
                        resp = await client.get(f"{HH_API_BASE}/areas", headers=HEADERS, timeout=10)
                        if resp.status_code == 200:
                            for area in resp.json():
                                _areas_cache[str(area["id"])] = area["name"]
                                for sub in area.get("areas", []):
                                    _areas_cache[str(sub["id"])] = sub["name"]

                        resp = await client.get(f"{HH_API_BASE}/professional_roles", headers=HEADERS, timeout=10)
                        if resp.status_code == 200:
                            for role in resp.json():
                                _roles_cache[str(role["id"])] = role["name"]
                        _cache_loaded = True
                        return
                    except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                        delay = BASE_DELAY * (2 ** attempt)
                        logger.warning(f"hh.ru dictionaries load attempt {attempt + 1} failed: {e}, retrying in {delay}s")
                        await asyncio.sleep(delay)
                    except Exception as e:
                        logger.warning(f"Failed to load hh.ru dictionaries: {e}")
                        return
        except Exception as e:
            logger.warning(f"Failed to create hh.ru client: {e}")
        logger.error("Failed to load hh.ru dictionaries after all retries")


def _parse_salary(salary: Optional[dict]) -> tuple[str, Optional[int], Optional[int]]:
    if not salary:
        return "", None, None
    currency = salary.get("currency", "RUR")
    fr = salary.get("from")
    to = salary.get("to")
    gross = salary.get("gross", False)

    parts = []
    if fr:
        parts.append(f"от {fr:,}".replace(",", " "))
    if to:
        parts.append(f"до {to:,}".replace(",", " "))
    label = " — ".join(parts) if parts else ""
    if gross and label:
        label += " (до вычета налогов)"
    if currency != "RUR":
        label += f" ({currency})"

    return label, fr, to


def _hh_to_vacancy(v: dict) -> Vacancy:
    salary_label, salary_from, salary_to = _parse_salary(v.get("salary"))
    area_name = v.get("area", {}).get("name", "")
    schedule_name = v.get("schedule", {}).get("name", "")
    experience_name = v.get("experience", {}).get("name", "")
    employer_name = v.get("employer", {}).get("name", "")
    skills = [s["name"] for s in v.get("key_skills", [])]

    snippet = v.get("snippet", {})
    description_parts = []
    if snippet:
        for field in ["requirement", "responsibility"]:
            text = snippet.get(field, "")
            if text:
                clean = text.replace("<highlight>", "").replace("</highlight>", "")
                description_parts.append(clean[:500])
    description = " ".join(description_parts)[:1000]

    return Vacancy(
        id=str(v["id"]),
        title=v.get("name", ""),
        company=employer_name,
        city=area_name,
        salary=salary_label,
        salary_from=salary_from,
        salary_to=salary_to,
        schedule=schedule_name,
        experience=experience_name,
        skills=skills[:20],
        url=v.get("alternate_url", ""),
        description=description,
        published_at=v.get("published_at", ""),
    )


async def search_vacancies(params: SearchParams) -> tuple[list[Vacancy], int]:
    await _load_dictionaries()
    _load_proxy_list()

    query_params = {
        "text": params.query,
        "page": params.page,
        "per_page": min(params.per_page, 50),
    }
    if params.area:
        query_params["area"] = params.area
    if params.salary_from:
        query_params["salary"] = params.salary_from
        query_params["only_with_salary"] = "true"
    if params.experience:
        query_params["experience"] = params.experience.value
    if params.schedule:
        query_params["schedule"] = params.schedule.value
    if params.professional_role:
        query_params["professional_role"] = params.professional_role

    last_error = None
    for attempt in range(MAX_RETRIES):
        proxy = _get_proxy()
        try:
            async with httpx.AsyncClient(proxy=proxy) as client:
                resp = await client.get(
                    f"{HH_API_BASE}/vacancies",
                    params=query_params,
                    headers=HEADERS,
                    timeout=15,
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", BASE_DELAY * (2 ** attempt)))
                    logger.warning(f"hh.ru rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                total = data.get("found", 0)
                vacancies = [_hh_to_vacancy(item) for item in items[:50]]
                return vacancies, total
        except httpx.HTTPStatusError as e:
            last_error = e
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(f"hh.ru API error {e.response.status_code}, attempt {attempt + 1}, retrying in {delay}s")
            await asyncio.sleep(delay)
        except httpx.TimeoutException as e:
            last_error = e
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(f"hh.ru timeout, attempt {attempt + 1}, retrying in {delay}s")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"hh.ru request failed: {e}")
            break

    logger.warning(f"hh.ru search failed after {MAX_RETRIES} retries: {last_error}")
    logger.info(f"Falling back to mock data for query='{params.query}'")
    mock = _get_mock_vacancies(params.query)
    return mock, len(mock)


async def get_area_suggestions(query: str) -> list[dict]:
    await _load_dictionaries()
    results = []
    q_lower = query.lower()
    for area_id, area_name in _areas_cache.items():
        if q_lower in area_name.lower():
            results.append({"id": area_id, "name": area_name})
    return results[:10]


async def get_role_suggestions(query: str) -> list[dict]:
    await _load_dictionaries()
    results = []
    q_lower = query.lower()
    for role_id, role_name in _roles_cache.items():
        if q_lower in role_name.lower():
            results.append({"id": role_id, "name": role_name})
    return results[:10]
