# ADR-003: Circuit Breaker для внешних API

## Статус
Принято

## Контекст
Приложение зависит от двух внешних API: hh.ru (поиск вакансий) и Groq (LLM анализ). Оба могут быть недоступны: hh.ru — блокировка IP или rate limit, Groq — простои или лимиты бесплатного tier. Нужно: не забивать event loop повторными запросами, быстро переключаться на fallback.

## Решения

### Паттерн: Circuit Breaker
Состояния:
- **Closed** — нормальная работа, запросы проходят
- **Open** — превышен порог ошибок, все запросы отклоняются, возвращается fallback
- **Half-Open** — через `recovery_timeout` пропускается один probe-запрос; при успехе → Closed, при ошибке → Open

### Пороги

| Breaker | Threshold | Recovery | Fallback |
|---------|-----------|----------|----------|
| `hh_breaker` | 5 ошибок | 60 сек | Mock-данные из `data/sample_vacancies.json` |
| `groq_breaker` | 3 ошибки | 30 сек | Rule-based анализ |

### Реализация
`backend/circuit_breaker.py` — `CircuitBreaker` класс с `call_allowed()`, `record_success()`, `record_failure()`, `get_state()`.

### Интеграция
- **hh_client.py:** `search_vacancies()` проверяет `hh_breaker.call_allowed()` перед запросом
- **analyzer.py:** `analyze_with_llm()` проверяет `groq_breaker.call_allowed()` перед вызовом Groq
- **main.py:** `/api/health/ready` возвращает состояние обоих breakers

### Почему не tenacity/retrying
- tenacity — более тяжёлый, для простых retry + circuit breaker достаточно своего решения
- Кастомный breaker даёт полный контроль над состояниями и интеграцией с health check

## Компромиссы

| Выбор | Плюс | Минус |
|-------|------|-------|
| Custom circuit breaker | Полный контроль, интеграция с health | Нужно поддерживать |
| Порог 5 для hh.ru | Не слишком агрессивный | Может пропускать transient errors |
| Порог 3 для Groq | Быстрый fallback | Может срабатывать на одном timeout |

## Follow-up Decisions
- [ ] Адаптивные пороги на основе latency percentile
- [ ] Prometheus метрики для circuit breaker state transitions
