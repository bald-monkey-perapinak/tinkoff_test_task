import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import AnalysisResult, CriteriaInput, Vacancy


@pytest.fixture
def sample_vacancy():
    """A fully-populated Vacancy instance for reuse across tests."""
    return Vacancy(
        id="vac-1",
        title="Python Developer",
        company="TestCorp",
        city="Moscow",
        salary="100000-150000 RUB",
        salary_from=100000,
        salary_to=150000,
        schedule="remote",
        experience="between1And3",
        skills=["python", "fastapi", "sql"],
        url="https://example.com/vacancy/1",
        description="Test vacancy description",
        published_at="2025-01-01",
        is_mock=True,
    )


@pytest.fixture
def sample_vacancy_no_salary():
    """Vacancy with no salary info."""
    return Vacancy(
        id="vac-2",
        title="Frontend Developer",
        company="WebInc",
        city="Berlin",
        salary="",
        salary_from=None,
        salary_to=None,
        schedule="office",
        experience="noExperience",
        skills=[],
        url="https://example.com/vacancy/2",
        description="No salary vacancy",
        published_at="2025-01-02",
        is_mock=True,
    )


@pytest.fixture
def sample_criteria():
    """Default CriteriaInput for rule-based analysis tests."""
    return CriteriaInput(
        direction="Python",
        city="Moscow",
        remote_only=True,
        min_salary=80000,
        experience_level="between1And3",
        key_skills=["python", "fastapi"],
    )


@pytest.fixture
def sample_criteria_empty():
    """Empty CriteriaInput with no filtering criteria."""
    return CriteriaInput()


@pytest.fixture
def sample_analysis_result():
    """A sample AnalysisResult."""
    return AnalysisResult(
        vacancy_id="vac-1",
        rank=1,
        fit_score=8,
        why_fits="направление совпадает",
        concerns="нет замечаний",
        summary="Python Developer в TestCorp",
    )


@pytest.fixture
def multiple_vacancies():
    """List of three varied Vacancy objects."""
    return [
        Vacancy(
            id="v1",
            title="Python Developer",
            company="Alpha",
            city="Moscow",
            salary="120000",
            salary_from=120000,
            salary_to=None,
            schedule="remote",
            experience="between1And3",
            skills=["python", "django"],
            url="https://example.com/v1",
            description="Desc 1",
            published_at="2025-01-01",
            is_mock=True,
        ),
        Vacancy(
            id="v2",
            title="Data Scientist",
            company="Beta",
            city="Saint Petersburg",
            salary="150000",
            salary_from=150000,
            salary_to=None,
            schedule="office",
            experience="between3And6",
            skills=["python", "ml", "pandas"],
            url="https://example.com/v2",
            description="Desc 2",
            published_at="2025-01-02",
            is_mock=True,
        ),
        Vacancy(
            id="v3",
            title="DevOps Engineer",
            company="Gamma",
            city="Moscow",
            salary="",
            salary_from=None,
            salary_to=None,
            schedule="remote",
            experience="moreThan6",
            skills=["docker", "kubernetes"],
            url="https://example.com/v3",
            description="Desc 3",
            published_at="2025-01-03",
            is_mock=True,
        ),
    ]
