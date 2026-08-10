"""E2E: the reviewer rejects a deliberately bad deliverable and approves a reasonable one."""
from orchestrator.agents.reviewer import review_subtask_result
from orchestrator.agents.schemas import ReviewVerdict, Subtask, SubtaskResult


def test_reviewer_rejects_empty_output():
    subtask = Subtask(
        id="st-1",
        description="Write a two-paragraph summary of the benefits of unit testing.",
        assigned_specialist="writing",
        depends_on=[],
        required_inputs="none",
        expected_output_format="two paragraphs of prose",
        estimated_complexity=1,
    )
    bad_result = SubtaskResult(subtask_id="st-1", output="", success=True)
    review = review_subtask_result(subtask, bad_result)
    assert review.verdict == ReviewVerdict.REJECTED


def test_reviewer_approves_reasonable_output():
    subtask = Subtask(
        id="st-1",
        description="State the boiling point of water at sea level.",
        assigned_specialist="writing",
        depends_on=[],
        required_inputs="none",
        expected_output_format="one sentence",
        estimated_complexity=1,
    )
    good_result = SubtaskResult(
        subtask_id="st-1",
        output="Water boils at 100 degrees Celsius (212°F) at sea level atmospheric pressure.",
        success=True,
    )
    review = review_subtask_result(subtask, good_result)
    assert review.verdict == ReviewVerdict.APPROVED
