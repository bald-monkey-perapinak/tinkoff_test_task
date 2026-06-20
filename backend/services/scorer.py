import logging
from dataclasses import dataclass, field
from datetime import datetime

from models import CriteriaInput, Vacancy

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    vacancy_id: str
    score: int
    reasons: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    weights_used: dict[str, float] = field(default_factory=dict)


class ScoreCalculator:
    WEIGHTS = {
        "direction": 3.0,
        "salary": 2.0,
        "skills": 2.0,
        "schedule": 1.5,
        "experience": 1.0,
        "date": 0.5,
    }

    def __init__(self, criteria: CriteriaInput):
        self.criteria = criteria
        self.date_threshold = self._parse_date(criteria.date_from) if criteria.date_from else None

    def score_vacancy(self, vacancy: Vacancy) -> ScoreResult:
        result = ScoreResult(vacancy_id=vacancy.id, score=5)

        self._score_direction(vacancy, result)
        self._score_salary(vacancy, result)
        self._score_skills(vacancy, result)
        self._score_schedule(vacancy, result)
        self._score_experience(vacancy, result)
        self._score_date(vacancy, result)

        result.score = max(1, min(10, result.score))

        if not result.reasons:
            result.reasons.append("вакансия может подойти по общим критериям")
        if not vacancy.skills:
            result.concerns.append("навыки не указаны")
        if not vacancy.salary:
            result.concerns.append("зарплата не указана")

        return result

    def score_vacancies(self, vacancies: list[Vacancy]) -> list[ScoreResult]:
        results = []
        for v in vacancies:
            try:
                results.append(self.score_vacancy(v))
            except Exception as e:
                logger.warning(f"Failed to score vacancy {v.id}: {e}")
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _score_direction(self, vacancy: Vacancy, result: ScoreResult):
        if not self.criteria.direction:
            return
        direction_lower = self.criteria.direction.lower()
        title_lower = vacancy.title.lower()
        if direction_lower in title_lower:
            result.score += self.WEIGHTS["direction"]
            result.reasons.append("направление совпадает")
            result.weights_used["direction"] = self.WEIGHTS["direction"]
        else:
            result.score -= 1
            result.concerns.append("направление не совпадает")
            result.weights_used["direction"] = -1.0

    def _score_salary(self, vacancy: Vacancy, result: ScoreResult):
        if not self.criteria.min_salary:
            return
        if vacancy.salary_from and vacancy.salary_from >= self.criteria.min_salary:
            result.score += self.WEIGHTS["salary"]
            result.reasons.append("зарплата устраивает")
            result.weights_used["salary"] = self.WEIGHTS["salary"]
        elif vacancy.salary_from and vacancy.salary_from < self.criteria.min_salary:
            result.score -= 1
            result.concerns.append("зарплата ниже порога")
            result.weights_used["salary"] = -1.0

    def _score_skills(self, vacancy: Vacancy, result: ScoreResult):
        if not self.criteria.key_skills:
            return
        matched = [s for s in self.criteria.key_skills if s.lower() in " ".join(vacancy.skills).lower()]
        if matched:
            result.score += self.WEIGHTS["skills"]
            result.reasons.append(f"навыки: {', '.join(matched)}")
            result.weights_used["skills"] = self.WEIGHTS["skills"]
        else:
            result.concerns.append("нет совпадений по навыкам")

    def _score_schedule(self, vacancy: Vacancy, result: ScoreResult):
        if not self.criteria.remote_only:
            return
        schedule_lower = vacancy.schedule.lower()
        if "удалён" in schedule_lower or "remote" in schedule_lower:
            result.score += self.WEIGHTS["schedule"]
            result.reasons.append("удалённый формат")
            result.weights_used["schedule"] = self.WEIGHTS["schedule"]
        else:
            result.score -= 1
            result.concerns.append("нет удалённого формата")
            result.weights_used["schedule"] = -1.0

    def _score_experience(self, vacancy: Vacancy, result: ScoreResult):
        if not self.criteria.experience_level:
            return
        level_lower = self.criteria.experience_level.lower()
        exp_lower = vacancy.experience.lower()
        if level_lower in exp_lower or exp_lower in level_lower:
            result.score += self.WEIGHTS["experience"]
            result.reasons.append("уровень опыта совпадает")
            result.weights_used["experience"] = self.WEIGHTS["experience"]

    def _score_date(self, vacancy: Vacancy, result: ScoreResult):
        if not self.date_threshold or not vacancy.published_at:
            return
        pub_date = self._parse_date(vacancy.published_at)
        if pub_date and pub_date < self.date_threshold:
            result.score -= 2
            result.concerns.append("вакансия старше порога даты")
            result.weights_used["date"] = -2.0
        elif pub_date and pub_date >= self.date_threshold:
            result.score += self.WEIGHTS["date"]
            result.reasons.append("дата публикации подходит")
            result.weights_used["date"] = self.WEIGHTS["date"]

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
