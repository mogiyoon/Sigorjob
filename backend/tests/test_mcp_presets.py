import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import agent as ai_agent
from config.store import config_store
from connections.mcp_presets import list_presets
from gateway.routes.setup import router as setup_router


class MCPPresetRouteTests(unittest.TestCase):
    def setUp(self):
        self.config_data: dict = {}
        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_config_delete = config_store.delete
        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = self._config_set
        config_store.delete = self._config_delete

        app = FastAPI()
        app.include_router(setup_router)
        self.client = TestClient(app)

    def tearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        config_store.delete = self._orig_config_delete

    def _config_set(self, key, value):
        self.config_data[key] = value

    def _config_delete(self, key):
        self.config_data.pop(key, None)

    def test_list_presets_returns_google_calendar_and_gmail(self):
        presets = list_presets()

        self.assertEqual([item["id"] for item in presets], ["google_calendar", "gmail"])
        self.assertEqual(presets[0]["name"], "google_calendar")
        self.assertIn("description", presets[0])
        self.assertEqual(presets[0]["command"], "npx")
        self.assertIsInstance(presets[0]["args"], list)
        self.assertEqual(presets[1]["name"], "gmail")
        self.assertIn("description", presets[1])
        self.assertEqual(presets[1]["command"], "npx")
        self.assertIsInstance(presets[1]["args"], list)

    def test_install_preset_saves_server_config(self):
        response = self.client.post("/setup/mcp/presets/google_calendar/install")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(
            self.config_data["mcp_servers"]["google_calendar"],
            {
                "name": "google_calendar",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-google-calendar"],
            },
        )

    def test_uninstall_preset_removes_server_config(self):
        self.config_data["mcp_servers"] = {
            "gmail": {
                "name": "gmail",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-gmail"],
            }
        }

        response = self.client.post("/setup/mcp/presets/gmail/uninstall")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(self.config_data["mcp_servers"], {})

    def test_get_presets_returns_install_status(self):
        self.config_data["mcp_servers"] = {
            "gmail": {
                "name": "gmail",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-gmail"],
            }
        }

        response = self.client.get("/setup/mcp/presets")

        self.assertEqual(response.status_code, 200)
        presets = {item["id"]: item for item in response.json()["presets"]}
        self.assertFalse(presets["google_calendar"]["installed"])
        self.assertTrue(presets["gmail"]["installed"])

    def test_install_preset_is_idempotent_when_already_installed(self):
        self.config_data["mcp_servers"] = {
            "gmail": {
                "name": "gmail",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-gmail"],
            }
        }
        before = dict(self.config_data["mcp_servers"]["gmail"])

        response = self.client.post("/setup/mcp/presets/gmail/install")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(self.config_data["mcp_servers"]["gmail"], before)


class FakeResponse:
    def __init__(self, text: str):
        self.content = [type("ContentBlock", (), {"text": text})()]


class FakeClient:
    def __init__(self, captured: dict):
        self._captured = captured
        self.messages = self

    def create(self, **kwargs):
        self._captured["system"] = kwargs["system"]
        self._captured["messages"] = kwargs["messages"]
        return FakeResponse('{"intent":"test","steps":[]}')


class AIAgentMCPPromptTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_data: dict = {}
        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_has_api_key = ai_agent.has_api_key
        self._orig_get_client = ai_agent.get_client
        self._orig_get_ai_instructions = ai_agent.get_ai_instructions
        self._orig_list_tools = ai_agent.list_tools
        self.captured: dict = {}

        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        ai_agent.has_api_key = lambda: True
        ai_agent.get_client = lambda: FakeClient(self.captured)
        ai_agent.get_ai_instructions = lambda: ""
        ai_agent.list_tools = lambda: [
            {"name": "mcp", "description": "Call configured MCP servers."},
            {"name": "browser", "description": "Open a browser page."},
        ]

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        ai_agent.has_api_key = self._orig_has_api_key
        ai_agent.get_client = self._orig_get_client
        ai_agent.get_ai_instructions = self._orig_get_ai_instructions
        ai_agent.list_tools = self._orig_list_tools

    async def test_system_prompt_includes_mcp_guidance_when_servers_are_configured(self):
        self.config_data["mcp_servers"] = {
            "gmail": {"name": "gmail", "transport": "stdio", "command": "npx", "args": ["gmail-server"]},
            "google_calendar": {
                "name": "google_calendar",
                "transport": "stdio",
                "command": "npx",
                "args": ["calendar-server"],
            },
        }

        result = await ai_agent.plan("내일 회의 추가하고 초대 메일 보내줘")

        self.assertEqual(result["steps"], [])
        system_prompt = self.captured["system"]
        self.assertIn("MCP tool guidance", system_prompt)
        self.assertIn("The `mcp` tool can call tools exposed by configured MCP servers.", system_prompt)
        self.assertIn("Available MCP servers: gmail, google_calendar.", system_prompt)


if __name__ == "__main__":
    unittest.main()
