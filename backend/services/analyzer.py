import json
import re
import hashlib
import logging
import asyncio
from config import GROQ_API_KEY, PROMPT_INPUT_MAX_LEN, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
from models import Vacancy, CriteriaInput, AnalysisResult
from database import get_analysis_cache, set_analysis_cache

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0

RULE_BASED_RESULTS = [
    "Компания крупная, стажировка оплачиваемая — хороший старт.",
    "Удалённый формат подходит для гибкого графика.",
    "Стек совпадает с указанными навыками.",
    "Требования превышают уровень junior — может быть сложно.",
    "Зарплата выше рынка для стажировки — стоит попробовать.",
]


def _sanitize(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'[^\w\s,.\-а-яА-ЯёЁa-zA-Z0-9;/:₽€$¥£]', '', text)
    return clean[:PROMPT_INPUT_MAX_LEN]


def _rule_based_analyze(vacancies: list[Vacancy], criteria: CriteriaInput) -> list[AnalysisResult]:
    results = []
    for i, v in enumerate(vacancies[:5]):
        score = 5
        concerns = []
        why = []

        if criteria.direction and criteria.direction.lower() in v.title.lower():
            score += 2
            why.append("направление совпадает")
        if criteria.remote_only and "удалён" in v.schedule.lower():
            score += 1
            why.append("удалённый формат")
        if criteria.min_salary and v.salary_from and v.salary_from >= criteria.min_salary:
            score += 1
            why.append("зарплата устраивает")
        if criteria.key_skills:
            matched = [s for s in criteria.key_skills if s.lower() in " ".join(v.skills).lower()]
            if matched:
                score += 1
                why.append(f"навыки: {', '.join(matched)}")

        if not why:
            why.append("вакансия может подойти по общим критериям")
        if not v.skills:
            concerns.append("навыки не указаны")
        if not v.salary:
            concerns.append("зарплата не указана")

        results.append(AnalysisResult(
            vacancy_id=v.id,
            rank=i + 1,
            fit_score=min(score, 10),
            why_fits="; ".join(why) if why else RULE_BASED_RESULTS[i % len(RULE_BASED_RESULTS)],
            concerns="; ".join(concerns) if concerns else "серьёзных замечаний нет",
            summary=f"{v.title} в {v.company}",
        ))
    return results


def _build_cache_key(vacancies: list[Vacancy], criteria: CriteriaInput) -> str:
    key_data = {
        "ids": sorted([v.id for v in vacancies[:20]]),
        "d": criteria.direction,
        "c": criteria.city,
        "r": criteria.remote_only,
        "s": criteria.min_salary,
        "e": criteria.experience_level,
        "k": sorted(criteria.key_skills),
    }
    return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:32]


async def analyze_with_llm(vacancies: list[Vacancy], criteria: CriteriaInput) -> list[AnalysisResult]:
    if not GROQ_API_KEY:
        logger.info("No GROQ_API_KEY, using rule-based analysis")
        return _rule_based_analyze(vacancies, criteria)

    cache_key = _build_cache_key(vacancies, criteria)
    cached = await get_analysis_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for analysis: {cache_key[:8]}...")
        return [AnalysisResult(**r) for r in cached["results"]]

    try:
        import groq
        client = groq.Groq(api_key=GROQ_API_KEY)

        vacancy_summaries = []
        for v in vacancies[:10]:
            vacancy_summaries.append({
                "id": v.id[:50],
                "title": v.title[:200],
                "company": v.company[:200],
                "city": v.city[:100],
                "salary": v.salary[:100],
                "schedule": v.schedule[:100],
                "experience": v.experience[:100],
                "skills": [s[:50] for s in v.skills[:10]],
                "description": v.description[:500],
            })

        safe_direction = _sanitize(criteria.direction)
        safe_city = _sanitize(criteria.city)
        safe_level = _sanitize(criteria.experience_level)
        safe_skills = ", ".join([_sanitize(s) for s in criteria.key_skills[:5]])

        prompt = f"""Ты — карьерный консультант. Проанализируй вакансии и отранжируй их по соответствию критериям.

Критерии пользователя:
- Направление: {safe_direction or 'любое'}
- Город: {safe_city or 'любой'}
- Только удалёнка: {'да' if criteria.remote_only else 'нет'}
- Минимальная зарплата: {criteria.min_salary or 'не указана'}
- Уровень опыта: {safe_level or 'любой'}
- Ключевые навыки: {safe_skills or 'не указаны'}

Вакансии:
{json.dumps(vacancy_summaries, ensure_ascii=False, indent=2)}

Верни JSON-массив (без markdown) с объектами:
[
  {{
    "vacancy_id": "id вакансии",
    "rank": 1,
    "fit_score": число от 1 до 10,
    "why_fits": "почему подходит (1-2 предложения)",
    "concerns": "что смущает (1-2 предложения)",
    "summary": "краткое резюме вакансии"
  }}
]

Правила:
- Отранжируй по fit_score от лучшего к худшему
- rank должен начинаться с 1 и идти по порядку
- Будь честен: если вакансия плохо подходит — скажи
- Отвечай ТОЛЬКО валидным JSON, без текста до/после"""

        response = None
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                )
                break
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Groq API attempt {attempt + 1} failed: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Groq API failed after {MAX_RETRIES} retries: {e}")

        if response is None:
            logger.error(f"Groq API exhausted all retries: {last_error}")
            return _rule_based_analyze(vacancies, criteria)

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        results_data = json.loads(content)
        if not isinstance(results_data, list):
            logger.warning("LLM returned non-array response")
            return _rule_based_analyze(vacancies, criteria)

        results = []
        for item in results_data[:10]:
            try:
                results.append(AnalysisResult(
                    vacancy_id=str(item.get("vacancy_id", ""))[:50],
                    rank=int(item.get("rank", 0)),
                    fit_score=max(1, min(10, int(item.get("fit_score", 5)))),
                    why_fits=str(item.get("why_fits", ""))[:500],
                    concerns=str(item.get("concerns", ""))[:500],
                    summary=str(item.get("summary", ""))[:200],
                ))
            except Exception as e:
                logger.warning(f"Skipping invalid LLM result: {e}")

        await set_analysis_cache(cache_key, json.dumps([r.model_dump() for r in results], ensure_ascii=False), "")
        return results

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return _rule_based_analyze(vacancies, criteria)
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return _rule_based_analyze(vacancies, criteria)
