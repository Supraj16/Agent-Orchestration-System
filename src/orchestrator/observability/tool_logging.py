"""Persists every tool invocation to Postgres `tool_calls`, and (via ToolObservabilityCallback)
also wraps it in an OTel span for the unified trace tree. This table remains the fast, flat
query path for tool-level cost/perf aggregation."""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.callbacks.base import BaseCallbackHandler
from opentelemetry import context as otel_context

from orchestrator.db.models import ToolCall
from orchestrator.db.session import session_scope
from orchestrator.observability.context import current_subtask_id, current_task_id

logger = logging.getLogger(__name__)


def log_tool_call(
    *,
    tool_name: str,
    inputs: dict,
    output: str | None,
    latency_ms: float,
    success: bool,
    error: str | None = None,
) -> None:
    try:
        with session_scope() as session:
            session.add(
                ToolCall(
                    task_id=current_task_id.get(),
                    subtask_id=current_subtask_id.get(),
                    tool_name=tool_name,
                    inputs=inputs,
                    output=output[:10_000] if output else output,
                    success=success,
                    error=error,
                    latency_ms=latency_ms,
                )
            )
    except Exception:  # noqa: BLE001 - logging must never break tool execution
        logger.exception("Failed to persist tool call log for tool=%s", tool_name)


class ToolObservabilityCallbackHandler(BaseCallbackHandler):
    """Attached to specialist agent invocations. Fires for every tool call regardless of source
    (hand-written registry tool or MCP-sourced) or rate-limiting outcome, so both custom and MCP
    tools get the same tool_calls row + trace span -- registry.guarded() only adds rate-limit
    enforcement on top for the tools it wraps."""

    def __init__(self) -> None:
        super().__init__()
        self._pending: dict[str, dict[str, Any]] = {}

    def on_tool_start(
        self, serialized: dict, input_str: str, *, run_id: Any = None, inputs: dict | None = None, **kwargs: Any
    ) -> None:
        from orchestrator.observability.tracing import get_tracer

        name = (serialized or {}).get("name", "unknown_tool")
        span = get_tracer().start_span(f"tool:{name}", context=otel_context.get_current())
        self._pending[str(run_id)] = {
            "start": time.monotonic(),
            "name": name,
            "inputs": inputs or {"input": input_str},
            "span": span,
        }

    def on_tool_end(self, output: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        info = self._pending.pop(str(run_id), None)
        if info is None:
            return
        latency_ms = (time.monotonic() - info["start"]) * 1000
        log_tool_call(tool_name=info["name"], inputs=info["inputs"], output=str(output), latency_ms=latency_ms, success=True)

        span = info["span"]
        span.set_attribute("tool_name", info["name"])
        span.set_attribute("span_kind", "tool")
        span.set_attribute("status", "success")
        span.set_attribute("latency_ms", latency_ms)
        span.set_attribute("task_id", current_task_id.get() or "")
        span.end()

    def on_tool_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        info = self._pending.pop(str(run_id), None)
        if info is None:
            return
        latency_ms = (time.monotonic() - info["start"]) * 1000
        log_tool_call(
            tool_name=info["name"],
            inputs=info["inputs"],
            output=None,
            latency_ms=latency_ms,
            success=False,
            error=str(error),
        )

        span = info["span"]
        span.set_attribute("tool_name", info["name"])
        span.set_attribute("span_kind", "tool")
        span.set_attribute("status", "error")
        span.set_attribute("latency_ms", latency_ms)
        span.set_attribute("error", str(error))
        span.set_attribute("task_id", current_task_id.get() or "")
        span.record_exception(error)
        span.end()
