from urllib.parse import quote_plus

from tools.base import BaseTool


class ReservationHelperTool(BaseTool):
    name = "reservation_helper"
    description = "Prepare useful booking or reservation links from natural-language reservation requests"

    async def run(self, params: dict) -> dict:
        query = (params.get("query") or "").strip()
        mode = (params.get("mode") or "reservation").strip()
        if not query:
            return {"success": False, "data": None, "error": "query is required"}

        query_with_suffix = query
        title = f"{query} 예약 찾기"
        if mode == "ticket":
            query_with_suffix = f"{query} 예매"
            title = f"{query} 예매 정보 찾기"
        elif mode == "discovery":
            if any(keyword in query for keyword in ("호텔", "숙소", "펜션", "리조트")):
                url = f"https://www.google.com/travel/search?q={quote_plus(query)}"
                return {
                    "success": True,
                    "data": {
                        "action": "open_url",
                        "url": url,
                        "title": f"{query} 찾기",
                    },
                    "error": None,
                }
            url = f"https://map.naver.com/p/search/{quote_plus(query)}"
            return {
                "success": True,
                "data": {
                    "action": "open_url",
                    "url": url,
                    "title": f"{query} 찾기",
                },
                "error": None,
            }
        elif any(keyword in query for keyword in ("호텔", "숙소", "펜션", "리조트")):
            url = f"https://www.google.com/travel/search?q={quote_plus(query)}"
            return {
                "success": True,
                "data": {
                    "action": "open_url",
                    "url": url,
                    "title": f"{query} 숙소 찾기",
                },
                "error": None,
            }
        elif any(keyword in query for keyword in ("식당", "맛집", "카페", "레스토랑")):
            url = f"https://map.naver.com/p/search/{quote_plus(query_with_suffix)}"
            return {
                "success": True,
                "data": {
                    "action": "open_url",
                    "url": url,
                    "title": title,
                },
                "error": None,
            }

        url = f"https://www.google.com/search?q={quote_plus(query_with_suffix)}"
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
    register(ReservationHelperTool())
