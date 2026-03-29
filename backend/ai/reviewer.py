import json
from ai.runtime import get_client, has_api_key
from logger.logger import get_logger

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
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        logger.error(f"AI quality review failed: {e}")
        return None
