from urllib.parse import quote_plus

from config.store import config_store
from tools.base import BaseTool

SHOPPING_URLS = {
    "naver": ("네이버 쇼핑", "https://search.shopping.naver.com/search/all?query={query}"),
    "coupang": ("쿠팡", "https://www.coupang.com/np/search?q={query}"),
    "11st": ("11번가", "https://search.11st.co.kr/Search.tmall?kwd={query}"),
    "gmarket": ("G마켓", "https://browse.gmarket.co.kr/search?keyword={query}"),
}

PURCHASE_PERMISSION_ID = "shopping_checkout_assist"


class ShoppingHelperTool(BaseTool):
    name = "shopping_helper"
    description = "Prepare shopping and checkout-ready links with permission-aware safety checks"

    async def run(self, params: dict) -> dict:
        query = (params.get("query") or "").strip()
        platform = (params.get("platform") or "naver").strip().lower()
        prefer_lowest_price = bool(params.get("prefer_lowest_price"))
        purchase_intent = bool(params.get("purchase_intent"))

        if not query:
            return {"success": False, "data": None, "error": "shopping query is required"}

        platform_name, url_template = SHOPPING_URLS.get(platform, SHOPPING_URLS["naver"])
        if purchase_intent and not _is_permission_granted(PURCHASE_PERMISSION_ID):
            return {
                "success": False,
                "data": {
                    "permission_required": PURCHASE_PERMISSION_ID,
                    "action": "permission_required",
                    "query": query,
                    "platform": platform,
                },
                "error": "쇼핑 구매 보조 권한이 필요합니다. 설정에서 권한을 켠 뒤 다시 시도해주세요.",
            }

        url = url_template.format(query=quote_plus(query))
        if prefer_lowest_price and platform == "naver":
            url = f"{url}&sort=price_asc"

        title = f"{platform_name}에서 {query}{' 최저가' if prefer_lowest_price else ''} 찾기"
        if purchase_intent:
            title = f"{platform_name}에서 {query} 구매 진행"

        return {
            "success": True,
            "data": {
                "action": "open_url",
                "url": url,
                "title": title,
                "shopping": True,
                "purchase_intent": purchase_intent,
                "prefer_lowest_price": prefer_lowest_price,
                "platform": platform,
                "query": query,
                "requires_confirmation": purchase_intent,
                "permission_id": PURCHASE_PERMISSION_ID if purchase_intent else None,
            },
            "error": None,
        }


def register_tools(register):
    register(ShoppingHelperTool())


def _is_permission_granted(permission_id: str) -> bool:
    granted_permissions = set(config_store.get("granted_permissions", []))
    return permission_id in granted_permissions
