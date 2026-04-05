import json
from ai.runtime import get_client, has_api_key
from logger.logger import get_logger
from tools.registry import list_tools

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You review automation results only when the non-AI quality gate says the result is insufficient.

Your job:
1. Decide if the result is actually acceptable anyway.
2. If not acceptable, propose at most one replacement retry step using the existing tools.

Available tools:
- file: read/write/copy/move/delete local files
- shell: execute an allowed shell command
- crawler: crawl a URL and extract text
- browser: prepare a web URL for opening in the client UI
- browser_auto: automate browser with Playwright (actions: navigate, extract_text, click, type, screenshot)

When the crawler result is insufficient (short text, CAPTCHA, access denied), prefer retrying with browser_auto using action "extract_text" and the same URL.

Respond ONLY with JSON in this format:
{
  "acceptable": true,
  "reason": "short Korean sentence",
  "retry_step": null
}

or

{
  "acceptable": false,
  "reason": "short Korean sentence",
  "retry_step": {
    "tool": "crawler",
    "params": {"url": "https://..."},
    "description": "retry with ..."
  }
}

Rules:
- Keep the retry plan to one step only.
- Prefer crawler/browser over shell.
- Do not propose dangerous shell commands.
- If the current result is clearly unusable, set acceptable to false.
"""

PREFLIGHT_PROMPT = """
You validate a proposed first action for a desktop automation assistant.

Your job:
1. Check whether the proposed step actually matches the user's intent.
2. If it does not, propose at most one replacement step using only existing tools.

Respond ONLY with JSON in this format:
{
  "acceptable": true,
  "reason": "short Korean sentence",
  "retry_step": null
}

or

{
  "acceptable": false,
  "reason": "short Korean sentence",
  "retry_step": {
    "tool": "tool_name",
    "params": {},
    "description": "short Korean sentence"
  }
}

Rules:
- Be conservative. Only reject the proposed step when it clearly mismatches the user's request.
- Correct typos and natural phrasing when inferring intent.
- Prefer purpose-built helper tools over generic search or crawl.
- Keep the replacement to one step only.
- Never invent unsupported tools.
"""

POSTFLIGHT_PROMPT = """
You validate the final usefulness of an automation step result for a desktop automation assistant.

Your job:
1. Check whether the produced result is actually the right final action for the user's request.
2. If not, propose at most one replacement retry step using only existing tools.

Respond ONLY with JSON in this format:
{
  "acceptable": true,
  "reason": "short Korean sentence",
  "retry_step": null
}

or

{
  "acceptable": false,
  "reason": "short Korean sentence",
  "retry_step": {
    "tool": "tool_name",
    "params": {},
    "description": "short Korean sentence"
  }
}

Rules:
- Be conservative. Only reject when the result clearly does not satisfy the user's intent.
- Correct typos and natural phrasing when inferring intent.
- Prefer a useful direct action such as mailto/tel/calendar helper over generic search pages.
- Keep the replacement to one step only.
- Never invent unsupported tools.
"""


def _available_tools_prompt() -> str:
    tools = list_tools()
    if not tools:
        return "- browser: prepare a web URL for opening in the client UI"
    return "\n".join(f"- {tool['name']}: {tool['description']}" for tool in tools)


def _parse_json_response(text: str) -> dict:
    parsed = text.strip()
    if "```" in parsed:
        parsed = parsed.split("```")[1]
        if parsed.startswith("json"):
            parsed = parsed[4:]
    return json.loads(parsed)


async def review(command: str, step: dict, result: dict, quality: dict) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        logger.info("AI quality review skipped: anthropic_api_key is not configured")
        return None

    payload = {
        "command": command,
        "step": step,
        "result": result,
        "quality": quality,
    }

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        return _parse_json_response(message.content[0].text)
    except Exception as e:
        logger.error(f"AI quality review failed: {e}")
        return None


async def preflight(command: str, step: dict) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        return None

    payload = {
        "command": command,
        "proposed_step": step,
    }

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            system=f"{PREFLIGHT_PROMPT}\n\nAvailable tools:\n{_available_tools_prompt()}",
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        return _parse_json_response(message.content[0].text)
    except Exception as e:
        logger.error(f"AI preflight review failed: {e}")
        return None


async def postflight(command: str, step: dict, result: dict) -> dict | None:
    client = get_client()
    if not has_api_key() or client is None:
        return None

    payload = {
        "command": command,
        "step": step,
        "result": result,
    }

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            system=f"{POSTFLIGHT_PROMPT}\n\nAvailable tools:\n{_available_tools_prompt()}",
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        return _parse_json_response(message.content[0].text)
    except Exception as e:
        logger.error(f"AI postflight review failed: {e}")
        return None
