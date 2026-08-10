from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.agents.schemas import ReviewResult, Subtask, SubtaskResult
from orchestrator.llm.router import get_model_for_role

REVIEWER_SYSTEM_PROMPT = """You are the Reviewer agent. You validate a specialist's output against
the subtask's expected_output_format before it is allowed to proceed. Reject if the output is
empty, off-topic, missing required elements, or does not follow the requested format. Be strict
but fair — do not reject for style preferences alone. quality_score should reflect how close the
output is to something you'd hand to the requester as-is."""


def review_subtask_result(subtask: Subtask, result: SubtaskResult) -> ReviewResult:
    model = get_model_for_role("reviewer").with_structured_output(ReviewResult)

    if not result.success:
        return ReviewResult(
            subtask_id=subtask.id,
            verdict="rejected",
            quality_score=0.0,
            feedback=f"Specialist execution failed: {result.error}",
        )

    # Deterministic guard: an empty/whitespace-only output is unambiguously a failure, and
    # relying on the LLM to catch it isn't reliable at the margins -- e2e testing found gpt-4o-mini
    # occasionally approving an empty string outright. No need to spend a call on it.
    if not result.output.strip():
        return ReviewResult(
            subtask_id=subtask.id,
            verdict="rejected",
            quality_score=0.0,
            feedback="Specialist produced an empty output.",
        )

    human = (
        f"Subtask description: {subtask.description}\n"
        f"Expected output format: {subtask.expected_output_format}\n\n"
        f"Specialist output:\n{result.output}\n\n"
        f"Set subtask_id to '{subtask.id}'."
    )
    review = model.invoke([SystemMessage(content=REVIEWER_SYSTEM_PROMPT), HumanMessage(content=human)])
    return review  # type: ignore[return-value]
