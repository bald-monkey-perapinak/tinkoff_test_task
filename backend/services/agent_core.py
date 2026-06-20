import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from config import (
    PROMPT_INPUT_MAX_LEN,
)
from models import CriteriaInput, Vacancy

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    SCORING = "scoring"
    REFLECTING = "reflecting"
    REPLANNING = "replanning"
    FINALIZING = "finalizing"
    DONE = "done"
    ERROR = "error"


@dataclass
class AgentContext:
    criteria: CriteriaInput = field(default_factory=CriteriaInput)
    user_key: str = "anonymous"
    state: AgentState = AgentState.IDLE
    iteration: int = 0
    max_iterations: int = 5
    consecutive_failures: int = 0
    start_time: float = 0.0
    reasoning: list[str] = field(default_factory=list)

    def add_reasoning(self, msg: str):
        self.reasoning.append(f"[{self.state.value}] {msg}")
        logger.debug(f"Reasoning: {msg}")


class DecisionEngine:
    async def decide(self, context: AgentContext, pool_size: int,
                     scored_count: int, high_score_count: int,
                     avg_score: float) -> str:
        if context.consecutive_failures >= 2:
            return "finalize"
        if context.iteration >= context.max_iterations:
            return "finalize"
        if high_score_count >= 3:
            return "finalize"
        if pool_size == 0 and context.iteration == 0:
            return "search"
        if pool_size < 5 and context.iteration < 3:
            return "expand_search"
        if avg_score < 4 and context.iteration < 3:
            return "adjust_search"
        if scored_count == 0 and context.iteration < 3:
            return "search"
        return "finalize"


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    import re
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'(?i)(ignore (all )?(previous|above) instructions?|system prompt|you are now|new instructions?|forget (everything|all))', '[removed]', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n+', ' ', text)
    clean = re.sub(r'[^\w\s,.\-\u0430-\u044f\u0410-\u042f\u0451\u0401a-zA-Z0-9;/:₽€$¥£()!?@#%&*+=]', '', text)
    return clean[:PROMPT_INPUT_MAX_LEN]


class AgentOrchestrator:
    def __init__(self):
        self.tools = None
        self.memory = None
        self.reflection = None
        self.planner = None
        self.tracer = None
        self.decision_engine = DecisionEngine()

    def _ensure_deps(self):
        if self.tools is None:
            from services.tools import ToolRegistry
            self.tools = ToolRegistry()
        if self.memory is None:
            from services.memory import MemoryManager
            self.memory = MemoryManager()
        if self.reflection is None:
            from services.reflection import ReflectionEngine
            self.reflection = ReflectionEngine()
        if self.planner is None:
            from services.planner import Planner
            self.planner = Planner()
        if self.tracer is None:
            from services.tracing import AgentTracer
            self.tracer = AgentTracer()

    async def run(
        self,
        vacancies: list[Vacancy],
        criteria: CriteriaInput,
        user_key: str = "anonymous",
    ) -> tuple[list, dict]:
        self._ensure_deps()
        context = AgentContext(
            criteria=criteria,
            user_key=user_key,
            start_time=time.time(),
        )
        context.add_reasoning(f"Начало анализа: {len(vacancies)} вакансий")

        self.memory.working.add_vacancies(vacancies)
        criteria_hash = self.memory.build_criteria_hash(criteria)

        plan = await self.planner.create_plan(criteria, pool_size=len(vacancies))
        context.add_reasoning(f"Создан план: {len(plan.steps)} шагов")

        plan = await self._execute_plan(plan, context, criteria_hash)

        results = await self._finalize(context, criteria_hash)

        total_ms = int((time.time() - context.start_time) * 1000)
        if self.tracer:
            self.tracer.finish(context, total_ms)

        metadata = {
            "analysis_type": "agent_hybrid",
            "iterations_used": context.iteration,
            "total_vacancies_pool": len(self.memory.working.vacancies),
            "overall_summary": self._build_summary(context, results),
            "plan_goal": plan.goal,
            "plan_steps": len(plan.steps),
            "reflections_count": len(self.reflection.get_history()),
            "total_searches": sum(1 for t in self.memory.working.tool_history if t["tool"] == "search_vacancies"),
            "state": context.state.value,
        }

        await self.memory.record_action(
            user_key=user_key,
            action="agent_run",
            args={"criteria_hash": criteria_hash, "vacancies_count": len(vacancies)},
            result_summary=f"Scored {len(results)} results, avg: {sum(r.score for r in results) / len(results):.1f}" if results else "No results",
            quality_score=max((r.score for r in results), default=0),
            criteria_hash=criteria_hash,
            reflection=self.reflection.get_strategy_summary(),
        )

        return results, metadata

    async def _execute_plan(self, plan, context, criteria_hash):
        for step in plan.steps:
            if step.status in ("completed", "failed", "skipped"):
                continue

            context.add_reasoning(f"Шаг {step.step_id}: {step.action} — {step.reason}")
            logger.info(f"[Agent] Step {step.step_id}: {step.action}")

            try:
                if step.action == "search_vacancies":
                    result = await self._handle_search(step, context)
                    plan.complete_step(step.step_id, result)
                    context.consecutive_failures = 0

                elif step.action == "expand_search":
                    result = await self._handle_expand(step, context)
                    plan.complete_step(step.step_id, result)
                    context.consecutive_failures = 0

                elif step.action == "score_vacancies":
                    result = await self._handle_score(context, criteria_hash)
                    plan.complete_step(step.step_id, result)

                elif step.action == "reflect":
                    result = await self._handle_reflect(context, criteria_hash)
                    plan.complete_step(step.step_id, result)

                    if not result.get("should_continue", True):
                        context.add_reasoning("Рефлексия: данных достаточно, завершаем")
                        break

                elif step.action == "finalize_report":
                    break

                else:
                    context.add_reasoning(f"Неизвестное действие: {step.action}, пропускаем")
                    plan.fail_step(step.step_id, f"Unknown action: {step.action}")

            except Exception as e:
                logger.error(f"Step {step.step_id} failed: {e}")
                plan.fail_step(step.step_id, str(e))
                context.consecutive_failures += 1
                context.add_reasoning(f"Ошибка: {e}")

            context.iteration += 1

            if context.consecutive_failures >= 2:
                context.add_reasoning("Слишком много ошибок, replan")
                plan = await self.planner.replan(
                    plan, f"consecutive_failures: {context.consecutive_failures}",
                    len(self.memory.working.vacancies), context.criteria,
                )
                context.consecutive_failures = 0

        return plan

    async def _handle_search(self, step, context) -> dict:
        params = step.params.copy()
        result = await self.tools.execute("search_vacancies", **params)
        if result.success:
            new_vacancies = result.data.get("vacancies", [])
            added = self.memory.working.add_vacancies(new_vacancies)
            context.add_reasoning(f"Найдено {len(new_vacancies)} вакансий ({added} новых)")
            self.memory.working.log_tool_call("search_vacancies", params, {"found": len(new_vacancies), "added": added}, result.duration_ms)
            return {"found": len(new_vacancies), "added": added}
        else:
            context.add_reasoning(f"Поиск не удался: {result.error}")
            return {"error": result.error}

    async def _handle_expand(self, step, context) -> dict:
        expand_result = await self.tools.execute("expand_search", **step.params)
        if not expand_result.success:
            return {"error": expand_result.error}

        queries = expand_result.data.get("queries", [])
        total_found = 0
        for q in queries[:3]:
            search_result = await self.tools.execute("search_vacancies", query=q, per_page=10)
            if search_result.success:
                new = search_result.data.get("vacancies", [])
                added = self.memory.working.add_vacancies(new)
                total_found += added
                context.add_reasoning(f"Расширенный поиск '{q}': {added} новых")

        context.add_reasoning(f"Расширение: всего {total_found} новых вакансий")
        return {"expanded": True, "total_new": total_found}

    async def _handle_score(self, context, criteria_hash) -> dict:
        from services.scorer import ScoreCalculator
        calculator = ScoreCalculator(context.criteria)
        scored = calculator.score_vacancies(self.memory.working.vacancies)
        self.memory.working.log_tool_call(
            "score_vacancies",
            {"vacancy_count": len(self.memory.working.vacancies)},
            {"scored_count": len(scored)},
            0,
        )
        context.add_reasoning(f"Оценено {len(scored)} вакансий")
        return {"scored": len(scored), "results": scored}

    async def _handle_reflect(self, context, criteria_hash) -> dict:
        from services.scorer import ScoreCalculator
        calculator = ScoreCalculator(context.criteria)
        scored = calculator.score_vacancies(self.memory.working.vacancies)

        patterns = await self.memory.get_patterns(context.user_key)

        reflection_result = await self.reflection.reflect(
            iteration=context.iteration,
            pool_size=len(self.memory.working.vacancies),
            vacancies=self.memory.working.vacancies,
            scored_results=scored,
            criteria=context.criteria,
            memory_patterns=patterns,
            consecutive_failures=context.consecutive_failures,
        )

        self.memory.working.reflections.append({
            "quality": reflection_result.quality_assessment,
            "action": reflection_result.next_action,
            "confidence": reflection_result.confidence,
        })

        context.add_reasoning(f"Рефлексия: {reflection_result.next_action} (confidence: {reflection_result.confidence:.2f})")

        return {
            "should_continue": reflection_result.should_continue,
            "next_action": reflection_result.next_action,
            "quality_assessment": reflection_result.quality_assessment,
        }

    async def _finalize(self, context, criteria_hash) -> list:
        from services.scorer import ScoreCalculator
        calculator = ScoreCalculator(context.criteria)
        scored = calculator.score_vacancies(self.memory.working.vacancies)
        top_results = scored[:5]

        context.add_reasoning(f"Финализация: {len(top_results)} лучших вакансий")
        context.state = AgentState.DONE
        return top_results

    def _build_summary(self, context, results) -> str:
        parts = [f"Проанализировано {len(self.memory.working.vacancies)} вакансий за {context.iteration} итераций."]
        if results:
            avg = sum(r.score for r in results) / len(results)
            parts.append(f"Средний score топ-5: {avg:.1f}/10.")
            parts.append(f"Лучший: {results[0].score}/10.")
        if context.reasoning:
            parts.append(f"Ключевые решения: {len(context.reasoning)}")
        return " ".join(parts)
