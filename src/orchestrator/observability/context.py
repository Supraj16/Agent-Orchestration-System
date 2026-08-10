"""Contextvars threading task/subtask/node identity down through deep call stacks (a
create_agent() tool-calling loop, an LLM callback) so tool-call logs, LLM usage spans, and node
spans can all be attributed to the right task without every function needing an extra parameter.
"""
from __future__ import annotations

import contextvars

current_task_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_task_id", default=None)
current_subtask_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_subtask_id", default=None)
current_node_name: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_node_name", default=None)
