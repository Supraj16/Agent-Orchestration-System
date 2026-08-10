"""CLI: run a single task through the full agent graph (Supervisor -> specialists -> Reviewer ->
Synthesis), backed by Postgres/Redis/Chroma. Pauses cleanly if a human-in-the-loop escalation
fires; resolve it with scripts/resolve_approval.py or the Streamlit Approval Queue page.

Usage:
    python scripts/run_task.py "<request>" [user_id] [--force-review]
"""
from __future__ import annotations

import sys
import uuid

from orchestrator.graph.build_graph import build_graph, initial_state


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scripts/run_task.py "<request>" [user_id] [--force-review]')
        raise SystemExit(1)

    user_request = sys.argv[1]
    args = sys.argv[2:]
    force_review = "--force-review" in args
    positional = [a for a in args if not a.startswith("--")]
    user_id = positional[0] if positional else "demo-user"

    task_id = str(uuid.uuid4())
    graph = build_graph()
    config = {"configurable": {"thread_id": task_id}}

    print(f"=== Task {task_id} (user={user_id}) ===\n{user_request}\n")

    paused = False
    for step in graph.stream(
        initial_state(task_id, user_request, user_id, force_review), config=config, stream_mode="updates"
    ):
        if "__interrupt__" in step:
            paused = True
            _print_interrupt(task_id, step["__interrupt__"])
            break
        for node_name, update in step.items():
            print(f"[{node_name}] {_summarize(update)}")

    if paused:
        return

    result = graph.get_state(config).values
    print("\n=== Final output ===")
    print(result.get("final_output"))


def _print_interrupt(task_id: str, interrupts) -> None:
    for intr in interrupts:
        payload = intr.value
        print("\n=== PAUSED FOR HUMAN REVIEW ===")
        print(f"approval_id: {payload.get('approval_id')}")
        print(f"level:       {payload.get('level')}")
        print(f"kind:        {payload.get('kind')}")
        for key, value in payload.items():
            if key not in ("approval_id", "level", "kind"):
                print(f"{key}: {value}")
    print(
        f"\nResolve with:\n"
        f'  python scripts/resolve_approval.py {task_id} approve\n'
        f'  python scripts/resolve_approval.py {task_id} modify "<edited content>"\n'
        f"  python scripts/resolve_approval.py {task_id} reject\n"
        f'  python scripts/resolve_approval.py {task_id} take_over "<your output>"'
    )


def _summarize(update: dict) -> str:
    parts = []
    if "plan" in update and update["plan"] is not None:
        plan = update["plan"]
        parts.append(f"plan with {len(plan.subtasks)} subtask(s), confidence={plan.confidence:.2f}")
    if "current_subtask_id" in update:
        parts.append(f"current_subtask_id={update['current_subtask_id']}")
    if "pending_result" in update and update["pending_result"] is not None:
        parts.append(f"specialist_success={update['pending_result'].success}")
    if "latest_review" in update and update["latest_review"] is not None:
        review = update["latest_review"]
        parts.append(f"review={review.verdict.value} score={review.quality_score:.2f}")
    if update.get("escalated"):
        parts.append(f"escalated={update['escalated']}")
    if "final_output" in update and update["final_output"]:
        parts.append("final_output produced")
    return ", ".join(parts) if parts else str(update)


if __name__ == "__main__":
    main()
