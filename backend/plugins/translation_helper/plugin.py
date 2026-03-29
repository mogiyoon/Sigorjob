from urllib.parse import quote_plus

from tools.base import BaseTool


class TranslationHelperTool(BaseTool):
    name = "translation_helper"
    description = "Prepare a translation page for common translation requests"

    async def run(self, params: dict) -> dict:
        text = (params.get("text") or "").strip()
        target_lang = (params.get("target_lang") or "en").strip().lower()
        if not text:
            return {"success": False, "data": None, "error": "text is required"}

        source_lang = "auto"
        url = (
            "https://translate.google.com/"
            f"?sl={source_lang}&tl={target_lang}&text={quote_plus(text)}&op=translate"
        )
        target_name = "영어" if target_lang == "en" else "한국어" if target_lang == "ko" else target_lang
        return {
            "success": True,
            "data": {
                "action": "open_url",
                "url": url,
                "title": f"{target_name} 번역 열기",
                "translation": True,
                "target_lang": target_lang,
            },
            "error": None,
        }


def register_tools(register):
    register(TranslationHelperTool())
