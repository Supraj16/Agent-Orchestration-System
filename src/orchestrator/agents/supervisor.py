from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.agents.schemas import ExecutionPlan
from orchestrator.llm.router import get_model_for_role

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor agent in a multi-agent orchestration system.

Given a complex user request, decompose it into an ordered list of subtasks. Each subtask must be
assigned to exactly one specialist from the available specialists list below. Subtasks may depend
on the output of earlier subtasks (list their ids in depends_on) — dependencies must form a DAG
(no cycles) and must only reference subtask ids that appear earlier in your list.

Available specialists: {specialists}

For each subtask, be concrete about required_inputs and expected_output_format so the specialist
and reviewer both know exactly what "done" looks like.

Set `confidence` (0.0-1.0) to your genuine confidence that this plan, if executed, will satisfy
the user's request. Be honest — low confidence is expected for ambiguous or very broad requests
and will correctly trigger human review rather than silently producing a bad result.

You may be given memories from this user's past tasks below. Use them to inform your plan —
reuse approaches that worked, avoid ones that didn't, and respect observed preferences — but
don't force-fit an irrelevant memory onto an unrelated request.
"""


def build_plan(
    user_request: str,
    specialists: list[str],
    feedback: str | None = None,
    memories: list[dict] | None = None,
) -> ExecutionPlan:
    model = get_model_for_role("supervisor").with_structured_output(ExecutionPlan)

    system = SUPERVISOR_SYSTEM_PROMPT.format(specialists=", ".join(specialists))
    human = f"User request:\n{user_request}"
    if memories:
        rendered = "\n\n".join(f"- {m['summary']}" for m in memories)
        human += f"\n\nRelevant memories from this user's past tasks:\n{rendered}"
    if feedback:
        human += f"\n\nA previous plan attempt failed review. Feedback to incorporate:\n{feedback}"

    result = model.invoke([SystemMessage(content=system), HumanMessage(content=human)])
    return result  # type: ignore[return-value]
