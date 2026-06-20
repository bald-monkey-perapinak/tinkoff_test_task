# ADR-001: Выбор технологического стека

## Статус
Принято

## Контекст
Telegram Mini App для AI-поиска вакансий. Нужно: backend API, frontend UI, интеграция с hh.ru API, LLM-анализ, Telegram бот для уведомлений.

## Решения

### Backend: FastAPI (Python 3.11+)
**Почему FastAPI, а не Flask/Django:**
- Нативная async/await поддержка — критично для интеграции с внешними API (hh.ru, Groq, Telegram)
- Автоматическая генерация OpenAPI-спецификации
- Pydantic валидация из коробки
- Высокая производительность на уровне Go/Node для I/O-bound задач

**Почему Python, а не Node.js/Go:**
- Groq SDK доступен на Python
- Библиотеки для работы с hh.ru API (хотя httpx — универсален)
- Быстрота прототипирования

### База данных: SQLite (aiosqlite)
**Почему SQLite, а не PostgreSQL/Redis:**
- Zero-конфигурация — нет отдельного сервера
- Async-доступ через aiosqlite
- Достаточно для single-user/low-traffic сценария
- WAL mode для конкурентного доступа

**Когда мигрировать:**
- PostgreSQL — при необходимости масштабирования на нескольких пользователей
- Redis — при необходимости кеширования сессий и rate limiting в распределённой среде

### LLM: Groq (Llama 3.3 70B)
**Почему Groq, а не OpenAI/Anthropic:**
- Бесплатный tier для тестовых задач
- Высокая скорость инференса (LPU-чипы)
- Llama 3.3 70B — хорошее качество для карьерного консалтинга на русском

**Fallback:**
- Rule-based scorer без API-ключа — garantия работы в любом окружении

### Frontend: React 18 + TypeScript + Vite
**Почему React, а не Vue/Svelte:**
- @twa-dev/sdk лучше поддерживает React
- TypeScript — строгая типизация для API-контрактов
- Vite — быстрый dev server с HMR

### Telegram Integration: @twa-dev/sdk
- Управление MainButton, BackButton, haptic feedback
- Темизация через themeParams
- Safe area insets для мобильных устройств

## Компромиссы

| Выбор | Плюс | Минус |
|-------|------|-------|
| SQLite | Zero-config, async | Нет horizontal scaling |
| In-memory session store → SQLite | Простота → Persistence | Нужна миграция |
| Groq бесплатный tier | Бесплатно | Rate limits, возможны простои |
| FastAPI | Скорость разработки | Меньше экосистема, чем Django |
| React | @twa-dev/sdk поддерживает | Больше boilerplate, чем Vue |

## Follow-up Decisions
- [ ] Миграция на PostgreSQL при >100 concurrent users
- [ ] Redis для кеширования сессий при масштабировании
- [ ] OpenAI/Anthropic как fallback если Groq недоступен
