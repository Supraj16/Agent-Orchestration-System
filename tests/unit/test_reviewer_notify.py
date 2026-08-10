from unittest.mock import patch

from orchestrator.agents.schemas import ReviewResult, ReviewVerdict, Subtask, SubtaskResult
from orchestrator.graph.build_graph import initial_state, reviewer_node
from orchestrator.hitl.triggers import ApprovalLevel

SUBTASK = Subtask(
    id="st-1",
    description="do the thing",
    assigned_specialist="research",
    depends_on=[],
    required_inputs="n/a",
    expected_output_format="text",
    estimated_complexity=1,
)


def _state():
    from orchestrator.agents.schemas import ExecutionPlan

    state = initial_state("t1", "some request")
    state["plan"] = ExecutionPlan(subtasks=[SUBTASK], confidence=0.9, reasoning="test")
    state["current_subtask_id"] = "st-1"
    state["pending_result"] = SubtaskResult(subtask_id="st-1", output="a mediocre attempt", success=True)
    return state


@patch("orchestrator.graph.build_graph.approval_queue.create_approval")
@patch("orchestrator.graph.build_graph.review_subtask_result")
def test_first_rejection_creates_notify_approval_without_blocking(mock_review, mock_create_approval):
    mock_review.return_value = ReviewResult(
        subtask_id="st-1", verdict=ReviewVerdict.REJECTED, quality_score=0.2, feedback="not good enough"
    )

    updates = reviewer_node(_state())

    assert updates.get("escalated") is not True
    assert updates["retries"] == {"st-1": 1}
    mock_create_approval.assert_called_once()
    _, kwargs = mock_create_approval.call_args
    assert kwargs["level"] == ApprovalLevel.NOTIFY.value
    assert kwargs["kind"] == "retry"
    assert kwargs["status"] == "acknowledged"


@patch("orchestrator.graph.build_graph.approval_queue.create_approval")
@patch("orchestrator.graph.build_graph.review_subtask_result")
def test_final_rejection_after_max_retries_escalates_to_take_over(mock_review, mock_create_approval):
    mock_review.return_value = ReviewResult(
        subtask_id="st-1", verdict=ReviewVerdict.REJECTED, quality_score=0.1, feedback="still bad"
    )
    state = _state()
    state["retries"] = {"st-1": 2}  # already at MAX_RETRIES_PER_SUBTASK

    updates = reviewer_node(state)

    assert updates["escalated"] is True
    assert updates["escalation_level"] == ApprovalLevel.TAKE_OVER.value
    assert updates["escalation_context"]["kind"] == "takeover_subtask"
    mock_create_approval.assert_not_called()
