"""E2E: escalation triggers fire at the right moments -- explicit review request pauses the
graph at the correct point rather than silently continuing."""
import uuid

from orchestrator.graph.build_graph import build_graph, initial_state


def test_force_review_triggers_plan_approval_escalation():
    task_id = str(uuid.uuid4())
    graph = build_graph()
    config = {"configurable": {"thread_id": task_id}}

    paused = False
    for step in graph.stream(
        initial_state(task_id, "Say hello in one short sentence.", "e2e-escalation-user", force_review=True),
        config=config,
        stream_mode="updates",
    ):
        if "__interrupt__" in step:
            paused = True
            payload = step["__interrupt__"][0].value
            assert payload["level"] == "approve_plan"
            assert payload["kind"] == "plan"
            break

    assert paused, "Expected the graph to pause for human review with force_review=True"
