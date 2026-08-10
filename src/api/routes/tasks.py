from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.tasks import run_orchestration
from orchestrator.db.task_repo import get_task
from orchestrator.observability.query import list_recent_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    user_request: str
    user_id: str = "demo-user"
    force_review: bool = False


class CreateTaskResponse(BaseModel):
    task_id: str


@router.post("", response_model=CreateTaskResponse)
def create_task(payload: CreateTaskRequest) -> CreateTaskResponse:
    task_id = str(uuid.uuid4())
    run_orchestration.delay(task_id, payload.user_request, payload.user_id, payload.force_review)
    return CreateTaskResponse(task_id=task_id)


@router.get("")
def list_tasks(limit: int = 50):
    return list_recent_tasks(limit=limit)


@router.get("/{task_id}")
def get_task_detail(task_id: str):
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
