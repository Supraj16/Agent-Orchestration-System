"""The Celery task that actually runs a task's graph. Celery provides async, horizontally
scalable execution at this top level; parallelism *within* a task (e.g. independent subtasks)
is LangGraph's own concern, not nested Celery tasks -- see the build plan's architecture notes
for why that split is deliberate."""
from __future__ import annotations

from api.celery_app import celery_app
from orchestrator.graph.build_graph import build_graph, initial_state


@celery_app.task(name="run_orchestration")
def run_orchestration(task_id: str, user_request: str, user_id: str, force_review: bool = False) -> dict:
    graph = build_graph()
    config = {"configurable": {"thread_id": task_id}}
    graph.invoke(initial_state(task_id, user_request, user_id, force_review), config=config)
    state = graph.get_state(config)
    return {"paused": bool(state.next), "final_output": state.values.get("final_output")}
