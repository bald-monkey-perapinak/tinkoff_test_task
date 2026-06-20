from datetime import datetime

from models import AnalysisResult, Vacancy
from services.security import sanitize_text, sanitize_url


def _escape_md(text: str) -> str:
    if not text:
        return ""
    text = sanitize_text(text)
    for ch in ("\\", "*", "_", "~", "#", "[", "]", "|", "`"):
        text = text.replace(ch, "\\" + ch)
    return text


def _escape_md_block(text: str) -> str:
    return "\n".join(_escape_md(line) for line in text.splitlines())


def _escape_table_cell(text: str) -> str:
    if not text:
        return ""
    text = sanitize_text(text)
    return text.replace("|", "\\|")


def _truncate_at_word(text: str, max_len: int) -> str:
    if not text or len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


ANALYSIS_TYPE_LABELS = {
    "llm": "🤖 AI-анализ (Groq function calling)",
    "llm_cached": "🤖 AI-анализ (из кэша)",
    "rule_based": "⚙️ Анализ по правилам (GROQ_API_KEY не задан)",
    "rule_based_circuit_breaker": "⚙️ Анализ по правилам (Groq недоступен)",
    "rule_based_fallback": "⚙️ Анализ по правилам (ошибка API)",
    "rule_based_max_iterations": "⚙️ Анализ по правилам (превышен лимит итераций)",
    "rule_based_error": "⚙️ Анализ по правилам (непредвиденная ошибка)",
}


def generate_report(
    vacancies: list[Vacancy],
    results: list[AnalysisResult],
    criteria_text: str = "",
    analysis_type: str = "llm",
    overall_summary: str = "",
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    analysis_label = ANALYSIS_TYPE_LABELS.get(analysis_type, f"Неизвестный тип: {sanitize_text(analysis_type, 80)}")
    lines = [
        "# Отчёт по анализу вакансий",
        "",
        f"**Дата:** {now}",
        f"**Режим анализа:** {analysis_label}",
        f"**Вакансий проанализировано:** {len(vacancies)}",
        f"**В результат топ:** {len(results)}",
        "",
    ]

    if results and all(r.fit_score < 5 for r in results):
        lines.append("> ⚠️ Ни одна вакансия не набрала более 4 баллов. Рекомендуется расширить поиск или снизить требования.")
        lines.append("")

    if criteria_text:
        lines.append("## Критерии поиска")
        lines.append(_escape_md_block(criteria_text))
        lines.append("")

    lines.append("## Результаты")
    lines.append("")

    if len(results) > 1:
        lines.append(f"Вакансии отсортированы по оценке соответствия ({results[0].fit_score}–{results[-1].fit_score} из 10).")
        lines.append("")

    if len(results) > 1:
        lines.append("### Сводная таблица")
        lines.append("")
        lines.append("| # | Вакансия | Компания | Оценка | Почему подходит |")
        lines.append("|---|----------|----------|--------|----------------|")
        for r in results:
            v = next((x for x in vacancies if x.id == r.vacancy_id), None)
            title = _escape_table_cell(v.title if v else "?")
            company = _escape_table_cell(v.company if v else "?")
            why_short = _escape_table_cell(_truncate_at_word(r.why_fits, 60))
            lines.append(f"| {r.rank} | {title} | {company} | {r.fit_score}/10 | {why_short} |")
        lines.append("")

    for r in results:
        v = next((x for x in vacancies if x.id == r.vacancy_id), None)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r.rank, f"#{r.rank}")

        lines.append(f"### {medal} {_escape_md(r.summary)}")
        lines.append("")
        lines.append("| Параметр | Значение |")
        lines.append("|----------|----------|")
        lines.append(f"| Компания | {_escape_table_cell(v.company if v else '?')} |")
        lines.append(f"| Город | {_escape_table_cell(v.city if v else '?')} |")
        lines.append(f"| Зарплата | {_escape_table_cell(v.salary if v else 'не указана')} |")
        lines.append(f"| Формат | {_escape_table_cell(v.schedule if v else '?')} |")
        lines.append(f"| Опыт | {_escape_table_cell(v.experience if v else '?')} |")
        lines.append(f"| Оценка соответствия | {r.fit_score}/10 |")
        lines.append("")
        lines.append(f"**Почему подходит:** {_escape_md(r.why_fits)}")
        lines.append("")
        lines.append(f"**Что смущает:** {_escape_md(r.concerns)}")
        if r.recommendation:
            lines.append("")
            lines.append(f"**Рекомендация:** {_escape_md(r.recommendation)}")
        if v and v.skills:
            lines.append("")
            lines.append(f"**Навыки:** {_escape_md(', '.join(v.skills))}")
        safe_url = sanitize_url(v.url) if v else ""
        if safe_url:
            lines.append("")
            lines.append(f"🔗 [Ссылка]({safe_url})")
        lines.append("")
        lines.append("---")
        lines.append("")

    if overall_summary:
        lines.append("## Резюме поиска")
        lines.append("")
        lines.append(_escape_md(overall_summary))
        lines.append("")

    lines.append(f"*Отчёт сгенерирован автоматически {now}*")
    return "\n".join(lines)
