import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import agent as ai_agent
from config.store import config_store


class FakeResponse:
    def __init__(self, text: str):
        self.content = [type("ContentBlock", (), {"text": text})()]


class FakeClient:
    def __init__(self, captured: dict, response_text: str):
        self._captured = captured
        self._response_text = response_text
        self.messages = self

    def create(self, **kwargs):
        self._captured["system"] = kwargs["system"]
        self._captured["messages"] = kwargs["messages"]
        return FakeResponse(self._response_text)


class AIAgentPromptTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_data: dict = {}
        self.captured: dict = {}
        self.response_text = '{"intent":"test","steps":[]}'

        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_has_api_key = ai_agent.has_api_key
        self._orig_get_client = ai_agent.get_client
        self._orig_get_ai_instructions = ai_agent.get_ai_instructions
        self._orig_list_tools = ai_agent.list_tools

        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        ai_agent.has_api_key = lambda: True
        ai_agent.get_client = lambda: FakeClient(self.captured, self.response_text)
        ai_agent.get_ai_instructions = lambda: ""
        ai_agent.list_tools = lambda: [
            {"name": "browser_auto", "description": "Automate a browser page."},
            {"name": "browser", "description": "Open a browser page."},
        ]

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        ai_agent.has_api_key = self._orig_has_api_key
        ai_agent.get_client = self._orig_get_client
        ai_agent.get_ai_instructions = self._orig_get_ai_instructions
        ai_agent.list_tools = self._orig_list_tools

    async def test_system_prompt_mentions_browser_auto_actions(self):
        await ai_agent.plan("브라우저로 페이지 열고 내용 확인해줘")

        system_prompt = self.captured["system"]
        self.assertIn("The `browser_auto` tool is for guided browser automation", system_prompt)
        self.assertIn("`navigate`", system_prompt)
        self.assertIn("`click`", system_prompt)
        self.assertIn("`type`", system_prompt)
        self.assertIn("`screenshot`", system_prompt)
        self.assertIn("`extract_text`", system_prompt)

    async def test_system_prompt_includes_mcp_guidance_with_configured_server_names(self):
        self.config_data["mcp_servers"] = {
            "gmail": {"name": "gmail", "transport": "stdio", "command": "npx", "args": ["gmail-server"]},
            "google_calendar": {
                "name": "google_calendar",
                "transport": "stdio",
                "command": "npx",
                "args": ["calendar-server"],
            },
        }
        ai_agent.list_tools = lambda: [
            {"name": "browser_auto", "description": "Automate a browser page."},
            {"name": "mcp", "description": "Call configured MCP servers."},
        ]

        await ai_agent.plan("내일 회의 추가하고 초대 메일 보내줘")

        system_prompt = self.captured["system"]
        self.assertIn("MCP tool guidance", system_prompt)
        self.assertIn("The `mcp` tool can call tools exposed by configured MCP servers.", system_prompt)
        self.assertIn("Available MCP servers: gmail, google_calendar.", system_prompt)

    async def test_system_prompt_includes_dynamic_parameter_syntax(self):
        await ai_agent.plan("앞 단계 결과를 다음 단계에 사용해줘")

        system_prompt = self.captured["system"]
        self.assertIn("${steps[N].result.data.field}", system_prompt)
        self.assertIn('"param_template": true', system_prompt)

    async def test_system_prompt_includes_conditional_step_guidance(self):
        await ai_agent.plan("조건에 따라 다음 단계를 실행해줘")

        system_prompt = self.captured["system"]
        self.assertIn("You may include a `condition` field on a step", system_prompt)
        self.assertIn("Use `condition` and dynamic parameters actively in multi-step plans", system_prompt)

    async def test_system_prompt_omits_mcp_section_when_no_servers_are_configured(self):
        await ai_agent.plan("일반 작업 계획만 세워줘")

        system_prompt = self.captured["system"]
        self.assertNotIn("MCP tool guidance", system_prompt)
        self.assertNotIn("The `mcp` tool can call tools exposed by configured MCP servers.", system_prompt)
        self.assertNotIn("Available MCP servers:", system_prompt)

    async def test_plan_returns_steps_with_param_template_flag(self):
        self.response_text = (
            '{"intent":"follow prior result","steps":[{"tool":"browser_auto","params":{"url":"${steps[0].result.data.url}"},'
            '"param_template":true,"description":"open the generated url"}]}'
        )

        result = await ai_agent.plan("앞 단계 URL로 열어줘")

        self.assertEqual(result["intent"], "follow prior result")
        self.assertEqual(len(result["steps"]), 1)
        self.assertTrue(result["steps"][0]["param_template"])
        self.assertEqual(result["steps"][0]["params"]["url"], "${steps[0].result.data.url}")


if __name__ == "__main__":
    unittest.main()
