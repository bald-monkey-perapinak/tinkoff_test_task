import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

import aiosqlite
from config import DB_PATH

logger = logging.getLogger(__name__)


@dataclass
class WorkingMemory:
    vacancies: list = field(default_factory=list)
    vacancy_ids: set = field(default_factory=set)
    tool_history: list[dict] = field(default_factory=list)
    plan: dict | None = None
    plan_step: int = 0
    reflections: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    _created_at: float = field(default_factory=time.time)

    def add_vacancy(self, vacancy) -> bool:
        vid = vacancy.id if hasattr(vacancy, "id") else str(vacancy.get("id", ""))
        if vid in self.vacancy_ids:
            return False
        self.vacancy_ids.add(vid)
        self.vacancies.append(vacancy)
        return True

    def add_vacancies(self, vacancies: list) -> int:
        added = 0
        for v in vacancies:
            if self.add_vacancy(v):
                added += 1
        return added

    def log_tool_call(self, tool_name: str, args: dict, result: dict, duration_ms: int):
        self.tool_history.append({
            "tool": tool_name,
            "args": args,
            "result_summary": str(result)[:200],
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        })

    def log_decision(self, decision: str, reason: str, context: str = ""):
        self.decisions.append({
            "decision": decision,
            "reason": reason,
            "context": context,
            "timestamp": time.time(),
        })

    def get_stats(self) -> dict:
        return {
            "vacancy_count": len(self.vacancies),
            "tool_calls": len(self.tool_history),
            "reflections": len(self.reflections),
            "decisions": len(self.decisions),
            "age_seconds": int(time.time() - self._created_at),
        }


@dataclass
class EpisodicEntry:
    id: int | None = None
    user_key: str = ""
    action: str = ""
    args: dict = field(default_factory=dict)
    result_summary: str = ""
    quality_score: int = 0
    criteria_hash: str = ""
    reflection: str = ""
    created_at: float = 0.0


class EpisodicMemory:
    def __init__(self):
        self.db_path = DB_PATH

    async def save(self, entry: EpisodicEntry):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT INTO agent_episodic_memory
                       (user_key, action, args_json, result_summary, quality_score, criteria_hash, reflection, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry.user_key,
                        entry.action,
                        json.dumps(entry.args, ensure_ascii=False),
                        entry.result_summary,
                        entry.quality_score,
                        entry.criteria_hash,
                        entry.reflection,
                        entry.created_at or time.time(),
                    ),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save episodic memory: {e}")

    async def get_recent(self, user_key: str, limit: int = 10) -> list[EpisodicEntry]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM agent_episodic_memory WHERE user_key = ? ORDER BY created_at DESC LIMIT ?",
                    (user_key, limit),
                )
                rows = await cursor.fetchall()
                return [self._row_to_entry(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get episodic memory: {e}")
            return []

    async def get_by_action(self, user_key: str, action: str, limit: int = 5) -> list[EpisodicEntry]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM agent_episodic_memory WHERE user_key = ? AND action = ? ORDER BY created_at DESC LIMIT ?",
                    (user_key, action, limit),
                )
                rows = await cursor.fetchall()
                return [self._row_to_entry(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get episodic memory by action: {e}")
            return []

    async def get_patterns(self, user_key: str) -> dict:
        entries = await self.get_recent(user_key, limit=50)
        if not entries:
            return {}
        action_counts = {}
        quality_by_action = {}
        for e in entries:
            action_counts[e.action] = action_counts.get(e.action, 0) + 1
            if e.action not in quality_by_action:
                quality_by_action[e.action] = []
            quality_by_action[e.action].append(e.quality_score)

        patterns = {}
        for action, scores in quality_by_action.items():
            avg = sum(scores) / len(scores) if scores else 0
            patterns[action] = {
                "count": action_counts[action],
                "avg_quality": round(avg, 2),
                "best_quality": max(scores) if scores else 0,
            }
        return patterns

    def _row_to_entry(self, row) -> EpisodicEntry:
        return EpisodicEntry(
            id=row["id"],
            user_key=row["user_key"],
            action=row["action"],
            args=json.loads(row["args_json"]) if row["args_json"] else {},
            result_summary=row["result_summary"],
            quality_score=row["quality_score"],
            criteria_hash=row["criteria_hash"],
            reflection=row["reflection"],
            created_at=row["created_at"],
        )


class SemanticMemory:
    def __init__(self):
        self.db_path = DB_PATH
        self._groq_client = None

    async def _get_groq_client(self):
        if self._groq_client is None:
            from config import GROQ_API_KEY
            if not GROQ_API_KEY:
                return None
            import groq
            self._groq_client = groq.Groq(api_key=GROQ_API_KEY)
        return self._groq_client

    async def get_embedding(self, text: str) -> list[float] | None:
        client = await self._get_groq_client()
        if not client:
            return None
        try:
            response = client.embeddings.create(
                model="llama-3.3-70b-versatile",
                input=text[:2000],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Groq embedding failed: {e}")
            return None

    async def save_vacancy_embedding(self, vacancy_id: str, embedding: list[float], criteria_hash: str = ""):
        try:
            import numpy as np
            blob = np.array(embedding, dtype=np.float32).tobytes()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO agent_semantic_memory (vacancy_id, embedding, criteria_hash, created_at) VALUES (?, ?, ?, ?)",
                    (vacancy_id, blob, criteria_hash, time.time()),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save vacancy embedding: {e}")

    async def find_similar(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        try:
            import numpy as np
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT vacancy_id, embedding FROM agent_semantic_memory ORDER BY created_at DESC LIMIT 200"
                )
                rows = await cursor.fetchall()

            if not rows:
                return []

            query_vec = np.array(query_embedding, dtype=np.float32)
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                return []

            scores = []
            for vid, blob in rows:
                try:
                    vec = np.frombuffer(blob, dtype=np.float32)
                    vec_norm = np.linalg.norm(vec)
                    if vec_norm == 0:
                        continue
                    cosine = float(np.dot(query_vec, vec) / (query_norm * vec_norm))
                    scores.append((vid, cosine))
                except Exception:
                    continue

            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]
        except Exception as e:
            logger.error(f"Failed to find similar vacancies: {e}")
            return []

    async def cleanup(self, max_age_days: int = 30):
        try:
            cutoff = time.time() - (max_age_days * 86400)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM agent_semantic_memory WHERE created_at < ?", (cutoff,))
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup semantic memory: {e}")


class MemoryManager:
    def __init__(self):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()

    def reset_working(self):
        self.working = WorkingMemory()

    async def record_action(self, user_key: str, action: str, args: dict,
                            result_summary: str, quality_score: int = 5,
                            criteria_hash: str = "", reflection: str = ""):
        entry = EpisodicEntry(
            user_key=user_key,
            action=action,
            args=args,
            result_summary=result_summary[:500],
            quality_score=quality_score,
            criteria_hash=criteria_hash,
            reflection=reflection[:500],
            created_at=time.time(),
        )
        await self.episodic.save(entry)

    async def get_action_history(self, user_key: str, action: str) -> list[EpisodicEntry]:
        return await self.episodic.get_by_action(user_key, action)

    async def get_patterns(self, user_key: str) -> dict:
        return await self.episodic.get_patterns(user_key)

    @staticmethod
    def build_criteria_hash(criteria) -> str:
        key_data = {
            "d": criteria.direction,
            "c": criteria.city,
            "r": criteria.remote_only,
            "s": criteria.min_salary,
            "e": criteria.experience_level,
            "k": sorted(criteria.key_skills),
            "df": criteria.date_from or "",
        }
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:32]
