# ADR-002: Аутентификация через Telegram initData

## Статус
Принято

## Контекст
Telegram Mini App требует аутентификации пользователей для привязки избранного и подписок к конкретному пользователю. Нужно: валидация initData, защита от подделки, isolation в dev mode.

## Решения

### Валидация initData
Telegram WebApp SDK передаёт `initData` — URL-encoded строку с HMAC-SHA256 подписью. Алгоритм:
1. Извлечь `hash` из initData
2. Вычислить `secret_key = HMAC_SHA256("WebAppData", bot_token)`
3. Проверить `HMAC_SHA256(data_to_sign, secret_key) == hash`
4. Проверить `auth_date` — максимум 1 час назад (защита от replay)

Реализация: `backend/auth.py`, функция `validate_telegram_init_data()`.

### Middleware vs Depends
**Выбор:** HTTP middleware (не FastAPI Depends).

**Почему:**
- Валидация нужна на всех `/api/*` маршрутах кроме health
- Middleware применяется автоматически, не нужно добавлять `Depends()` к каждому эндпоинту
- Middleware может вернуть JSONResponse с ошибкой до вызова handler'а

**Компромисс:** middleware не имеет типобезопасности FastAPI Depends, но для auth это приемлемо.

### Dev mode bypass
На localhost (`host` содержит `localhost` или `127.0.0.1`) валидация пропускается. Chat ID генерируется по хешу `client_host:user_agent` — уникальный для каждого браузера, но не привязан к Telegram.

### Защита subscription/favorite endpoints
- `chat_id` берётся из auth middleware, а не из тела запроса
- `api_subscribe` проверяет соответствие `sub.chat_id` с auth `chat_id`
- `api_add_favorite` перезаписывает `fav.chat_id` из auth

## Компромиссы

| Выбор | Плюс | Минус |
|-------|------|-------|
| Middleware | Автоматически для всех маршрутов | Меньше контроля per-route |
| Dev mode bypass | Удобно для разработки | Нет изоляции пользователей в dev |
| HMAC validation | Стандарт Telegram, timing-safe | Нужен bot token |

## Follow-up Decisions
- [ ] Rate limiting per chat_id (сейчас per IP через slowapi)
- [ ] Session-based auth для non-Telegram клиентов
