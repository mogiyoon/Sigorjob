from tools.base import BaseTool


class BrowserTool(BaseTool):
    name = "browser"
    description = "웹 URL 열기용 링크를 준비"

    async def run(self, params: dict) -> dict:
        url = (params.get("url") or "").strip()
        title = (params.get("title") or "링크 열기").strip()
        if not url:
            return {"success": False, "data": None, "error": "url is required"}
        if not (
            url.startswith("https://")
            or url.startswith("http://")
            or url.startswith("mailto:")
            or url.startswith("tel:")
            or url.startswith("sms:")
        ):
            return {"success": False, "data": None, "error": "http/https/mailto/tel/sms url is required"}
        return {
            "success": True,
            "data": {
                "action": "open_url",
                "url": url,
                "title": title,
            },
            "error": None,
        }
