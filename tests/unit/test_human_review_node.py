from unittest.mock import patch

from orchestrator.graph.build_graph import human_review_wait_node, initial_state


def _state_with_context(context: dict) -> dict:
    state = initial_state("t1", "some request")
    state["escalation_level"] = "approve_plan"
    state["escalation_context"] = context
    state["pending_approval_id"] = "approval-1"
    return state


@patch("orchestrator.hitl.approval_queue.resolve_approval")
@patch("orchestrator.graph.build_graph.interrupt")
def test_plan_take_over_sets_final_output_directly(mock_interrupt, mock_resolve):
    mock_interrupt.return_value = {"action": "take_over", "edited_content": "human wrote this", "resolver": "op"}
    state = _state_with_context({"kind": "plan", "plan": {}})

    updates = human_review_wait_node(state)

    assert updates["human_review_outcome"] == "takeover_whole_task"
    assert updates["final_output"] == "human wrote this"
    assert updates["escalated"] is False


@patch("orchestrator.hitl.approval_queue.resolve_approval")
@patch("orchestrator.graph.build_graph.interrupt")
def test_sensitive_action_take_over_finalizes_subtask(mock_interrupt, mock_resolve):
    mock_interrupt.return_value = {"action": "take_over", "edited_content": "human output", "resolver": "op"}
    state = _state_with_context({"kind": "sensitive_action", "subtask_id": "st-1"})

    updates = human_review_wait_node(state)

    assert updates["human_review_outcome"] == "finalize_and_dispatch"
    assert updates["subtask_results"]["st-1"].output == "human output"


@patch("orchestrator.hitl.approval_queue.resolve_approval")
@patch("orchestrator.graph.build_graph.interrupt")
def test_takeover_subtask_falls_back_to_last_output_when_approved_without_edit(mock_interrupt, mock_resolve):
    mock_interrupt.return_value = {"action": "approve", "edited_content": None, "resolver": "op"}
    state = _state_with_context({"kind": "takeover_subtask", "subtask_id": "st-1", "last_output": "best attempt"})

    updates = human_review_wait_node(state)

    assert updates["human_review_outcome"] == "finalize_and_dispatch"
    assert updates["subtask_results"]["st-1"].output == "best attempt"


@patch("orchestrator.hitl.approval_queue.resolve_approval")
@patch("orchestrator.graph.build_graph.interrupt")
def test_reject_short_circuits_regardless_of_kind(mock_interrupt, mock_resolve):
    mock_interrupt.return_value = {"action": "reject", "edited_content": None, "resolver": "op"}
    state = _state_with_context({"kind": "sensitive_action", "subtask_id": "st-1"})

    updates = human_review_wait_node(state)

    assert updates["human_review_outcome"] == "reject_task"
    assert "rejected" in updates["final_output"].lower()
