from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def run(self, params: dict) -> dict[str, Any]:
        """
        params: Tool 입력
        반환: {"success": bool, "data": Any, "error": str | None}
        """
        ...

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
        }
