import platform
from pathlib import Path

from tools.base import BaseTool


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = "현재 시스템 기본 정보를 반환"

    async def run(self, params: dict) -> dict:
        return {
            "success": True,
            "data": {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "hostname": platform.node(),
                "cwd": str(Path.cwd()),
            },
            "error": None,
        }
