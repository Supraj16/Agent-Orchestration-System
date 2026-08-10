"""E2E: the graph recovers gracefully from a specialist that always fails -- it retries, then
escalates to a human rather than crashing the whole run."""
import uuid
from unittest.mock import patch

from orchestrator.agents.schemas import SubtaskResult


def _always_fails(subtask, task_id, feedback=None, dependency_outputs=None):
    return SubtaskResult(subtask_id=subtask.id, output="", success=False, error="simulated specialist failure")


def test_repeated_specialist_failure_escalates_instead_of_crashing():
    failing_runners = {name: _always_fails for name in ("research", "data_analysis", "writing", "code_execution")}

    with patch("orchestrator.graph.build_graph.SPECIALIST_RUNNERS", failing_runners):
        from orchestrator.graph.build_graph import build_graph, initial_state

        task_id = str(uuid.uuid4())
        graph = build_graph()
        config = {"configurable": {"thread_id": task_id}}

        paused = False
        for step in graph.stream(
            initial_state(task_id, "Write one sentence about the weather.", "e2e-failure-user"),
            config=config,
            stream_mode="updates",
        ):
            if "__interrupt__" in step:
                paused = True
                payload = step["__interrupt__"][0].value
                assert payload["level"] == "take_over"
                assert payload["kind"] == "takeover_subtask"
                assert payload["attempts"] == 3
                break

    assert paused, "Expected repeated specialist failure to escalate to a human rather than raise"
