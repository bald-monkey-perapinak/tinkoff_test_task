# Vacancy Agent — AI-агент для поиска стажировок/вакансий

Telegram Mini App с AI-анализом вакансий на базе FastAPI + React + Groq API.

## Архитектура

```
Telegram Mini App (React + @twa-dev/sdk)
        ↕
FastAPI Backend → hh.ru API (публичный)
        ↕
SQLite (избранное, подписки)   Groq API (LLM анализ)
        ↕
Telegram Bot API (уведомления)
```

### Агентный pipeline

```
analyze_with_llm()
    │
    ├─ GROQ доступен? ──нет──> _run_hybrid() [rule-based через ScoreCalculator]
    │
    └─ да
         │
         ├─ Кэш есть? ──да──> вернуть кэш
         │
         └─ нет ──> VacancyAgent._run_llm_only()
                       │
                       ├─ _plan() — LLM создаёт план поиска
                       │           (если не удалось → fallback на hybrid)
                       │
                       └─ _execute() loop:
                            ├─ LLM решает: search / reflect / finalize
                            ├─ Принудительный reflection gate каждые 2 поиска
                            └─ finalize только через explicit tool call модели
```

## Быстрый старт

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# (опционально) создайте .env файл:
# GROQ_API_KEY=gsk_...    — ключ groq.com для AI-анализа
# TELEGRAM_BOT_TOKEN=...  — токен Telegram-бота (через @BotFather)

uvicorn main:app --reload --port 8000
```

### 2. Frontend (локальная разработка)

```bash
cd frontend
npm install
npm run dev
```

Откройте http://localhost:5173 в браузере. Приложение работает и как standalone web app.

### 3. Telegram Mini App

#### Настройка бота
1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота
3. Создайте Web App: `/newapp`
4. Выберите бота → введите название приложения
5. Укажите URL: `https://your-domain.com`
6. Загрузите логотип (512x512) и миниатюру (128x128)

#### Деплой
```bash
# Соберите фронтенд
cd frontend
npm run build

# Скопируйте dist/ на хостинг (Vercel, Netlify, Railway, etc.)
# Убедитесь, что backend доступен по HTTPS
```

#### .env для продакшена
```
GROQ_API_KEY=gsk_...
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_WEBAPP_URL=https://your-domain.com
```

#### Открытие Mini App
- Через меню бота: `/start` → кнопка Menu → Web App
- Через inline-кнопку:
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
keyboard = [[InlineKeyboardButton("Открыть", web_app=WebAppInfo(url="https://your-domain.com"))]]
```

## Как пользоваться ботом

### Поиск вакансий

1. На вкладке **«Поиск»** введите должность — например, `junior python developer`
2. Укажите город (автодополнение из справочника hh.ru)
3. Задайте фильтры:
   - **Зарплата от** — минимальная сумма в рублях
   - **Формат** — удалёнка / полный день / гибкий
   - **Опыт** — без опыта / 1–3 года / 3–6 лет
   - **Только удалёнка** — чекбокс
4. Нажмите **«Найти вакансии»**
5. Просматривайте карточки, добавляйте в избранное (★)
6. Нажмите **«AI-проанализировать»** внизу экрана для оценки

### AI-анализ

1. Перейдите на вкладку **«AI-анализ»**
2. Нажмите **«AI-проанализировать вакансии»**
3. Получите топ-5 вакансий с оценкой соответствия (1–10) и объяснениями:
   - Почему подходит
   - Что смущает
4. Скачайте отчёт: **.md** / **.csv** / **.json**

### Загрузка своих вакансий

1. Перейдите на вкладку **«Загрузка»**
2. Подготовьте файл формата JSON или CSV (см. [пример](data/sample_vacancies.json))
3. Перетащите файл в зону загрузки или нажмите для выбора
4. Вакансии появятся на вкладке «Поиск» — можно анализировать

### Подписки на новые вакансии

1. Настройте фильтры на вкладке **«Поиск»** (должность, город, зарплата)
2. Перейдите на **«Уведомления»**
3. Нажмите **«Создать подписку по текущим фильтрам»**
4. Бот будет проверять hh.ru каждые 5 минут и присылать новые вакансии в Telegram

> Требуется настроенный Telegram-бот (токен через @BotFather) и переменная `TELEGRAM_BOT_TOKEN` в `.env`

### CLI (без веб-интерфейса)

```bash
cd backend

# Интерактивный ввод критериев
python cli.py --file ../data/sample_vacancies.json

# С файлом критериев
python cli.py --file vacancies.json --criteria criteria.md --output report.md
```

Формат `criteria.md`:
```markdown
- Направление: Python
- Город: Москва
- Только удалёнка: да
- Минимальная зарплата: 80000
- Уровень: без опыта
- Навыки: Python, FastAPI, SQL
- Дата публикации от: 2026-06-01
```

## Пример входных данных

> Полный пример: [`data/sample_vacancies.json`](data/sample_vacancies.json)
> Пример отчёта: [`data/sample_report.md`](data/sample_report.md)

### vacancies.json
```json
[
  {
    "title": "Junior Python Developer",
    "company": "Тинькофф",
    "city": "Москва",
    "salary": "от 80 000 ₽",
    "salary_from": 80000,
    "schedule": "гибрид",
    "experience": "без опыта",
    "skills": ["Python", "SQL", "Git"],
    "url": "https://hh.ru/vacancy/12345",
    "description": "Разработка внутренних сервисов"
  }
]
```

## Пример результата

### AI-анализ top-5
```
🥇 Junior Python Developer — Тинькофф
   Соответствие: 9/10
   Почему подходит: Python в стеке, зарплата выше порога, крупная компания
   Что смущает: Гибридный формат — 2 дня в офисе
   🔗 Открыть вакансию →

🥈 Стажёр Backend-разработчик — Яндекс
   Соответствие: 8/10
   Почему подходит: Полная удалёнка, Python в стеке, менторство
   Что смущает: Зарплата на нижней границе
```

## API Endpoints

| Method | Path | Описание |
|--------|------|----------|
| GET | `/api/search` | Поиск вакансий через hh.ru API |
| POST | `/api/upload` | Загрузка CSV/JSON файла (с проверкой расширения) |
| POST | `/api/analyze` | AI-анализ по критериям (Groq) |
| GET | `/api/report` | Markdown-отчёт |
| GET | `/api/favorites` | Список избранного |
| POST | `/api/favorites` | Добавить в избранное |
| DELETE | `/api/favorites/{id}` | Убрать из избранного |
| GET | `/api/subscriptions` | Список подписок |
| POST | `/api/subscribe` | Создать подписку |
| DELETE | `/api/subscribe/{id}` | Удалить подписку |
| GET | `/api/areas?q=` | Автокомплит городов |
| GET | `/api/roles?q=` | Автокомплит сфер |
| GET | `/api/health/live` | Liveness probe |
| GET | `/api/health/ready` | Readiness probe (БД, circuit breaker) |

> FastAPI автоматически генерирует интерактивную документацию API: Swagger UI доступен по адресу `/docs`, ReDoc — по `/redoc`.

## Надёжность и безопасность

- **Единый scoring** — вся оценка вакансий проходит через `ScoreCalculator` (scorer.py) с весовыми коэффициентами. Нет дублирования логики.
- **Prompt sanitization** — защита от injection: фильтрация HTML, JS-ссылок, инъекций в LLM-промпт
- **Retry с exponential backoff** — Groq API (3 попытки, задержка 1→2→4с) и hh.ru API (3 попытки + respect Retry-After при HTTP 429)
- **Кэширование анализа** — SHA-256 hash от (вакансии + критерии), повторный запрос отдаёт кэш без обращения к LLM
- **Rule-based fallback** — при отсутствии Groq API-ключа или срабатывании circuit breaker анализ работает через `ScoreCalculator`
- **Фильтр по дате публикации** — `date_from` в критериях исключает старые вакансии до оценки
- **Mock-fallback для hh.ru** — при недоступности API загружаются данные из `data/sample_vacancies.json`
- **CSV-injection protection** — экранирование `=`, `+`, `-`, `@` в начале CSV-полей
- **Circuit breaker** — автоматическое отключение при ошибках Groq/hh.ru с последующим восстановлением

## Прокси для hh.ru

hh.ru может блокировать IP при частых запросах. Приложение поддерживает ротацию прокси:

1. **Один прокси:** `HH_PROXY=http://proxy:port`
2. **Ротация из файла:** `HH_PROXY_LIST=data/proxies.txt` (по одному прокси на строку)
3. **Без прокси:** приложение работает напрямую; при блокировке — fallback на mock-данные

**Уровни отказоустойчивости:** реальный API → ротация прокси → circuit breaker → mock-данные.

## Стек

- **Backend**: FastAPI, Python 3.11+, httpx, aiosqlite, groq
- **Frontend**: React 18, TypeScript, Vite, `@twa-dev/sdk` (Telegram Web App)
- **LLM**: Groq API (Llama 3.3 70B)
- **Данные**: hh.ru API (публичный)

## Ограничения

- **hh.ru API**: публичный, лимит ~200 req/мин, не требует ключа
- **Groq**: бесплатный ключ groq.com, без ключа — rule-based fallback
- **Telegram Bot**: опционально, нужен BotFather для создания бота
- **SQLite**: для прототипа
- **Деплой**: Mini App требует HTTPS (Vercel, Netlify, Railway)

**hh.ru API и ToS:** Используется только официальный публичный API hh.ru без авторизации. Переменные `HH_PROXY`/`HH_PROXY_LIST` предназначены исключительно для отказоустойчивости при сетевых блокировках IP, а **не** для обхода rate-limit или антибот защиты. При недоступности hh.ru приложение полностью работает на mock-данных (fallback).
