"""Long-term semantic memory: after a task completes, extract a durable summary (what was
asked, what approach worked, tools used, facts discovered, preferences observed), embed it, and
store it in ChromaDB with a mirrored metadata row in Postgres (`memories`) for importance
scoring/decay/consolidation, which operate over SQL rather than vector-store metadata."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from orchestrator.db.models import Memory
from orchestrator.db.session import session_scope
from orchestrator.llm.router import get_model_for_role
from orchestrator.memory.chroma_client import get_memory_collection

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
ACCESS_BOOST = 0.05


class MemoryExtraction(BaseModel):
    what_was_asked: str
    approach_that_worked: str
    tools_used: list[str] = Field(default_factory=list)
    facts_discovered: list[str] = Field(default_factory=list)
    user_preferences_observed: list[str] = Field(default_factory=list)


EXTRACTION_SYSTEM_PROMPT = """You extract a durable memory from a completed agent task, so future
tasks for the same user can be planned better. Be concise and factual; only include
user_preferences_observed if something was genuinely inferable about how this user likes tasks
done (tone, format, tool choice, etc.) — leave it empty otherwise."""


def _render_summary(extraction: MemoryExtraction) -> str:
    lines = [
        f"Request: {extraction.what_was_asked}",
        f"Approach that worked: {extraction.approach_that_worked}",
    ]
    if extraction.tools_used:
        lines.append("Tools used: " + ", ".join(extraction.tools_used))
    if extraction.facts_discovered:
        lines.append("Facts discovered: " + "; ".join(extraction.facts_discovered))
    if extraction.user_preferences_observed:
        lines.append("User preferences: " + "; ".join(extraction.user_preferences_observed))
    return "\n".join(lines)


def extract_and_store_memory(
    *, task_id: str, user_id: str, user_request: str, tool_calls: list[str], final_output: str
) -> str | None:
    """Best-effort: a failure here must never break a task that already completed successfully."""
    try:
        model = get_model_for_role("supervisor").with_structured_output(MemoryExtraction)
        human = (
            f"User request: {user_request}\n\n"
            f"Tools used across the task: {', '.join(tool_calls) or 'none'}\n\n"
            f"Final delivered output:\n{final_output}"
        )
        extraction: MemoryExtraction = model.invoke(
            [SystemMessage(content=EXTRACTION_SYSTEM_PROMPT), HumanMessage(content=human)]
        )
        summary = _render_summary(extraction)
        memory_id = str(uuid.uuid4())

        with session_scope() as session:
            session.add(Memory(id=memory_id, task_id=task_id, user_id=user_id, summary=summary))

        get_memory_collection().add(
            ids=[memory_id], documents=[summary], metadatas=[{"user_id": user_id, "task_id": task_id}]
        )
        return memory_id
    except Exception:
        logger.exception("Failed to extract/store long-term memory for task=%s", task_id)
        return None


def query_similar_memories(user_id: str, query_text: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Semantic search over this user's memories. Retrieval counts as access — bumps
    access_count/importance/last_accessed, per the "frequently accessed -> more important"
    importance model."""
    try:
        results = get_memory_collection().query(
            query_texts=[query_text], n_results=top_k, where={"user_id": user_id}
        )
    except Exception:
        logger.exception("Memory retrieval failed; planning will proceed without memory context.")
        return []

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    if not ids:
        return []

    memories: list[dict] = []
    with session_scope() as session:
        for mem_id, doc in zip(ids, documents):
            row = session.get(Memory, mem_id)
            if row is None:
                continue
            row.access_count += 1
            row.importance_score = min(1.0, row.importance_score + ACCESS_BOOST)
            row.last_accessed_at = datetime.now(timezone.utc)
            memories.append({"id": mem_id, "summary": doc, "importance": row.importance_score})
    return memories


def list_user_memories(user_id: str) -> list[dict]:
    """All memories for a user, most important first. Backs the memory dashboard."""
    with session_scope() as session:
        rows = (
            session.query(Memory)
            .filter(Memory.user_id == user_id)
            .order_by(Memory.importance_score.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "summary": row.summary,
                "importance_score": row.importance_score,
                "access_count": row.access_count,
                "created_at": row.created_at,
                "last_accessed_at": row.last_accessed_at,
            }
            for row in rows
        ]


def delete_user_memories(user_id: str) -> int:
    """Deletes every memory for a user from both Postgres and Chroma. Used for user data
    deletion requests; becomes a DELETE endpoint once the API layer exists (milestone 6)."""
    with session_scope() as session:
        rows = session.query(Memory).filter(Memory.user_id == user_id).all()
        ids = [row.id for row in rows]
        for row in rows:
            session.delete(row)

    if ids:
        get_memory_collection().delete(ids=ids)
    return len(ids)
