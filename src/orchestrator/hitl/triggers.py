"""Escalation triggers and the approval levels they map to.

Trigger -> level mapping:
- Low supervisor confidence, or the user explicitly asked for review -> APPROVE_PLAN
  (review the whole plan before any work begins; most conservative).
- A specialist used a tool flagged `sensitive` in the tool registry -> APPROVE_ACTION
  (confirm this specific action/result before it's allowed to count).
- A subtask exhausted its retries (kept failing review) -> TAKE_OVER (the agent has
  demonstrably failed at this a few times; offer the human a direct hand-off rather than
  asking them to keep approving broken attempts).
- Any single retry (that may still succeed) -> NOTIFY (non-blocking; recorded for visibility,
  doesn't pause the graph).
"""
from __future__ import annotations

from enum import Enum

from orchestrator.agents.schemas import SubtaskResult
from orchestrator.tools.bootstrap import bootstrap_tools
from orchestrator.tools.registry import tool_registry


class ApprovalLevel(str, Enum):
    NOTIFY = "notify"
    APPROVE_ACTION = "approve_action"
    APPROVE_PLAN = "approve_plan"
    TAKE_OVER = "take_over"


def sensitive_tools_used(result: SubtaskResult) -> list[str]:
    """Returns the names of any sensitive-flagged tools this result's tool_calls invoked.
    tool_calls entries are rendered as "tool_name({args})" by the specialist factory."""
    bootstrap_tools()
    used: list[str] = []
    for call in result.tool_calls:
        name = call.split("(", 1)[0]
        try:
            spec = tool_registry.spec(name)
        except KeyError:
            continue
        if spec.sensitive and name not in used:
            used.append(name)
    return used
