import json
from ai.runtime import get_client, has_api_key
from connections.registry import list_mcp_servers
from plugins import get_ai_instructions
from logger.logger import get_logger
from tools.registry import list_tools

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are an automation orchestration assistant.
Given a user's natural language command, your job is to produce an execution plan.

Available tools will be listed below.

Respond ONLY with a JSON object in this exact format:
{
  "intent": "one-line summary of what the user wants",
  "steps": [
    {
      "tool": "tool_name",
      "params": { ... },
      "description": "what this step does"
    }
  ]
}

Rules:
- Use the fewest steps possible.
- Do not include steps that are not needed.
- Never suggest shell commands that could be dangerous.
- Prefer purpose-built helper tools over generic browser search when a helper can safely handle the request.
- For reminders, schedules, alerts, recurring summaries, or routine notifications, prefer a schedule/reminder helper instead of browser search.
- For time-based automation, recurring work, weather alerts, or calendar creation, avoid generic search if any helper tool can take the request.
- Use browser/search only when the user explicitly asked to search, browse, open a site, compare products, find a place, or continue in a web destination.
- If the user asks for shopping, ordering, booking, or sign-up, and full completion is not possible with available tools, open the most relevant destination page only when that destination is clearly implied.
- For ambiguous requests, prefer an empty plan over a low-value generic web search.
- Return steps as [] if the best remaining action would only be a vague generic search page.
"""

BROWSER_ASSIST_PROMPT = """
You are a fallback classifier for a desktop automation assistant.
The main planner could not produce a reliable tool plan.
Choose the safest browser destination intent that best helps the user continue.

Return ONLY a JSON object in this format:
{
  "intent_type": "shopping_search|place_search|service_search|search|none",
  "platform": "naver|coupang|11st|gmarket|youtube|github|namu|naver_map|google_maps|google",
  "query": "short cleaned query string",
  "prefer_lowest_price": true
}

Rules:
- Use shopping_search for buying/order/product-price intents.
- Use place_search for restaurants, cafes, hospitals, directions, accommodations, local places.
- Use service_search for service-specific searches such as YouTube, GitHub, NamuWiki.
- Use search only as a last resort.
- Do not use search just because the request is unclear.
- If the user did not explicitly ask to search, browse, open, compare, or find something on the web, prefer none.
- If the user mentions lowest price, set prefer_lowest_price to true.
- Never return checkout, payment, or login actions. Only safe destination pages.
- If nothing useful can be inferred, return {"intent_type":"none","platform":"","query":"","prefer_lowest_price":false}
"""

AUTOMATION_ASSIST_PROMPT = """
You are a fallback intent router for a desktop automation assistant.
The main planner could not produce a reliable plan.
Choose the safest non-browser automation helper that best fits the request.

Return ONLY a JSON object in this format:
{
  "tool": "reminder_helper|weather_alert_helper|calendar_helper|shopping_helper|none",
  "text": "cleaned natural-language payload for the helper tool",
  "description": "short description"
}

Rules:
- Use reminder_helper for time-based reminders, summaries, alerts, or daily routine notifications.
- Use weather_alert_helper for recurring weather update requests.
- Use calendar_helper for calendar event creation requests.
- Use shopping_helper for shopping/purchase-assist requests that should stay inside Sigorjob tools.
- Prefer a useful helper tool over returning none.
- Return none only if no safe helper applies.
"""

DRAFT_CONTINUATION_PROMPT = """
You are helping finish a draft for a desktop automation assistant.
The assistant already produced a safe non-AI draft or opened the compose flow.
Your job is to improve the remaining draft work, not to change the core intent.

Return ONLY a JSON object in this exact format:
{
  "subject": "string",
  "body": "string"
}

Rules:
- Preserve the original language unless the user clearly asked for another language.
- Keep the recipient unchanged.
- If subject is not needed (for example plain message draft), return an empty string or keep the existing one.
- Make the body natural, useful, and ready to send.
- Do not invent facts that are not implied by the user command or the existing draft.
"""

TASK_CONTINUATION_PROMPT = """
You are continuing an in-progress automation task for a desktop agent.
The original non-AI flow already produced some results, but the user wants the AI to keep going.

You will receive:
- the original command
- the current task result
- the available tools

Return ONLY a JSON object in this exact format:
{
  "intent": "short summary",
  "summary": "what the AI continuation is trying to achieve",
  "steps": [
    {
      "tool": "tool_name",
      "params": { },
      "description": "what this step does"
    }
  ]
}

Rules:
- Prefer purpose-built helper tools over generic browser search when possible.
- Use browser only when it is genuinely the best next action.
- If the current result is already sufficient and no extra execution is needed, return an empty steps array and provide a useful summary.
- For mail, message, schedule, shopping, reservation, calendar, route, or reminder flows, continue from the current result instead of restarting from scratch.
- Never invent unsupported tools.
"""

CLARIFICATION_PROMPT = """
You are the first-pass intent reviewer for a desktop automation assistant.
Decide whether the assistant needs one short follow-up question before it can safely or usefully act.

Return ONLY a JSON object in this exact format:
{
  "needs_clarification": true,
  "question": "short Korean follow-up question",
  "reason": "short Korean sentence"
}

or

{
  "needs_clarification": false,
  "question": "",
  "reason": "short Korean sentence"
}

Rules:
- Ask at most one question.
- Ask only when the missing detail would materially change the action.
- Do not ask if the current command is already actionable enough.
- Do not ask for trivia that can be safely inferred or deferred.
- Prefer Korean.
"""


async def plan(command: str) -> dict:
    """사용자 명령을 받아 실행 계획 반환."""
    logger.info(f"AI planning for: {command}")
    client = get_client()
    if not has_api_key() or client is None:
        logger.info("AI planning skipped: anthropic_api_key is not configured")
        return {"intent": command, "steps": []}
    try:
        plugin_instructions = get_ai_instructions()
        tools_prompt = _build_tools_prompt()
        mcp_prompt = _build_mcp_prompt()
        system_prompt = f"{SYSTEM_PROMPT}\n\nAvailable tools:\n{tools_prompt}"
        if plugin_instructions:
            system_prompt = f"{SYSTEM_PROMPT}\n\nPlugin-specific guidance:\n{plugin_instructions}"
            system_prompt = f"{system_prompt}\n\nAvailable tools:\n{tools_prompt}"
        if mcp_prompt:
            system_prompt = f"{system_prompt}\n\n{mcp_prompt}"
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": command}],
        )
        text = message.content[0].text.strip()
        # JSON 블록 추출
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        logger.error(f"AI planning failed: {e}")
        return {"intent": command, "steps": []}


async def browser_assist(command: str) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        return None
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=BROWSER_ASSIST_PROMPT,
            messages=[{"role": "user", "content": command}],
        )
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        if str(data.get("intent_type") or "") == "none":
            return None
        return data
    except Exception as e:
        logger.error(f"AI browser assist failed: {e}")
        return None


async def automation_assist(command: str) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        return None
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=AUTOMATION_ASSIST_PROMPT,
            messages=[{"role": "user", "content": command}],
        )
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        if str(data.get("tool") or "") == "none":
            return None
        return data
    except Exception as e:
        logger.error(f"AI automation assist failed: {e}")
        return None


async def continue_draft(command: str, draft: dict) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        return None
    try:
        payload = {
            "command": command,
            "draft_type": draft.get("draft_type"),
            "recipient": draft.get("recipient"),
            "subject": draft.get("subject", ""),
            "body": draft.get("body", ""),
        }
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=DRAFT_CONTINUATION_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        return {
            "subject": str(data.get("subject", draft.get("subject", "")) or ""),
            "body": str(data.get("body", draft.get("body", "")) or ""),
        }
    except Exception as e:
        logger.error(f"AI draft continuation failed: {e}")
        return None


async def continue_task(command: str, current_result: dict) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        return None
    try:
        tools_prompt = _build_tools_prompt()
        mcp_prompt = _build_mcp_prompt()
        system_prompt = f"{TASK_CONTINUATION_PROMPT}\n\nAvailable tools:\n{tools_prompt}"
        if mcp_prompt:
            system_prompt = f"{system_prompt}\n\n{mcp_prompt}"
        payload = {
            "command": command,
            "current_result": current_result,
        }
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        steps = data.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        return {
            "intent": str(data.get("intent", command) or command),
            "summary": str(data.get("summary", "") or ""),
            "steps": steps,
        }
    except Exception as e:
        logger.error(f"AI task continuation failed: {e}")
        return None


async def request_clarification(command: str, history: list[dict] | None = None) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        return None
    try:
        payload = {
            "command": command,
            "history": history or [],
        }
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=CLARIFICATION_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        return {
            "needs_clarification": bool(data.get("needs_clarification")),
            "question": str(data.get("question", "") or "").strip(),
            "reason": str(data.get("reason", "") or "").strip(),
        }
    except Exception as e:
        logger.error(f"AI clarification review failed: {e}")
        return None


def _build_tools_prompt() -> str:
    tools = list_tools()
    if not tools:
        return "- browser: prepare a web URL for opening in the client UI"
    return "\n".join(f"- {tool['name']}: {tool['description']}" for tool in tools)


def _build_mcp_prompt() -> str:
    servers = list_mcp_servers()
    if not servers:
        return ""

    server_names = ", ".join(sorted(str(server.get("name") or "").strip() for server in servers if server.get("name")))
    if not server_names:
        return ""

    return (
        "MCP tool guidance:\n"
        "- The `mcp` tool can call tools exposed by configured MCP servers.\n"
        f"- Available MCP servers: {server_names}.\n"
        "- When the user asks for calendar or email work and an MCP server fits, you may use the `mcp` tool with "
        '`server`, `tool`, and optional `arguments`.\n'
        "- Do not invent server names. Use only the configured servers listed above."
    )
