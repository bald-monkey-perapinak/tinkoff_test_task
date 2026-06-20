import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from circuit_breaker import groq_breaker
from config import ANALYSIS_MAX_VACANCIES, AGENT_TIMEOUT_SECONDS, GROQ_API_KEY, PROMPT_INPUT_MAX_LEN
from database import get_analysis_cache, set_analysis_cache
from models import AnalysisResult, CriteriaInput, Vacancy

logger = logging.getLogger(__name__)

@dataclass
class AnalysisMetadata:
    analysis_type: str = "llm"
    iterations_used: int = 1
    total_vacancies_pool: int = 0
    overall_summary: str = ""


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _sanitize(text: str) -> str:
    return _sanitize_vacancy_field(text, PROMPT_INPUT_MAX_LEN)


def _sanitize_vacancy_field(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'(?i)(ignore (all )?(previous|above) instructions?|system prompt|you are now|new instructions?|forget (everything|all))', '[removed]', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n+', ' ', text)
    clean = re.sub(r'[^\w\s,.\-а-яА-ЯёЁa-zA-Z0-9;/:₽€$¥£()!?@#%&*+=]', '', text)
    return clean[:max_len]


def _rule_based_analyze(vacancies: list[Vacancy], criteria: CriteriaInput) -> list[AnalysisResult]:
    from services.scorer import ScoreCalculator

    date_threshold = _parse_date(criteria.date_from) if criteria.date_from else None
    filtered = []
    for v in vacancies[:ANALYSIS_MAX_VACANCIES]:
        if date_threshold and v.published_at:
            pub_date = _parse_date(v.published_at)
            if pub_date and pub_date < date_threshold:
                continue
        filtered.append(v)

    calculator = ScoreCalculator(criteria)
    scored = calculator.score_vacancies(filtered)
    top = scored[:5]

    results = []
    for sr in top:
        vacancy = next((v for v in vacancies if v.id == sr.vacancy_id), None)
        summary = f"{vacancy.title} в {vacancy.company}" if vacancy else sr.vacancy_id
        results.append(AnalysisResult(
            vacancy_id=sr.vacancy_id,
            rank=1,
            fit_score=max(1, min(10, int(sr.score))),
            why_fits="; ".join(sr.reasons),
            concerns="; ".join(sr.concerns) if sr.concerns else "серьёзных замечаний нет",
            summary=summary,
        ))

    results.sort(key=lambda r: r.fit_score, reverse=True)
    for i, r in enumerate(results):
        r.rank = i + 1

    if not results:
        pass
    elif all(r.fit_score < 5 for r in results):
        for r in results:
            r.recommendation = "Ни одна вакансия не набрала более 4 баллов. Рекомендуется расширить поиск или снизить требования."
    else:
        for r in results:
            if r.fit_score < 5:
                r.recommendation = "Эта вакансия слабо подходит. Обратите внимание на вакансии с более высоким score."
            elif r.fit_score >= 7:
                r.recommendation = "Хороший вариант — стоит откликнуться."

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
        "df": criteria.date_from or "",
    }
    return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:32]


def _parse_finalize_results(args: dict, valid_vacancies: list[Vacancy]) -> list[AnalysisResult]:
    valid_ids = {v.id for v in valid_vacancies}
    results = []
    for item in args.get("results", []):
        try:
            vid = str(item.get("vacancy_id", ""))[:50]
            if vid not in valid_ids:
                continue
            why = str(item.get("why_fits", ""))[:500]
            why = re.sub(r'\[.*?\]\((javascript:|data:).*?\)', '[blocked]', why, flags=re.IGNORECASE)
            why = re.sub(r'<script.*?</script>', '', why, flags=re.IGNORECASE | re.DOTALL)
            concerns = str(item.get("concerns", ""))[:500]
            concerns = re.sub(r'\[.*?\]\((javascript:|data:).*?\)', '[blocked]', concerns, flags=re.IGNORECASE)
            concerns = re.sub(r'<script.*?</script>', '', concerns, flags=re.IGNORECASE | re.DOTALL)
            summary = str(item.get("summary", ""))[:200]
            summary = re.sub(r'\[.*?\]\((javascript:|data:).*?\)', '[blocked]', summary, flags=re.IGNORECASE)
            summary = re.sub(r'<script.*?</script>', '', summary, flags=re.IGNORECASE | re.DOTALL)
            recommendation = str(item.get("recommendation", ""))[:500]
            recommendation = re.sub(r'\[.*?\]\((javascript:|data:).*?\)', '[blocked]', recommendation, flags=re.IGNORECASE)
            recommendation = re.sub(r'<script.*?</script>', '', recommendation, flags=re.IGNORECASE | re.DOTALL)
            results.append(AnalysisResult(
                vacancy_id=vid,
                rank=int(item.get("rank", 1)),
                fit_score=max(1, min(10, int(item.get("fit_score", 5)))),
                why_fits=why,
                concerns=concerns,
                summary=summary,
                recommendation=recommendation,
            ))
        except Exception as e:
            logger.warning(f"Skipping invalid LLM result: {e}")
    valid_ranks = {r.rank for r in results}
    all_valid = (
        len(results) <= 5
        and valid_ranks == set(range(1, len(results) + 1))
    )
    if not all_valid:
        results.sort(key=lambda r: r.fit_score, reverse=True)
        for i, r in enumerate(results):
            r.rank = i + 1
    else:
        results.sort(key=lambda r: r.rank)
    return results[:5]


async def analyze_with_llm(vacancies: list[Vacancy], criteria: CriteriaInput, user_key: str = "anonymous") -> tuple[list[AnalysisResult], AnalysisMetadata]:
    if not GROQ_API_KEY:
        logger.info("No GROQ_API_KEY, using rule-based analysis")
        results = _rule_based_analyze(vacancies, criteria)
        return results, AnalysisMetadata(analysis_type="rule_based", total_vacancies_pool=len(vacancies))

    cache_key = _build_cache_key(vacancies, criteria)
    cached = await get_analysis_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for analysis: {cache_key[:8]}...")
        return [AnalysisResult(**r) for r in cached["results"]], AnalysisMetadata(analysis_type="llm_cached", total_vacancies_pool=len(vacancies))

    if not await groq_breaker.call_allowed():
        logger.warning("Groq circuit breaker open, using rule-based analysis")
        results = _rule_based_analyze(vacancies, criteria)
        return results, AnalysisMetadata(analysis_type="rule_based_circuit_breaker", total_vacancies_pool=len(vacancies))

    try:
        from services.agent import VacancyAgent
        agent = VacancyAgent()
        results, metadata = await asyncio.wait_for(
            agent.run(vacancies, criteria, user_key=user_key),
            timeout=float(AGENT_TIMEOUT_SECONDS),
        )

        if not results:
            logger.warning("[Agent] Agent returned no results, falling back to rule-based")
            results = _rule_based_analyze(vacancies, criteria)
            return results, AnalysisMetadata(analysis_type="rule_based_agent_empty", total_vacancies_pool=len(vacancies))

        await set_analysis_cache(cache_key, json.dumps([r.model_dump() for r in results], ensure_ascii=False))

        return results, AnalysisMetadata(
            analysis_type=metadata.get("analysis_type", "llm"),
            iterations_used=metadata.get("iterations_used", 1),
            total_vacancies_pool=metadata.get("total_vacancies_pool", len(vacancies)),
            overall_summary=metadata.get("overall_summary", ""),
        )

    except asyncio.TimeoutError:
        logger.error(f"[Agent] Agent timed out after {AGENT_TIMEOUT_SECONDS}s")
        results = _rule_based_analyze(vacancies, criteria)
        return results, AnalysisMetadata(analysis_type="rule_based_timeout", total_vacancies_pool=len(vacancies))
    except Exception as e:
        logger.error(f"[Agent] Agent error: {e}")
        results = _rule_based_analyze(vacancies, criteria)
        return results, AnalysisMetadata(analysis_type="rule_based_error", total_vacancies_pool=len(vacancies))
