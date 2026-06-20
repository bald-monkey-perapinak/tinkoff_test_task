import pytest
from models import CriteriaInput, Vacancy
from services.tools import (
    ExpandSearchTool,
    FilterResultsTool,
    GenerateReportTool,
    ReflectTool,
    ScoreVacanciesTool,
    ToolRegistry,
)


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
        "skills": ["Python", "FastAPI"],
        "url": "https://hh.ru/vacancy/123",
        "description": "Разработка",
        "published_at": "2026-06-15",
    }
    defaults.update(kwargs)
    return Vacancy(**defaults)


class TestToolRegistry:
    def test_register_default_tools(self):
        registry = ToolRegistry()
        names = registry.get_tool_names()
        assert "search_vacancies" in names
        assert "filter_results" in names
        assert "score_vacancies" in names
        assert "generate_report" in names
        assert "expand_search" in names
        assert "reflect" in names

    def test_get_tool(self):
        registry = ToolRegistry()
        tool = registry.get("search_vacancies")
        assert tool is not None
        assert tool.name == "search_vacancies"

    def test_get_unknown_tool(self):
        registry = ToolRegistry()
        tool = registry.get("nonexistent_tool")
        assert tool is None

    def test_get_all_schemas(self):
        registry = ToolRegistry()
        schemas = registry.get_all_schemas()
        assert len(schemas) == 6
        assert all("function" in s for s in schemas)

    def test_get_descriptions(self):
        registry = ToolRegistry()
        descriptions = registry.get_descriptions()
        assert "search_vacancies" in descriptions
        assert len(descriptions["search_vacancies"]) > 0

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = await registry.execute("nonexistent_tool")
        assert result.success is False
        assert "Unknown tool" in result.error


class TestFilterResultsTool:
    @pytest.mark.asyncio
    async def test_filter_remote(self):
        tool = FilterResultsTool()
        vacancies = [
            _make_vacancy(id="1", schedule="удалённая"),
            _make_vacancy(id="2", schedule="полный день"),
        ]
        result = await tool.execute(vacancies=vacancies, require_remote=True)
        assert result.success is True
        assert result.data["filtered_count"] == 1

    @pytest.mark.asyncio
    async def test_filter_skills(self):
        tool = FilterResultsTool()
        vacancies = [
            _make_vacancy(id="1", skills=["Python", "FastAPI"]),
            _make_vacancy(id="2", skills=["Java", "Spring"]),
        ]
        result = await tool.execute(vacancies=vacancies, require_skills=["Python"])
        assert result.success is True
        assert result.data["filtered_count"] == 1


class TestScoreVacanciesTool:
    @pytest.mark.asyncio
    async def test_score_vacancies(self):
        tool = ScoreVacanciesTool()
        vacancies = [
            _make_vacancy(id="1", title="Python Developer"),
            _make_vacancy(id="2", title="Java Developer"),
        ]
        criteria = CriteriaInput(direction="Python")
        result = await tool.execute(vacancies=vacancies, criteria=criteria)
        assert result.success is True
        assert result.data["count"] == 2
        results = result.data["results"]
        assert results[0].score >= results[1].score


class TestGenerateReportTool:
    @pytest.mark.asyncio
    async def test_generate_report(self):
        tool = GenerateReportTool()
        vacancies = [_make_vacancy()]
        from models import AnalysisResult
        results = [AnalysisResult(
            vacancy_id="123", rank=1, fit_score=8,
            why_fits="test", concerns="none", summary="Test",
        )]
        result = await tool.execute(
            vacancies=vacancies, results=results,
            criteria_text="Python developer",
            analysis_type="test",
            overall_summary="Test summary",
        )
        assert result.success is True
        assert "Отчёт по анализу" in result.data["report"]


class TestExpandSearchTool:
    @pytest.mark.asyncio
    async def test_expand_python_query(self):
        tool = ExpandSearchTool()
        result = await tool.execute(original_query="python developer", direction="Python")
        assert result.success is True
        assert len(result.data["queries"]) > 1
        assert "python developer" in result.data["queries"]

    @pytest.mark.asyncio
    async def test_expand_unknown_query(self):
        tool = ExpandSearchTool()
        result = await tool.execute(original_query="unknown query")
        assert result.success is True
        assert len(result.data["queries"]) >= 2


class TestReflectTool:
    @pytest.mark.asyncio
    async def test_reflect_finalize_when_enough(self):
        tool = ReflectTool()
        result = await tool.execute(iteration=1, pool_size=10, avg_score=7.5, high_score_count=4)
        assert result.success is True
        assert result.data["should_continue"] is False
        assert result.data["suggested_action"] == "finalize"

    @pytest.mark.asyncio
    async def test_reflect_continue_when_few(self):
        tool = ReflectTool()
        result = await tool.execute(iteration=1, pool_size=3, avg_score=5.0, high_score_count=0)
        assert result.success is True
        assert result.data["should_continue"] is True
        assert result.data["suggested_action"] == "expand_search"

    @pytest.mark.asyncio
    async def test_reflect_finalize_on_max_iterations(self):
        tool = ReflectTool()
        result = await tool.execute(iteration=5, pool_size=10, avg_score=5.0, high_score_count=1)
        assert result.success is True
        assert result.data["should_continue"] is False
        assert result.data["suggested_action"] == "finalize"
