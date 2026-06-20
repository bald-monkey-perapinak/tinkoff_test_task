import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from models import CriteriaInput, SearchParams, Vacancy

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str = ""
    duration_ms: int = 0
    metadata: dict = field(default_factory=dict)


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters_schema: dict = field(default_factory=dict)

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def to_llm_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class SearchVacanciesTool(BaseTool):
    name = "search_vacancies"
    description = "Поиск вакансий через hh.ru API. Используй когда нужно найти или расширить пул вакансий."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос"},
            "area": {"type": "string", "description": "Город/регион"},
            "schedule": {"type": "string", "enum": ["fullDay", "remote", "flexible", "shift", "rotation"]},
            "salary_from": {"type": "integer", "description": "Минимальная зарплата"},
            "experience": {"type": "string", "enum": ["noExperience", "between1And3", "between3And6", "moreThan6"]},
            "per_page": {"type": "integer", "description": "Количество результатов (1-100)"},
        },
        "required": ["query"],
    }

    async def execute(self, query: str = "", area: str = None, schedule: str = None,
                      salary_from: int = None, experience: str = None, per_page: int = 20,
                      **kwargs) -> ToolResult:
        from services.hh_client import search_vacancies

        start = time.monotonic()
        try:
            schedule_enum = None
            if schedule:
                from models import Schedule
                try:
                    schedule_enum = Schedule(schedule)
                except ValueError:
                    pass

            params = SearchParams(
                query=query,
                area=area,
                salary_from=salary_from,
                schedule=schedule_enum,
                experience=experience,
                per_page=min(per_page, 50),
            )
            vacancies, total = await search_vacancies(params)
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                data={"vacancies": vacancies, "total": total},
                duration_ms=duration,
                metadata={"query": query, "area": area},
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            logger.error(f"SearchVacanciesTool failed: {e}")
            return ToolResult(success=False, error=str(e), duration_ms=duration)


class FilterResultsTool(BaseTool):
    name = "filter_results"
    description = "Фильтрация вакансий по критериям. Используй чтобы сузить пул вакансий."
    parameters_schema = {
        "type": "object",
        "properties": {
            "min_score": {"type": "integer", "description": "Минимальный score (1-10)"},
            "require_remote": {"type": "boolean", "description": "Только удалёнка"},
            "require_skills": {"type": "array", "items": {"type": "string"}, "description": "Необходимые навыки"},
        },
    }

    async def execute(self, vacancies: list[Vacancy] = None, min_score: int = 0,
                      require_remote: bool = False, require_skills: list[str] = None,
                      **kwargs) -> ToolResult:
        start = time.monotonic()
        try:
            filtered = list(vacancies or [])
            if require_remote:
                filtered = [v for v in filtered if "удалён" in v.schedule.lower() or "remote" in v.schedule.lower()]
            if require_skills:
                filtered = [v for v in filtered if any(s.lower() in " ".join(v.skills).lower() for s in require_skills)]

            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                data={"vacancies": filtered, "original_count": len(vacancies or []), "filtered_count": len(filtered)},
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(success=False, error=str(e), duration_ms=duration)


class ScoreVacanciesTool(BaseTool):
    name = "score_vacancies"
    description = "Оценка вакансий по критериям. Возвращает отсортированный список с score."
    parameters_schema = {
        "type": "object",
        "properties": {
            "criteria": {"type": "object", "description": "Критерии оценки"},
        },
        "required": ["criteria"],
    }

    async def execute(self, vacancies: list[Vacancy] = None, criteria: CriteriaInput = None,
                      **kwargs) -> ToolResult:
        from services.scorer import ScoreCalculator

        start = time.monotonic()
        try:
            calculator = ScoreCalculator(criteria or CriteriaInput())
            results = calculator.score_vacancies(vacancies or [])
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                data={"results": results, "count": len(results)},
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(success=False, error=str(e), duration_ms=duration)


class GenerateReportTool(BaseTool):
    name = "generate_report"
    description = "Генерация Markdown-отчёта по результатам анализа."
    parameters_schema = {
        "type": "object",
        "properties": {
            "vacancies": {"type": "array", "description": "Список вакансий"},
            "results": {"type": "array", "description": "Результаты анализа"},
            "criteria_text": {"type": "string", "description": "Текст критериев"},
            "analysis_type": {"type": "string", "description": "Тип анализа"},
            "overall_summary": {"type": "string", "description": "Общее резюме"},
        },
    }

    async def execute(self, vacancies: list[Vacancy] = None, results: list = None,
                      criteria_text: str = "", analysis_type: str = "llm",
                      overall_summary: str = "", **kwargs) -> ToolResult:
        from services.report import generate_report

        start = time.monotonic()
        try:
            report = generate_report(
                vacancies or [], results or [], criteria_text,
                analysis_type=analysis_type, overall_summary=overall_summary,
            )
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                data={"report": report, "length": len(report)},
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(success=False, error=str(e), duration_ms=duration)


class ExpandSearchTool(BaseTool):
    name = "expand_search"
    description = "Расширение поискового запроса альтернативными формулировками. Используй когда мало результатов."
    parameters_schema = {
        "type": "object",
        "properties": {
            "original_query": {"type": "string", "description": "Исходный запрос"},
            "direction": {"type": "string", "description": "Направление поиска"},
        },
        "required": ["original_query"],
    }

    QUERY_EXPANSIONS = {
        "python": ["python developer", "python backend", "python разработчик", "junior python"],
        "javascript": ["javascript developer", "js developer", "frontend developer", "react developer"],
        "java": ["java developer", "java backend", "java разработчик"],
        "devops": ["devops engineer", "sre engineer", "platform engineer"],
        "data": ["data engineer", "data analyst", "data scientist", "ml engineer"],
    }

    async def execute(self, original_query: str = "", direction: str = "",
                      **kwargs) -> ToolResult:
        start = time.monotonic()
        try:
            queries = [original_query]
            direction_lower = direction.lower() if direction else ""
            for key, expansions in self.QUERY_EXPANSIONS.items():
                if key in original_query.lower() or key in direction_lower:
                    queries.extend(expansions[:2])
                    break
            if len(queries) == 1:
                queries.append(f"junior {original_query}")
                queries.append(f"{original_query} стажировка")

            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                data={"queries": queries, "original": original_query},
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(success=False, error=str(e), duration_ms=duration)


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, BaseTool] = {}
        self._register_defaults()

    def _register_defaults(self):
        for tool_cls in [
            SearchVacanciesTool,
            FilterResultsTool,
            GenerateReportTool,
            ExpandSearchTool,
        ]:
            self.register(tool_cls())

    def register(self, tool: BaseTool):
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> BaseTool | None:
        return self.tools.get(name)

    async def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        return await tool.execute(**kwargs)

    def get_all_schemas(self) -> list[dict]:
        return [tool.to_llm_schema() for tool in self.tools.values()]

    def get_tool_names(self) -> list[str]:
        return list(self.tools.keys())

    def get_descriptions(self) -> dict[str, str]:
        return {name: tool.description for name, tool in self.tools.items()}
