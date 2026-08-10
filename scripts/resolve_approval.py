"""CLI: resolve a paused task's pending human-in-the-loop escalation and resume the graph.
The Streamlit Approval Queue page does the same thing under the hood (orchestrator.hitl.resume)
-- this script exists for fast manual testing without the UI.

Usage:
    python scripts/resolve_approval.py <task_id> <approve|modify|reject|take_over> ["<edited content>"]
"""
from __future__ import annotations

import sys

from orchestrator.hitl.resume import resume_task

VALID_ACTIONS = {"approve", "modify", "reject", "take_over"}


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[2] not in VALID_ACTIONS:
        print('Usage: python scripts/resolve_approval.py <task_id> <approve|modify|reject|take_over> ["<content>"]')
        raise SystemExit(1)

    task_id = sys.argv[1]
    action = sys.argv[2]
    edited_content = sys.argv[3] if len(sys.argv) > 3 else None

    resolution = {"action": action, "edited_content": edited_content, "resolver": "cli-operator"}
    result = resume_task(task_id, resolution)

    if result["paused"]:
        print("\n=== PAUSED AGAIN FOR FURTHER HUMAN REVIEW ===")
        print(f"Check the Approval Queue for task {task_id}.")
        return

    print("\n=== Final output ===")
    print(result["values"].get("final_output"))


if __name__ == "__main__":
    main()
