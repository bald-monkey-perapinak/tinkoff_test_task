import logging
from dataclasses import dataclass, field

from models import CriteriaInput, Vacancy

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    should_continue: bool
    quality_assessment: str
    strategy_adjustment: str
    next_action: str
    suggested_query: str = ""
    suggested_area: str = ""
    suggested_schedule: str = ""
    confidence: float = 0.5
    reasoning: list[str] = field(default_factory=list)


class ReflectionEngine:
    def __init__(self):
        self._history: list[ReflectionResult] = []

    async def reflect(
        self,
        iteration: int,
        pool_size: int,
        vacancies: list[Vacancy],
        scored_results: list,
        criteria: CriteriaInput,
        memory_patterns: dict | None = None,
        consecutive_failures: int = 0,
    ) -> ReflectionResult:
        reasoning = []
        should_continue = True
        next_action = "continue"
        suggested_query = ""
        suggested_area = ""
        suggested_schedule = ""
        confidence = 0.5

        high_score_count = sum(1 for r in scored_results if r.score >= 7)
        avg_score = sum(r.score for r in scored_results) / len(scored_results) if scored_results else 0
        low_score_count = sum(1 for r in scored_results if r.score < 4)

        if consecutive_failures >= 2:
            should_continue = False
            next_action = "finalize"
            reasoning.append(f"Достигнут лимит неудачных итераций ({consecutive_failures})")
            confidence = 0.8

        elif high_score_count >= 3:
            should_continue = False
            next_action = "finalize"
            reasoning.append(f"Достаточно хороших вариантов ({high_score_count} с score >= 7)")
            confidence = 0.9

        elif pool_size < 5 and iteration < 3:
            should_continue = True
            next_action = "expand_search"
            reasoning.append(f"Мало вакансий в пуле ({pool_size}), расширяем поиск")
            if criteria.direction:
                suggested_query = criteria.direction
            confidence = 0.6

        elif avg_score < 4 and iteration < 3:
            should_continue = True
            next_action = "adjust_search"
            reasoning.append(f"Низкий средний score ({avg_score:.1f}), корректируем стратегию")
            if criteria.remote_only:
                suggested_schedule = "remote"
            if criteria.city:
                suggested_area = criteria.city
            confidence = 0.5

        elif iteration >= 4:
            should_continue = False
            next_action = "finalize"
            reasoning.append(f"Достигнут лимит итераций ({iteration})")
            confidence = 0.7

        else:
            should_continue = True
            next_action = "continue"
            reasoning.append(f"Пул ({pool_size} вакансий), средний score ({avg_score:.1f}) — продолжаем")
            confidence = 0.6

        if memory_patterns:
            for action, pattern in memory_patterns.items():
                if pattern.get("avg_quality", 0) > 6:
                    reasoning.append(f"Паттерн '{action}' показывает хорошие результаты (avg: {pattern['avg_quality']})")

        quality_assessment = f"Пул: {pool_size}, avg_score: {avg_score:.1f}, high: {high_score_count}, low: {low_score_count}"
        strategy_adjustment = f"Следующее действие: {next_action}"

        result = ReflectionResult(
            should_continue=should_continue,
            quality_assessment=quality_assessment,
            strategy_adjustment=strategy_adjustment,
            next_action=next_action,
            suggested_query=suggested_query,
            suggested_area=suggested_area,
            suggested_schedule=suggested_schedule,
            confidence=confidence,
            reasoning=reasoning,
        )
        self._history.append(result)
        logger.info(f"Reflection #{iteration}: continue={should_continue}, action={next_action}, confidence={confidence:.2f}")
        return result

    def get_history(self) -> list[ReflectionResult]:
        return list(self._history)

    def get_last(self) -> ReflectionResult | None:
        return self._history[-1] if self._history else None

    def get_strategy_summary(self) -> str:
        if not self._history:
            return "Нет данных рефлексии"
        last = self._history[-1]
        parts = [f"Последняя рефлексия: {last.quality_assessment}"]
        parts.append(f"Рекомендация: {last.next_action} (confidence: {last.confidence:.2f})")
        if last.reasoning:
            parts.append("Причины:")
            for r in last.reasoning:
                parts.append(f"  - {r}")
        return "\n".join(parts)
