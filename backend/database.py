import aiosqlite
import json
import logging
import time
import asyncio
import shutil
from config import DB_PATH, SESSION_TTL_SECONDS
from models import Favorite, Subscription, Vacancy

logger = logging.getLogger(__name__)

MAX_SESSION_PAYLOAD_BYTES = 2 * 1024 * 1024  # 2MB


async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vacancy_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    url TEXT DEFAULT ''
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    query TEXT DEFAULT '',
                    area TEXT,
                    schedule TEXT,
                    min_salary INTEGER,
                    is_active INTEGER DEFAULT 1
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS seen_vacancies (
                    chat_id INTEGER NOT NULL,
                    vacancy_id TEXT NOT NULL,
                    PRIMARY KEY (chat_id, vacancy_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    vacancies_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    cache_key TEXT PRIMARY KEY,
                    results_json TEXT NOT NULL,
                    report TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            await db.commit()
            logger.info("Database initialized with WAL mode")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def add_favorite(fav: Favorite):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO favorites (vacancy_id, title, company, url) VALUES (?, ?, ?, ?)",
                (fav.vacancy_id, fav.title, fav.company, fav.url)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to add favorite: {e}")
        raise


async def remove_favorite(vacancy_id: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM favorites WHERE vacancy_id = ?", (vacancy_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to remove favorite: {e}")
        raise


async def get_favorites() -> list[Favorite]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM favorites ORDER BY id DESC")
            rows = await cursor.fetchall()
            return [Favorite(**dict(row)) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get favorites: {e}")
        return []


async def add_subscription(sub: Subscription) -> int:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO subscriptions (chat_id, query, area, schedule, min_salary) VALUES (?, ?, ?, ?, ?)",
                (sub.chat_id, sub.query, sub.area, sub.schedule, sub.min_salary)
            )
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to add subscription: {e}")
        raise


async def remove_subscription(sub_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to remove subscription: {e}")
        raise


async def get_active_subscriptions() -> list[Subscription]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM subscriptions WHERE is_active = 1")
            rows = await cursor.fetchall()
            return [Subscription(**dict(row)) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get subscriptions: {e}")
        return []


async def is_vacancy_seen(chat_id: int, vacancy_id: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM seen_vacancies WHERE chat_id = ? AND vacancy_id = ?",
                (chat_id, vacancy_id)
            )
            return await cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check seen vacancy: {e}")
        return False


async def mark_vacancy_seen(chat_id: int, vacancy_id: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO seen_vacancies (chat_id, vacancy_id) VALUES (?, ?)",
                (chat_id, vacancy_id)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to mark vacancy seen: {e}")


async def save_session(session_id: str, vacancies: list, created_at: float):
    try:
        vacancies_json = json.dumps([v.model_dump() for v in vacancies])
        if len(vacancies_json.encode("utf-8")) > MAX_SESSION_PAYLOAD_BYTES:
            logger.error(f"Session payload too large: {len(vacancies_json)} bytes, rejecting")
            raise ValueError("Session payload exceeds size limit")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sessions (session_id, vacancies_json, created_at) VALUES (?, ?, ?)",
                (session_id, vacancies_json, created_at),
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        raise


async def get_session(session_id: str) -> dict | None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT vacancies_json, created_at FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            vacancies = [Vacancy.model_validate(v) for v in json.loads(row[0])]
            return {"vacancies": vacancies, "created_at": row[1]}
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        return None


async def delete_session(session_id: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")


async def cleanup_expired_sessions():
    try:
        cutoff = time.time() - SESSION_TTL_SECONDS
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")


async def get_all_session_vacancies() -> list[Vacancy]:
    try:
        cutoff = time.time() - SESSION_TTL_SECONDS
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT vacancies_json FROM sessions WHERE created_at >= ?",
                (cutoff,),
            )
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                result.extend(Vacancy.model_validate(v) for v in json.loads(row[0]))
            return result
    except Exception as e:
        logger.error(f"Failed to get all session vacancies: {e}")
        return []


ANALYSIS_CACHE_TTL = 3600  # 1 hour


async def get_analysis_cache(cache_key: str) -> dict | None:
    try:
        cutoff = time.time() - ANALYSIS_CACHE_TTL
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT results_json, report FROM analysis_cache WHERE cache_key = ? AND created_at >= ?",
                (cache_key, cutoff),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return {"results": json.loads(row[0]), "report": row[1]}
    except Exception as e:
        logger.error(f"Failed to get analysis cache: {e}")
        return None


async def set_analysis_cache(cache_key: str, results_json: str, report: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO analysis_cache (cache_key, results_json, report, created_at) VALUES (?, ?, ?, ?)",
                (cache_key, results_json, report, time.time()),
            )
            await db.commit()
            await db.execute("DELETE FROM analysis_cache WHERE created_at < ?", (time.time() - ANALYSIS_CACHE_TTL * 2,))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to set analysis cache: {e}")


async def backup_database():
    try:
        backup_dir = DB_PATH.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"vacancy_bot_{int(time.time())}.db"
        async with aiosqlite.connect(DB_PATH) as source:
            async with aiosqlite.connect(backup_path) as dest:
                await source.backup(dest)
        logger.info(f"Database backed up to {backup_path}")
        for old in sorted(backup_dir.glob("vacancy_bot_*.db"))[:-5]:
            old.unlink()
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
