import json
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ApprovalRequest, ApprovalStatus, Task as TaskModel, TaskStatus
from db.session import get_session
from orchestrator import engine as orchestrator

router = APIRouter()


class ApprovalActionRequest(BaseModel):
    action: str
    reason: str | None = None


@router.get("/approvals")
async def list_approvals(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.pending)
    )
    rows = result.scalars().all()
    return {
        "approvals": [
            {
                "task_id": row.task_id,
                "command": row.command,
                "risk_level": row.risk_level,
                "reason": row.reason,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/approval/{task_id}")
async def approval_action(
    task_id: str,
    req: ApprovalActionRequest,
    session: AsyncSession = Depends(get_session),
):
    approval_result = await session.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.task_id == task_id,
            ApprovalRequest.status == ApprovalStatus.pending,
        )
    )
    approval = approval_result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")

    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task_row = task_result.scalar_one_or_none()
    if task_row is None:
        raise HTTPException(status_code=404, detail="task not found")

    if req.action == "reject":
        approval.status = ApprovalStatus.rejected
        approval.resolved_at = datetime.now(timezone.utc)
        if req.reason:
            approval.reason = req.reason
        task_row.status = TaskStatus.cancelled
        task_row.error = req.reason or "approval rejected"
        task_row.result = json.dumps(
            {
                "summary": req.reason or "승인 거부로 작업이 취소되었습니다.",
                "results": [],
            }
        )
        task_row.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return {"task_id": task_id, "status": "cancelled"}

    if req.action != "approve":
        raise HTTPException(status_code=400, detail="invalid action")

    approval.status = ApprovalStatus.approved
    approval.resolved_at = datetime.now(timezone.utc)
    await session.commit()

    task = orchestrator.deserialize_task(task_row.id, task_row.command, task_row.plan)
    asyncio.create_task(orchestrator.run(task))
    return {"task_id": task_id, "status": "running"}
