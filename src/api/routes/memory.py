from __future__ import annotations

from fastapi import APIRouter

from orchestrator.memory.long_term import delete_user_memories, list_user_memories

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/{user_id}")
def get_memories(user_id: str):
    return list_user_memories(user_id)


@router.delete("/{user_id}")
def delete_memories(user_id: str):
    return {"deleted": delete_user_memories(user_id)}
