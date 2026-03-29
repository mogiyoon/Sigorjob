from urllib.parse import quote_plus

from tools.base import BaseTool


class DeliveryHelperTool(BaseTool):
    name = "delivery_helper"
    description = "Prepare useful food delivery search links from natural-language delivery requests"

    async def run(self, params: dict) -> dict:
        query = (params.get("query") or "").strip()
        if not query:
            return {"success": False, "data": None, "error": "query is required"}

        search_query = f"{query} 배달"
        return {
            "success": True,
            "data": {
                "action": "open_url",
                "url": f"https://www.google.com/search?q={quote_plus(search_query)}",
                "title": f"{query} 배달 찾기",
            },
            "error": None,
        }


def register_tools(register):
    register(DeliveryHelperTool())
