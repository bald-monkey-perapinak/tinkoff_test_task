import argparse
import asyncio
import pathlib
import sys

from models import CriteriaInput
from services.parser import parse_uploaded_file
from services.analyzer import analyze_with_llm
from services.report import generate_report


CRITERIA_FIELDS = {
    "направление": "direction",
    "город": "city",
    "только удалёнка": "remote_only",
    "минимальная зарплата": "min_salary",
    "уровень": "experience_level",
    "навыки": "key_skills",
}


def parse_criteria_file(path: str) -> CriteriaInput:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    data: dict = {}
    for line in text.splitlines():
        line = line.strip().lstrip("- ").strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key not in CRITERIA_FIELDS:
            continue
        field = CRITERIA_FIELDS[key]
        if field == "remote_only":
            data[field] = value.lower() in ("да", "yes", "true", "1")
        elif field == "min_salary":
            try:
                data[field] = int(value)
            except ValueError:
                pass
        elif field == "key_skills":
            data[field] = [s.strip() for s in value.split(",") if s.strip()]
        else:
            data[field] = value
    return CriteriaInput(**data)


def interactive_criteria() -> CriteriaInput:
    print("\n--- Введите критерии поиска (оставьте пустым для пропуска) ---\n")
    direction = input("  Направление (например, Python): ").strip()
    city = input("  Город: ").strip()
    remote_raw = input("  Только удалёнка (да/нет): ").strip().lower()
    remote_only = remote_raw in ("да", "yes", "true", "1")
    salary_raw = input("  Минимальная зарплата: ").strip()
    min_salary = None
    if salary_raw:
        try:
            min_salary = int(salary_raw)
        except ValueError:
            pass
    experience_level = input("  Уровень опыта (без опыта / 1-3 года / 3-6 лет): ").strip()
    skills_raw = input("  Навыки (через запятую): ").strip()
    key_skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []

    return CriteriaInput(
        direction=direction,
        city=city,
        remote_only=remote_only,
        min_salary=min_salary,
        experience_level=experience_level,
        key_skills=key_skills,
    )


def build_criteria_text(criteria: CriteriaInput) -> str:
    return "\n".join(filter(None, [
        f"- Направление: {criteria.direction}" if criteria.direction else None,
        f"- Город: {criteria.city}" if criteria.city else None,
        f"- Только удалёнка: да" if criteria.remote_only else None,
        f"- Минимальная зарплата: {criteria.min_salary}" if criteria.min_salary else None,
        f"- Уровень: {criteria.experience_level}" if criteria.experience_level else None,
        f"- Навыки: {', '.join(criteria.key_skills)}" if criteria.key_skills else None,
    ]))


async def run_pipeline(file_path: str, criteria: CriteriaInput, output_path: str):
    print(f"\n[1/3] Чтение вакансий из {file_path}...")
    content = pathlib.Path(file_path).read_text(encoding="utf-8")
    vacancies = parse_uploaded_file(file_path, content)
    print(f"  Загружено: {len(vacancies)} вакансий")
    if not vacancies:
        print("  Ошибка: вакансии не найдены или неверный формат файла")
        sys.exit(1)

    print(f"\n[2/3] Анализ через LLM...")
    results = await analyze_with_llm(vacancies[:20], criteria)
    print(f"  Проанализировано: {len(results)} вакансий")

    criteria_text = build_criteria_text(criteria)
    report = generate_report(vacancies, results, criteria_text)

    pathlib.Path(output_path).write_text(report, encoding="utf-8")
    print(f"\n[3/3] Отчёт записан в {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CLI для анализа вакансий: загрузка → LLM-анализ → markdown-отчёт",
    )
    parser.add_argument(
        "--file", "-f",
        required=True,
        help="Путь к JSON или CSV файлу с вакансиями",
    )
    parser.add_argument(
        "--criteria", "-c",
        default=None,
        help="Путь к criteria.md (если не указан — интерактивный ввод)",
    )
    parser.add_argument(
        "--output", "-o",
        default="report.md",
        help="Путь для записи отчёта (по умолчанию report.md)",
    )
    args = parser.parse_args()

    if not pathlib.Path(args.file).exists():
        print(f"Ошибка: файл {args.file} не найден")
        sys.exit(1)

    if args.criteria:
        if not pathlib.Path(args.criteria).exists():
            print(f"Ошибка: файл критериев {args.criteria} не найден")
            sys.exit(1)
        criteria = parse_criteria_file(args.criteria)
        print(f"Критерии загружены из {args.criteria}")
    else:
        criteria = interactive_criteria()

    asyncio.run(run_pipeline(args.file, criteria, args.output))


if __name__ == "__main__":
    main()
