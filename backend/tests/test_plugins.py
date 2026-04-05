import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.store import config_store
from intent import router as intent_router
from plugins import describe_plugins, get_ai_instructions, load_plugins
from tools.registry import get, load_default_tools


class PluginLoaderTests(unittest.TestCase):
    def test_example_plugin_loads(self):
        load_default_tools()
        load_plugins()
        self.assertIsNotNone(get("example_echo"))
        names = {plugin["name"] for plugin in describe_plugins()}
        self.assertIn("example_echo", names)
        self.assertIn("example_echo", get_ai_instructions())
        self.assertIn("reservation_helper", names)
        self.assertIn("delivery_helper", names)
        self.assertIn("draft_helper", names)
        self.assertIn("calendar_helper", names)
        self.assertIn("weather_alert_helper", names)
        self.assertIn("route_helper", names)
        self.assertIn("communication_helper", names)
        self.assertIn("travel_helper", names)


class PluginRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_data: dict = {}
        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_config_delete = config_store.delete
        self._orig_config_all = config_store.all
        self._orig_ai_plan = intent_router.ai_agent.plan
        self._orig_has_api_key = intent_router.has_api_key
        self._orig_router_record_task_trace = intent_router.record_task_trace
        intent_router.has_api_key = lambda: False
        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        config_store.delete = lambda key: self.config_data.pop(key, None)
        config_store.all = lambda: dict(self.config_data)
        async def noop_record_task_trace(*args, **kwargs):
            return None
        intent_router.record_task_trace = noop_record_task_trace
        load_default_tools()
        load_plugins()
        config_store.set("custom_commands", [])

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        config_store.delete = self._orig_config_delete
        config_store.all = self._orig_config_all
        intent_router.ai_agent.plan = self._orig_ai_plan
        intent_router.has_api_key = self._orig_has_api_key
        intent_router.record_task_trace = self._orig_router_record_task_trace

    async def test_reservation_plugin_route(self):
        task = await intent_router.route("성수 맛집 예약해줘")
        self.assertEqual(task.steps[0].tool, "reservation_helper")
        self.assertEqual(task.steps[0].params["mode"], "reservation")

    async def test_delivery_plugin_route(self):
        task = await intent_router.route("성수 피자 배달시켜줘")
        self.assertEqual(task.steps[0].tool, "delivery_helper")

    async def test_draft_plugin_route(self):
        task = await intent_router.route("민수에게 메시지 초안 써줘 오늘 10분 늦을 것 같아")
        self.assertEqual(task.steps[0].tool, "draft_helper")

    async def test_calendar_plugin_route(self):
        task = await intent_router.route("내일 오후 3시 팀 회의 캘린더에 일정 추가해줘")
        self.assertEqual(task.steps[0].tool, "calendar_helper")
        self.assertFalse(task.used_ai)

    async def test_calendar_ai_first_route_uses_ai_plan(self):
        """AI-first mode: AI plans calendar requests when API key is present."""
        intent_router.has_api_key = lambda: True

        async def fake_plan(command):
            return {
                "intent": command,
                "steps": [
                    {"tool": "calendar_helper", "params": {"text": command}, "description": "add calendar event"}
                ],
            }

        original_plan = intent_router.ai_agent.plan
        intent_router.ai_agent.plan = fake_plan
        try:
            task = await intent_router.route("4월 11일 16시에 벚꽃 일정 추가해줘")
        finally:
            intent_router.ai_agent.plan = original_plan

        self.assertEqual(task.steps[0].tool, "calendar_helper")
        self.assertTrue(task.used_ai)

    async def test_calendar_helper_preserves_explicit_month_day_in_google_link(self):
        tool = get("calendar_helper")
        result = await tool.run({"text": "4월 11일 16시에 벚꽃 일정 추가", "use_fallback": True})
        self.assertTrue(result["success"])
        calendar = result["data"]["calendar"]
        self.assertEqual(calendar["title"], "벚꽃")
        self.assertIn("20260411T070000Z/20260411T080000Z", calendar["dates"])
        self.assertEqual(
            calendar["summary"],
            "4월 11일 16시에 **벚꽃** 일정을",
        )

    async def test_calendar_helper_with_oauth_token_creates_event_via_api(self):
        tool = get("calendar_helper")
        connector_data = {
            "action": "open_url",
            "url": "https://calendar.google.com/event?eid=abc",
            "event_id": "event-123",
            "event_link": "https://calendar.google.com/event?eid=abc",
            "calendar": {"title": "팀 회의"},
        }
        connector_result = type(
            "ConnectorResult",
            (),
            {"handled": True, "success": True, "data": connector_data, "error": None},
        )()

        with patch("plugins.calendar_helper.plugin.oauth.get_stored_tokens", return_value={"access_token": "token"}), patch(
            "plugins.calendar_helper.plugin.connection_manager.execute_capability",
            new=AsyncMock(return_value=connector_result),
        ) as execute_capability:
            result = await tool.run({"text": "내일 오후 3시 팀 회의 캘린더에 일정 추가해줘"})

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["event_id"], "event-123")
        self.assertEqual(result["data"]["event_link"], "https://calendar.google.com/event?eid=abc")
        execute_capability.assert_awaited_once()

    async def test_calendar_helper_without_oauth_token_returns_needs_connection_result(self):
        tool = get("calendar_helper")

        with patch("plugins.calendar_helper.plugin.oauth.get_stored_tokens", return_value=None):
            result = await tool.run({"text": "4월 11일 16시에 벚꽃 일정 추가"})

        self.assertFalse(result["success"])
        self.assertIn("connection required", result["error"])
        self.assertIn("calendar.google.com/calendar/render?action=TEMPLATE", result["data"]["fallback_url"])

    async def test_calendar_helper_fallback_request_preserves_existing_link_generation(self):
        tool = get("calendar_helper")

        with patch("plugins.calendar_helper.plugin.oauth.get_stored_tokens", return_value=None):
            missing_connection = await tool.run({"text": "4월 11일 16시에 벚꽃 일정 추가"})

        fallback_result = await tool.run({"text": "4월 11일 16시에 벚꽃 일정 추가", "use_fallback": True})

        self.assertTrue(fallback_result["success"])
        self.assertEqual(fallback_result["data"]["url"], missing_connection["data"]["fallback_url"])

    async def test_weather_alert_plugin_route(self):
        task = await intent_router.route("아침 8시에 기상청에서 스크롤한 거 바탕으로 날씨 알림 보내줘")
        self.assertEqual(task.steps[0].tool, "weather_alert_helper")

    async def test_route_helper_plugin_route(self):
        task = await intent_router.route("성수에서 강남역까지 길찾아줘")
        self.assertEqual(task.steps[0].tool, "route_helper")

    async def test_communication_helper_plugin_route(self):
        task = await intent_router.route("010-1234-5678로 전화해줘")
        self.assertEqual(task.steps[0].tool, "communication_helper")

    async def test_travel_helper_plugin_route(self):
        task = await intent_router.route("제주도 항공권 찾아줘")
        self.assertEqual(task.steps[0].tool, "travel_helper")

    async def test_custom_command_rule_rewrites_to_saved_action(self):
        config_store.set(
            "custom_commands",
            [
                {
                    "id": "custom-1",
                    "trigger": "합주 준비",
                    "match_type": "contains",
                    "action_text": "현재 시간",
                    "enabled": True,
                }
            ],
        )
        task = await intent_router.route("합주 준비 좀 해줘")
        self.assertEqual(task.steps[0].tool, "time")

    async def test_ai_helper_plan_without_text_is_hydrated_from_command(self):
        async def fake_plan(command: str):
            return {
                "intent": command,
                "steps": [
                    {
                        "tool": "calendar_helper",
                        "params": {},
                        "description": "calendar fallback",
                    }
                ],
            }

        intent_router.ai_agent.plan = fake_plan
        task = await intent_router.route("오늘 17시 일정에 합주 추가해줘")
        self.assertEqual(task.steps[0].tool, "calendar_helper")
        self.assertEqual(task.steps[0].params["text"], "오늘 17시 일정에 합주 추가해줘")


if __name__ == "__main__":
    unittest.main()
