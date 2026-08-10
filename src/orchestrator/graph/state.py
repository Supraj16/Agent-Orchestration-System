from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from orchestrator.agents.schemas import ExecutionPlan, ReviewResult, SubtaskResult

MAX_RETRIES_PER_SUBTASK = 2
LOW_CONFIDENCE_THRESHOLD = 0.55
REVIEW_QUALITY_THRESHOLD = 0.6


def _merge_dict(left: dict, right: dict) -> dict:
    return {**left, **right}


class OrchestratorState(TypedDict):
    task_id: str
    user_id: str
    user_request: str
    force_review: bool
    """Set by the caller: user explicitly requested human review of the plan before any work begins."""

    plan: ExecutionPlan | None
    subtask_results: Annotated[dict[str, SubtaskResult], _merge_dict]
    """Approved, finalized results only."""
    pending_result: SubtaskResult | None
    """Latest specialist output, awaiting review."""
    retries: Annotated[dict[str, int], _merge_dict]
    latest_review: ReviewResult | None
    current_subtask_id: str | None

    escalated: bool
    escalation_reason: str | None
    escalation_level: str | None
    """ApprovalLevel value: notify | approve_action | approve_plan | take_over."""
    escalation_context: dict | None
    """Payload shown to the human reviewer; shape depends on escalation_context['kind']."""
    pending_approval_id: str | None
    human_review_outcome: str | None
    """Set by the human-review-wait node: resume_dispatch | resume_reviewer | finalize_and_dispatch
    | takeover_whole_task | reject_task."""

    final_output: str | None
    errors: Annotated[list[str], operator.add]
