import re
import yaml
from pathlib import Path
from orchestrator.task import Task, Step
from ai import agent as ai_agent
from ai.runtime import has_api_key
from custom_commands import match_custom_command
from intent import risk_evaluator
from intent.normalizer import (
    _looks_like_automation_request,
    allows_browser_fallback,
    build_ai_assisted_browser_intent,
    build_last_resort_intent,
    detect_intent,
    normalize_command,
)
from plugins import load_plugin_rules
from logger.logger import get_logger
from debug_trace import record_task_trace

logger = get_logger(__name__)

_rules: list[dict] = []
_TEXT_REQUIRED_TOOLS = {
    "calendar_helper",
    "communication_helper",
    "reminder_helper",
    "route_helper",
    "translation_helper",
    "weather_alert_helper",
}
_AI_BYPASS_TOOLS = {
    "calendar_helper",
    "communication_helper",
    "delivery_helper",
    "draft_helper",
    "reservation_helper",
    "route_helper",
    "travel_helper",
    "weather_alert_helper",
}
_AI_BYPASS_INTENT_CATEGORIES = {
    "crawl",
    "file_copy",
    "file_delete",
    "file_move",
    "file_read",
    "file_write",
    "open_url",
    "reminder_schedule",
    "search",
    "shopping_search",
}


def load_rules():
    global _rules
    path = Path(__file__).parent / "rules" / "rules.yaml"
    with open(path) as f:
        base_rules = yaml.safe_load(f).get("rules", [])
    _rules = [*base_rules, *load_plugin_rules()]


async def route(command: str, context: dict | None = None) -> Task:
    """명령어를 받아 Task 생성."""
    if not _rules:
        load_rules()

    clarification = _build_clarification_context(command, context or {})
    normalized_command = normalize_command(clarification["analysis_command"])
    task = Task(command=clarification["original_command"] or normalized_command)
    await record_task_trace(
        task.id,
        stage="router",
        event="route_started",
        status=task.status,
        detail={
            "command_length": len(command or ""),
            "normalized_length": len(normalized_command or ""),
            "clarification_history_count": len(clarification["history"]),
        },
    )

    custom_command = match_custom_command(normalized_command)
    if custom_command:
        logger.info(f"[{task.id}] custom command matched: {custom_command['id']}")
        await record_task_trace(
            task.id,
            stage="router",
            event="custom_command_matched",
            detail={"custom_command_id": custom_command["id"], "match_type": custom_command["match_type"]},
        )
        normalized_command = normalize_command(str(custom_command["action_text"]))
        task.intent = str(custom_command["action_text"])
        task.result_data = {
            "custom_command": {
                "id": custom_command["id"],
                "trigger": custom_command["trigger"],
                "match_type": custom_command["match_type"],
                "action_text": custom_command["action_text"],
            }
        }
        return await _route_legacy(task, normalized_command, clarification)

    if not has_api_key():
        return await _route_legacy(task, normalized_command, clarification)

    logger.info(f"[{task.id}] AI-first planning started")
    await record_task_trace(
        task.id,
        stage="router",
        event="ai_plan_requested",
        detail={"reason": "api_key_available"},
    )

    plan = await ai_agent.plan(normalized_command)
    task.intent = str(plan.get("intent", normalized_command) or normalized_command)
    task.steps = _build_steps_from_plan(plan)
    for step in task.steps:
        _hydrate_step_params(step, normalized_command)

    if task.steps:
        task.used_ai = True
        task.ai_usage["planner"] = "ai_agent.plan"
        _annotate_risk(task)
        await record_task_trace(
            task.id,
            stage="router",
            event="route_completed",
            status=task.status,
            detail={"step_count": len(task.steps), "risk_level": task.risk_level, "used_ai": True},
        )
        return task

    logger.info(f"[{task.id}] AI returned no executable steps, falling back to legacy routing")
    return await _route_legacy(task, normalized_command, clarification)


async def _route_legacy(task: Task, normalized_command: str, clarification: dict) -> Task:
    """기존 규칙 우선 라우팅 경로."""
    step = _match_rules(normalized_command)
    if step is None:
        normalized_intent = detect_intent(normalized_command)
        if normalized_intent:
            step = Step(
                tool=_intent_tool(normalized_intent.category),
                params=normalized_intent.params,
                description=normalized_intent.description,
            )
    if step:
        _hydrate_step_params(step, normalized_command)
        logger.info(f"[{task.id}] rule matched: {step.tool}")
        task.intent = normalized_command
        task.steps = [step]
        _annotate_risk(task)
        await record_task_trace(
            task.id,
            stage="router",
            event="rule_matched",
            status=task.status,
            detail={"tool": step.tool, "risk_level": task.risk_level},
        )
        return task

    if has_api_key():
        await record_task_trace(
            task.id,
            stage="router",
            event="clarification_review_started",
            detail={"history_count": len(clarification["history"])},
        )
        clarification_review = await ai_agent.request_clarification(
            clarification["analysis_command"],
            clarification["history"],
        )
        if clarification_review and clarification_review.get("needs_clarification"):
            question = str(clarification_review.get("question") or "").strip()
            if question:
                task.used_ai = True
                if len(clarification["history"]) >= 3:
                    task.status = "failed"
                    task.summary = "질문을 세 번 주고받았지만 아직 요청을 명확히 이해하지 못했습니다."
                    task.error = task.summary
                    task.result_data = {
                        "clarification": {
                            "original_command": clarification["original_command"],
                            "attempt": len(clarification["history"]),
                            "max_attempts": 3,
                            "history": clarification["history"],
                            "question": question,
                        }
                    }
                    await record_task_trace(
                        task.id,
                        stage="router",
                        event="clarification_limit_reached",
                        status="failed",
                        detail={"history_count": len(clarification["history"]), "max_attempts": 3},
                    )
                    return task

                task.status = "needs_clarification"
                task.summary = question
                task.result_data = {
                    "clarification": {
                        "original_command": clarification["original_command"],
                        "attempt": len(clarification["history"]) + 1,
                        "max_attempts": 3,
                        "history": clarification["history"],
                        "question": question,
                        }
                    }
                await record_task_trace(
                    task.id,
                    stage="router",
                    event="clarification_requested",
                    status="needs_clarification",
                    detail={"next_attempt": len(clarification["history"]) + 1, "max_attempts": 3},
                )
                return task

    logger.info(f"[{task.id}] no rule matched, calling AI")
    await record_task_trace(
        task.id,
        stage="router",
        event="ai_plan_requested",
        detail={"reason": "no_rule_match"},
    )
    task.used_ai = True
    task.ai_usage["planner"] = "ai_agent.plan"
    plan = await ai_agent.plan(normalized_command)
    task.intent = str(plan.get("intent", normalized_command) or normalized_command)
    task.steps = _build_steps_from_plan(plan)
    for step in task.steps:
        _hydrate_step_params(step, normalized_command)
    if task.steps and _looks_like_automation_request(normalized_command):
        only_browser = all(step.tool == "browser" for step in task.steps)
        if only_browser:
            logger.info(f"[{task.id}] AI returned browser-only plan for automation request, retrying helper fallback")
            await record_task_trace(
                task.id,
                stage="router",
                event="browser_only_plan_rejected",
                detail={"step_count": len(task.steps)},
            )
            task.steps = []
    if not task.steps:
        automation_hint = await ai_agent.automation_assist(normalized_command)
        if automation_hint:
            tool = str(automation_hint.get("tool") or "").strip()
            text = str(automation_hint.get("text") or normalized_command).strip() or normalized_command
            description = str(automation_hint.get("description") or "ai_automation_fallback").strip()
            if tool in {
                "reminder_helper",
                "weather_alert_helper",
                "calendar_helper",
            }:
                fallback_step = Step(
                    tool=tool,
                    params={"text": text},
                    description=description,
                )
                logger.info(f"[{task.id}] using AI automation fallback: {fallback_step.tool}")
                task.steps = [fallback_step]
                await record_task_trace(
                    task.id,
                    stage="router",
                    event="ai_automation_fallback",
                    detail={"tool": fallback_step.tool},
                )
        if not task.steps and allows_browser_fallback(normalized_command):
            ai_browser_hint = await ai_agent.browser_assist(normalized_command)
            if ai_browser_hint:
                task.used_ai = True
                task.ai_usage["browser_assist"] = "ai_agent.browser_assist"
                assisted_intent = build_ai_assisted_browser_intent(ai_browser_hint, normalized_command)
                if assisted_intent:
                    fallback_step = Step(
                        tool=_intent_tool(assisted_intent.category),
                        params=assisted_intent.params,
                        description=assisted_intent.description,
                    )
                    logger.info(f"[{task.id}] using AI browser fallback: {fallback_step.tool}")
                    task.steps = [fallback_step]
                    await record_task_trace(
                        task.id,
                        stage="router",
                        event="ai_browser_fallback",
                        detail={"tool": fallback_step.tool},
                    )
        if task.steps:
            _annotate_risk(task)
            await record_task_trace(
                task.id,
                stage="router",
                event="route_completed",
                status=task.status,
                detail={"step_count": len(task.steps), "risk_level": task.risk_level},
            )
            return task
        if not has_api_key():
            fallback_intent = build_last_resort_intent(normalized_command)
            if fallback_intent:
                fallback_step = Step(
                    tool=_intent_tool(fallback_intent.category),
                    params=fallback_intent.params,
                    description=fallback_intent.description,
                )
                logger.info(f"[{task.id}] using last-resort fallback: {fallback_step.tool}")
                task.steps = [fallback_step]
                await record_task_trace(
                    task.id,
                    stage="router",
                    event="last_resort_fallback",
                    detail={"tool": fallback_step.tool},
                )
    _annotate_risk(task)
    await record_task_trace(
        task.id,
        stage="router",
        event="route_completed",
        status=task.status,
        detail={"step_count": len(task.steps), "risk_level": task.risk_level},
    )
    return task


async def _complete_direct_route(task: Task, normalized_command: str, step: Step) -> Task:
    _hydrate_step_params(step, normalized_command)
    logger.info(f"[{task.id}] rule matched: {step.tool}")
    task.intent = normalized_command
    task.steps = [step]
    _annotate_risk(task)
    await record_task_trace(
        task.id,
        stage="router",
        event="rule_matched",
        status=task.status,
        detail={"tool": step.tool, "risk_level": task.risk_level},
    )
    return task


def _build_steps_from_plan(plan: dict) -> list[Step]:
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return []

    built_steps: list[Step] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        tool = str(step.get("tool") or "").strip()
        if not tool:
            continue
        params = step.get("params")
        built_steps.append(
            Step(
                tool=tool,
                params=params if isinstance(params, dict) else {},
                description=str(step.get("description", "") or ""),
                condition=step.get("condition"),
                param_template=bool(step.get("param_template", False)),
            )
        )
    return built_steps


def _build_clarification_context(command: str, context: dict) -> dict:
    clarification = context.get("clarification") if isinstance(context, dict) else None
    if not isinstance(clarification, dict):
        return {
            "original_command": command.strip(),
            "analysis_command": command.strip(),
            "history": [],
        }

    original_command = str(clarification.get("original_command") or command).strip()
    history = clarification.get("history") or []
    normalized_history: list[dict[str, str]] = []
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if question and answer:
                normalized_history.append({"question": question, "answer": answer})

    pending_question = str(clarification.get("question") or "").strip()
    latest_answer = command.strip()
    if pending_question and latest_answer:
        normalized_history.append({"question": pending_question, "answer": latest_answer})

    lines = [original_command]
    if normalized_history:
        lines.append("")
        lines.append("Follow-up answers:")
        for index, item in enumerate(normalized_history, start=1):
            lines.append(f"Q{index}. {item['question']}")
            lines.append(f"A{index}. {item['answer']}")

    return {
        "original_command": original_command,
        "analysis_command": "\n".join(lines).strip(),
        "history": normalized_history,
    }


def _match_rules(command: str) -> Step | None:
    for rule in _rules:
        pattern = rule["pattern"]
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            params = _resolve_params(rule.get("params", {}), match)
            return Step(tool=rule["tool"], params=params, description=rule["name"])
    return None


def _intent_tool(category: str) -> str:
    mapping = {
        "search": "crawler",
        "crawl": "crawler",
        "open_url": "browser",
        "shopping_search": "shopping_helper",
        "reminder_schedule": "reminder_helper",
        "shell_pwd": "shell",
        "shell_ls": "shell",
        "shell_ls_path": "shell",
        "file_read": "file",
        "file_write": "file",
        "file_copy": "file",
        "file_move": "file",
        "file_delete": "file",
        "time": "time",
        "system_info": "system_info",
    }
    return mapping[category]


def _hydrate_step_params(step: Step, command: str) -> None:
    params = step.params if isinstance(step.params, dict) else {}
    if step.tool in _TEXT_REQUIRED_TOOLS and not str(params.get("text") or "").strip():
        params["text"] = command
    step.params = params


def _resolve_params(template: dict, match: re.Match) -> dict:
    """템플릿의 {match_1}, {match_2} 등을 캡처 그룹으로 치환."""
    result = {}
    groups = match.groups()
    for key, val in template.items():
        if isinstance(val, str):
            for i, g in enumerate(groups, 1):
                if g:
                    val = val.replace(f"{{match_{i}}}", g)
        result[key] = val
    return result


def _annotate_risk(task: Task) -> None:
    if not task.steps:
        task.risk_level = "low"
        return

    levels = ["low", "medium", "high"]
    highest = "low"
    reasons: list[str] = []

    for step in task.steps:
        step.risk_level = risk_evaluator.evaluate(step.tool, step.params)
        if levels.index(step.risk_level) > levels.index(highest):
            highest = step.risk_level
        if step.risk_level in {"medium", "high"}:
            reasons.append(f"{step.tool} step requires approval ({step.risk_level})")

    task.risk_level = highest
    task.approval_reason = "; ".join(reasons)
