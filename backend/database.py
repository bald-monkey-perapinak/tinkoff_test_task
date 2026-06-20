import json
import logging
import time

import aiosqlite
from config import ANALYSIS_CACHE_TTL, DB_PATH, MAX_SESSION_PAYLOAD_BYTES, SESSION_TTL_SECONDS
from models import AgentMemoryEntry, Favorite, Subscription, Vacancy

logger = logging.getLogger(__name__)


async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    vacancy_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    url TEXT DEFAULT '',
                    UNIQUE(chat_id, vacancy_id)
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL,
                    criteria_hash TEXT NOT NULL,
                    results_summary TEXT NOT NULL,
                    top_score INTEGER DEFAULT 0,
                    reflection TEXT DEFAULT '',
                    created_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    args_json TEXT DEFAULT '{}',
                    result_summary TEXT DEFAULT '',
                    quality_score INTEGER DEFAULT 5,
                    criteria_hash TEXT DEFAULT '',
                    reflection TEXT DEFAULT '',
                    created_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_traces (
                    trace_id TEXT PRIMARY KEY,
                    user_key TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    reasoning_chain TEXT DEFAULT '[]',
                    tool_calls_json TEXT DEFAULT '[]',
                    total_duration_ms INTEGER DEFAULT 0,
                    quality_score REAL DEFAULT 0.0,
                    created_at REAL NOT NULL
                )
            """)
            await db.commit()
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_analysis_cache_created_at ON analysis_cache(created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_agent_memory_user_key ON agent_memory(user_key)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_episodic_user_key ON agent_episodic_memory(user_key)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_episodic_action ON agent_episodic_memory(action)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_traces_user_key ON agent_traces(user_key)")
            await db.commit()
            logger.info("Database initialized with WAL mode")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def add_favorite(fav: Favorite):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO favorites (chat_id, vacancy_id, title, company, url) VALUES (?, ?, ?, ?, ?)",
                (fav.chat_id, fav.vacancy_id, fav.title, fav.company, fav.url)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to add favorite: {e}")
        raise


async def remove_favorite(chat_id: int, vacancy_id: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM favorites WHERE chat_id = ? AND vacancy_id = ?", (chat_id, vacancy_id))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to remove favorite: {e}")
        raise


async def get_favorites(chat_id: int) -> list[Favorite]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM favorites WHERE chat_id = ? ORDER BY id DESC", (chat_id,))
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


async def remove_subscription(chat_id: int, sub_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM subscriptions WHERE id = ? AND chat_id = ?", (sub_id, chat_id))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to remove subscription: {e}")
        raise


async def get_active_subscriptions(chat_id: int | None = None) -> list[Subscription]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if chat_id is not None:
                cursor = await db.execute("SELECT * FROM subscriptions WHERE is_active = 1 AND chat_id = ?", (chat_id,))
            else:
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


async def batch_is_vacancy_seen(chat_id: int, vacancy_ids: list[str]) -> set[str]:
    if not vacancy_ids:
        return set()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            placeholders = ",".join("?" * len(vacancy_ids))
            cursor = await db.execute(
                f"SELECT vacancy_id FROM seen_vacancies WHERE chat_id = ? AND vacancy_id IN ({placeholders})",
                (chat_id, *vacancy_ids),
            )
            return {row[0] for row in await cursor.fetchall()}
    except Exception as e:
        logger.error(f"Failed to batch check seen vacancies: {e}")
        return set()


async def batch_mark_vacancies_seen(chat_id: int, vacancy_ids: list[str]):
    if not vacancy_ids:
        return
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executemany(
                "INSERT OR IGNORE INTO seen_vacancies (chat_id, vacancy_id) VALUES (?, ?)",
                [(chat_id, vid) for vid in vacancy_ids],
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to batch mark vacancies seen: {e}")


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


async def save_agent_memory(entry: AgentMemoryEntry):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO agent_memory (user_key, criteria_hash, results_summary, top_score, reflection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (entry.user_key, entry.criteria_hash, entry.results_summary, entry.top_score, entry.reflection, entry.created_at),
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to save agent memory: {e}")


async def get_agent_memory(user_key: str, limit: int = 10) -> list[AgentMemoryEntry]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM agent_memory WHERE user_key = ? ORDER BY created_at DESC LIMIT ?",
                (user_key, limit),
            )
            rows = await cursor.fetchall()
            return [AgentMemoryEntry(**dict(row)) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get agent memory: {e}")
        return []


async def get_similar_memory_by_criteria(user_key: str, criteria_hash: str) -> AgentMemoryEntry | None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM agent_memory WHERE user_key = ? AND criteria_hash = ? ORDER BY created_at DESC LIMIT 1",
                (user_key, criteria_hash),
            )
            row = await cursor.fetchone()
            return AgentMemoryEntry(**dict(row)) if row else None
    except Exception as e:
        logger.error(f"Failed to get agent memory by criteria: {e}")
        return None


async def save_agent_trace(trace_id: str, user_key: str, steps_json: str,
                           reasoning_chain: str, tool_calls_json: str,
                           total_duration_ms: int, quality_score: float):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO agent_traces
                   (trace_id, user_key, steps_json, reasoning_chain, tool_calls_json, total_duration_ms, quality_score, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (trace_id, user_key, steps_json, reasoning_chain, tool_calls_json,
                 total_duration_ms, quality_score, time.time()),
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to save agent trace: {e}")


async def get_agent_trace(trace_id: str) -> dict | None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM agent_traces WHERE trace_id = ?", (trace_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)
    except Exception as e:
        logger.error(f"Failed to get agent trace: {e}")
        return None


async def get_agent_traces(user_key: str, limit: int = 10) -> list[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM agent_traces WHERE user_key = ? ORDER BY created_at DESC LIMIT ?",
                (user_key, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get agent traces: {e}")
        return []
