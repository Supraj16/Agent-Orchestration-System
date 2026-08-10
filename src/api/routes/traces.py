from __future__ import annotations

from fastapi import APIRouter

from orchestrator.observability.query import get_aggregate_cost_stats, get_task_cost_summary, get_trace_tree

router = APIRouter(tags=["traces"])


@router.get("/traces/{task_id}")
def get_trace(task_id: str):
    return get_trace_tree(task_id)


@router.get("/traces/{task_id}/cost")
def get_cost(task_id: str):
    return get_task_cost_summary(task_id)


@router.get("/costs/summary")
def get_cost_summary(limit_tasks: int = 200):
    return get_aggregate_cost_stats(limit_tasks=limit_tasks)
