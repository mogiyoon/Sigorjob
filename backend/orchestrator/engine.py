import json
import uuid
from datetime import datetime, timezone

from orchestrator.task import Step, Task
from orchestrator import result_quality
from tools import registry
from ai import agent as ai_agent
from ai import summarizer
from ai import reviewer as ai_reviewer
from db.models import ApprovalRequest, ApprovalStatus, Task as TaskModel, TaskLog, TaskStatus
from db.session import AsyncSessionLocal
from logger.logger import get_logger
from notifications.store import enqueue_notification

logger = get_logger(__name__)


async def save_pending(task: Task) -> None:
    async with AsyncSessionLocal() as session:
        await _update_db(task, session)


async def save_approval_request(task: Task) -> None:
    async with AsyncSessionLocal() as session:
        task.status = "approval_required"
        task.summary = task.approval_reason or "승인이 필요한 작업입니다."
        await _update_db(task, session)
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=task.id,
            command=task.command,
            risk_level=task.risk_level,
            reason=task.approval_reason or None,
            status=ApprovalStatus.pending,
        )
        session.add(approval)
        await session.commit()


async def run(task: Task, *, persist: bool = True) -> Task:
    """Task를 받아 순서대로 Tool 실행."""
    if not persist:
        return await _run_without_persistence(task)

    async with AsyncSessionLocal() as session:
        task.status = "running"
        await _update_db(task, session)
        logger.info(f"[{task.id}] start — {task.command}")
        await _execute_steps(task, session=session)
        task.completed_at = datetime.now(timezone.utc)
        await _update_db(task, session)
        logger.info(f"[{task.id}] {task.status}")

    return task


async def _run_without_persistence(task: Task) -> Task:
    task.status = "running"
    logger.info(f"[{task.id}] start — {task.command}")
    await _execute_steps(task, session=None)
    task.completed_at = datetime.now(timezone.utc)
    logger.info(f"[{task.id}] {task.status}")
    return task


async def _execute_steps(task: Task, session=None) -> None:
    review_budget = 1
    postflight_budget = 1
    step_index = 0
    while step_index < len(task.steps):
        i = step_index
        step = task.steps[step_index]
        tool = registry.get(step.tool)
        if tool is None:
            error = f"tool not found: {step.tool}"
            if session is not None:
                await _log(task.id, "error", error, session)
            task.status = "failed"
            task.error = error
            return

        if session is not None:
            await _log(task.id, "info", f"step {i+1}: {step.description or step.tool}", session)

        result = await tool.run(step.params)
        quality = result_quality.evaluate(step.tool, step.params, result)
        result["quality"] = quality.to_dict()
        step.result = result
        task.results.append(result)

        if not result.get("success"):
            error = result.get("error", "unknown error")
            if session is not None:
                await _log(task.id, "error", f"step {i+1} failed: {error}", session)
            task.status = "failed"
            task.error = error
            task.summary = str(error)
            return

        if _should_postflight_review(step, result) and postflight_budget > 0:
            postflight_budget -= 1
            review = await ai_reviewer.postflight(
                task.command,
                {
                    "tool": step.tool,
                    "params": step.params,
                    "description": step.description,
                },
                result,
            )
            if review and not review.get("acceptable", True):
                continuation_steps = await _build_ai_takeover_steps(task)
                if continuation_steps:
                    task.steps[step_index + 1:step_index + 1] = continuation_steps
                    if session is not None:
                        await _log(task.id, "warning", f"step {i+1} AI postflight handed off to AI continuation", session)
                    step_index += 1
                    continue

                retry_step = review.get("retry_step") or {}
                if retry_step.get("tool") and isinstance(retry_step.get("params"), dict):
                    inserted = Step(
                        tool=retry_step["tool"],
                        params=retry_step["params"],
                        description=retry_step.get("description", "ai_postflight_retry"),
                    )
                    task.steps.insert(step_index + 1, inserted)
                    if session is not None:
                        await _log(task.id, "warning", f"step {i+1} AI postflight requested retry: {inserted.description}", session)
                    step_index += 1
                    continue
                if session is not None:
                    await _log(task.id, "error", f"step {i+1} AI postflight rejected result: {review.get('reason', 'result mismatch')}", session)
                task.status = "failed"
                task.error = str(review.get("reason") or "AI postflight rejected the final action.")
                task.summary = task.error
                return

        if quality.needs_ai_review and review_budget > 0:
            review_budget -= 1
            review = await ai_reviewer.review(
                task.command,
                {
                    "tool": step.tool,
                    "params": step.params,
                    "description": step.description,
                },
                result,
                quality.to_dict(),
            )
            if review:
                result["ai_review"] = review
                if review.get("acceptable"):
                    if session is not None:
                        await _log(task.id, "info", f"step {i+1} AI review accepted result", session)
                    step_index += 1
                    continue
                retry_step = review.get("retry_step")
                if retry_step and retry_step.get("tool") and retry_step.get("params"):
                    inserted = Step(
                        tool=retry_step["tool"],
                        params=retry_step["params"],
                        description=retry_step.get("description", "ai_retry"),
                    )
                    task.steps.insert(step_index + 1, inserted)
                    if session is not None:
                        await _log(task.id, "warning", f"step {i+1} AI requested retry: {inserted.description}", session)
                    step_index += 1
                    continue

        if quality.blocking:
            if session is not None:
                await _log(task.id, "warning", f"step {i+1} quality insufficient: {quality.message}", session)
            task.status = "failed"
            task.error = quality.message
            task.summary = quality.message
            return

        step_index += 1

    task.status = "done"
    task.summary = await summarizer.summarize(task.command, task.results)
    if "모바일" in task.command.lower() or "mobile" in task.command.lower():
        task.summary = f"{task.summary} 모바일 앱의 작업 목록에서도 확인할 수 있습니다.".strip()
    _maybe_enqueue_mobile_notification(task)


def _maybe_enqueue_mobile_notification(task: Task) -> None:
    command = (task.command or "").lower()
    should_notify = any(keyword in command for keyword in ("모바일", "mobile", "알림", "notify"))
    if not should_notify:
        for result in task.results:
            data = result.get("data") or {}
            if isinstance(data, dict) and data.get("notify_mobile"):
                should_notify = True
                break
    if not should_notify:
        return

    title = "Sigorjob 알림"
    if "날씨" in command:
        title = "날씨 알림"
    elif "메일" in command or "이메일" in command:
        title = "메일 작업 알림"

    body = task.summary or task.error or "새 작업 결과가 준비되었습니다."
    enqueue_notification(title=title, body=body)


async def _update_db(task: Task, session):
    from sqlalchemy import select
    result = await session.execute(select(TaskModel).where(TaskModel.id == task.id))
    row = result.scalar_one_or_none()

    if row is None:
        row = TaskModel(id=task.id, command=task.command)
        session.add(row)

    row.status = TaskStatus(task.status)
    row.plan = json.dumps(
        [
            {
                "tool": s.tool,
                "params": s.params,
                "description": s.description,
                "risk_level": s.risk_level,
            }
            for s in task.steps
        ]
    )
    row.result = json.dumps({"summary": task.summary, "results": task.results})
    row.error = task.error or None
    row.completed_at = task.completed_at
    await session.commit()


async def _log(task_id: str, level: str, message: str, session):
    log = TaskLog(id=str(uuid.uuid4()), task_id=task_id, level=level, message=message)
    session.add(log)
    await session.commit()


def deserialize_task(task_id: str, command: str, plan_json: str | None) -> Task:
    steps_data = json.loads(plan_json or "[]")
    task = Task(id=task_id, command=command)
    task.steps = [
        Step(
            tool=step["tool"],
            params=step["params"],
            description=step.get("description", ""),
            risk_level=step.get("risk_level", "low"),
        )
        for step in steps_data
    ]
    return task


def _should_postflight_review(step: Step, result: dict) -> bool:
    if step.tool in {"browser", "crawler"}:
        return True
    data = result.get("data") or {}
    return isinstance(data, dict) and data.get("action") == "open_url"


async def _build_ai_takeover_steps(task: Task) -> list[Step]:
    continuation = await ai_agent.continue_task(
        task.command,
        {
            "summary": task.summary,
            "results": task.results,
        },
    )
    if not continuation:
        return []

    steps = continuation.get("steps", [])
    if not isinstance(steps, list):
        return []

    return [
        Step(
            tool=step["tool"],
            params=step["params"],
            description=step.get("description", "ai_takeover"),
        )
        for step in steps
        if step.get("tool") and isinstance(step.get("params"), dict)
    ]
