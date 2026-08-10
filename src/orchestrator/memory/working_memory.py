"""Shared, per-task working memory in Redis: the current plan, completed subtask outputs, and
error log. Scoped to a single task and cleared when the task finishes. This is intentionally
separate from LangGraph's own checkpointed state — it's the fast, simple, cross-process-readable
view of "what's happening right now" that a live dashboard or another worker could poll without
touching the checkpoint DB.
"""
from __future__ import annotations

import json

from orchestrator.memory.redis_client import get_redis

TTL_SECONDS = 60 * 60 * 6  # working memory for an abandoned/crashed task self-expires after 6h


def _key(task_id: str) -> str:
    return f"working_memory:{task_id}"


def set_plan(task_id: str, plan: dict) -> None:
    r = get_redis()
    r.hset(_key(task_id), "plan", json.dumps(plan))
    r.expire(_key(task_id), TTL_SECONDS)


def add_subtask_result(task_id: str, subtask_id: str, result: dict) -> None:
    r = get_redis()
    r.hset(_key(task_id), f"result:{subtask_id}", json.dumps(result))
    r.expire(_key(task_id), TTL_SECONDS)


def add_error(task_id: str, message: str) -> None:
    r = get_redis()
    r.rpush(f"{_key(task_id)}:errors", message)
    r.expire(f"{_key(task_id)}:errors", TTL_SECONDS)


def get_snapshot(task_id: str) -> dict:
    r = get_redis()
    raw = r.hgetall(_key(task_id))
    errors = r.lrange(f"{_key(task_id)}:errors", 0, -1)
    return {k: json.loads(v) for k, v in raw.items()} | {"errors": errors}


def clear(task_id: str) -> None:
    r = get_redis()
    r.delete(_key(task_id), f"{_key(task_id)}:errors")
