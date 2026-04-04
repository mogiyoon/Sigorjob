from datetime import datetime, timezone

from tools.base import BaseTool


class TimeTool(BaseTool):
    name = "time"
    description = "Return the current time"
    description_ko = "현재 시간 반환"
    description_en = "Return the current time"

    async def run(self, params: dict) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "success": True,
            "data": {
                "utc": now.isoformat(),
                "local": datetime.now().astimezone().isoformat(),
            },
            "error": None,
        }
