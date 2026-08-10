from __future__ import annotations

from orchestrator.db.models import Task
from orchestrator.db.session import session_scope


def upsert_task(task_id: str, **fields) -> None:
    with session_scope() as session:
        task = session.get(Task, task_id)
        if task is None:
            task = Task(id=task_id)
            session.add(task)
        for key, value in fields.items():
            if value is not None:
                setattr(task, key, value)


def get_task(task_id: str) -> dict | None:
    with session_scope() as session:
        task = session.get(Task, task_id)
        if task is None:
            return None
        return {
            "id": task.id,
            "user_id": task.user_id,
            "user_request": task.user_request,
            "status": task.status,
            "plan": task.plan,
            "final_output": task.final_output,
            "created_at": task.created_at,
        }
