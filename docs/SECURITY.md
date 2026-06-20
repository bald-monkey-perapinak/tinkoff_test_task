# Security Model

Проект считает недоверенными все внешние данные: `vacancies.csv/json`, `criteria.md`, ответы hh.ru, ответы LLM и текст вакансий.

## Входные файлы

- CLI и API принимают только CSV/JSON.
- Размер upload ограничен `MAX_UPLOAD_SIZE`.
- CSV без заголовков, CSV с чрезмерным числом колонок и битый JSON не валят приложение.
- CSV обрабатывается с лимитом строк, JSON - с лимитом элементов и вложенности.
- Вакансии без минимальной идентичности (`id`, `title` или `url`) пропускаются.
- Дубли удаляются до анализа.

## Prompt Injection

- Все поля вакансий и критериев проходят sanitization перед попаданием в prompt.
- Из текста удаляются типовые инструкции вида `ignore previous instructions`, `system prompt`, `reveal token`.
- Описание вакансии обрезается перед передачей в LLM.
- В prompt явно указано, что вакансии - пользовательский контент, а инструкции внутри них нужно игнорировать.
- Агент работает только с whitelist tools, без shell/file-system/tool execution из LLM.

## Валидация LLM Output

- `vacancy_id` принимается только из исходного пула вакансий.
- `fit_score` ограничивается диапазоном `1..10`.
- `rank` пересчитывается сервером при некорректных значениях.
- Текстовые поля результата очищаются и ограничиваются по длине.
- При timeout, ошибке LLM или невалидном ответе включается rule-based fallback.

## Отчеты и экспорт

- Markdown-отчет экранирует пользовательский текст.
- `javascript:` и `data:` ссылки не выводятся.
- CSV export защищен от spreadsheet formula injection (`=`, `+`, `-`, `@`, tab, carriage return).
- HTML/script из пользовательского текста не попадает в отчет.

## API и Runtime

- Для внешнего Telegram Mini App проверяется Telegram `initData`.
- На API включены rate limits.
- Внешние вызовы имеют timeout, retry и circuit breaker.
- Клиенту не возвращаются внутренние stack traces.
- Секреты читаются из environment variables и не должны логироваться.

## Agent Memory

- В память агента сохраняются только краткие summary/reflection.
- Сохраняемый и загружаемый memory context проходит sanitization.
- Сырые вакансии, токены, headers и Telegram initData в memory не сохраняются.
