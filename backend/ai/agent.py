import json
from ai.runtime import get_client, has_api_key
from plugins import get_ai_instructions
from logger.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are an automation orchestration assistant.
Given a user's natural language command, your job is to produce an execution plan.

Available tools:
- file: read/write/copy/move local files
  params: {operation: read|write|copy|move, path, content (write only), src/dst (copy/move)}
- shell: execute an allowed shell command
  params: {command: string}
- crawler: crawl a URL and extract text
  params: {url: string, selector: string (optional)}
- browser: prepare a web URL for opening in the client UI
  params: {url: string, title: string (optional)}

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
- Prefer a useful fallback over an empty plan.
- If the user asks for shopping, ordering, booking, or sign-up, and full completion is not possible with available tools, open the most relevant search or destination page instead of returning no steps.
- For search-like or research-like requests, opening a relevant search page or collecting links is better than returning no steps.
- Return steps as [] only if there is truly no safe and useful action you can take.
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
- If the user mentions lowest price, set prefer_lowest_price to true.
- Never return checkout, payment, or login actions. Only safe destination pages.
- If nothing useful can be inferred, return {"intent_type":"none","platform":"","query":"","prefer_lowest_price":false}
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
        system_prompt = SYSTEM_PROMPT
        if plugin_instructions:
            system_prompt = f"{SYSTEM_PROMPT}\n\nPlugin-specific guidance:\n{plugin_instructions}"
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
