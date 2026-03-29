from tools.base import BaseTool


class EchoTool(BaseTool):
    name = "example_echo"
    description = "Echo back plugin text for testing plugin registration"

    async def run(self, params: dict) -> dict:
        text = (params.get("text") or "").strip()
        return {
            "success": True,
            "data": {
                "message": text or "example echo plugin executed",
            },
            "error": None,
        }


def register_tools(register):
    register(EchoTool())
