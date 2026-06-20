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
# Собрайте фронтенд
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

## Использование

### Вкладка «Поиск»
- Введите название должности (например, "junior python developer")
- Укажите город (autocomplete из справочника hh.ru)
- Фильтры: зарплата от, формат (удалёнка/офис/гибрид), опыт
- Нажмите «Найти вакансии» — результаты отображаются карточками
- Добавляйте понравившиеся в избранное (★)
- Кнопка «AI-проанализировать» внизу экрана (Telegram MainButton)

### Вкладка «AI-анализ»
- Нажмите «AI-проанализировать вакансии»
- Получите top-5 с оценкой соответствия (1-10) и объяснениями
- Скачайте Markdown-отчёт
- Кнопка «Назад» (Telegram BackButton) для возврата к поиску

### Вкладка «Загрузка»
- Подготовьте файл `vacancies.json` или `vacancies.csv`
- Перетащите или выберите файл
- Данные загружаются для анализа

### Вкладка «Уведомления»
- Настройте фильтры поиска на вкладке «Поиск»
- Перейдите на «Уведомления»
- Нажмите «Создать подписку по текущим фильтрам»
- Бот будет присылать новые вакансии (требуется настроенный Telegram-бот)

## Пример входных данных

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

### Markdown-отчёт (скачивается)
```markdown
# Отчёт по анализу вакансий
Дата: 2026-06-19
Вакансий проанализировано: 20
В результат топ: 5

## 🥇 Junior Python Developer — Тинькофф
| Параметр | Значение |
|----------|----------|
| Город | Москва |
| Зарплата | от 80 000 ₽ |
| Оценка | 9/10 |
```

## Telegram Web App SDK

Приложение использует `@twa-dev/sdk` для интеграции с Telegram:

| API | Использование |
|-----|---------------|
| `WebApp.ready()` | Уведомление Telegram что app готов |
| `WebApp.expand()` | Развёртывание на весь экран |
| `WebApp.themeParams` | Автоматическая подстройка под тему |
| `WebApp.MainButton` | Основная кнопка внизу экрана |
| `WebApp.BackButton` | Кнопка «Назад» |
| `WebApp.HapticFeedback` | Вибрация при действиях |
| `WebApp.openLink()` | Открытие ссылок в in-app браузере |
| `WebApp.showAlert()` | Нативные alert-диалоги |
| `WebApp.safeAreaInset` | Безопасные зоны (Dynamic Island, notch) |

## API Endpoints

| Method | Path | Описание |
|--------|------|----------|
| GET | `/api/search` | Поиск вакансий через hh.ru API |
| POST | `/api/upload` | Загрузка CSV/JSON файла |
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

## Ограничения

- **hh.ru API**: публичный, лимит ~200 req/мин, не требует ключа
- **Groq**: бесплатный ключ groq.com, без ключа — rule-based fallback
- **Telegram Bot**: опционально, нужен BotFather для создания бота
- **SQLite**: для прототипа
- **Деплой**: Mini App требует HTTPS (Vercel, Netlify, Railway)

## Стек

- **Backend**: FastAPI, Python 3.11+, httpx, aiosqlite, groq
- **Frontend**: React 18, TypeScript, Vite, `@twa-dev/sdk` (Telegram Web App)
- **LLM**: Groq API (Llama 3.3 70B)
- **Данные**: hh.ru API (публичный)
