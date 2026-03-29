import re
from urllib.parse import quote_plus

from tools.base import BaseTool


class RouteHelperTool(BaseTool):
    name = "route_helper"
    description = "Prepare a directions link from natural-language navigation requests"

    async def run(self, params: dict) -> dict:
        text = (params.get("text") or "").strip()
        if not text:
            return {"success": False, "data": None, "error": "text is required"}

        origin, destination = _parse_route(text)
        if not destination:
            return {"success": False, "data": None, "error": "destination is required"}

        url = "https://www.google.com/maps/dir/?api=1"
        if origin:
            url += f"&origin={quote_plus(origin)}"
        url += f"&destination={quote_plus(destination)}&travelmode=transit"

        title = f"{destination} 길찾기"
        if origin:
            title = f"{origin}에서 {destination}까지 길찾기"

        return {
            "success": True,
            "data": {
                "action": "open_url",
                "url": url,
                "title": title,
            },
            "error": None,
        }


def register_tools(register):
    register(RouteHelperTool())


def _parse_route(text: str) -> tuple[str | None, str | None]:
    cleaned = re.sub(r"\s*(길찾아줘|길 찾아줘|길 안내해줘|경로 알려줘|가는 길 알려줘)\s*$", "", text).strip()
    match = re.search(r"(.+?)에서\s+(.+?)(?:까지|로)\s*$", cleaned)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    match = re.search(r"(.+?)(?:까지|로)\s*$", cleaned)
    if match:
        return None, match.group(1).strip()
    return None, cleaned or None
