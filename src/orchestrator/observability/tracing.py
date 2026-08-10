"""OpenTelemetry setup: a real TracerProvider + a custom PostgresSpanExporter, so every span
(agent node, tool call, LLM usage) is both a genuine OTel span and immediately queryable for the
Trace Explorer / Cost Dashboard without standing up Jaeger/Tempo.
"""
from __future__ import annotations

import functools
import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from orchestrator.db.models import Span as SpanModel
from orchestrator.db.session import session_scope
from orchestrator.observability.context import current_node_name, current_subtask_id, current_task_id

logger = logging.getLogger(__name__)

SERVICE_NAME = "agent-orchestrator"


class PostgresSpanExporter(SpanExporter):
    def export(self, spans) -> SpanExportResult:
        try:
            with session_scope() as session:
                for span in spans:
                    ctx = span.get_span_context()
                    parent = span.parent
                    attrs = dict(span.attributes or {})
                    session.add(
                        SpanModel(
                            span_id=format(ctx.span_id, "016x"),
                            parent_span_id=format(parent.span_id, "016x") if parent else None,
                            trace_id=format(ctx.trace_id, "032x"),
                            task_id=attrs.get("task_id") or None,
                            name=span.name,
                            span_kind=attrs.get("span_kind", "system"),
                            status=attrs.get("status", "success"),
                            start_time=datetime.fromtimestamp(span.start_time / 1e9, tz=timezone.utc),
                            end_time=datetime.fromtimestamp(span.end_time / 1e9, tz=timezone.utc),
                            latency_ms=attrs.get("latency_ms", 0.0),
                            attributes=attrs,
                        )
                    )
            return SpanExportResult.SUCCESS
        except Exception:
            logger.exception("Failed to export spans to Postgres")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass


_tracer_provider: TracerProvider | None = None


def _get_provider() -> TracerProvider:
    global _tracer_provider
    if _tracer_provider is None:
        provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
        # SimpleSpanProcessor exports synchronously as each span ends. Deliberate: this system
        # runs as short-lived CLI invocations for now, where a BatchSpanProcessor's async
        # flush might not complete before the process exits. Revisit for BatchSpanProcessor
        # once this runs inside a long-lived API/worker process (milestone 6).
        provider.add_span_processor(SimpleSpanProcessor(PostgresSpanExporter()))
        trace.set_tracer_provider(provider)
        _tracer_provider = provider
    return _tracer_provider


def get_tracer():
    _get_provider()
    return trace.get_tracer(SERVICE_NAME)


def _sanitize_for_attribute(value) -> str:
    """OTel span attributes must be primitives; JSON-encode anything structured."""
    try:
        return json.dumps(value, default=str)[:4000]
    except Exception:
        return str(value)[:4000]


def _is_graph_bubble_up(exc: Exception) -> bool:
    try:
        from langgraph.errors import GraphBubbleUp

        return isinstance(exc, GraphBubbleUp)
    except ImportError:
        return False


def _summarize_result(result: dict) -> dict:
    """Sanitizes a node's return dict for span attributes: Pydantic models -> dicts."""
    summary = {}
    for key, value in result.items():
        if hasattr(value, "model_dump"):
            summary[key] = value.model_dump(mode="json")
        elif isinstance(value, dict):
            summary[key] = {
                k: (v.model_dump(mode="json") if hasattr(v, "model_dump") else v) for k, v in value.items()
            }
        else:
            summary[key] = value
    return summary


def traced_node(name: str, kind: str = "agent") -> Callable:
    """Decorator for LangGraph node functions: wraps execution in a real OTel span, records the
    node's return value (sanitized) as an attribute, and sets task/subtask/node identity in
    contextvars so nested tool calls and LLM usage attribute to the right place."""

    def decorator(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            tracer = get_tracer()
            task_id = state.get("task_id")
            subtask_id = state.get("current_subtask_id")

            task_token = current_task_id.set(task_id)
            subtask_token = current_subtask_id.set(subtask_id)
            node_token = current_node_name.set(name)

            start = time.monotonic()
            try:
                with tracer.start_as_current_span(name) as span:
                    try:
                        result = fn(state)
                        latency_ms = (time.monotonic() - start) * 1000
                        span.set_attribute("task_id", task_id or "")
                        span.set_attribute("span_kind", kind)
                        span.set_attribute("status", "escalated" if result.get("escalated") else "success")
                        span.set_attribute("latency_ms", latency_ms)
                        if subtask_id:
                            span.set_attribute("subtask_id", subtask_id)
                        span.set_attribute("result", _sanitize_for_attribute(_summarize_result(result)))
                        return result
                    except Exception as exc:
                        latency_ms = (time.monotonic() - start) * 1000
                        span.set_attribute("task_id", task_id or "")
                        span.set_attribute("span_kind", kind)
                        span.set_attribute("latency_ms", latency_ms)
                        # interrupt() unwinds via GraphInterrupt (a normal Exception subclass)
                        # to pause the graph -- that's a pause, not a failure; don't mark it as
                        # a trace error or it'll look like every human-review node crashed.
                        if _is_graph_bubble_up(exc):
                            span.set_attribute("status", "paused")
                        else:
                            span.set_attribute("status", "error")
                            span.set_attribute("error", str(exc))
                            span.record_exception(exc)
                        raise
            finally:
                current_task_id.reset(task_token)
                current_subtask_id.reset(subtask_token)
                current_node_name.reset(node_token)

        return wrapper

    return decorator


def traced_tool_call(name: str) -> "trace.Span":
    """Context manager for wrapping a single tool invocation in a span, nested under whatever
    node span is currently active. Used by the tool registry."""
    tracer = get_tracer()
    return tracer.start_as_current_span(f"tool:{name}")


def record_llm_usage(*, model: str, input_tokens: int, output_tokens: int, latency_ms: float = 0.0) -> None:
    from orchestrator.observability.cost import compute_cost

    tracer = get_tracer()
    cost = compute_cost(model, input_tokens, output_tokens)
    task_id = current_task_id.get()
    node_name = current_node_name.get()
    with tracer.start_as_current_span("llm_call") as span:
        span.set_attribute("task_id", task_id or "")
        span.set_attribute("span_kind", "llm_call")
        span.set_attribute("status", "success")
        span.set_attribute("latency_ms", latency_ms)
        span.set_attribute("model", model or "unknown")
        span.set_attribute("node_name", node_name or "")
        span.set_attribute("input_tokens", input_tokens)
        span.set_attribute("output_tokens", output_tokens)
        span.set_attribute("cost_usd", cost)
