from models import CriteriaInput, Vacancy
from services.scorer import ScoreCalculator, ScoreResult


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
        "skills": ["Python", "FastAPI", "SQL"],
        "url": "https://hh.ru/vacancy/123",
        "description": "Разработка backend",
        "published_at": "2026-06-15",
    }
    defaults.update(kwargs)
    return Vacancy(**defaults)


class TestScoreCalculator:
    def test_basic_scoring(self):
        criteria = CriteriaInput(direction="Python", min_salary=70000)
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy()
        result = calc.score_vacancy(vacancy)
        assert isinstance(result, ScoreResult)
        assert result.score >= 5
        assert result.vacancy_id == "123"

    def test_direction_match_increases_score(self):
        criteria = CriteriaInput(direction="Python")
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(title="Python Developer")
        result = calc.score_vacancy(vacancy)
        assert "направление совпадает" in result.reasons
        assert result.score > 5

    def test_direction_no_match_decreases_score(self):
        criteria = CriteriaInput(direction="Java")
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(title="Python Developer")
        result = calc.score_vacancy(vacancy)
        assert "направление не совпадает" in result.concerns
        assert result.score < 5

    def test_salary_match(self):
        criteria = CriteriaInput(min_salary=70000)
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(salary_from=80000)
        result = calc.score_vacancy(vacancy)
        assert "зарплата устраивает" in result.reasons

    def test_salary_below_threshold(self):
        criteria = CriteriaInput(min_salary=100000)
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(salary_from=80000)
        result = calc.score_vacancy(vacancy)
        assert "зарплата ниже порога" in result.concerns

    def test_skills_match(self):
        criteria = CriteriaInput(key_skills=["Python", "FastAPI"])
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(skills=["Python", "FastAPI", "SQL"])
        result = calc.score_vacancy(vacancy)
        assert any("навыки" in r for r in result.reasons)

    def test_remote_match(self):
        criteria = CriteriaInput(remote_only=True)
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(schedule="удалённая")
        result = calc.score_vacancy(vacancy)
        assert "удалённый формат" in result.reasons

    def test_remote_no_match(self):
        criteria = CriteriaInput(remote_only=True)
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(schedule="полный день")
        result = calc.score_vacancy(vacancy)
        assert "нет удалённого формата" in result.concerns

    def test_score_capped_at_10(self):
        criteria = CriteriaInput(direction="Python", remote_only=True, min_salary=0, key_skills=["Python", "FastAPI", "SQL"])
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(salary_from=200000)
        result = calc.score_vacancy(vacancy)
        assert result.score <= 10

    def test_score_floored_at_1(self):
        criteria = CriteriaInput(direction="Java", remote_only=True)
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(title="Python Developer", schedule="полный день")
        result = calc.score_vacancy(vacancy)
        assert result.score >= 1

    def test_no_skills_concern(self):
        criteria = CriteriaInput()
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(skills=[])
        result = calc.score_vacancy(vacancy)
        assert "навыки не указаны" in result.concerns

    def test_no_salary_concern(self):
        criteria = CriteriaInput()
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(salary="", salary_from=None)
        result = calc.score_vacancy(vacancy)
        assert "зарплата не указана" in result.concerns

    def test_score_vacancies_sorted(self):
        criteria = CriteriaInput(direction="Python")
        calc = ScoreCalculator(criteria)
        vacancies = [
            _make_vacancy(id="1", title="Java Developer"),
            _make_vacancy(id="2", title="Python Developer"),
            _make_vacancy(id="3", title="Python Senior"),
        ]
        results = calc.score_vacancies(vacancies)
        assert len(results) == 3
        assert results[0].score >= results[1].score >= results[2].score

    def test_date_from_filters_old(self):
        criteria = CriteriaInput(date_from="2026-06-01")
        calc = ScoreCalculator(criteria)
        vacancy = _make_vacancy(published_at="2026-05-01")
        result = calc.score_vacancy(vacancy)
        assert any("старше" in c for c in result.concerns)
