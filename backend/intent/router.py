import re
import yaml
from pathlib import Path
from orchestrator.task import Task, Step
from ai import agent as ai_agent
from ai.runtime import has_api_key
from intent import risk_evaluator
from intent.normalizer import (
    _looks_like_automation_request,
    build_ai_assisted_browser_intent,
    build_last_resort_intent,
    detect_intent,
    normalize_command,
)
from plugins import load_plugin_rules
from logger.logger import get_logger

logger = get_logger(__name__)

_rules: list[dict] = []


def load_rules():
    global _rules
    path = Path(__file__).parent / "rules" / "rules.yaml"
    with open(path) as f:
        base_rules = yaml.safe_load(f).get("rules", [])
    _rules = [*base_rules, *load_plugin_rules()]


async def route(command: str) -> Task:
    """명령어를 받아 Task 생성. 비AI 우선 → 실패 시 AI가 전체를 이어받음."""
    if not _rules:
        load_rules()

    normalized_command = normalize_command(command)
    task = Task(command=normalized_command)

    # 1. 규칙 매칭 시도
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
        logger.info(f"[{task.id}] rule matched: {step.tool}")
        task.intent = normalized_command
        task.steps = [step]
        _annotate_risk(task)
        return task

    # 2. 비AI가 놓친 요청은 AI가 메인 에이전트처럼 이어받음
    logger.info(f"[{task.id}] no rule matched, calling AI")
    plan = await ai_agent.plan(normalized_command)
    task.intent = plan.get("intent", normalized_command)
    task.steps = [
        Step(tool=s["tool"], params=s["params"], description=s.get("description", ""))
        for s in plan.get("steps", [])
    ]
    if task.steps and _looks_like_automation_request(normalized_command):
        only_browser = all(step.tool == "browser" for step in task.steps)
        if only_browser:
            logger.info(f"[{task.id}] AI returned browser-only plan for automation request, retrying helper fallback")
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
        if not task.steps:
            ai_browser_hint = await ai_agent.browser_assist(normalized_command)
            if ai_browser_hint:
                assisted_intent = build_ai_assisted_browser_intent(ai_browser_hint, normalized_command)
                if assisted_intent:
                    fallback_step = Step(
                        tool=_intent_tool(assisted_intent.category),
                        params=assisted_intent.params,
                        description=assisted_intent.description,
                    )
                    logger.info(f"[{task.id}] using AI browser fallback: {fallback_step.tool}")
                    task.steps = [fallback_step]
        if task.steps:
            _annotate_risk(task)
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
    _annotate_risk(task)
    return task


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
