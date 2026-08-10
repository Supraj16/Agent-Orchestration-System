from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), nullable=True)
    user_request: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|completed|escalated|failed
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    """Also used as the Chroma vector id, so Postgres and Chroma always agree on identity."""
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    user_id: Mapped[str] = mapped_column(String(255), default="default")
    summary: Mapped[str] = mapped_column(Text)
    """The text that was embedded — human-readable, also what similarity search matches against."""
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    access_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    level: Mapped[str] = mapped_column(String(32))  # ApprovalLevel value
    kind: Mapped[str] = mapped_column(String(32))  # "plan" | "sensitive_action" | "takeover_subtask"
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|resolved|acknowledged
    context: Mapped[dict] = mapped_column(JSON)
    resolution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolver: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Span(Base):
    """A single OpenTelemetry span, written by our custom PostgresSpanExporter. Not a hard FK to
    tasks -- spans are exported asynchronously and must never be lost or blocked by ordering
    relative to the Task row's own commits."""

    __tablename__ = "spans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    span_id: Mapped[str] = mapped_column(String(32))
    parent_span_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(32))
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    span_kind: Mapped[str] = mapped_column(String(32))  # agent | tool | llm_call | system
    status: Mapped[str] = mapped_column(String(32), default="success")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[float] = mapped_column(Float)
    attributes: Mapped[dict] = mapped_column(JSON)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    subtask_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128))
    inputs: Mapped[dict] = mapped_column(JSON)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
