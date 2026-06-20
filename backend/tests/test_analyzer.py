import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Vacancy, CriteriaInput, AnalysisResult
from services.analyzer import _rule_based_analyze, _sanitize


class TestSanitize:
    """Tests for _sanitize helper."""

    def test_empty_input(self):
        """Empty string returns empty string."""
        assert _sanitize("") == ""

    def test_none_like_input(self):
        """None input returns empty string."""
        assert _sanitize(None) == ""

    def test_normal_text(self):
        """Normal text passes through unchanged."""
        assert _sanitize("Python Developer") == "Python Developer"

    def test_dangerous_chars_removed(self):
        """Dangerous characters like <, >, |, \\ are stripped."""
        text = "test<script>alert('xss')</script>end"
        result = _sanitize(text)
        assert "<" not in result
        assert ">" not in result
        assert "script" in result

    def test_pipes_and_backslashes(self):
        """Pipe and backslash characters are removed."""
        text = "cmd | grep test \\n"
        result = _sanitize(text)
        assert "|" not in result
        assert "\\" not in result

    def test_preserves_cyrillic(self):
        """Cyrillic characters are preserved."""
        text = "Разработчик на Питоне"
        result = _sanitize(text)
        assert result == text

    def test_preserves_currency_symbols(self):
        """Currency symbols are preserved."""
        text = "salary: 100000 ₽ $ €"
        result = _sanitize(text)
        assert "₽" in result
        assert "$" in result
        assert "€" in result

    def test_preserves_common_punctuation(self):
        """Common punctuation (comma, period, hyphen) is preserved."""
        text = "hello, world - test.name"
        result = _sanitize(text)
        assert "," in result
        assert "." in result
        assert "-" in result

    def test_long_text_truncated(self):
        """Text longer than PROMPT_INPUT_MAX_LEN is truncated."""
        from config import PROMPT_INPUT_MAX_LEN
        long_text = "a" * (PROMPT_INPUT_MAX_LEN + 500)
        result = _sanitize(long_text)
        assert len(result) == PROMPT_INPUT_MAX_LEN

    def test_special_injection_chars(self):
        """Characters like backtick are stripped; $ is preserved by regex."""
        text = "`rm -rf /` test"
        result = _sanitize(text)
        assert "`" not in result


class TestRuleBasedAnalyze:
    """Tests for _rule_based_analyze."""

    def test_with_no_criteria(self, multiple_vacancies):
        """No matching criteria still produces results for each vacancy."""
        criteria = CriteriaInput()
        results = _rule_based_analyze(multiple_vacancies, criteria)
        assert len(results) == 3
        assert all(isinstance(r, AnalysisResult) for r in results)
        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[2].rank == 3

    def test_max_5_vacancies(self):
        """Only first 5 vacancies are analyzed."""
        vacancies = [
            Vacancy(id=str(i), title=f"Dev{i}", company="C")
            for i in range(10)
        ]
        results = _rule_based_analyze(vacancies, CriteriaInput())
        assert len(results) == 5

    def test_direction_match(self):
        """Direction matching in title increases score and adds reason."""
        vacancies = [
            Vacancy(id="1", title="Python Developer", company="C", skills=["python"]),
        ]
        criteria = CriteriaInput(direction="Python")
        results = _rule_based_analyze(vacancies, criteria)
        assert len(results) == 1
        assert results[0].fit_score >= 7
        assert "направление совпадает" in results[0].why_fits

    def test_direction_no_match(self):
        """Non-matching direction does not add direction reason."""
        vacancies = [
            Vacancy(id="1", title="Java Developer", company="C"),
        ]
        criteria = CriteriaInput(direction="Python")
        results = _rule_based_analyze(vacancies, criteria)
        assert "направление совпадает" not in results[0].why_fits

    def test_remote_match(self):
        """remote_only with 'удалён' in schedule increases score."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", schedule="удалённый формат"),
        ]
        criteria = CriteriaInput(remote_only=True)
        results = _rule_based_analyze(vacancies, criteria)
        assert results[0].fit_score >= 6
        assert "удалённый формат" in results[0].why_fits

    def test_remote_no_match(self):
        """remote_only but schedule does not contain 'удалён'."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", schedule="office"),
        ]
        criteria = CriteriaInput(remote_only=True)
        results = _rule_based_analyze(vacancies, criteria)
        assert "удалённый формат" not in results[0].why_fits

    def test_salary_match(self):
        """Min salary met by salary_from increases score."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", salary_from=100000),
        ]
        criteria = CriteriaInput(min_salary=80000)
        results = _rule_based_analyze(vacancies, criteria)
        assert results[0].fit_score >= 6
        assert "зарплата устраивает" in results[0].why_fits

    def test_salary_no_match(self):
        """Min salary not met by salary_from."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", salary_from=50000),
        ]
        criteria = CriteriaInput(min_salary=80000)
        results = _rule_based_analyze(vacancies, criteria)
        assert "зарплата устраивает" not in results[0].why_fits

    def test_salary_none_no_match(self):
        """Min salary specified but vacancy has no salary_from."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", salary_from=None),
        ]
        criteria = CriteriaInput(min_salary=80000)
        results = _rule_based_analyze(vacancies, criteria)
        assert "зарплата устраивает" not in results[0].why_fits

    def test_skills_match(self):
        """Matching skills increase score and add skill reasons."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", skills=["python", "fastapi"]),
        ]
        criteria = CriteriaInput(key_skills=["python", "redis"])
        results = _rule_based_analyze(vacancies, criteria)
        assert results[0].fit_score >= 6
        assert "навыки: python" in results[0].why_fits

    def test_skills_no_match(self):
        """No matching skills means no skill reason."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", skills=["java"]),
        ]
        criteria = CriteriaInput(key_skills=["python"])
        results = _rule_based_analyze(vacancies, criteria)
        assert "навыки:" not in results[0].why_fits

    def test_multiple_criteria_combined(self):
        """Multiple matching criteria stack."""
        vacancies = [
            Vacancy(
                id="1",
                title="Python Developer",
                company="C",
                schedule="удалённый",
                salary_from=100000,
                skills=["python"],
            ),
        ]
        criteria = CriteriaInput(
            direction="Python",
            remote_only=True,
            min_salary=80000,
            key_skills=["python"],
        )
        results = _rule_based_analyze(vacancies, criteria)
        assert results[0].fit_score == 10  # 5 + 2 + 1 + 1 + 1

    def test_no_skills_concern(self):
        """Vacancy with no skills produces concern."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", skills=[]),
        ]
        results = _rule_based_analyze(vacancies, CriteriaInput())
        assert "навыки не указаны" in results[0].concerns

    def test_no_salary_concern(self):
        """Vacancy with empty salary produces concern."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", salary=""),
        ]
        results = _rule_based_analyze(vacancies, CriteriaInput())
        assert "зарплата не указана" in results[0].concerns

    def test_no_matching_criteria_default_reason(self):
        """When no criteria match, default reason is used."""
        vacancies = [
            Vacancy(id="1", title="Dev", company="C", salary="100k", skills=["java"]),
        ]
        criteria = CriteriaInput(direction="Python")
        results = _rule_based_analyze(vacancies, criteria)
        assert "вакансия может подойти по общим критериям" in results[0].why_fits

    def test_score_capped_at_10(self):
        """Fit score never exceeds 10."""
        vacancies = [
            Vacancy(
                id="1",
                title="Python Developer",
                company="C",
                schedule="удалённый",
                salary_from=200000,
                skills=["python", "fastapi"],
            ),
        ]
        criteria = CriteriaInput(
            direction="Python",
            remote_only=True,
            min_salary=100000,
            key_skills=["python", "fastapi"],
        )
        results = _rule_based_analyze(vacancies, criteria)
        assert results[0].fit_score == 10

    def test_summary_format(self):
        """Summary follows 'title в company' format."""
        vacancies = [
            Vacancy(id="1", title="Backend Dev", company="MegaCorp"),
        ]
        results = _rule_based_analyze(vacancies, CriteriaInput())
        assert results[0].summary == "Backend Dev в MegaCorp"

    @pytest.mark.parametrize("skills,expected_concern", [
        ([], "навыки не указаны"),
        (["python"], "серьёзных замечаний нет"),
    ])
    def test_skills_concern_parametrized(self, skills, expected_concern):
        """Parametrized test: empty skills produce concern, non-empty don't."""
        vacancies = [Vacancy(id="1", title="Dev", company="C", skills=skills, salary="100k")]
        results = _rule_based_analyze(vacancies, CriteriaInput())
        assert expected_concern in results[0].concerns

    @pytest.mark.parametrize("salary,expected_concern", [
        ("", "зарплата не указана"),
        ("100k", "серьёзных замечаний нет"),
    ])
    def test_salary_concern_parametrized(self, salary, expected_concern):
        """Parametrized test: empty salary produces concern."""
        vacancies = [Vacancy(id="1", title="Dev", company="C", skills=["py"], salary=salary)]
        results = _rule_based_analyze(vacancies, CriteriaInput())
        assert expected_concern in results[0].concerns
