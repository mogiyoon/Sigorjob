from datetime import datetime, timezone

from tools.base import BaseTool


class TimeTool(BaseTool):
    name = "time"
    description = "현재 시간을 반환"

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
