import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
        load_default_tools()
        load_plugins()

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

    async def test_email_send_intent_with_address_and_message_routes_to_browser(self):
        task = await intent_router.route("vmcf@naver.com으로 안녕이라는 메시지 보여줘")
        self.assertEqual(task.steps[0].tool, "browser")
        self.assertIn("mailto:vmcf@naver.com", task.steps[0].params["url"])
        self.assertIn("body=%EC%95%88%EB%85%95", task.steps[0].params["url"])


if __name__ == "__main__":
    unittest.main()
