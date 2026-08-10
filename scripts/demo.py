"""End-to-end showcase: run two related requests for the same user so you can see the full
lifecycle in one narrated pass --

  1. A multi-specialist research task: supervisor decomposition -> specialists (research,
     data analysis, writing) executing with real tool calls -> reviewer validating each
     output -> synthesis.
  2. A related follow-up request for the SAME user, with --force-review, so you can see
     long-term memory from step 1 inform the plan, and a human-in-the-loop approval pause
     that this script resolves itself (playing the human) via the same resume path the
     Streamlit Approval Queue uses.

Then prints a trace/cost summary pulled straight from the observability layer.

Usage:
    python scripts/demo.py
"""
from __future__ import annotations

import time
import uuid

from orchestrator.graph.build_graph import build_graph, initial_state
from orchestrator.hitl.resume import resume_task
from orchestrator.observability.query import get_task_cost_summary, get_trace_tree

DEMO_USER = "demo-showcase-user"


def _banner(text: str) -> None:
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


def _run(user_request: str, *, force_review: bool = False) -> tuple[str, dict]:
    task_id = str(uuid.uuid4())
    graph = build_graph()
    config = {"configurable": {"thread_id": task_id}}

    print(f"Task {task_id}\nRequest: {user_request}\n")
    for step in graph.stream(
        initial_state(task_id, user_request, DEMO_USER, force_review), config=config, stream_mode="updates"
    ):
        if "__interrupt__" in step:
            payload = step["__interrupt__"][0].value
            print(f"\n--- PAUSED: human review requested ({payload.get('level')} / {payload.get('kind')}) ---")
            if payload.get("kind") == "plan":
                print(f"Plan confidence: {payload.get('plan', {}).get('confidence')}")
                print(f"Reasoning: {payload.get('reason')}")
            print("--- Simulating a human clicking 'Approve' in the Approval Queue ---\n")
            result = resume_task(task_id, {"action": "approve", "edited_content": None, "resolver": "demo-script"})
            return task_id, result["values"]
        for node_name, update in step.items():
            summary = _summarize(update)
            if summary:
                print(f"  [{node_name}] {summary}")

    return task_id, graph.get_state(config).values


def _summarize(update: dict) -> str:
    if "plan" in update and update["plan"] is not None:
        plan = update["plan"]
        return f"planned {len(plan.subtasks)} subtask(s), confidence={plan.confidence:.2f}"
    if "pending_result" in update and update["pending_result"] is not None:
        r = update["pending_result"]
        return f"specialist finished (success={r.success}, {len(r.tool_calls)} tool call(s))"
    if "latest_review" in update and update["latest_review"] is not None:
        review = update["latest_review"]
        return f"reviewer: {review.verdict.value} (score={review.quality_score:.2f})"
    if update.get("final_output"):
        return "final output produced"
    return ""


def main() -> None:
    _banner("STEP 1: Multi-specialist research task (fresh user, no memory yet)")
    task_id_1, values_1 = _run(
        "Research the main advantages of using a message queue (like RabbitMQ or Kafka) in a "
        "microservices architecture, analyze which advantage matters most for a high-traffic "
        "e-commerce system, and write a short recommendation."
    )
    print(f"\nFinal output:\n{values_1.get('final_output')}\n")

    _banner("STEP 2: Related follow-up for the SAME user, with --force-review")
    print("Watch for the Supervisor citing memory from Step 1, and the human-approval pause.\n")
    task_id_2, values_2 = _run(
        "Now do the same kind of analysis, but for choosing between synchronous REST calls and "
        "an event-driven approach for order processing.",
        force_review=True,
    )
    print(f"\nFinal output:\n{values_2.get('final_output')}\n")

    _banner("TRACE + COST SUMMARY")
    for label, task_id in [("Step 1", task_id_1), ("Step 2", task_id_2)]:
        cost = get_task_cost_summary(task_id)
        spans = get_trace_tree(task_id)
        print(
            f"{label} ({task_id[:8]}): {len(spans)} spans, {cost['llm_call_count']} LLM calls, "
            f"{cost['tool_call_count']} tool calls, ${cost['total_cost_usd']:.4f}"
        )
    print(
        "\nOpen the Trace Explorer / Cost Dashboard / Memory Dashboard in the Streamlit UI "
        "(streamlit run src/ui/review_app.py) to inspect both tasks visually."
    )


if __name__ == "__main__":
    start = time.monotonic()
    main()
    print(f"\nDemo finished in {time.monotonic() - start:.1f}s")
