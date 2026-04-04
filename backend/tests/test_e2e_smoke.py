import os
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.store import config_store
from connections.base import ConnectionExecutionResult
from db import session as db_session
from intent import router as intent_router
from orchestrator import engine as orchestrator_engine
from orchestrator.task import Step
from plugins import load_plugins
from policy import auto_approval
from tools import registry
from tools.base import BaseTool


class E2EEmitTool(BaseTool):
    name = "e2e_emit_tool"
    description = "Emit deterministic data for E2E smoke tests."

    async def run(self, params: dict) -> dict:
        return {
            "success": True,
            "data": {
                "value": params.get("value", "dynamic-value"),
                "nested": {"message": "resolved"},
            },
            "error": None,
        }


class E2ECaptureTool(BaseTool):
    name = "e2e_capture_tool"
    description = "Capture params for E2E smoke tests."

    async def run(self, params: dict) -> dict:
        return {"success": True, "data": params, "error": None}


class E2ESmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.tmpdir.name, "test.db")
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
        self.config_data: dict = {"custom_commands": []}
        self.calendar_payloads: list[dict] = []

        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_config_delete = config_store.delete
        self._orig_config_all = config_store.all
        self._orig_db_engine = db_session.engine
        self._orig_db_session_local = db_session.AsyncSessionLocal
        self._orig_orchestrator_session_local = orchestrator_engine.AsyncSessionLocal
        self._orig_router_record_task_trace = intent_router.record_task_trace
        self._orig_orchestrator_record_task_trace = orchestrator_engine.record_task_trace
        self._orig_router_has_api_key = intent_router.has_api_key
        self._orig_ai_plan = intent_router.ai_agent.plan
        self._orig_ai_request_clarification = intent_router.ai_agent.request_clarification
        self._orig_ai_automation_assist = intent_router.ai_agent.automation_assist
        self._orig_ai_browser_assist = intent_router.ai_agent.browser_assist
        self._orig_orchestrator_continue_task = orchestrator_engine.ai_agent.continue_task
        self._orig_summarize = orchestrator_engine.summarizer.summarize
        self._orig_review = orchestrator_engine.ai_reviewer.review
        self._orig_calendar_execute = None

        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        config_store.delete = lambda key: self.config_data.pop(key, None)
        config_store.all = lambda: dict(self.config_data)

        db_session.engine = self.engine
        db_session.AsyncSessionLocal = self.session_maker
        orchestrator_engine.AsyncSessionLocal = self.session_maker
        await db_session.init_db()

        async def noop_trace(*args, **kwargs):
            return None

        async def fake_summarize(command: str, results: list[dict], *, allow_ai: bool = True):
            return "done"

        async def fake_continue_task(command: str, current_result: dict):
            return None

        async def fake_request_clarification(command: str, history: list[dict]):
            return None

        async def fake_automation_assist(command: str):
            return None

        async def fake_browser_assist(command: str):
            return None

        async def fake_review(command: str, step: dict, result: dict, quality: dict):
            return None

        intent_router.record_task_trace = noop_trace
        orchestrator_engine.record_task_trace = noop_trace
        intent_router.has_api_key = lambda: False
        intent_router.ai_agent.request_clarification = fake_request_clarification
        intent_router.ai_agent.automation_assist = fake_automation_assist
        intent_router.ai_agent.browser_assist = fake_browser_assist
        orchestrator_engine.ai_agent.continue_task = fake_continue_task
        orchestrator_engine.summarizer.summarize = fake_summarize
        orchestrator_engine.ai_reviewer.review = fake_review

        registry.load_default_tools()
        registry.register(E2EEmitTool())
        registry.register(E2ECaptureTool())
        load_plugins()
        intent_router._rules = []

        from plugins.calendar_helper import plugin as calendar_plugin

        self._orig_calendar_execute = calendar_plugin.connection_manager.execute_capability

        async def fake_execute_capability(capability: str, payload: dict):
            self.calendar_payloads.append({"capability": capability, "payload": payload})
            return ConnectionExecutionResult(
                success=True,
                handled=True,
                data={
                    "calendar_event_id": "mock-event",
                    "title": payload["title"],
                    "dates": payload["dates"],
                },
            )

        calendar_plugin.connection_manager.execute_capability = fake_execute_capability

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        config_store.delete = self._orig_config_delete
        config_store.all = self._orig_config_all
        db_session.engine = self._orig_db_engine
        db_session.AsyncSessionLocal = self._orig_db_session_local
        orchestrator_engine.AsyncSessionLocal = self._orig_orchestrator_session_local
        intent_router.record_task_trace = self._orig_router_record_task_trace
        orchestrator_engine.record_task_trace = self._orig_orchestrator_record_task_trace
        intent_router.has_api_key = self._orig_router_has_api_key
        intent_router.ai_agent.plan = self._orig_ai_plan
        intent_router.ai_agent.request_clarification = self._orig_ai_request_clarification
        intent_router.ai_agent.automation_assist = self._orig_ai_automation_assist
        intent_router.ai_agent.browser_assist = self._orig_ai_browser_assist
        orchestrator_engine.ai_agent.continue_task = self._orig_orchestrator_continue_task
        orchestrator_engine.summarizer.summarize = self._orig_summarize
        orchestrator_engine.ai_reviewer.review = self._orig_review

        from plugins.calendar_helper import plugin as calendar_plugin

        calendar_plugin.connection_manager.execute_capability = self._orig_calendar_execute

        await self.engine.dispose()
        self.tmpdir.cleanup()

    async def test_time_command_routes_and_executes_without_ai(self):
        task = await intent_router.route("current time")
        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertFalse(result.used_ai)
        self.assertEqual(result.steps[0].tool, "time")
        self.assertIn("utc", result.results[0]["data"])
        self.assertIn("local", result.results[0]["data"])

    async def test_file_read_command_routes_and_executes(self):
        path = Path("/tmp/e2e-smoke-read.txt")
        path.write_text("smoke-content", encoding="utf-8")

        task = await intent_router.route(f"{path} 파일 읽어줘")
        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertFalse(result.used_ai)
        self.assertEqual(result.steps[0].tool, "file")
        self.assertEqual(result.results[0]["data"], "smoke-content")

    async def test_shell_command_routes_and_executes(self):
        task = await intent_router.route("ls")
        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertFalse(result.used_ai)
        self.assertEqual(result.steps[0].tool, "shell")
        self.assertIsInstance(result.results[0]["data"], str)

    async def test_calendar_command_routes_to_helper_with_correct_params(self):
        command = "내일 오후 3시 팀 회의 캘린더에 일정 추가해줘"
        expected_text = "내일 오후 3시 팀 회의"

        task = await intent_router.route(command)
        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(task.steps[0].tool, "calendar_helper")
        self.assertEqual(task.steps[0].params["text"], expected_text)
        self.assertEqual(result.status, "done")
        self.assertEqual(len(self.calendar_payloads), 1)
        self.assertEqual(self.calendar_payloads[0]["capability"], "create_calendar_event")
        self.assertEqual(
            self.calendar_payloads[0]["payload"]["source_text"],
            expected_text,
        )

    async def test_unknown_command_triggers_ai_fallback(self):
        async def fake_plan(command: str):
            return {
                "intent": "fallback plan",
                "steps": [{"tool": "time", "params": {}, "description": "time fallback"}],
            }

        intent_router.ai_agent.plan = fake_plan

        task = await intent_router.route("규칙에 없는 이상한 명령")
        result = await orchestrator_engine.run(task, persist=False)

        self.assertTrue(task.used_ai)
        self.assertEqual(task.steps[0].tool, "time")
        self.assertEqual(result.status, "done")

    async def test_multi_step_task_with_dynamic_params_executes(self):
        async def fake_plan(command: str):
            return {
                "intent": command,
                "steps": [
                    {
                        "tool": "e2e_emit_tool",
                        "params": {"value": "from-step-1"},
                        "description": "emit data",
                    },
                    {
                        "tool": "e2e_capture_tool",
                        "params": {"message": "${steps[0].result.data.value}"},
                        "description": "capture data",
                    },
                ],
            }

        intent_router.ai_agent.plan = fake_plan

        task = await intent_router.route("dynamic smoke command")
        task.steps[1].param_template = True
        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertEqual(task.steps[1].params["message"], "from-step-1")
        self.assertEqual(result.steps[1].result["data"]["message"], "from-step-1")

    async def test_medium_risk_task_gets_approval_required_status(self):
        task = await intent_router.route("/tmp/e2e-approval.txt 파일에 hello 써줘")

        self.assertEqual(task.risk_level, "medium")
        self.assertTrue(orchestrator_engine.requires_manual_approval(task))

        await orchestrator_engine.save_approval_request(task)

        self.assertEqual(task.status, "approval_required")

    async def test_approval_followed_by_execution_completes_task(self):
        path = Path("/tmp/e2e-approved-write.txt")
        if path.exists():
            path.unlink()

        task = await intent_router.route(f"{path} 파일에 approved-content 써줘")

        await orchestrator_engine.save_approval_request(task)
        self.assertEqual(task.status, "approval_required")

        orchestrator_engine.record_approved_patterns(task)
        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(encoding="utf-8"), "approved-content")
        self.assertIn("auto_approval_patterns", self.config_data)
        self.assertFalse(auto_approval.is_auto_approved("file", {"operation": "read", "path": str(path)}))


if __name__ == "__main__":
    unittest.main()
