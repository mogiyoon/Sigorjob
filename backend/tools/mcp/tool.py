from __future__ import annotations

from typing import Any

from connections.registry import get_mcp_server, list_mcp_servers
from connections.drivers.mcp_client import MCPClient
from tools.base import BaseTool


class MCPTool(BaseTool):
    name = "mcp"
    description = "Call configured external server tools"
    description_ko = "설정된 외부 서버 도구 호출"
    description_en = "Call configured external server tools"

    async def run(self, params: dict) -> dict[str, Any]:
        server_name = str(params.get("server") or "").strip()
        tool_name = str(params.get("tool") or "").strip()
        arguments = params.get("arguments") or {}

        if not list_mcp_servers():
            return {"success": False, "data": None, "error": "no mcp servers configured"}

        if not server_name:
            return {"success": False, "data": None, "error": "server not found"}

        server_config = get_mcp_server(server_name)
        if server_config is None:
            return {"success": False, "data": None, "error": "server not found"}

        if not tool_name:
            return {"success": False, "data": None, "error": "tool not found"}

        client = MCPClient(server_config)
        try:
            tools = await client.list_tools()
            if not any(item.get("name") == tool_name for item in tools):
                return {"success": False, "data": None, "error": "tool not found"}

            result = await client.call_tool(tool_name, arguments)
            return {"success": True, "data": {"result": result}, "error": None}
        except Exception as exc:
            return {"success": False, "data": None, "error": str(exc)}
        finally:
            await client.close()
