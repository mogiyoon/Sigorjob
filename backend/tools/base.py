from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    description_ko: str = ""
    description_en: str = ""

    @abstractmethod
    async def run(self, params: dict) -> dict[str, Any]:
        """
        params: Tool 입력
        반환: {"success": bool, "data": Any, "error": str | None}
        """
        ...

    def schema(self, locale: str = "en") -> dict:
        description = self.description_en or self.description
        if locale == "ko":
            description = self.description_ko or description
        return {
            "name": self.name,
            "description": description,
        }
