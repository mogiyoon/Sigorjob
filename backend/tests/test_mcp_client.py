import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.store import config_store
from connections.drivers.mcp_client import MCPClient
from tools.mcp.tool import MCPTool
from tools.registry import get, load_default_tools


class FakeTransport:
    def __init__(self, tools: list[dict], results: dict[str, object] | None = None):
        self._tools = tools
        self._results = results or {}
        self.closed = False

    async def request(self, method: str, params: dict) -> dict:
        if method == "tools/list":
            return {"tools": self._tools}
        if method == "tools/call":
            return {"result": self._results[params["name"]]}
        raise AssertionError(f"unexpected method: {method}")

    async def close(self) -> None:
        self.closed = True


class MCPClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_tools_returns_descriptions(self):
        client = MCPClient(
            {"name": "calendar"},
            transport_factory=lambda server_config: FakeTransport(
                [
                    {
                        "name": "create_event",
                        "description": "Create a calendar event",
                        "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}},
                    }
                ]
            ),
        )

        try:
            tools = await client.list_tools()
        finally:
            await client.close()

        self.assertEqual(
            tools,
            [
                {
                    "name": "create_event",
                    "description": "Create a calendar event",
                    "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}},
                }
            ],
        )


class MCPToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_data: dict = {}
        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_registry = __import__("tools.registry", fromlist=["_registry"])._registry.copy()
        self._orig_mcp_client = __import__("tools.mcp.tool", fromlist=["MCPClient"]).MCPClient
        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        registry_module._registry.clear()
        load_default_tools()

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        registry_module._registry.clear()
        registry_module._registry.update(self._orig_registry)
        tool_module = __import__("tools.mcp.tool", fromlist=["MCPClient"])
        tool_module.MCPClient = self._orig_mcp_client

    async def test_mcp_tool_run_with_valid_server_and_tool_name(self):
        self.config_data["mcp_servers"] = {
            "calendar": {"transport": "stdio", "command": "fake-server"},
        }

        class FakeMCPClient:
            def __init__(self, server_config: dict):
                self.server_config = server_config

            async def list_tools(self) -> list[dict]:
                return [{"name": "create_event", "description": "Create event", "inputSchema": {}}]

            async def call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
                return {"server": self.server_config["name"], "tool": tool_name, "arguments": arguments or {}}

            async def close(self) -> None:
                return None

        tool_module = __import__("tools.mcp.tool", fromlist=["MCPClient"])
        tool_module.MCPClient = FakeMCPClient

        tool = MCPTool()
        result = await tool.run(
            {"server": "calendar", "tool": "create_event", "arguments": {"title": "Planning"}}
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["data"],
            {
                "result": {
                    "server": "calendar",
                    "tool": "create_event",
                    "arguments": {"title": "Planning"},
                }
            },
        )

    async def test_mcp_tool_run_with_unknown_server(self):
        self.config_data["mcp_servers"] = {
            "calendar": {"transport": "stdio", "command": "fake-server"},
        }

        tool = MCPTool()
        result = await tool.run({"server": "gmail", "tool": "send_email"})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "server not found")

    async def test_mcp_tool_run_with_unknown_tool_name(self):
        self.config_data["mcp_servers"] = {
            "calendar": {"transport": "stdio", "command": "fake-server"},
        }

        class FakeMCPClient:
            def __init__(self, server_config: dict):
                self.server_config = server_config

            async def list_tools(self) -> list[dict]:
                return [{"name": "create_event", "description": "Create event", "inputSchema": {}}]

            async def call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
                raise AssertionError("call_tool should not run when tool name is unknown")

            async def close(self) -> None:
                return None

        tool_module = __import__("tools.mcp.tool", fromlist=["MCPClient"])
        tool_module.MCPClient = FakeMCPClient

        tool = MCPTool()
        result = await tool.run({"server": "calendar", "tool": "delete_event"})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "tool not found")

    async def test_mcp_tool_is_registered_in_tool_registry(self):
        self.assertIsNotNone(get("mcp"))

    async def test_mcp_tool_returns_helpful_error_when_no_servers_are_configured(self):
        tool = MCPTool()
        result = await tool.run({"server": "calendar", "tool": "create_event"})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "no mcp servers configured")


if __name__ == "__main__":
    unittest.main()
