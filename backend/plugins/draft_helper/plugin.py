from tools.base import BaseTool


class DraftHelperTool(BaseTool):
    name = "draft_helper"
    description = "Generate basic message or email drafts without calling AI"

    async def run(self, params: dict) -> dict:
        content = (params.get("content") or "").strip()
        draft_type = (params.get("draft_type") or "message").strip()
        recipient = (params.get("recipient") or "").strip()
        if not content:
            return {"success": False, "data": None, "error": "content is required"}

        if draft_type == "email":
            subject = f"{recipient + ' 관련 ' if recipient else ''}메일 초안"
            body = f"안녕하세요,\n\n{content}\n\n감사합니다."
            return {
                "success": True,
                "data": {
                    "draft_type": "email",
                    "recipient": recipient or None,
                    "subject": subject,
                    "body": body,
                },
                "error": None,
            }

        body = f"{recipient + '님, ' if recipient else ''}{content}"
        return {
            "success": True,
            "data": {
                "draft_type": "message",
                "recipient": recipient or None,
                "body": body,
            },
            "error": None,
        }


def register_tools(register):
    register(DraftHelperTool())
