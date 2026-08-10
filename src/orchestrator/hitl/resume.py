"""Resumes a paused task with a human's resolution. Used by both the CLI resolver
(scripts/resolve_approval.py) and the Streamlit Approval Queue page, so there's exactly one
place that knows how to talk to the graph's Command(resume=...) API."""
from __future__ import annotations

from langgraph.types import Command

from orchestrator.graph.build_graph import build_graph


def resume_task(task_id: str, resolution: dict) -> dict:
    graph = build_graph()
    config = {"configurable": {"thread_id": task_id}}
    graph.invoke(Command(resume=resolution), config=config)
    state = graph.get_state(config)
    return {"values": state.values, "paused": bool(state.next)}
