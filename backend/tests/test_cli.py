import pytest
import sys
import os
import pathlib
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import CriteriaInput
from cli import parse_criteria_file, build_criteria_text


SAMPLE_CRITERIA = """\
- Направление: Python
- Город: Москва
- Только удалёнка: да
- Минимальная зарплата: 80000
- Уровень: без опыта
- Навыки: Python, FastAPI, SQL
"""


class TestParseCriteriaFile:

    def test_full_criteria(self, tmp_path):
        criteria_path = tmp_path / "criteria.md"
        criteria_path.write_text(SAMPLE_CRITERIA, encoding="utf-8")
        result = parse_criteria_file(str(criteria_path))
        assert result.direction == "Python"
        assert result.city == "Москва"
        assert result.remote_only is True
        assert result.min_salary == 80000
        assert result.experience_level == "без опыта"
        assert result.key_skills == ["Python", "FastAPI", "SQL"]

    def test_partial_criteria(self, tmp_path):
        criteria_path = tmp_path / "criteria.md"
        criteria_path.write_text("- Направление: Go\n- Город: СПб\n", encoding="utf-8")
        result = parse_criteria_file(str(criteria_path))
        assert result.direction == "Go"
        assert result.city == "СПб"
        assert result.remote_only is False
        assert result.min_salary is None
        assert result.key_skills == []

    def test_empty_file(self, tmp_path):
        criteria_path = tmp_path / "criteria.md"
        criteria_path.write_text("", encoding="utf-8")
        result = parse_criteria_file(str(criteria_path))
        assert result == CriteriaInput()

    def test_unknown_fields_ignored(self, tmp_path):
        criteria_path = tmp_path / "criteria.md"
        criteria_path.write_text("- Направление: Java\n- Бла-бла: что-то\n", encoding="utf-8")
        result = parse_criteria_file(str(criteria_path))
        assert result.direction == "Java"

    def test_remote_only_no(self, tmp_path):
        criteria_path = tmp_path / "criteria.md"
        criteria_path.write_text("- Только удалёнка: нет\n", encoding="utf-8")
        result = parse_criteria_file(str(criteria_path))
        assert result.remote_only is False

    def test_skills_comma_separated(self, tmp_path):
        criteria_path = tmp_path / "criteria.md"
        criteria_path.write_text("- Навыки: Python, Docker, Redis, PostgreSQL\n", encoding="utf-8")
        result = parse_criteria_file(str(criteria_path))
        assert result.key_skills == ["Python", "Docker", "Redis", "PostgreSQL"]

    def test_non_numeric_salary_ignored(self, tmp_path):
        criteria_path = tmp_path / "criteria.md"
        criteria_path.write_text("- Минимальная зарплата: неизвестно\n", encoding="utf-8")
        result = parse_criteria_file(str(criteria_path))
        assert result.min_salary is None


class TestBuildCriteriaText:

    def test_full_criteria_text(self):
        criteria = CriteriaInput(
            direction="Python",
            city="Москва",
            remote_only=True,
            min_salary=80000,
            experience_level="без опыта",
            key_skills=["Python", "FastAPI"],
        )
        text = build_criteria_text(criteria)
        assert "- Направление: Python" in text
        assert "- Город: Москва" in text
        assert "- Только удалёнка: да" in text
        assert "- Минимальная зарплата: 80000" in text
        assert "- Уровень: без опыта" in text
        assert "- Навыки: Python, FastAPI" in text

    def test_empty_criteria_text(self):
        criteria = CriteriaInput()
        text = build_criteria_text(criteria)
        assert text == ""

    def test_partial_criteria_text(self):
        criteria = CriteriaInput(direction="Go", min_salary=100000)
        text = build_criteria_text(criteria)
        assert "- Направление: Go" in text
        assert "- Минимальная зарплата: 100000" in text
        assert "Город" not in text
        assert "удалёнка" not in text
