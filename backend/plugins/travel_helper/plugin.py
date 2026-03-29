from urllib.parse import quote_plus

from tools.base import BaseTool


class TravelHelperTool(BaseTool):
    name = "travel_helper"
    description = "Prepare useful travel booking or discovery links from natural-language travel requests"

    async def run(self, params: dict) -> dict:
        query = (params.get("query") or "").strip()
        mode = (params.get("mode") or "").strip()
        if not query or mode not in {"flight", "train", "bus", "hotel"}:
            return {"success": False, "data": None, "error": "query and mode are required"}

        if mode == "flight":
            url = f"https://www.google.com/travel/flights?q={quote_plus(query)}"
            title = f"{query} 항공권 찾기"
        elif mode == "train":
            url = f"https://www.google.com/search?q={quote_plus(query + ' KTX 예매')}"
            title = f"{query} 기차 예매 정보"
        elif mode == "bus":
            url = f"https://www.google.com/search?q={quote_plus(query + ' 고속버스 예매')}"
            title = f"{query} 버스 예매 정보"
        else:
            url = f"https://www.google.com/travel/search?q={quote_plus(query)}"
            title = f"{query} 숙소 찾기"

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
    register(TravelHelperTool())
