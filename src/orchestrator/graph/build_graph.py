from __future__ import annotations

from typing import Callable

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from orchestrator.agents.reviewer import review_subtask_result
from orchestrator.agents.schemas import ExecutionPlan, ReviewResult, ReviewVerdict, Subtask, SubtaskResult
from orchestrator.agents.specialists.code_execution import run_code_execution_subtask
from orchestrator.agents.specialists.data_analysis import run_data_analysis_subtask
from orchestrator.agents.specialists.research import run_research_subtask
from orchestrator.agents.specialists.writing import run_writing_subtask
from orchestrator.agents.supervisor import build_plan
from orchestrator.db.task_repo import upsert_task
from orchestrator.graph.checkpointer import get_checkpointer
from orchestrator.graph.state import (
    LOW_CONFIDENCE_THRESHOLD,
    MAX_RETRIES_PER_SUBTASK,
    REVIEW_QUALITY_THRESHOLD,
    OrchestratorState,
)
from orchestrator.hitl import approval_queue
from orchestrator.hitl.triggers import ApprovalLevel, sensitive_tools_used
from orchestrator.llm.router import get_model_for_role
from orchestrator.memory import long_term, working_memory
from orchestrator.observability.tracing import traced_node

SpecialistRunner = Callable[[Subtask, str, str | None, dict[str, str] | None], SubtaskResult]

SPECIALIST_RUNNERS: dict[str, SpecialistRunner] = {
    "research": run_research_subtask,
    "data_analysis": run_data_analysis_subtask,
    "writing": run_writing_subtask,
    "code_execution": run_code_execution_subtask,
}
SUPPORTED_SPECIALISTS = list(SPECIALIST_RUNNERS.keys())


def _get_subtask(plan: ExecutionPlan, subtask_id: str) -> Subtask:
    return next(s for s in plan.subtasks if s.id == subtask_id)


def _find_next_ready_subtask(plan: ExecutionPlan, completed: dict) -> Subtask | None:
    completed_ids = set(completed.keys())
    for subtask in plan.subtasks:
        if subtask.id in completed_ids:
            continue
        if set(subtask.depends_on).issubset(completed_ids):
            return subtask
    return None


def _rejection_feedback(state: OrchestratorState, subtask: Subtask) -> str | None:
    latest_review = state.get("latest_review")
    if latest_review and latest_review.subtask_id == subtask.id and latest_review.verdict == ReviewVerdict.REJECTED:
        return latest_review.feedback
    return None


# --- Nodes ---


@traced_node("planner", kind="agent")
def planner_node(state: OrchestratorState) -> dict:
    memories = long_term.query_similar_memories(state["user_id"], state["user_request"])
    plan = build_plan(state["user_request"], specialists=SUPPORTED_SPECIALISTS, memories=memories)
    updates: dict = {"plan": plan}

    low_confidence = plan.confidence < LOW_CONFIDENCE_THRESHOLD
    if low_confidence or state.get("force_review"):
        reason = (
            f"Supervisor confidence {plan.confidence:.2f} is below the {LOW_CONFIDENCE_THRESHOLD} threshold."
            if low_confidence
            else "User explicitly requested plan review before execution."
        )
        updates["escalated"] = True
        updates["escalation_reason"] = reason
        updates["escalation_level"] = ApprovalLevel.APPROVE_PLAN.value
        updates["escalation_context"] = {
            "kind": "plan",
            "reason": reason,
            "plan": plan.model_dump(mode="json"),
        }

    upsert_task(
        state["task_id"],
        user_id=state["user_id"],
        user_request=state["user_request"],
        status="pending_review" if updates.get("escalated") else "running",
        plan=plan.model_dump(mode="json"),
    )
    working_memory.set_plan(state["task_id"], plan.model_dump(mode="json"))
    return updates


@traced_node("dispatch", kind="system")
def dispatch_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    assert plan is not None
    next_subtask = _find_next_ready_subtask(plan, state["subtask_results"])

    if next_subtask is None:
        return {"current_subtask_id": None}

    if next_subtask.assigned_specialist not in SUPPORTED_SPECIALISTS:
        reason = f"Specialist '{next_subtask.assigned_specialist}' is not a recognized specialist."
        return {
            "current_subtask_id": next_subtask.id,
            "escalated": True,
            "escalation_reason": reason,
            "escalation_level": ApprovalLevel.TAKE_OVER.value,
            "escalation_context": {
                "kind": "takeover_subtask",
                "subtask_id": next_subtask.id,
                "subtask_description": next_subtask.description,
                "attempts": 0,
                "last_output": "",
                "last_feedback": reason,
            },
        }

    return {"current_subtask_id": next_subtask.id}


def make_specialist_node(specialist_name: str, runner: SpecialistRunner) -> Callable[[OrchestratorState], dict]:
    @traced_node(f"specialist_{specialist_name}", kind="agent")
    def node(state: OrchestratorState) -> dict:
        plan = state["plan"]
        assert plan is not None
        subtask = _get_subtask(plan, state["current_subtask_id"])
        feedback = _rejection_feedback(state, subtask)
        dependency_outputs = {
            dep_id: state["subtask_results"][dep_id].output
            for dep_id in subtask.depends_on
            if dep_id in state["subtask_results"]
        }
        result = runner(subtask, state["task_id"], feedback, dependency_outputs)
        if not result.success:
            working_memory.add_error(state["task_id"], f"{specialist_name}/{subtask.id}: {result.error}")

        updates: dict = {"pending_result": result}

        sensitive = sensitive_tools_used(result)
        if sensitive:
            updates["escalated"] = True
            updates["escalation_reason"] = f"Subtask '{subtask.id}' used sensitive tool(s): {', '.join(sensitive)}."
            updates["escalation_level"] = ApprovalLevel.APPROVE_ACTION.value
            updates["escalation_context"] = {
                "kind": "sensitive_action",
                "subtask_id": subtask.id,
                "subtask_description": subtask.description,
                "proposed_output": result.output,
                "tool_calls": result.tool_calls,
                "sensitive_tools": sensitive,
            }
        return updates

    return node


@traced_node("reviewer", kind="agent")
def reviewer_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    assert plan is not None
    subtask = _get_subtask(plan, state["current_subtask_id"])
    result = state["pending_result"]
    assert result is not None

    review = review_subtask_result(subtask, result)
    updates: dict = {"latest_review": review}

    approved = review.verdict == ReviewVerdict.APPROVED and review.quality_score >= REVIEW_QUALITY_THRESHOLD
    if approved:
        updates["subtask_results"] = {subtask.id: result}
        working_memory.add_subtask_result(state["task_id"], subtask.id, result.model_dump(mode="json"))
        return updates

    attempt = state["retries"].get(subtask.id, 0) + 1
    updates["retries"] = {subtask.id: attempt}

    if attempt <= MAX_RETRIES_PER_SUBTASK:
        # NOTIFY level: non-blocking, purely for visibility in the approval dashboard.
        approval_queue.create_approval(
            task_id=state["task_id"],
            level=ApprovalLevel.NOTIFY.value,
            kind="retry",
            context={
                "subtask_id": subtask.id,
                "subtask_description": subtask.description,
                "attempt": attempt,
                "feedback": review.feedback,
            },
            status="acknowledged",
        )
        return updates

    reason = f"Subtask '{subtask.id}' failed review {attempt} times. Last feedback: {review.feedback}"
    updates["escalated"] = True
    updates["escalation_reason"] = reason
    updates["escalation_level"] = ApprovalLevel.TAKE_OVER.value
    updates["escalation_context"] = {
        "kind": "takeover_subtask",
        "subtask_id": subtask.id,
        "subtask_description": subtask.description,
        "attempts": attempt,
        "last_output": result.output,
        "last_feedback": review.feedback,
    }
    return updates


@traced_node("prepare_human_review", kind="system")
def prepare_human_review_node(state: OrchestratorState) -> dict:
    """Creates the durable approval record. Kept separate from the interrupt()-calling node
    because LangGraph re-runs a node's entire body from the top on resume -- if this side
    effect lived in the same node as interrupt(), resuming would create a duplicate approval
    row every time."""
    ctx = state["escalation_context"]
    assert ctx is not None
    approval_id = approval_queue.create_approval(
        task_id=state["task_id"], level=state["escalation_level"], kind=ctx["kind"], context=ctx
    )
    upsert_task(state["task_id"], status="pending_review")
    return {"pending_approval_id": approval_id}


@traced_node("human_review_wait", kind="escalation")
def human_review_wait_node(state: OrchestratorState) -> dict:
    ctx = state["escalation_context"]
    assert ctx is not None
    approval_id = state["pending_approval_id"]

    resolution = interrupt({"approval_id": approval_id, "level": state["escalation_level"], **ctx})
    approval_queue.resolve_approval(approval_id, resolution)

    action = resolution.get("action", "approve")
    kind = ctx["kind"]
    updates: dict = {
        "escalated": False,
        "escalation_context": None,
        "escalation_level": None,
        "pending_approval_id": None,
    }

    if action == "reject":
        updates["human_review_outcome"] = "reject_task"
        updates["final_output"] = f"Task rejected by human reviewer during {kind} review."
        return updates

    if kind == "plan":
        if action == "take_over":
            updates["human_review_outcome"] = "takeover_whole_task"
            updates["final_output"] = resolution.get("edited_content") or ""
            return updates
        if action == "modify" and resolution.get("edited_content"):
            updates["plan"] = ExecutionPlan.model_validate(resolution["edited_content"])
        updates["human_review_outcome"] = "resume_dispatch"
        return updates

    if kind == "sensitive_action":
        subtask_id = ctx["subtask_id"]
        if action == "take_over":
            result = SubtaskResult(subtask_id=subtask_id, output=resolution.get("edited_content") or "", success=True)
            updates["subtask_results"] = {subtask_id: result}
            updates["human_review_outcome"] = "finalize_and_dispatch"
            return updates
        if action == "modify" and resolution.get("edited_content"):
            original = state["pending_result"]
            assert original is not None
            updates["pending_result"] = SubtaskResult(
                subtask_id=subtask_id,
                output=resolution["edited_content"],
                success=True,
                tool_calls=original.tool_calls,
            )
        updates["human_review_outcome"] = "resume_reviewer"
        return updates

    if kind == "takeover_subtask":
        subtask_id = ctx["subtask_id"]
        content = resolution.get("edited_content") or ctx.get("last_output") or ""
        result = SubtaskResult(subtask_id=subtask_id, output=content, success=True)
        updates["subtask_results"] = {subtask_id: result}
        updates["human_review_outcome"] = "finalize_and_dispatch"
        return updates

    raise ValueError(f"Unhandled escalation kind: {kind}")


@traced_node("synthesis", kind="agent")
def synthesis_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    assert plan is not None
    model = get_model_for_role("supervisor")

    sections = []
    for subtask in plan.subtasks:
        result = state["subtask_results"].get(subtask.id)
        if result:
            sections.append(f"### {subtask.description}\n{result.output}")

    prompt = (
        "Combine the following completed subtask outputs into one coherent final answer to the "
        f"user's original request.\n\nOriginal request: {state['user_request']}\n\n" + "\n\n".join(sections)
    )
    response = model.invoke([HumanMessage(content=prompt)])
    final_output = response.content

    upsert_task(state["task_id"], status="completed", final_output=final_output)
    working_memory.clear(state["task_id"])

    all_tool_calls = [call for result in state["subtask_results"].values() for call in result.tool_calls]
    long_term.extract_and_store_memory(
        task_id=state["task_id"],
        user_id=state["user_id"],
        user_request=state["user_request"],
        tool_calls=all_tool_calls,
        final_output=final_output,
    )
    return {"final_output": final_output}


@traced_node("terminal", kind="system")
def terminal_node(state: OrchestratorState) -> dict:
    """Handles the two outcomes that skip normal synthesis: a human took over and supplied the
    final output directly, or a human rejected the task outright."""
    outcome = state["human_review_outcome"]
    status = "completed" if outcome == "takeover_whole_task" else "rejected"
    upsert_task(state["task_id"], status=status, final_output=state["final_output"])
    working_memory.clear(state["task_id"])
    return {}


# --- Routers (read-only; no state mutation) ---


def route_after_planning(state: OrchestratorState) -> str:
    return "prepare_human_review" if state.get("escalated") else "dispatch"


def route_after_dispatch(state: OrchestratorState) -> str:
    if state.get("escalated"):
        return "prepare_human_review"
    if state["current_subtask_id"] is None:
        return "synthesis"
    plan = state["plan"]
    assert plan is not None
    subtask = _get_subtask(plan, state["current_subtask_id"])
    return f"specialist_{subtask.assigned_specialist}"


def route_after_specialist(state: OrchestratorState) -> str:
    return "prepare_human_review" if state.get("escalated") else "reviewer"


def route_after_review(state: OrchestratorState) -> str:
    if state.get("escalated"):
        return "prepare_human_review"
    review = state["latest_review"]
    assert review is not None
    if review.verdict == ReviewVerdict.APPROVED:
        return "dispatch"
    plan = state["plan"]
    assert plan is not None
    subtask = _get_subtask(plan, state["current_subtask_id"])
    return f"specialist_{subtask.assigned_specialist}"


def route_after_human_review(state: OrchestratorState) -> str:
    outcome = state["human_review_outcome"]
    return {
        "resume_dispatch": "dispatch",
        "resume_reviewer": "reviewer",
        "finalize_and_dispatch": "dispatch",
        "takeover_whole_task": "terminal",
        "reject_task": "terminal",
    }[outcome]


def build_graph():
    graph = StateGraph(OrchestratorState)

    graph.add_node("planner", planner_node)
    graph.add_node("dispatch", dispatch_node)
    for name, runner in SPECIALIST_RUNNERS.items():
        graph.add_node(f"specialist_{name}", make_specialist_node(name, runner))
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("prepare_human_review", prepare_human_review_node)
    graph.add_node("human_review_wait", human_review_wait_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("terminal", terminal_node)

    specialist_node_names = [f"specialist_{name}" for name in SPECIALIST_RUNNERS]

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", route_after_planning, ["dispatch", "prepare_human_review"])
    graph.add_conditional_edges(
        "dispatch", route_after_dispatch, [*specialist_node_names, "synthesis", "prepare_human_review"]
    )
    for node_name in specialist_node_names:
        graph.add_conditional_edges(node_name, route_after_specialist, ["reviewer", "prepare_human_review"])
    graph.add_conditional_edges(
        "reviewer", route_after_review, ["dispatch", *specialist_node_names, "prepare_human_review"]
    )
    graph.add_edge("prepare_human_review", "human_review_wait")
    graph.add_conditional_edges("human_review_wait", route_after_human_review, ["dispatch", "reviewer", "terminal"])
    graph.add_edge("synthesis", END)
    graph.add_edge("terminal", END)

    # The graph state holds our Pydantic models directly (ExecutionPlan, SubtaskResult, etc.);
    # allowlist them so the checkpointer's msgpack serializer doesn't warn/block on them.
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[ExecutionPlan, Subtask, SubtaskResult, ReviewResult, ReviewVerdict]
    )
    return graph.compile(checkpointer=get_checkpointer(serde=serde))


def initial_state(
    task_id: str, user_request: str, user_id: str = "demo-user", force_review: bool = False
) -> OrchestratorState:
    return {
        "task_id": task_id,
        "user_id": user_id,
        "user_request": user_request,
        "force_review": force_review,
        "plan": None,
        "subtask_results": {},
        "pending_result": None,
        "retries": {},
        "latest_review": None,
        "current_subtask_id": None,
        "escalated": False,
        "escalation_reason": None,
        "escalation_level": None,
        "escalation_context": None,
        "pending_approval_id": None,
        "human_review_outcome": None,
        "final_output": None,
        "errors": [],
    }
