import platform
from pathlib import Path

from tools.base import BaseTool


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = "Return basic information about the current system"
    description_ko = "현재 시스템 기본 정보 반환"
    description_en = "Return basic information about the current system"

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
