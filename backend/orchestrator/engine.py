import json
import re
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
from debug_trace import record_task_trace

logger = get_logger(__name__)
_TEMPLATE_PATTERN = re.compile(r"\$\{([^{}]+)\}")


async def save_pending(task: Task) -> None:
    async with AsyncSessionLocal() as session:
        await _update_db(task, session)
        await record_task_trace(
            task.id,
            stage="orchestrator",
            event="state_persisted",
            status=task.status,
            detail={"step_count": len(task.steps), "result_count": len(task.results)},
            session=session,
        )


async def save_approval_request(task: Task) -> None:
    async with AsyncSessionLocal() as session:
        task.status = "approval_required"
        task.summary = task.approval_reason or "승인이 필요한 작업입니다."
        await _update_db(task, session)
        await record_task_trace(
            task.id,
            stage="orchestrator",
            event="approval_saved",
            status=task.status,
            detail={"risk_level": task.risk_level, "step_count": len(task.steps)},
            session=session,
        )
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
        await record_task_trace(
            task.id,
            stage="orchestrator",
            event="run_started",
            status=task.status,
            detail={"step_count": len(task.steps)},
            session=session,
        )
        logger.info(f"[{task.id}] start — {task.command}")
        await _execute_steps(task, session=session)
        task.completed_at = datetime.now(timezone.utc)
        await _update_db(task, session)
        await record_task_trace(
            task.id,
            stage="orchestrator",
            event="run_finished",
            status=task.status,
            detail={"result_count": len(task.results), "has_error": bool(task.error)},
            session=session,
        )
        logger.info(f"[{task.id}] {task.status}")

    return task


async def _run_without_persistence(task: Task) -> Task:
    task.status = "running"
    await record_task_trace(
        task.id,
        stage="orchestrator",
        event="run_started_without_persistence",
        status=task.status,
        detail={"step_count": len(task.steps)},
    )
    logger.info(f"[{task.id}] start — {task.command}")
    await _execute_steps(task, session=None)
    task.completed_at = datetime.now(timezone.utc)
    await record_task_trace(
        task.id,
        stage="orchestrator",
        event="run_finished_without_persistence",
        status=task.status,
        detail={"result_count": len(task.results), "has_error": bool(task.error)},
    )
    logger.info(f"[{task.id}] {task.status}")
    return task


async def _execute_steps(task: Task, session=None) -> None:
    review_budget = 3
    step_index = 0
    while step_index < len(task.steps):
        i = step_index
        step = task.steps[step_index]
        if not _should_execute_step(task, step):
            await record_task_trace(
                task.id,
                stage="orchestrator",
                event="step_skipped",
                status=task.status,
                detail={"step_index": i + 1, "tool": step.tool, "condition": step.condition},
                session=session,
            )
            step_index += 1
            continue

        if step.param_template:
            step.params = _resolve_template_value(step.params, task)

        await record_task_trace(
            task.id,
            stage="orchestrator",
            event="step_started",
            status=task.status,
            detail={"step_index": i + 1, "tool": step.tool, "risk_level": step.risk_level},
            session=session,
        )
        tool = registry.get(step.tool)
        if tool is None:
            error = f"tool not found: {step.tool}"
            if session is not None:
                await _log(task.id, "error", error, session)
            task.status = "failed"
            task.error = error
            await record_task_trace(
                task.id,
                stage="orchestrator",
                event="tool_missing",
                status=task.status,
                detail={"step_index": i + 1, "tool": step.tool},
                session=session,
            )
            return

        if session is not None:
            await _log(task.id, "info", f"step {i+1}: {step.description or step.tool}", session)

        result = await tool.run(step.params)
        quality = result_quality.evaluate(step.tool, step.params, result)
        result["quality"] = quality.to_dict()
        step.result = result
        task.results.append(result)
        await record_task_trace(
            task.id,
            stage="orchestrator",
            event="step_completed",
            status=task.status,
            detail={
                "step_index": i + 1,
                "tool": step.tool,
                "success": bool(result.get("success")),
                "quality_status": quality.status,
                "quality_blocking": quality.blocking,
                "needs_ai_review": quality.needs_ai_review,
            },
            session=session,
        )

        if not result.get("success"):
            error = result.get("error", "unknown error")
            if session is not None:
                await _log(task.id, "error", f"step {i+1} failed: {error}", session)
            task.status = "failed"
            task.error = error
            task.summary = str(error)
            await record_task_trace(
                task.id,
                stage="orchestrator",
                event="step_failed",
                status=task.status,
                detail={"step_index": i + 1, "tool": step.tool},
                session=session,
            )
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
                await record_task_trace(
                    task.id,
                    stage="orchestrator",
                    event="ai_review_completed",
                    status=task.status,
                    detail={
                        "step_index": i + 1,
                        "tool": step.tool,
                        "acceptable": bool(review.get("acceptable")),
                        "has_retry_step": bool(review.get("retry_step")),
                    },
                    session=session,
                )
                if review.get("acceptable"):
                    if session is not None:
                        await _log(task.id, "info", f"step {i+1} AI review accepted result", session)
                    task.used_ai = True
                    step_index += 1
                    continue
                inserted_steps = await _continue_with_ai_plan(task, step, result, quality.to_dict(), after_step_index=i, session=session)
                if inserted_steps:
                    step_index += 1
                    continue
                retry_step = review.get("retry_step")
                if retry_step and retry_step.get("tool") and retry_step.get("params"):
                    inserted = Step(
                        tool=retry_step["tool"],
                        params=retry_step["params"],
                        description=retry_step.get("description", "ai_retry"),
                    )
                    task.used_ai = True
                    task.steps.insert(step_index + 1, inserted)
                    if session is not None:
                        await _log(task.id, "warning", f"step {i+1} AI requested retry: {inserted.description}", session)
                    await record_task_trace(
                        task.id,
                        stage="orchestrator",
                        event="retry_step_inserted",
                        status=task.status,
                        detail={"after_step_index": i + 1, "tool": inserted.tool},
                        session=session,
                    )
                    step_index += 1
                    continue

        if quality.blocking:
            if session is not None:
                await _log(task.id, "warning", f"step {i+1} quality insufficient: {quality.message}", session)
            task.status = "failed"
            task.error = quality.message
            task.summary = quality.message
            await record_task_trace(
                task.id,
                stage="orchestrator",
                event="quality_blocked",
                status=task.status,
                detail={"step_index": i + 1, "tool": step.tool, "quality_status": quality.status},
                session=session,
            )
            return

        step_index += 1

    task.status = "done"
    task.summary = await summarizer.summarize(task.command, task.results, allow_ai=task.used_ai)
    if "모바일" in task.command.lower() or "mobile" in task.command.lower():
        task.summary = f"{task.summary} 모바일 앱의 작업 목록에서도 확인할 수 있습니다.".strip()
    _maybe_enqueue_mobile_notification(task)


async def _continue_with_ai_plan(
    task: Task,
    step: Step,
    result: dict,
    quality: dict,
    *,
    after_step_index: int,
    session=None,
) -> list[Step]:
    continuation = await ai_agent.continue_task(
        task.command,
        {
            "summary": task.summary,
            "results": task.results,
            "latest_step": {
                "tool": step.tool,
                "params": step.params,
                "description": step.description,
            },
            "latest_result": result,
            "quality": quality,
        },
    )
    if not continuation:
        return []

    inserted_steps = [
        Step(
            tool=next_step["tool"],
            params=next_step["params"],
            description=next_step.get("description", ""),
        )
        for next_step in continuation.get("steps", [])
        if next_step.get("tool") and isinstance(next_step.get("params"), dict)
    ]
    if not inserted_steps:
        return []

    task.used_ai = True
    for offset, inserted in enumerate(inserted_steps, start=1):
        task.steps.insert(after_step_index + offset, inserted)

    if session is not None:
        descriptions = ", ".join(step.description or step.tool for step in inserted_steps)
        await _log(task.id, "warning", f"AI continuation planned next steps: {descriptions}", session)

    await record_task_trace(
        task.id,
        stage="orchestrator",
        event="ai_continuation_inserted",
        status=task.status,
        detail={
            "after_step_index": after_step_index + 1,
            "step_count": len(inserted_steps),
            "tools": [step.tool for step in inserted_steps],
        },
        session=session,
    )
    return inserted_steps


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
                "condition": s.condition,
                "param_template": s.param_template,
            }
            for s in task.steps
        ]
    )
    if task.result_data:
        payload = {"summary": task.summary, "results": task.results, **task.result_data}
    else:
        payload = {"summary": task.summary, "results": task.results}
    row.result = json.dumps(payload, ensure_ascii=False)
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
            condition=step.get("condition"),
            param_template=step.get("param_template", False),
        )
        for step in steps_data
    ]
    return task


def _should_execute_step(task: Task, step: Step) -> bool:
    if step.condition is None:
        return True

    resolved = _resolve_template_value(step.condition, task)
    if isinstance(resolved, bool):
        return resolved
    if resolved is None:
        return False
    if isinstance(resolved, str):
        normalized = resolved.strip().lower()
        if normalized in {"", "0", "false", "no", "off", "none", "null"}:
            return False
    return bool(resolved)


def _resolve_template_value(value, task: Task):
    if isinstance(value, dict):
        return {key: _resolve_template_value(item, task) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_template_value(item, task) for item in value]
    if not isinstance(value, str):
        return value

    exact_match = _TEMPLATE_PATTERN.fullmatch(value)
    if exact_match:
        resolved = _resolve_reference(exact_match.group(1), task)
        return "" if resolved is _MissingValue else resolved

    def replace(match: re.Match[str]) -> str:
        resolved = _resolve_reference(match.group(1), task)
        if resolved is _MissingValue:
            return ""
        return str(resolved)

    return _TEMPLATE_PATTERN.sub(replace, value)


class _MissingValueType:
    pass


_MissingValue = _MissingValueType()


def _resolve_reference(reference: str, task: Task):
    current = {"steps": task.steps}
    for token in _parse_reference_tokens(reference):
        current = _read_reference_token(current, token)
        if current is _MissingValue:
            return _MissingValue
    return current


def _parse_reference_tokens(reference: str) -> list[str | int]:
    tokens: list[str | int] = []
    for part in reference.split("."):
        if not part:
            return []
        position = 0
        while position < len(part):
            if part[position] == "[":
                end = part.find("]", position)
                if end == -1:
                    return []
                index = part[position + 1 : end]
                if not index.isdigit():
                    return []
                tokens.append(int(index))
                position = end + 1
                continue

            next_bracket = part.find("[", position)
            if next_bracket == -1:
                tokens.append(part[position:])
                break
            tokens.append(part[position:next_bracket])
            position = next_bracket
    return tokens


def _read_reference_token(current, token: str | int):
    if isinstance(token, int):
        if isinstance(current, (list, tuple)) and 0 <= token < len(current):
            return current[token]
        return _MissingValue

    if isinstance(current, dict):
        return current.get(token, _MissingValue)

    return getattr(current, token, _MissingValue)
