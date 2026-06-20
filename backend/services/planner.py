import logging
import time
from dataclasses import dataclass, field

from models import CriteriaInput

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    step_id: int
    action: str
    params: dict = field(default_factory=dict)
    reason: str = ""
    status: str = "pending"
    result: dict | None = None


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    fallback_strategy: str = ""
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)

    def current_step(self) -> PlanStep | None:
        for step in self.steps:
            if step.status == "pending":
                return step
        return None

    def complete_step(self, step_id: int, result: dict):
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "completed"
                step.result = result
                return

    def fail_step(self, step_id: int, reason: str):
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "failed"
                step.result = {"error": reason}
                return

    def get_completed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    def get_failed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "failed")

    def is_finished(self) -> bool:
        return all(s.status in ("completed", "failed", "skipped") for s in self.steps)


class Planner:
    def __init__(self):
        self._plans: list[Plan] = []

    async def create_plan(self, criteria: CriteriaInput, pool_size: int = 0,
                          memory_patterns: dict | None = None) -> Plan:
        steps = []
        step_id = 0

        if pool_size == 0:
            steps.append(PlanStep(
                step_id=step_id,
                action="search_vacancies",
                params={"query": criteria.direction or "стажировка", "per_page": 20},
                reason="Начальный поиск вакансий",
            ))
            step_id += 1

            if criteria.city:
                steps.append(PlanStep(
                    step_id=step_id,
                    action="search_vacancies",
                    params={"query": criteria.direction or "стажировка", "area": criteria.city, "per_page": 20},
                    reason=f"Поиск в городе {criteria.city}",
                ))
                step_id += 1
        else:
            steps.append(PlanStep(
                step_id=step_id,
                action="score_vacancies",
                params={"criteria": criteria.model_dump()},
                reason="Оценка текущего пула вакансий",
            ))
            step_id += 1

        steps.append(PlanStep(
            step_id=step_id,
            action="reflect",
            params={"iteration": 0, "pool_size": pool_size},
            reason="Оценка качества результатов",
        ))
        step_id += 1

        steps.append(PlanStep(
            step_id=step_id,
            action="finalize_report",
            params={},
            reason="Генерация итогового отчёта",
        ))

        if memory_patterns:
            for action, pattern in memory_patterns.items():
                if pattern.get("avg_quality", 0) > 6 and pattern.get("count", 0) > 2:
                    logger.info(f"Memory pattern: '{action}' works well (avg: {pattern['avg_quality']})")

        goal = f"Найти лучшие вакансии по критериям: {criteria.direction or 'любое направление'}, {criteria.city or 'любой город'}"
        plan = Plan(
            goal=goal,
            steps=steps,
            fallback_strategy="Если основной поиск не дал результатов — расширить запрос, убрать фильтры",
            confidence=0.6,
        )
        self._plans.append(plan)
        logger.info(f"Plan created: {len(steps)} steps. Goal: {goal}")
        return plan

    async def replan(self, current_plan: Plan, failure_reason: str,
                     pool_size: int, criteria: CriteriaInput) -> Plan:
        new_steps = []
        step_id = 0

        if "search" in failure_reason.lower() or "timeout" in failure_reason.lower():
            new_steps.append(PlanStep(
                step_id=step_id,
                action="expand_search",
                params={"original_query": criteria.direction or "стажировка", "direction": criteria.direction},
                reason=f"Расширение поиска после ошибки: {failure_reason}",
            ))
            step_id += 1
        elif "low_score" in failure_reason.lower() or "мало результатов" in failure_reason.lower():
            new_steps.append(PlanStep(
                step_id=step_id,
                action="search_vacancies",
                params={"query": criteria.direction or "стажировка", "per_page": 50},
                reason="Расширенный поиск с увеличенным per_page",
            ))
            step_id += 1

        new_steps.append(PlanStep(
            step_id=step_id,
            action="score_vacancies",
            params={"criteria": criteria.model_dump()},
            reason="Повторная оценка после изменений",
        ))
        step_id += 1

        new_steps.append(PlanStep(
            step_id=step_id,
            action="finalize_report",
            params={},
            reason="Итоговый отчёт",
        ))

        goal = f"Replan после ошибки: {failure_reason[:100]}"
        plan = Plan(
            goal=goal,
            steps=new_steps,
            fallback_strategy="Если и replan не помог — вернуть лучшее из текущего пула",
            confidence=0.4,
        )
        self._plans.append(plan)
        logger.info(f"Replan created: {len(new_steps)} steps. Reason: {failure_reason[:100]}")
        return plan

    def get_plan_history(self) -> list[Plan]:
        return list(self._plans)

    def get_last_plan(self) -> Plan | None:
        return self._plans[-1] if self._plans else None
