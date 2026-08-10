"""Memory maintenance: importance decay (memories quietly lose relevance if unused, and expire
below a threshold) and consolidation (near-duplicate memories for the same user get merged into
one higher-level summary). Runs as a standalone callable for now, tested via
`scripts/run_memory_maintenance.py`; becomes a Celery-beat periodic task once Celery is wired up
in milestone 6 — the logic doesn't change, only what schedules it.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from orchestrator.db.models import Memory
from orchestrator.db.session import session_scope
from orchestrator.llm.router import get_model_for_role
from orchestrator.memory.chroma_client import get_memory_collection

logger = logging.getLogger(__name__)

DECAY_RATE_PER_DAY = 0.97
EXPIRATION_THRESHOLD = 0.05
CONSOLIDATION_DISTANCE_THRESHOLD = 0.08  # cosine distance; lower = more similar
CONSOLIDATION_NEIGHBORS = 5


def apply_decay() -> tuple[int, int]:
    """Returns (updated_count, expired_count)."""
    now = datetime.now(timezone.utc)
    expired_ids: list[str] = []
    updated = 0

    with session_scope() as session:
        for row in session.query(Memory).all():
            days_idle = max((now - row.last_accessed_at).total_seconds() / 86400, 0)
            row.importance_score *= DECAY_RATE_PER_DAY**days_idle
            if row.importance_score < EXPIRATION_THRESHOLD:
                expired_ids.append(row.id)
                session.delete(row)
            else:
                updated += 1

    if expired_ids:
        get_memory_collection().delete(ids=expired_ids)
    return updated, len(expired_ids)


def _merge_summaries(summaries: list[str]) -> str:
    model = get_model_for_role("supervisor")
    prompt = (
        "The following are separate memory entries about very similar past tasks for the same "
        "user. Merge them into one consolidated memory that captures the recurring pattern "
        "(what's typically asked, what approach works, tools used, consistently observed user "
        "preferences) without redundant repetition.\n\n" + "\n\n---\n\n".join(summaries)
    )
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content


def consolidate_memories(user_id: str) -> int:
    """Returns the number of consolidation merges performed for this user."""
    collection = get_memory_collection()
    merges = 0

    with session_scope() as session:
        rows = session.query(Memory).filter(Memory.user_id == user_id).order_by(Memory.created_at).all()
        rows_by_id = {row.id: row for row in rows}
        processed: set[str] = set()

        for row in rows:
            if row.id in processed:
                continue

            results = collection.query(
                query_texts=[row.summary], n_results=CONSOLIDATION_NEIGHBORS, where={"user_id": user_id}
            )
            neighbor_ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]

            group_ids = {row.id}
            for neighbor_id, distance in zip(neighbor_ids, distances):
                if neighbor_id in processed or neighbor_id not in rows_by_id:
                    continue
                if neighbor_id != row.id and distance <= CONSOLIDATION_DISTANCE_THRESHOLD:
                    group_ids.add(neighbor_id)

            if len(group_ids) < 2:
                processed.add(row.id)
                continue

            group_rows = [rows_by_id[gid] for gid in group_ids]
            merged_summary = _merge_summaries([r.summary for r in group_rows])
            new_id = str(uuid.uuid4())
            session.add(
                Memory(
                    id=new_id,
                    user_id=user_id,
                    summary=merged_summary,
                    importance_score=max(r.importance_score for r in group_rows),
                    access_count=sum(r.access_count for r in group_rows),
                )
            )
            for r in group_rows:
                session.delete(r)
                processed.add(r.id)

            collection.delete(ids=list(group_ids))
            collection.add(ids=[new_id], documents=[merged_summary], metadatas=[{"user_id": user_id}])
            merges += 1

    return merges


def run_memory_maintenance() -> dict:
    updated, expired = apply_decay()
    with session_scope() as session:
        user_ids = [row[0] for row in session.query(Memory.user_id).distinct().all()]

    total_merges = 0
    for user_id in user_ids:
        try:
            total_merges += consolidate_memories(user_id)
        except Exception:
            logger.exception("Consolidation failed for user_id=%s", user_id)

    return {"decayed_updated": updated, "expired": expired, "consolidation_merges": total_merges}
