import json
import re
import uuid
from datetime import datetime, timezone

from policy import auto_approval
from orchestrator import capability_gate
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
    if not requires_manual_approval(task):
        await save_pending(task)
        return

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


def requires_manual_approval(task: Task) -> bool:
    if task.risk_level == "high":
        return True
    if task.risk_level != "medium":
        return False

    approval_steps = _approval_target_steps(task)
    if not approval_steps:
        return True
    return any(not auto_approval.is_auto_approved(step.tool, step.params) for step in approval_steps)


def record_approved_patterns(task: Task) -> list[dict]:
    if task.risk_level != "medium":
        return []
    return [auto_approval.record_approved_pattern(step.tool, step.params) for step in _approval_target_steps(task)]


async def run(task: Task, *, persist: bool = True) -> Task:
    """Task를 받아 순서대로 Tool 실행."""
    missing_capabilities = capability_gate.check_capabilities(task.steps)
    if missing_capabilities:
        _mark_task_needs_setup(task, missing_capabilities)
        if not persist:
            await record_task_trace(
                task.id,
                stage="orchestrator",
                event="needs_setup_without_persistence",
                status=task.status,
                detail={"missing_capabilities": missing_capabilities},
            )
            return task

        async with AsyncSessionLocal() as session:
            await _update_db(task, session)
            await record_task_trace(
                task.id,
                stage="orchestrator",
                event="needs_setup",
                status=task.status,
                detail={"missing_capabilities": missing_capabilities},
                session=session,
            )
        return task

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
            ai_process_tool = registry.get("ai_process")
            if ai_process_tool is not None and step.params:
                logger.warning(f"[{task.id}] tool '{step.tool}' not found, falling back to ai_process")
                await record_task_trace(
                    task.id,
                    stage="orchestrator",
                    event="tool_fallback_to_ai_process",
                    status=task.status,
                    detail={"step_index": i + 1, "original_tool": step.tool},
                    session=session,
                )
                instruction = step.description or step.params.get("instruction") or f"Perform: {step.tool}"
                text = step.params.get("text") or step.params.get("content") or step.params.get("input") or ""
                step.params = {"text": str(text), "instruction": str(instruction)}
                step.tool = "ai_process"
                tool = ai_process_tool
                task.used_ai = True
            else:
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
            # Crawler HTTP/network failure → auto-fallback to browser_auto extract_text
            if step.tool == "crawler" and step.params.get("url"):
                fallback = _build_crawler_fallback_step(step)
                if fallback is not None:
                    task.steps.insert(step_index + 1, fallback)
                    if session is not None:
                        await _log(task.id, "info", f"step {i+1} crawler failed, auto-fallback to browser_auto", session)
                    await record_task_trace(
                        task.id,
                        stage="orchestrator",
                        event="crawler_auto_fallback",
                        status=task.status,
                        detail={"step_index": i + 1, "url": step.params.get("url")},
                        session=session,
                    )
                    step_index += 1
                    continue

            error = result.get("error", "unknown error")

            # Missing param errors → ask clarification instead of failing
            clarification = _maybe_clarification(step.tool, error, task.command)
            if clarification is not None:
                task.status = "needs_clarification"
                task.summary = clarification
                task.result_data = {
                    **task.result_data,
                    "clarification": {
                        "original_command": task.command,
                        "attempt": 1,
                        "max_attempts": 3,
                        "history": [],
                        "question": clarification,
                    },
                }
                if session is not None:
                    await _log(task.id, "info", f"step {i+1} missing param, asking clarification", session)
                await record_task_trace(
                    task.id,
                    stage="orchestrator",
                    event="step_needs_clarification",
                    status=task.status,
                    detail={"step_index": i + 1, "tool": step.tool, "error": error},
                    session=session,
                )
                return

            if session is not None:
                await _log(task.id, "error", f"step {i+1} failed: {error}", session)
            task.status = "failed"
            task.error = error
            task.summary = _friendly_error(step.tool, error, task.command)
            await record_task_trace(
                task.id,
                stage="orchestrator",
                event="step_failed",
                status=task.status,
                detail={"step_index": i + 1, "tool": step.tool},
                session=session,
            )
            return

        # Crawler quality insufficient (short text, CAPTCHA) → auto-fallback to browser_auto
        if step.tool == "crawler" and quality.status == "insufficient" and step.params.get("url"):
            fallback = _build_crawler_fallback_step(step)
            if fallback is not None:
                task.steps.insert(step_index + 1, fallback)
                if session is not None:
                    await _log(task.id, "info", f"step {i+1} crawler quality insufficient, auto-fallback to browser_auto", session)
                await record_task_trace(
                    task.id,
                    stage="orchestrator",
                    event="crawler_quality_fallback",
                    status=task.status,
                    detail={"step_index": i + 1, "url": step.params.get("url"), "quality": quality.status},
                    session=session,
                )
                step_index += 1
                continue

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
            continuation = await ai_agent.continue_task(
                task.command,
                {
                    "summary": task.summary,
                    "results": task.results,
                    **task.result_data,
                },
            )
            continuation_steps = [
                Step(
                    tool=item["tool"],
                    params=item["params"],
                    description=item.get("description", ""),
                )
                for item in (continuation or {}).get("steps", [])
                if item.get("tool") and isinstance(item.get("params"), dict)
            ]
            if continuation_steps:
                task.used_ai = True
                task.intent = str((continuation or {}).get("intent") or task.intent or task.command)
                task.steps.extend(continuation_steps)
                await record_task_trace(
                    task.id,
                    stage="orchestrator",
                    event="ai_continuation_planned",
                    status=task.status,
                    detail={"after_step_index": i + 1, "step_count": len(continuation_steps)},
                    session=session,
                )
                if session is not None:
                    await _log(task.id, "info", f"step {i+1} AI continuation planned {len(continuation_steps)} step(s)", session)
                step_index += 1
                continue
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


_FRIENDLY_ERRORS: dict[str, dict[str, str]] = {
    "content is required": {
        "draft_helper": "메시지 내용을 파악하지 못했습니다. 보내실 내용을 좀 더 구체적으로 말씀해주세요.",
        "_default": "작업에 필요한 내용이 부족합니다. 좀 더 구체적으로 말씀해주세요.",
    },
    "text and mode are required": {
        "communication_helper": "문자/카카오톡 내용과 발송 방법을 파악하지 못했습니다. 보내실 내용을 좀 더 구체적으로 말씀해주세요.",
        "_default": "작업에 필요한 정보가 부족합니다. 좀 더 구체적으로 말씀해주세요.",
    },
    "text is required": {
        "_default": "처리할 텍스트를 파악하지 못했습니다. 내용을 좀 더 구체적으로 말씀해주세요.",
    },
    "query is required": {
        "reservation_helper": "검색할 장소나 키워드를 파악하지 못했습니다. 좀 더 구체적으로 말씀해주세요.",
        "_default": "검색어를 파악하지 못했습니다. 좀 더 구체적으로 말씀해주세요.",
    },
    "missing text": {
        "ai_process": "AI가 처리할 내용을 파악하지 못했습니다. 요청을 좀 더 구체적으로 말씀해주세요.",
        "_default": "처리할 내용이 부족합니다. 좀 더 구체적으로 말씀해주세요.",
    },
    "url is required": {
        "_default": "웹 주소를 찾지 못했습니다. URL을 포함해서 다시 요청해주세요.",
    },
}


_CLARIFICATION_QUESTIONS: dict[str, dict[str, str]] = {
    "content is required": {
        "draft_helper": "어떤 내용으로 보내드릴까요?",
        "_default": "어떤 내용을 작성해드릴까요?",
    },
    "text and mode are required": {
        "communication_helper": "어떤 내용으로, 어떤 방법(문자/카카오톡)으로 보내드릴까요?",
    },
    "text is required": {
        "_default": "어떤 내용을 처리해드릴까요?",
    },
    "query is required": {
        "reservation_helper": "어떤 장소를 찾아드릴까요?",
        "_default": "어떤 키워드로 검색해드릴까요?",
    },
    "missing text": {
        "ai_process": "어떤 내용을 도와드릴까요?",
    },
}


def _maybe_clarification(tool: str, error: str, command: str) -> str | None:
    """Return a follow-up question if the error is a missing-param type, else None."""
    error_lower = (error or "").strip().lower()
    for pattern, questions in _CLARIFICATION_QUESTIONS.items():
        if pattern in error_lower:
            return questions.get(tool, questions.get("_default", None))
    return None


def _friendly_error(tool: str, error: str, command: str) -> str:
    """Convert raw tool errors to user-friendly messages."""
    error_lower = (error or "").strip().lower()
    for pattern, messages in _FRIENDLY_ERRORS.items():
        if pattern in error_lower:
            return messages.get(tool, messages.get("_default", str(error)))

    # Generic fallback for unknown errors
    if "not found" in error_lower:
        return "요청을 처리할 도구를 찾지 못했습니다. 다시 시도해주세요."
    if "timeout" in error_lower:
        return "요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
    if "connection" in error_lower or "network" in error_lower:
        return "네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인해주세요."

    return f"요청을 처리하는 중 문제가 발생했습니다. ({error})"


def _build_crawler_fallback_step(crawler_step: Step) -> Step | None:
    """Build a browser_auto extract_text step as fallback for a failed/insufficient crawler step."""
    url = crawler_step.params.get("url")
    if not url:
        return None
    return Step(
        tool="browser_auto",
        params={"action": "extract_text", "url": url, "headless": True},
        description=f"crawler fallback: Playwright로 텍스트 추출 ({url})",
    )


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


def _mark_task_needs_setup(task: Task, missing_capabilities: list[dict]) -> None:
    primary = missing_capabilities[0]
    task.status = "needs_setup"
    task.summary = str(primary.get("setup_message") or "")
    task.result_data = {
        **task.result_data,
        "missing_capabilities": missing_capabilities,
        "setup_action": {
            "connection_id": primary.get("connection_id"),
            "capability": primary.get("capability_name"),
            "action": primary.get("setup_action"),
        },
        "setup_message": primary.get("setup_message"),
        "fallback_available": any(bool(item.get("fallback_available")) for item in missing_capabilities),
        "fallback_description": primary.get("fallback_description") or "",
    }


async def _update_db(task: Task, session):
    from sqlalchemy import select
    result = await session.execute(select(TaskModel).where(TaskModel.id == task.id))
    row = result.scalar_one_or_none()

    if row is None:
        row = TaskModel(id=task.id, command=task.command)
        session.add(row)

    try:
        row.status = TaskStatus(task.status)
    except ValueError:
        row.status = task.status
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


def _approval_target_steps(task: Task) -> list[Step]:
    steps = [step for step in task.steps if step.risk_level == "medium"]
    if steps:
        return steps
    if task.risk_level == "medium":
        return list(task.steps)
    return []


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
