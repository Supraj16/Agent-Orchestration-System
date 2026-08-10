from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestrator.hitl.approval_queue import get_approval, get_pending_approvals
from orchestrator.hitl.resume import resume_task

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ResolveApprovalRequest(BaseModel):
    action: str  # approve | modify | reject | take_over
    edited_content: str | None = None
    resolver: str = "api"


@router.get("")
def list_pending():
    return get_pending_approvals()


@router.post("/{approval_id}/resolve")
def resolve(approval_id: str, payload: ResolveApprovalRequest):
    approval = get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    resolution = {"action": payload.action, "edited_content": payload.edited_content, "resolver": payload.resolver}
    result = resume_task(approval["task_id"], resolution)
    return {"paused": result["paused"], "final_output": result["values"].get("final_output")}
