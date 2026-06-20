from datetime import datetime
from models import Vacancy, AnalysisResult


def _escape_md(text: str) -> str:
    if not text:
        return ""
    return text.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")


def generate_report(
    vacancies: list[Vacancy],
    results: list[AnalysisResult],
    criteria_text: str = "",
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Отчёт по анализу вакансий",
        f"",
        f"**Дата:** {now}",
        f"**Вакансий проанализировано:** {len(vacancies)}",
        f"**В результат топ:** {len(results)}",
        f"",
    ]

    if criteria_text:
        lines.append("## Критерии поиска")
        lines.append(criteria_text)
        lines.append("")

    lines.append("## Результаты")
    lines.append("")

    for r in results:
        v = next((x for x in vacancies if x.id == r.vacancy_id), None)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r.rank, f"#{r.rank}")

        lines.append(f"### {medal} {r.summary}")
        lines.append(f"")
        lines.append(f"| Параметр | Значение |")
        lines.append(f"|----------|----------|")
        lines.append(f"| Компания | {_escape_md(v.company if v else '?')} |")
        lines.append(f"| Город | {_escape_md(v.city if v else '?')} |")
        lines.append(f"| Зарплата | {_escape_md(v.salary if v else 'не указана')} |")
        lines.append(f"| Формат | {_escape_md(v.schedule if v else '?')} |")
        lines.append(f"| Опыт | {_escape_md(v.experience if v else '?')} |")
        lines.append(f"| Оценка соответствия | {r.fit_score}/10 |")
        lines.append(f"")
        lines.append(f"**Почему подходит:** {_escape_md(r.why_fits)}")
        lines.append(f"")
        lines.append(f"**Что смущает:** {_escape_md(r.concerns)}")
        if r.recommendation:
            lines.append(f"")
            lines.append(f"**Рекомендация:** {r.recommendation}")
        if v and v.skills:
            lines.append(f"")
            lines.append(f"**Навыки:** {', '.join(v.skills)}")
        if v and v.url:
            lines.append(f"")
            lines.append(f"🔗 [Ссылка]({v.url})")
        lines.append(f"")
        lines.append("---")
        lines.append("")

    lines.append(f"*Отчёт сгенерирован автоматически {now}*")
    return "\n".join(lines)
