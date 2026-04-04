import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import summarizer as ai_summarizer
from config.store import config_store
from intent import router as intent_router


class FakeResponse:
    def __init__(self, text: str):
        self.content = [type("ContentBlock", (), {"text": text})()]


class FakeClient:
    def __init__(self, captured: dict, response_text: str):
        self._captured = captured
        self._response_text = response_text
        self.messages = self

    def create(self, **kwargs):
        self._captured["kwargs"] = kwargs
        return FakeResponse(self._response_text)


class AIFirstRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_data: dict = {"custom_commands": []}

        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_config_delete = config_store.delete
        self._orig_config_all = config_store.all
        self._orig_router_has_api_key = intent_router.has_api_key
        self._orig_router_plan = intent_router.ai_agent.plan
        self._orig_router_request_clarification = intent_router.ai_agent.request_clarification
        self._orig_router_automation_assist = intent_router.ai_agent.automation_assist
        self._orig_router_browser_assist = intent_router.ai_agent.browser_assist
        self._orig_router_record_task_trace = intent_router.record_task_trace
        self._orig_summarizer_has_api_key = ai_summarizer.has_api_key
        self._orig_summarizer_get_client = ai_summarizer.get_client

        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        config_store.delete = lambda key: self.config_data.pop(key, None)
        config_store.all = lambda: dict(self.config_data)

        async def noop_record_task_trace(*args, **kwargs):
            return None

        async def fake_request_clarification(command: str, history: list[dict] | None = None):
            return None

        async def fake_automation_assist(command: str):
            return None

        async def fake_browser_assist(command: str):
            return None

        async def default_plan(command: str):
            return {"intent": command, "steps": []}

        intent_router.has_api_key = lambda: False
        intent_router.ai_agent.plan = default_plan
        intent_router.ai_agent.request_clarification = fake_request_clarification
        intent_router.ai_agent.automation_assist = fake_automation_assist
        intent_router.ai_agent.browser_assist = fake_browser_assist
        intent_router.record_task_trace = noop_record_task_trace

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        config_store.delete = self._orig_config_delete
        config_store.all = self._orig_config_all
        intent_router.has_api_key = self._orig_router_has_api_key
        intent_router.ai_agent.plan = self._orig_router_plan
        intent_router.ai_agent.request_clarification = self._orig_router_request_clarification
        intent_router.ai_agent.automation_assist = self._orig_router_automation_assist
        intent_router.ai_agent.browser_assist = self._orig_router_browser_assist
        intent_router.record_task_trace = self._orig_router_record_task_trace
        ai_summarizer.has_api_key = self._orig_summarizer_has_api_key
        ai_summarizer.get_client = self._orig_summarizer_get_client

    async def test_ai_first_with_api_key_uses_ai_plan(self):
        intent_router.has_api_key = lambda: True

        async def fake_plan(command: str):
            return {
                "intent": "ai planned intent",
                "steps": [{"tool": "time", "params": {}, "description": "tell time"}],
            }

        intent_router.ai_agent.plan = fake_plan

        task = await intent_router.route("현재 시간 알려줘")

        self.assertTrue(task.used_ai)
        self.assertEqual(task.intent, "ai planned intent")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].tool, "time")
        self.assertEqual(task.ai_usage["planner"], "ai_agent.plan")

    async def test_ai_first_preserves_all_multi_step_ai_plan_steps(self):
        intent_router.has_api_key = lambda: True

        async def fake_plan(command: str):
            return {
                "intent": command,
                "steps": [
                    {"tool": "time", "params": {}, "description": "step 1"},
                    {"tool": "system_info", "params": {}, "description": "step 2"},
                    {"tool": "time", "params": {}, "description": "step 3"},
                ],
            }

        intent_router.ai_agent.plan = fake_plan

        task = await intent_router.route("복합 작업 해줘")

        self.assertEqual(len(task.steps), 3)
        self.assertEqual([step.description for step in task.steps], ["step 1", "step 2", "step 3"])

    async def test_legacy_without_api_key_uses_rule_matching(self):
        called = {"plan": False}

        async def fake_plan(command: str):
            called["plan"] = True
            return {"intent": command, "steps": []}

        intent_router.has_api_key = lambda: False
        intent_router.ai_agent.plan = fake_plan

        task = await intent_router.route("https://example.com 읽어와")

        self.assertFalse(task.used_ai)
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].tool, "crawler")
        self.assertFalse(called["plan"])

    async def test_custom_command_short_circuits_before_ai_plan(self):
        self.config_data["custom_commands"] = [
            {
                "id": "custom-1",
                "trigger": "합주 준비",
                "match_type": "contains",
                "action_text": "현재 시간",
                "enabled": True,
            }
        ]
        intent_router.has_api_key = lambda: True

        async def fail_if_called(command: str):
            raise AssertionError("AI plan should not run after a custom command match")

        intent_router.ai_agent.plan = fail_if_called

        task = await intent_router.route("합주 준비 좀 해줘")

        self.assertEqual(task.steps[0].tool, "time")
        self.assertFalse(task.used_ai)

    async def test_ai_plan_preserves_param_template_steps(self):
        intent_router.has_api_key = lambda: True

        async def fake_plan(command: str):
            return {
                "intent": command,
                "steps": [
                    {
                        "tool": "browser_auto",
                        "params": {"url": "${steps[0].result.data.url}"},
                        "param_template": True,
                        "description": "open generated url",
                    }
                ],
            }

        intent_router.ai_agent.plan = fake_plan

        task = await intent_router.route("앞 단계 결과로 열어줘")

        self.assertEqual(len(task.steps), 1)
        self.assertTrue(task.steps[0].param_template)
        self.assertEqual(task.steps[0].params["url"], "${steps[0].result.data.url}")

    async def test_ai_plan_preserves_condition_steps(self):
        intent_router.has_api_key = lambda: True

        async def fake_plan(command: str):
            return {
                "intent": command,
                "steps": [
                    {
                        "tool": "time",
                        "params": {},
                        "condition": "${steps[0].result.success}",
                        "description": "conditional step",
                    }
                ],
            }

        intent_router.ai_agent.plan = fake_plan

        task = await intent_router.route("조건부 실행해줘")

        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].condition, "${steps[0].result.success}")

    async def test_summarizer_prompt_is_language_agnostic(self):
        captured: dict = {}
        ai_summarizer.has_api_key = lambda: True
        ai_summarizer.get_client = lambda: FakeClient(captured, "summary")

        result = await ai_summarizer.summarize(
            "Summarize this in English",
            [{"success": True, "data": {"value": "ok"}}],
        )

        self.assertEqual(result, "summary")
        prompt = captured["kwargs"]["messages"][0]["content"]
        self.assertIn("same language as the user command", prompt)
        self.assertNotIn("in Korean", prompt)


if __name__ == "__main__":
    unittest.main()
