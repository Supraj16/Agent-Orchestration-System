"""Replay/time-travel debugging, built directly on LangGraph's own checkpoint history rather
than a bespoke replay engine -- every graph step is already checkpointed by the Postgres
checkpointer, so "step through a past run" is just reading that history, and "fork with a
modified input" is LangGraph's native update_state() + invoke(None, ...) from an older
checkpoint. Forking re-runs real nodes under the SAME task_id (real side effects, on purpose --
see the Replay UI for why that's the honest choice here)."""
from __future__ import annotations

from orchestrator.graph.build_graph import build_graph


def list_checkpoints(task_id: str) -> list[dict]:
    """Most-recent-first, matching LangGraph's own get_state_history() order."""
    graph = build_graph()
    config = {"configurable": {"thread_id": task_id}}
    checkpoints = []
    for snapshot in graph.get_state_history(config):
        checkpoints.append(
            {
                "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
                "next": list(snapshot.next),
                "values": snapshot.values,
                "created_at": snapshot.created_at,
            }
        )
    return checkpoints


def fork_and_replay(task_id: str, checkpoint_id: str, state_overrides: dict) -> dict:
    """Forks execution from an older checkpoint with the given field overrides applied, then
    resumes. Runs under the same thread_id, so this really re-executes the back half of the
    task (Postgres/Redis/Chroma side effects included) -- that's the honest characterization of
    "replay for debugging" in a system whose nodes aren't pure functions."""
    graph = build_graph()
    source_config = {"configurable": {"thread_id": task_id, "checkpoint_id": checkpoint_id}}
    forked_config = graph.update_state(source_config, state_overrides)
    graph.invoke(None, config=forked_config)
    return graph.get_state({"configurable": {"thread_id": task_id}}).values
