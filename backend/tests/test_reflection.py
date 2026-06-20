import pytest
from models import CriteriaInput, Vacancy
from services.reflection import ReflectionEngine


def _make_vacancy(**kwargs) -> Vacancy:
    defaults = {
        "id": "123",
        "title": "Python Developer",
        "company": "TestCorp",
        "city": "Москва",
        "salary": "от 80000",
        "salary_from": 80000,
        "schedule": "удалённая",
        "experience": "без опыта",
        "skills": ["Python"],
        "url": "https://hh.ru/vacancy/123",
        "description": "Разработка",
        "published_at": "2026-06-15",
    }
    defaults.update(kwargs)
    return Vacancy(**defaults)


def _make_scored(score: int) -> object:
    class MockScored:
        def __init__(self, s):
            self.score = s
    return MockScored(score)


class TestReflectionEngine:
    @pytest.mark.asyncio
    async def test_reflect_continue_when_few_vacancies(self):
        engine = ReflectionEngine()
        criteria = CriteriaInput(direction="Python")
        result = await engine.reflect(
            iteration=1, pool_size=3, vacancies=[],
            scored_results=[], criteria=criteria,
        )
        assert result.should_continue is True
        assert result.next_action == "expand_search"

    @pytest.mark.asyncio
    async def test_reflect_finalize_when_many_high_score(self):
        engine = ReflectionEngine()
        criteria = CriteriaInput()
        scored = [_make_scored(8), _make_scored(7), _make_scored(9)]
        result = await engine.reflect(
            iteration=2, pool_size=10, vacancies=[],
            scored_results=scored, criteria=criteria,
        )
        assert result.should_continue is False
        assert result.next_action == "finalize"

    @pytest.mark.asyncio
    async def test_reflect_finalize_on_max_iterations(self):
        engine = ReflectionEngine()
        criteria = CriteriaInput()
        scored = [_make_scored(5)]
        result = await engine.reflect(
            iteration=5, pool_size=10, vacancies=[],
            scored_results=scored, criteria=criteria,
        )
        assert result.should_continue is False
        assert result.next_action == "finalize"

    @pytest.mark.asyncio
    async def test_reflect_low_score_adjusts_search(self):
        engine = ReflectionEngine()
        criteria = CriteriaInput()
        scored = [_make_scored(3), _make_scored(2), _make_scored(4)]
        result = await engine.reflect(
            iteration=1, pool_size=10, vacancies=[],
            scored_results=scored, criteria=criteria,
        )
        assert result.should_continue is True
        assert result.next_action == "adjust_search"

    @pytest.mark.asyncio
    async def test_reflect_consecutive_failures_finalize(self):
        engine = ReflectionEngine()
        criteria = CriteriaInput()
        result = await engine.reflect(
            iteration=1, pool_size=5, vacancies=[],
            scored_results=[], criteria=criteria,
            consecutive_failures=3,
        )
        assert result.should_continue is False

    @pytest.mark.asyncio
    async def test_reflect_with_memory_patterns(self):
        engine = ReflectionEngine()
        criteria = CriteriaInput()
        patterns = {"search_vacancies": {"count": 5, "avg_quality": 7.5, "best_quality": 9}}
        result = await engine.reflect(
            iteration=2, pool_size=10, vacancies=[],
            scored_results=[_make_scored(7)], criteria=criteria,
            memory_patterns=patterns,
        )
        assert result.should_continue is True
        assert any("паттерн" in r.lower() or "search" in r.lower() for r in result.reasoning)

    def test_get_history(self):
        engine = ReflectionEngine()
        assert len(engine.get_history()) == 0

    def test_get_strategy_summary_empty(self):
        engine = ReflectionEngine()
        summary = engine.get_strategy_summary()
        assert "Нет данных" in summary
