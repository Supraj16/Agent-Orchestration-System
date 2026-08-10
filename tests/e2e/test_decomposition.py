"""E2E: task decomposition produces valid plans. Requires live OpenAI + Postgres/Redis/Chroma."""
from orchestrator.agents.supervisor import build_plan
from orchestrator.graph.build_graph import SUPPORTED_SPECIALISTS


def test_decomposition_produces_valid_dag():
    plan = build_plan(
        "Summarize the key differences between TCP and UDP in two sentences.",
        specialists=SUPPORTED_SPECIALISTS,
    )
    assert len(plan.subtasks) >= 1
    seen_ids: set[str] = set()
    for subtask in plan.subtasks:
        assert subtask.assigned_specialist in SUPPORTED_SPECIALISTS
        # dependencies must only reference subtasks that appear earlier -> valid DAG, no cycles
        assert set(subtask.depends_on).issubset(seen_ids)
        seen_ids.add(subtask.id)
    assert 0.0 <= plan.confidence <= 1.0
