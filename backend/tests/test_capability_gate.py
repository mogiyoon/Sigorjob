import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.secret_store import secret_store
from config.store import config_store
from orchestrator import capability_gate
from orchestrator import engine as orchestrator_engine
from orchestrator.task import Step, Task
from tools import registry
from tools.base import BaseTool


class MCPTestTool(BaseTool):
    name = "mcp"
    description = "MCP test tool."

    async def run(self, params: dict) -> dict:
        return {"success": True, "data": {"executed": True}, "error": None}


class CapabilityGateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_data: dict = {}
        self.secret_data: dict = {}

        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_secret_get = secret_store.get
        self._orig_record_task_trace = orchestrator_engine.record_task_trace
        self._orig_summarize = orchestrator_engine.summarizer.summarize
        self._orig_mcp_tool = registry.get("mcp")

        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        secret_store.get = lambda key: self.secret_data.get(key)

        async def noop_trace(*args, **kwargs):
            return None

        async def fake_summarize(command: str, results: list[dict], *, allow_ai: bool = True):
            return "done"

        orchestrator_engine.record_task_trace = noop_trace
        orchestrator_engine.summarizer.summarize = fake_summarize

        registry.register(MCPTestTool())

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        secret_store.get = self._orig_secret_get
        orchestrator_engine.record_task_trace = self._orig_record_task_trace
        orchestrator_engine.summarizer.summarize = self._orig_summarize
        if self._orig_mcp_tool is not None:
            registry.register(self._orig_mcp_tool)

    def test_check_capability_for_calendar_returns_missing_when_oauth_token_absent(self):
        self.config_data["granted_permissions"] = ["external_connection_access", "calendar_event_creation"]

        result = capability_gate.check_capability(
            Step(tool="mcp", params={"server": "google_calendar", "tool": "create_calendar_event"})
        )

        self.assertEqual(
            result,
            {
                "satisfied": False,
                "connection_id": "google_calendar",
                "capability_name": "create_calendar_event",
                "setup_action": "oauth",
                "setup_message": result["setup_message"],
                "fallback_available": True,
                "fallback_description": result["fallback_description"],
                "missing_permissions": [],
            },
        )

    def test_check_capability_for_crawler_returns_satisfied(self):
        result = capability_gate.check_capability(Step(tool="crawler", params={"url": "https://example.com"}))

        self.assertEqual(result, {"satisfied": True})

    def test_check_capability_for_calendar_returns_satisfied_with_oauth_token(self):
        self.config_data["granted_permissions"] = ["external_connection_access", "calendar_event_creation"]
        self.secret_data["google_oauth_tokens:google_calendar"] = '{"access_token":"token"}'

        result = capability_gate.check_capability(
            Step(tool="mcp", params={"server": "google_calendar", "tool": "create_calendar_event"})
        )

        self.assertTrue(result["satisfied"])
        self.assertEqual(result["connection_id"], "google_calendar")
        self.assertEqual(result["capability_name"], "create_calendar_event")

    async def test_calendar_task_without_oauth_returns_needs_setup(self):
        self.config_data["granted_permissions"] = ["external_connection_access", "calendar_event_creation"]
        task = Task(
            command="캘린더에 회의 일정 추가해줘",
            steps=[Step(tool="mcp", params={"server": "google_calendar", "tool": "create_calendar_event"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "needs_setup")
        self.assertEqual(
            result.result_data["setup_action"],
            {
                "connection_id": "google_calendar",
                "capability": "create_calendar_event",
                "action": "oauth",
            },
        )
        self.assertIn("google_calendar", str(result.result_data["missing_capabilities"]).lower())

    async def test_gmail_task_without_oauth_returns_needs_setup(self):
        self.config_data["granted_permissions"] = ["external_connection_access", "email_send_access"]
        task = Task(
            command="메일 보내줘",
            steps=[Step(tool="mcp", params={"server": "gmail", "tool": "send_email"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "needs_setup")
        self.assertEqual(result.result_data["setup_action"]["connection_id"], "gmail")
        self.assertEqual(result.result_data["setup_action"]["capability"], "send_email")

    async def test_needs_setup_result_includes_human_readable_message(self):
        self.config_data["granted_permissions"] = ["external_connection_access", "calendar_event_creation"]
        task = Task(
            command="캘린더에 일정 추가",
            steps=[Step(tool="mcp", params={"server": "google_calendar", "tool": "create_calendar_event"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertIn("연결이 필요", result.result_data["setup_message"])
        self.assertIn("connection is required", result.result_data["setup_message"])

    async def test_needs_setup_result_includes_fallback_option(self):
        self.config_data["granted_permissions"] = ["external_connection_access", "calendar_event_creation"]
        task = Task(
            command="캘린더에 일정 추가",
            steps=[Step(tool="mcp", params={"server": "google_calendar", "tool": "create_calendar_event"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertTrue(result.result_data["fallback_available"])
        self.assertIn("calendar link", result.result_data["fallback_description"])

    async def test_task_with_satisfied_capability_executes_normally(self):
        self.config_data["granted_permissions"] = ["external_connection_access", "calendar_event_creation"]
        self.secret_data["google_oauth_tokens:google_calendar"] = '{"access_token":"token"}'
        task = Task(
            command="캘린더에 일정 추가",
            steps=[Step(tool="mcp", params={"server": "google_calendar", "tool": "create_calendar_event"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertNotIn("setup_action", result.result_data)
        self.assertEqual(result.results[0]["data"]["executed"], True)

    def test_task_status_needs_setup_is_valid(self):
        task = Task(status="needs_setup")

        self.assertEqual(task.status, "needs_setup")


if __name__ == "__main__":
    unittest.main()
