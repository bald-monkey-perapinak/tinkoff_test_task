import pytest

from models import Vacancy, AnalysisResult
from services.report import generate_report


class TestGenerateReport:
    """Tests for generate_report."""

    def test_report_with_results(self, sample_vacancy, sample_analysis_result):
        """Report generated with vacancies and results contains expected sections."""
        report = generate_report(
            vacancies=[sample_vacancy],
            results=[sample_analysis_result],
        )
        assert "# Отчёт по анализу вакансий" in report
        assert "**Дата:**" in report
        assert "**Вакансий проанализировано:** 1" in report
        assert "**В результат топ:** 1" in report
        assert "## Результаты" in report
        assert "Python Developer в TestCorp" in report
        assert "TestCorp" in report
        assert "Moscow" in report
        assert "100000-150000 RUB" in report
        assert "remote" in report
        assert "8/10" in report
        assert "направление совпадает" in report
        assert "python, fastapi, sql" in report
        assert "🔗 [Ссылка](https://example.com/vacancy/1)" in report

    def test_report_without_results(self, sample_vacancy):
        """Report with no results shows 0 in top count."""
        report = generate_report(
            vacancies=[sample_vacancy],
            results=[],
        )
        assert "**В результат топ:** 0" in report
        assert "## Результаты" in report
        assert "Python Developer" not in report

    def test_report_empty_vacancies_and_results(self):
        """Report with empty vacancies and results list is valid."""
        report = generate_report(vacancies=[], results=[])
        assert "**Вакансий проанализировано:** 0" in report
        assert "**В результат топ:** 0" in report
        assert "# Отчёт по анализу вакансий" in report

    def test_report_with_criteria_text(self, sample_vacancy, sample_analysis_result):
        """Criteria text is included when provided."""
        criteria = "Направление: Python\nГород: Moscow"
        report = generate_report(
            vacancies=[sample_vacancy],
            results=[sample_analysis_result],
            criteria_text=criteria,
        )
        assert "## Критерии поиска" in report
        assert "Направление: Python" in report

    def test_report_without_criteria_text(self, sample_vacancy, sample_analysis_result):
        """No criteria section when criteria_text is empty."""
        report = generate_report(
            vacancies=[sample_vacancy],
            results=[sample_analysis_result],
            criteria_text="",
        )
        assert "## Критерии поиска" not in report

    def test_report_medal_emojis(self):
        """Rank 1/2/3 get medal emojis; rank 4+ get #N format."""
        vacancies = [
            Vacancy(id=f"v{i}", title=f"Dev{i}", company=f"C{i}")
            for i in range(5)
        ]
        results = [
            AnalysisResult(vacancy_id=f"v{i}", rank=i + 1, fit_score=10 - i)
            for i in range(5)
        ]
        report = generate_report(vacancies=vacancies, results=results)
        assert "🥇" in report
        assert "🥈" in report
        assert "🥉" in report
        assert "#4" in report
        assert "#5" in report

    def test_report_vacancy_not_found(self, sample_analysis_result):
        """When vacancy_id doesn't match any vacancy, '?' placeholders are used."""
        report = generate_report(
            vacancies=[],
            results=[sample_analysis_result],
        )
        assert "|" in report
        assert "?" in report

    def test_report_vacancy_no_skills(self):
        """Vacancy with no skills does not show skills section."""
        vacancy = Vacancy(id="v1", title="Dev", company="C", skills=[])
        result = AnalysisResult(
            vacancy_id="v1", rank=1, fit_score=5,
            why_fits="reason", concerns="none", summary="Dev в C",
        )
        report = generate_report(vacancies=[vacancy], results=[result])
        assert "**Навыки:**" not in report

    def test_report_vacancy_no_url(self):
        """Vacancy with no url does not show link section."""
        vacancy = Vacancy(id="v1", title="Dev", company="C", url="")
        result = AnalysisResult(
            vacancy_id="v1", rank=1, fit_score=5,
            why_fits="reason", concerns="none", summary="Dev в C",
        )
        report = generate_report(vacancies=[vacancy], results=[result])
        assert "🔗 [Ссылка]" not in report

    def test_report_contains_footer(self, sample_vacancy, sample_analysis_result):
        """Report ends with auto-generated footer."""
        report = generate_report(
            vacancies=[sample_vacancy],
            results=[sample_analysis_result],
        )
        assert "*Отчёт сгенерирован автоматически" in report

    def test_report_multiple_results(self, multiple_vacancies):
        """Report with multiple results contains all summaries."""
        results = [
            AnalysisResult(
                vacancy_id=v.id,
                rank=i + 1,
                fit_score=10 - i,
                why_fits="good",
                concerns="none",
                summary=f"{v.title} в {v.company}",
            )
            for i, v in enumerate(multiple_vacancies)
        ]
        report = generate_report(vacancies=multiple_vacancies, results=results)
        assert "Python Developer в Alpha" in report
        assert "Data Scientist в Beta" in report
        assert "DevOps Engineer в Gamma" in report
        assert "**В результат топ:** 3" in report

    def test_report_table_structure(self, sample_vacancy, sample_analysis_result):
        """Each result has a properly formatted markdown table."""
        report = generate_report(
            vacancies=[sample_vacancy],
            results=[sample_analysis_result],
        )
        assert "| Параметр | Значение |" in report
        assert "|----------|----------|" in report
        assert "| Компания |" in report
        assert "| Город |" in report
        assert "| Зарплата |" in report
        assert "| Формат |" in report
        assert "| Опыт |" in report
        assert "| Оценка соответствия |" in report
