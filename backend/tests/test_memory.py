import time

import pytest
from models import Vacancy
from services.memory import (
    EpisodicEntry,
    EpisodicMemory,
    MemoryManager,
    WorkingMemory,
)


@pytest.fixture(autouse=True)
async def init_test_db():
    from database import init_db
    await init_db()
    yield


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


class TestWorkingMemory:
    def test_add_vacancy(self):
        wm = WorkingMemory()
        v = _make_vacancy()
        added = wm.add_vacancy(v)
        assert added is True
        assert len(wm.vacancies) == 1

    def test_add_duplicate_vacancy(self):
        wm = WorkingMemory()
        v = _make_vacancy()
        wm.add_vacancy(v)
        added = wm.add_vacancy(v)
        assert added is False
        assert len(wm.vacancies) == 1

    def test_add_vacancies_batch(self):
        wm = WorkingMemory()
        vacancies = [_make_vacancy(id=str(i)) for i in range(5)]
        added = wm.add_vacancies(vacancies)
        assert added == 5
        assert len(wm.vacancies) == 5

    def test_add_vacancies_mixed(self):
        wm = WorkingMemory()
        vacancies = [_make_vacancy(id="1"), _make_vacancy(id="2"), _make_vacancy(id="1")]
        added = wm.add_vacancies(vacancies)
        assert added == 2

    def test_log_tool_call(self):
        wm = WorkingMemory()
        wm.log_tool_call("search", {"query": "python"}, {"found": 10}, 150)
        assert len(wm.tool_history) == 1
        assert wm.tool_history[0]["tool"] == "search"

    def test_log_decision(self):
        wm = WorkingMemory()
        wm.log_decision("expand_search", "мало результатов", "pool_size=3")
        assert len(wm.decisions) == 1

    def test_get_stats(self):
        wm = WorkingMemory()
        wm.add_vacancy(_make_vacancy())
        wm.log_tool_call("test", {}, {}, 0)
        stats = wm.get_stats()
        assert stats["vacancy_count"] == 1
        assert stats["tool_calls"] == 1


class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_save_and_get(self):
        mem = EpisodicMemory()
        entry = EpisodicEntry(
            user_key="test_user",
            action="search",
            args={"query": "python"},
            result_summary="Found 10 vacancies",
            quality_score=7,
            criteria_hash="abc123",
            reflection="Good results",
            created_at=time.time(),
        )
        await mem.save(entry)
        recent = await mem.get_recent("test_user", limit=5)
        assert len(recent) >= 1
        assert recent[0].action == "search"

    @pytest.mark.asyncio
    async def test_get_by_action(self):
        mem = EpisodicMemory()
        await mem.save(EpisodicEntry(user_key="test_user", action="search", created_at=time.time()))
        await mem.save(EpisodicEntry(user_key="test_user", action="score", created_at=time.time()))
        search_entries = await mem.get_by_action("test_user", "search")
        assert len(search_entries) >= 1
        assert all(e.action == "search" for e in search_entries)

    @pytest.mark.asyncio
    async def test_get_patterns(self):
        mem = EpisodicMemory()
        unique_key = f"test_patterns_{int(time.time() * 1000)}"
        await mem.save(EpisodicEntry(user_key=unique_key, action="search", quality_score=8, created_at=time.time()))
        await mem.save(EpisodicEntry(user_key=unique_key, action="search", quality_score=6, created_at=time.time()))
        patterns = await mem.get_patterns(unique_key)
        assert "search" in patterns
        assert patterns["search"]["count"] == 2
        assert patterns["search"]["avg_quality"] == 7.0


class TestMemoryManager:
    def test_build_criteria_hash(self):
        from models import CriteriaInput
        criteria = CriteriaInput(direction="Python", city="Москва")
        h = MemoryManager.build_criteria_hash(criteria)
        assert len(h) == 32

    def test_build_criteria_hash_deterministic(self):
        from models import CriteriaInput
        c1 = CriteriaInput(direction="Python")
        c2 = CriteriaInput(direction="Python")
        assert MemoryManager.build_criteria_hash(c1) == MemoryManager.build_criteria_hash(c2)

    def test_build_criteria_hash_different(self):
        from models import CriteriaInput
        c1 = CriteriaInput(direction="Python")
        c2 = CriteriaInput(direction="Java")
        assert MemoryManager.build_criteria_hash(c1) != MemoryManager.build_criteria_hash(c2)

    def test_reset_working(self):
        mm = MemoryManager()
        mm.working.add_vacancy(_make_vacancy())
        assert len(mm.working.vacancies) == 1
        mm.reset_working()
        assert len(mm.working.vacancies) == 0
