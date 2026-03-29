import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from db.session import get_session
from db.models import ApprovalRequest, Task as TaskModel, TaskLog
from intent import router as intent_router
from orchestrator import engine as orchestrator

router = APIRouter()


class CommandRequest(BaseModel):
    text: str
    context: dict = {}


class DeleteTasksRequest(BaseModel):
    task_ids: list[str]


class TaskResponse(BaseModel):
    task_id: str
    command: str | None = None
    status: str
    result: dict | None = None
    created_at: str | None = None
    completed_at: str | None = None


@router.post("/command", response_model=TaskResponse)
async def command(req: CommandRequest):
    task = await intent_router.route(req.text)

    if not task.steps:
        return TaskResponse(
            task_id=task.id,
            command=req.text,
            status="failed",
            result={"summary": "실행 가능한 작업을 찾지 못했습니다.", "results": []},
        )

    if task.risk_level in {"medium", "high"}:
        await orchestrator.save_approval_request(task)
        return TaskResponse(
            task_id=task.id,
            command=req.text,
            status="approval_required",
            result={
                "summary": task.approval_reason or "승인이 필요한 작업입니다.",
                "results": [],
            },
        )

    await orchestrator.save_pending(task)
    asyncio.create_task(orchestrator.run(task))

    return TaskResponse(task_id=task.id, command=req.text, status="pending")


@router.get("/tasks")
async def list_tasks(limit: int = 20, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TaskModel).order_by(TaskModel.created_at.desc()).limit(max(1, min(limit, 100)))
    )
    rows = result.scalars().all()

    return {
        "tasks": [
            {
                "task_id": row.id,
                "command": row.command,
                "status": row.status.value,
                "result": json.loads(row.result) if row.result else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
            for row in rows
        ]
    }


@router.get("/task/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="task not found")

    result_data = json.loads(row.result) if row.result else None
    return TaskResponse(
        task_id=row.id,
        command=row.command,
        status=row.status.value,
        result=result_data,
        created_at=row.created_at.isoformat() if row.created_at else None,
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
    )


@router.post("/task/{task_id}/retry", response_model=TaskResponse)
async def retry_task(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    row = result.scalar_one_or_none()

    if row is None:
      raise HTTPException(status_code=404, detail="task not found")

    retry_task_plan = await intent_router.route(row.command)

    if not retry_task_plan.steps:
        return TaskResponse(
            task_id=retry_task_plan.id,
            command=row.command,
            status="failed",
            result={"summary": "재실행 가능한 작업을 찾지 못했습니다.", "results": []},
        )

    if retry_task_plan.risk_level in {"medium", "high"}:
        await orchestrator.save_approval_request(retry_task_plan)
        return TaskResponse(
            task_id=retry_task_plan.id,
            command=row.command,
            status="approval_required",
            result={
                "summary": retry_task_plan.approval_reason or "승인이 필요한 작업입니다.",
                "results": [],
            },
        )

    await orchestrator.save_pending(retry_task_plan)
    asyncio.create_task(orchestrator.run(retry_task_plan))
    return TaskResponse(task_id=retry_task_plan.id, command=row.command, status="pending")


@router.delete("/task/{task_id}")
async def delete_task(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="task not found")

    await session.execute(delete(TaskLog).where(TaskLog.task_id == task_id))
    await session.execute(delete(ApprovalRequest).where(ApprovalRequest.task_id == task_id))
    await session.delete(row)
    await session.commit()

    return {"success": True, "task_id": task_id}


@router.post("/tasks/delete")
async def delete_tasks(req: DeleteTasksRequest, session: AsyncSession = Depends(get_session)):
    task_ids = list(dict.fromkeys([task_id for task_id in req.task_ids if task_id]))
    if not task_ids:
        raise HTTPException(status_code=400, detail="no task ids provided")

    result = await session.execute(select(TaskModel.id).where(TaskModel.id.in_(task_ids)))
    existing_ids = set(result.scalars().all())
    if not existing_ids:
        raise HTTPException(status_code=404, detail="tasks not found")

    await session.execute(delete(TaskLog).where(TaskLog.task_id.in_(existing_ids)))
    await session.execute(delete(ApprovalRequest).where(ApprovalRequest.task_id.in_(existing_ids)))
    await session.execute(delete(TaskModel).where(TaskModel.id.in_(existing_ids)))
    await session.commit()

    return {"success": True, "deleted_task_ids": sorted(existing_ids)}
