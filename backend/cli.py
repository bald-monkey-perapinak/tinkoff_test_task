import argparse
import asyncio
import logging
import pathlib
import sys

from config import ANALYSIS_MAX_VACANCIES
from models import CriteriaInput
from services.analyzer import analyze_with_llm
from services.parser import parse_uploaded_file
from services.report import generate_report

CRITERIA_FIELDS = {
    "направление": "direction",
    "город": "city",
    "только удалёнка": "remote_only",
    "минимальная зарплата": "min_salary",
    "уровень": "experience_level",
    "навыки": "key_skills",
    "дата публикации от": "date_from",
}


def parse_criteria_file(path: str) -> CriteriaInput:
    raw = pathlib.Path(path).read_bytes()
    text = raw.decode("utf-8", errors="replace").replace("\x00", "")
    data: dict = {}
    _logger = logging.getLogger(__name__)
    for line in text.splitlines():
        line = line.strip().lstrip("- ").strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key not in CRITERIA_FIELDS:
            _logger.warning(f"Unrecognized criteria field '{key}' — ignored. Valid fields: {', '.join(CRITERIA_FIELDS.keys())}")
            continue
        field = CRITERIA_FIELDS[key]
        if field == "remote_only":
            data[field] = value.lower() in ("да", "yes", "true", "1")
        elif field == "min_salary":
            try:
                val = int(value)
                if val < 0 or val > 10_000_000:
                    _logger.warning(f"min_salary={val} is outside reasonable range (0-10000000), ignoring")
                else:
                    data[field] = val
            except ValueError:
                _logger.warning(f"Non-numeric min_salary value: {value}")
        elif field == "key_skills":
            data[field] = [s.strip() for s in value.split(",") if s.strip()]
        else:
            data[field] = value
    return CriteriaInput(**data)


def interactive_criteria() -> CriteriaInput:
    print("\n--- Введите критерии поиска (оставьте пустым для пропуска) ---\n", file=sys.stderr)
    direction = input("  Направление (например, Python): ").strip()
    city = input("  Город: ").strip()
    remote_raw = input("  Только удалёнка (да/нет): ").strip().lower()
    remote_only = remote_raw in ("да", "yes", "true", "1")
    salary_raw = input("  Минимальная зарплата: ").strip()
    min_salary = None
    if salary_raw:
        try:
            val = int(salary_raw)
            if val < 0 or val > 10_000_000:
                print(f"  Warning: min_salary={val} is outside reasonable range (0-10000000), ignoring", file=sys.stderr)
            else:
                min_salary = val
        except ValueError:
            print(f"  Warning: non-numeric min_salary value: {salary_raw}", file=sys.stderr)
    experience_level = input("  Уровень опыта (без опыта / 1-3 года / 3-6 лет): ").strip()
    skills_raw = input("  Навыки (через запятую): ").strip()
    key_skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []
    date_from = input("  Дата публикации от (YYYY-MM-DD): ").strip() or None

    return CriteriaInput(
        direction=direction,
        city=city,
        remote_only=remote_only,
        min_salary=min_salary,
        experience_level=experience_level,
        key_skills=key_skills,
        date_from=date_from,
    )


def build_criteria_text(criteria: CriteriaInput) -> str:
    return "\n".join(filter(None, [
        f"- Направление: {criteria.direction}" if criteria.direction else None,
        f"- Город: {criteria.city}" if criteria.city else None,
        "- Только удалёнка: да" if criteria.remote_only else None,
        f"- Минимальная зарплата: {criteria.min_salary}" if criteria.min_salary else None,
        f"- Уровень: {criteria.experience_level}" if criteria.experience_level else None,
        f"- Навыки: {', '.join(criteria.key_skills)}" if criteria.key_skills else None,
        f"- Дата публикации от: {criteria.date_from}" if criteria.date_from else None,
    ]))


async def run_pipeline(file_path: str, criteria: CriteriaInput, output_path: str) -> int:
    logger = logging.getLogger("cli")

    logger.info(f"[1/3] Чтение вакансий из {file_path}")
    try:
        raw = pathlib.Path(file_path).read_bytes()
    except OSError as e:
        logger.error(f"Не удалось прочитать файл {file_path}: {e}")
        report = generate_report([], [], criteria_text=build_criteria_text(criteria), overall_summary=f"Ошибка чтения файла: {e}")
        pathlib.Path(output_path).write_text(report, encoding="utf-8")
        return 1

    content = raw.decode("utf-8", errors="replace").replace("\x00", "")
    vacancies = parse_uploaded_file(file_path, content)
    logger.info(f"  Загружено: {len(vacancies)} вакансий")
    if not vacancies:
        logger.warning("  Вакансии не найдены или неверный формат файла")
        report = generate_report([], [], criteria_text=build_criteria_text(criteria), overall_summary="Вакансии не найдены или неверный формат файла.")
        pathlib.Path(output_path).write_text(report, encoding="utf-8")
        return 1

    logger.info("[2/3] Агентный анализ через LLM...")
    results, metadata = await analyze_with_llm(vacancies[:ANALYSIS_MAX_VACANCIES], criteria)
    logger.info(f"  Проанализировано: {len(results)} вакансий")
    logger.info(f"  Тип анализа: {metadata.analysis_type}")
    logger.info(f"  Итераций агента: {metadata.iterations_used}")
    logger.info(f"  Пул вакансий: {metadata.total_vacancies_pool}")

    criteria_text = build_criteria_text(criteria)
    report = generate_report(vacancies, results, criteria_text, analysis_type=metadata.analysis_type, overall_summary=metadata.overall_summary)

    pathlib.Path(output_path).write_text(report, encoding="utf-8")
    logger.info(f"[3/3] Отчёт записан в {output_path}")
    return 0


def _find_criteria_file() -> str | None:
    for name in ("criteria.md", "criteria.txt", "criteria"):
        if pathlib.Path(name).is_file():
            return name
    return None


ALLOWED_EXTENSIONS = {".csv", ".json"}


def main():
    from logging_config import setup_logging
    setup_logging()
    logger = logging.getLogger("cli")

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
        help="Путь к criteria.md (если не указан — авто-поиск или интерактивный ввод)",
    )
    parser.add_argument(
        "--output", "-o",
        default="report.md",
        help="Путь для записи отчёта (по умолчанию report.md)",
    )
    args = parser.parse_args()

    file_path = pathlib.Path(args.file)
    if not file_path.exists():
        logger.error(f"Файл {args.file} не найден")
        report = generate_report([], [], overall_summary=f"Файл {args.file} не найден.")
        pathlib.Path(args.output).write_text(report, encoding="utf-8")
        sys.exit(1)

    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        logger.error(f"Неподдерживаемый формат файла: {file_path.suffix}. Допустимы: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
        sys.exit(1)

    criteria_path = args.criteria or _find_criteria_file()
    if criteria_path:
        if not pathlib.Path(criteria_path).exists():
            logger.error(f"Файл критериев {criteria_path} не найден")
            sys.exit(1)
        criteria = parse_criteria_file(criteria_path)
        logger.info(f"Критерии загружены из {criteria_path}")
    else:
        criteria = interactive_criteria()

    try:
        exit_code = asyncio.run(run_pipeline(args.file, criteria, args.output))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except (OSError, ValueError) as e:
        logger.error(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        report = generate_report([], [], criteria_text=build_criteria_text(criteria), overall_summary=f"Error: {e}")
        pathlib.Path(args.output).write_text(report, encoding="utf-8")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
