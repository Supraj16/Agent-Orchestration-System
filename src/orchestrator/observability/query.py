"""Read-side queries backing the Trace Explorer and Cost Dashboard: reconstructing a trace tree
for one task, and aggregating cost/tool-usage/escalation stats across tasks."""
from __future__ import annotations

from sqlalchemy import func

from orchestrator.db.models import Span, Task, ToolCall
from orchestrator.db.session import session_scope


def list_recent_tasks(limit: int = 50) -> list[dict]:
    with session_scope() as session:
        rows = session.query(Task).order_by(Task.created_at.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "user_request": row.user_request,
                "status": row.status,
                "escalated": row.escalated,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def get_trace_tree(task_id: str) -> list[dict]:
    """Flat list of spans for a task, most useful when the caller builds a tree from
    parent_span_id itself (see the Streamlit Trace Explorer for the recursive renderer)."""
    with session_scope() as session:
        rows = session.query(Span).filter(Span.task_id == task_id).order_by(Span.start_time.asc()).all()
        return [
            {
                "span_id": row.span_id,
                "parent_span_id": row.parent_span_id,
                "name": row.name,
                "span_kind": row.span_kind,
                "status": row.status,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "latency_ms": row.latency_ms,
                "attributes": row.attributes,
            }
            for row in rows
        ]


def get_task_cost_summary(task_id: str) -> dict:
    with session_scope() as session:
        llm_spans = session.query(Span).filter(Span.task_id == task_id, Span.span_kind == "llm_call").all()
        tool_calls = session.query(ToolCall).filter(ToolCall.task_id == task_id).count()

        total_cost = sum(s.attributes.get("cost_usd", 0.0) for s in llm_spans)
        total_input_tokens = sum(s.attributes.get("input_tokens", 0) for s in llm_spans)
        total_output_tokens = sum(s.attributes.get("output_tokens", 0) for s in llm_spans)
        by_model: dict[str, dict] = {}
        for s in llm_spans:
            model = s.attributes.get("model", "unknown")
            entry = by_model.setdefault(model, {"calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0})
            entry["calls"] += 1
            entry["cost_usd"] += s.attributes.get("cost_usd", 0.0)
            entry["input_tokens"] += s.attributes.get("input_tokens", 0)
            entry["output_tokens"] += s.attributes.get("output_tokens", 0)

        return {
            "total_cost_usd": total_cost,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "llm_call_count": len(llm_spans),
            "tool_call_count": tool_calls,
            "by_model": by_model,
        }


def get_aggregate_cost_stats(limit_tasks: int = 200) -> dict:
    """Cost/perf rollup across recent tasks: total spend, spend by model, spend by agent node,
    tool usage counts, and escalation rate."""
    with session_scope() as session:
        recent_task_ids = [
            row[0]
            for row in session.query(Task.id).order_by(Task.created_at.desc()).limit(limit_tasks).all()
        ]
        if not recent_task_ids:
            return {
                "total_cost_usd": 0.0,
                "task_count": 0,
                "escalation_rate": 0.0,
                "by_model": {},
                "by_node": {},
                "tool_usage": {},
            }

        llm_spans = (
            session.query(Span)
            .filter(Span.task_id.in_(recent_task_ids), Span.span_kind == "llm_call")
            .all()
        )
        by_model: dict[str, dict] = {}
        by_node: dict[str, dict] = {}
        total_cost = 0.0
        for s in llm_spans:
            cost = s.attributes.get("cost_usd", 0.0)
            total_cost += cost
            model = s.attributes.get("model", "unknown")
            node = s.attributes.get("node_name", "unknown")
            m_entry = by_model.setdefault(model, {"calls": 0, "cost_usd": 0.0})
            m_entry["calls"] += 1
            m_entry["cost_usd"] += cost
            n_entry = by_node.setdefault(node, {"calls": 0, "cost_usd": 0.0})
            n_entry["calls"] += 1
            n_entry["cost_usd"] += cost

        tool_rows = (
            session.query(ToolCall.tool_name, func.count(ToolCall.id))
            .filter(ToolCall.task_id.in_(recent_task_ids))
            .group_by(ToolCall.tool_name)
            .all()
        )
        tool_usage = {name: count for name, count in tool_rows}

        escalated_count = (
            session.query(Task).filter(Task.id.in_(recent_task_ids), Task.escalated.is_(True)).count()
        )

        return {
            "total_cost_usd": total_cost,
            "task_count": len(recent_task_ids),
            "escalation_rate": escalated_count / len(recent_task_ids),
            "by_model": by_model,
            "by_node": by_node,
            "tool_usage": tool_usage,
        }
