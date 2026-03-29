import re
from urllib.parse import quote_plus

from tools.base import BaseTool


class CommunicationHelperTool(BaseTool):
    name = "communication_helper"
    description = "Prepare phone and SMS actions from natural-language requests"

    async def run(self, params: dict) -> dict:
        text = (params.get("text") or "").strip()
        mode = (params.get("mode") or "").strip()
        content = (params.get("content") or "").strip()
        if not text or mode not in {"call", "sms"}:
            return {"success": False, "data": None, "error": "text and mode are required"}

        phone = _extract_phone_number(text)
        if mode == "call":
            if not phone:
                return {
                    "success": True,
                    "data": {
                        "draft_type": "message",
                        "recipient": text,
                        "body": f"{text}에게 전화가 필요합니다.",
                    },
                    "error": None,
                }
            return {
                "success": True,
                "data": {
                    "action": "open_url",
                    "url": f"tel:{phone}",
                    "title": f"{phone} 전화 걸기",
                },
                "error": None,
            }

        if phone:
            sms_url = f"sms:{phone}"
            if content:
                sms_url += f"?body={quote_plus(content)}"
            return {
                "success": True,
                "data": {
                    "action": "open_url",
                    "url": sms_url,
                    "title": f"{phone} 문자 보내기",
                },
                "error": None,
            }

        body = content or f"{text}에게 보낼 메시지"
        return {
            "success": True,
            "data": {
                "draft_type": "message",
                "recipient": text,
                "body": f"{text}님, {body}",
            },
            "error": None,
        }


def register_tools(register):
    register(CommunicationHelperTool())


def _extract_phone_number(text: str) -> str | None:
    match = re.search(r"(\+?\d[\d\s-]{7,}\d)", text)
    if not match:
        return None
    return re.sub(r"[^\d+]", "", match.group(1))
