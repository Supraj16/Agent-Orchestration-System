"""Durable approval queue backed by Postgres. Separate from LangGraph's own interrupt/checkpoint
machinery so a UI in a different process (Streamlit) can list and resolve pending approvals
just by querying the database — it doesn't need to know anything about LangGraph."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from orchestrator.db.models import Approval
from orchestrator.db.session import session_scope


def create_approval(*, task_id: str, level: str, kind: str, context: dict, status: str = "pending") -> str:
    approval_id = str(uuid.uuid4())
    with session_scope() as session:
        session.add(
            Approval(id=approval_id, task_id=task_id, level=level, kind=kind, context=context, status=status)
        )
    return approval_id


def resolve_approval(approval_id: str, resolution: dict, resolver: str | None = None) -> None:
    with session_scope() as session:
        approval = session.get(Approval, approval_id)
        if approval is None:
            return
        approval.status = "resolved"
        approval.resolution = resolution
        approval.resolver = resolver or resolution.get("resolver")
        approval.resolved_at = datetime.now(timezone.utc)


def get_approval(approval_id: str) -> dict | None:
    with session_scope() as session:
        approval = session.get(Approval, approval_id)
        if approval is None:
            return None
        return _to_dict(approval)


def get_pending_approvals() -> list[dict]:
    with session_scope() as session:
        rows = (
            session.query(Approval)
            .filter(Approval.status == "pending")
            .order_by(Approval.created_at.asc())
            .all()
        )
        return [_to_dict(row) for row in rows]


def get_recent_approvals(limit: int = 50) -> list[dict]:
    with session_scope() as session:
        rows = session.query(Approval).order_by(Approval.created_at.desc()).limit(limit).all()
        return [_to_dict(row) for row in rows]


def _to_dict(approval: Approval) -> dict:
    return {
        "id": approval.id,
        "task_id": approval.task_id,
        "level": approval.level,
        "kind": approval.kind,
        "status": approval.status,
        "context": approval.context,
        "resolution": approval.resolution,
        "resolver": approval.resolver,
        "created_at": approval.created_at,
        "resolved_at": approval.resolved_at,
    }
