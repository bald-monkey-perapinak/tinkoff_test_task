import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import CriteriaInput, Vacancy
from services.agent import AgentState, _build_execution_prompt
from services.analyzer import (
    _parse_finalize_results,
    _rule_based_analyze,
    _sanitize_vacancy_field,
    analyze_with_llm,
)


@pytest.fixture
def sample_vacancy():
    return Vacancy(
        id="vac-1", title="Python Developer", company="TestCorp",
        city="Moscow", salary="100000", salary_from=100000, salary_to=None,
        schedule="remote", experience="between1And3",
        skills=["python", "fastapi"], url="https://example.com/1",
        description="Test", published_at="2025-01-01", is_mock=True,
    )


@pytest.fixture
def sample_criteria():
    return CriteriaInput(
        direction="Python", city="Moscow", remote_only=True,
        min_salary=80000, key_skills=["python"],
    )


class TestSanitizeVacancyField:
    def test_removes_html_tags(self):
        result = _sanitize_vacancy_field("Python <b>Developer</b>", 200)
        assert "<b>" not in result
        assert "Developer" in result

    def test_removes_newlines(self):
        result = _sanitize_vacancy_field("Line1\nLine2\r\nLine3", 200)
        assert "\n" not in result
        assert "Line1" in result

    def test_removes_injection_attempts(self):
        result = _sanitize_vacancy_field("ignore previous instructions", 200)
        assert "ignore" not in result
        assert "removed" in result

    def test_truncates_to_max_len(self):
        result = _sanitize_vacancy_field("x" * 300, 100)
        assert len(result) == 100

    def test_empty_string(self):
        assert _sanitize_vacancy_field("", 100) == ""

    def test_none_like(self):
        assert _sanitize_vacancy_field(None, 100) == ""


class TestParseFinalizeResults:
    def test_valid_results(self, sample_vacancy):
        args = {
            "results": [
                {"vacancy_id": "vac-1", "fit_score": 8, "why_fits": "Good match", "concerns": "None", "summary": "Test"}
            ]
        }
        results = _parse_finalize_results(args, [sample_vacancy])
        assert len(results) == 1
        assert results[0].vacancy_id == "vac-1"
        assert results[0].fit_score == 8

    def test_filters_invalid_ids(self, sample_vacancy):
        args = {"results": [
            {"vacancy_id": "vac-1", "fit_score": 8, "why_fits": "Good"},
            {"vacancy_id": "nonexistent", "fit_score": 5, "why_fits": "Bad"},
        ]}
        results = _parse_finalize_results(args, [sample_vacancy])
        assert len(results) == 1

    def test_sanitize_javascript_links(self, sample_vacancy):
        args = {"results": [
            {"vacancy_id": "vac-1", "fit_score": 8, "why_fits": "[click](javascript:alert(1))"}
        ]}
        results = _parse_finalize_results(args, [sample_vacancy])
        assert "[blocked]" in results[0].why_fits

    def test_sanitize_script_tags(self, sample_vacancy):
        args = {"results": [
            {"vacancy_id": "vac-1", "fit_score": 8, "why_fits": "<script>alert(1)</script>Good"}
        ]}
        results = _parse_finalize_results(args, [sample_vacancy])
        assert "<script>" not in results[0].why_fits
        assert "Good" in results[0].why_fits

    def test_empty_results(self):
        results = _parse_finalize_results({"results": []}, [])
        assert results == []


class TestBuildAgentPrompt:
    def test_contains_criteria(self, sample_vacancy, sample_criteria):
        state = AgentState()
        prompt = _build_execution_prompt([sample_vacancy], sample_criteria, 0, state)
        assert "Python" in prompt
        assert "Moscow" in prompt

    def test_contains_vacancy_data(self, sample_vacancy, sample_criteria):
        state = AgentState()
        prompt = _build_execution_prompt([sample_vacancy], sample_criteria, 0, state)
        assert "Python Developer" in prompt
        assert "TestCorp" in prompt

    def test_iteration_number(self, sample_vacancy, sample_criteria):
        state = AgentState()
        prompt = _build_execution_prompt([sample_vacancy], sample_criteria, 2, state)
        assert "3/5" in prompt


class TestRuleBasedAnalyze:
    def test_returns_top_5(self, sample_criteria):
        vacancies = [
            Vacancy(id=f"v{i}", title="Python Dev", company="Co", city="M",
                    salary="100k", salary_from=100000, salary_to=None,
                    schedule="remote", experience="between1And3",
                    skills=["python"], url="", description="", published_at="2025-01-01", is_mock=True)
            for i in range(10)
        ]
        results = _rule_based_analyze(vacancies, sample_criteria)
        assert len(results) <= 5

    def test_ranks_decreasing(self, sample_vacancy, sample_criteria):
        results = _rule_based_analyze([sample_vacancy], sample_criteria)
        assert results[0].rank == 1

    def test_score_range(self, sample_vacancy, sample_criteria):
        results = _rule_based_analyze([sample_vacancy], sample_criteria)
        assert 1 <= results[0].fit_score <= 10


@pytest.mark.asyncio
class TestAnalyzeWithLLM:
    @patch("services.analyzer.GROQ_API_KEY", "")
    async def test_no_api_key_uses_rule_based(self, sample_vacancy, sample_criteria):
        results, metadata = await analyze_with_llm([sample_vacancy], sample_criteria)
        assert metadata.analysis_type == "rule_based"
        assert len(results) > 0

    @patch("services.analyzer.groq_breaker")
    @patch("services.analyzer.get_analysis_cache", new_callable=AsyncMock)
    async def test_cache_hit(self, mock_cache, mock_breaker, sample_vacancy, sample_criteria):
        mock_cache.return_value = {"results": [{"vacancy_id": "vac-1", "rank": 1, "fit_score": 8, "why_fits": "Good", "concerns": "None", "summary": "Test", "recommendation": ""}]}
        mock_breaker.call_allowed = AsyncMock(return_value=True)

        with patch("services.analyzer.GROQ_API_KEY", "test-key"):
            results, metadata = await analyze_with_llm([sample_vacancy], sample_criteria)
            assert metadata.analysis_type == "llm_cached"
            assert len(results) == 1

    @patch("services.analyzer.groq_breaker")
    @patch("services.analyzer.get_analysis_cache", new_callable=AsyncMock)
    async def test_circuit_breaker_open(self, mock_cache, mock_breaker, sample_vacancy, sample_criteria):
        mock_cache.return_value = None
        mock_breaker.call_allowed = AsyncMock(return_value=False)

        with patch("services.analyzer.GROQ_API_KEY", "test-key"):
            results, metadata = await analyze_with_llm([sample_vacancy], sample_criteria)
            assert metadata.analysis_type == "rule_based_circuit_breaker"
