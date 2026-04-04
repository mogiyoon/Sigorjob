import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import registry
from tools.browser_auto import tool as browser_auto_module
from tools.browser_auto.tool import BrowserAutoTool


class FakeResponse:
    def __init__(self, status: int):
        self.status = status


class FakePage:
    def __init__(self):
        self.url = ""
        self.current_text = "Example page text"
        self.last_click_selector = None
        self.last_fill = None
        self.last_screenshot_path = None

    async def goto(self, url: str, wait_until: str, timeout: int):
        self.url = url
        return FakeResponse(200)

    async def title(self) -> str:
        return "Example Title"

    async def text_content(self, selector: str, timeout: int) -> str:
        return self.current_text

    async def click(self, selector: str, timeout: int) -> None:
        self.last_click_selector = selector

    async def fill(self, selector: str, text: str, timeout: int) -> None:
        self.last_fill = (selector, text)

    async def screenshot(self, path: str, timeout: int) -> None:
        self.last_screenshot_path = path


class FakeContext:
    def __init__(self, page: FakePage):
        self.page = page
        self.closed = False

    async def new_page(self) -> FakePage:
        return self.page

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, page: FakePage):
        self.page = page
        self.closed = False
        self.context = FakeContext(page)

    async def new_context(self) -> FakeContext:
        return self.context

    async def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, factory: "FakePlaywrightFactory"):
        self.factory = factory

    async def launch(self, headless: bool) -> FakeBrowser:
        self.factory.launch_headless_values.append(headless)
        browser = FakeBrowser(self.factory.current_page)
        self.factory.last_browser = browser
        self.factory.last_context = browser.context
        return browser


class FakePlaywright:
    def __init__(self, factory: "FakePlaywrightFactory"):
        self.chromium = FakeChromium(factory)


class FakePlaywrightContextManager:
    def __init__(self, factory: "FakePlaywrightFactory"):
        self.factory = factory

    async def __aenter__(self) -> FakePlaywright:
        page = FakePage()
        page.current_text = self.factory.next_text
        self.factory.current_page = page
        self.factory.last_page = page
        return FakePlaywright(self.factory)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePlaywrightFactory:
    def __init__(self):
        self.next_text = "Example page text"
        self.current_page: FakePage | None = None
        self.last_page: FakePage | None = None
        self.last_context: FakeContext | None = None
        self.last_browser: FakeBrowser | None = None
        self.launch_headless_values: list[bool] = []

    def __call__(self) -> FakePlaywrightContextManager:
        return FakePlaywrightContextManager(self)


class BrowserAutoToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = BrowserAutoTool()
        self.original_async_playwright = browser_auto_module.async_playwright
        self.factory = FakePlaywrightFactory()
        browser_auto_module.async_playwright = self.factory

    def tearDown(self):
        browser_auto_module.async_playwright = self.original_async_playwright

    async def test_navigate_action_returns_url_title_and_status(self):
        result = await self.tool.run({"action": "navigate", "url": "https://example.com"})

        self.assertTrue(result["success"])
        self.assertEqual(
            result["data"],
            {"url": "https://example.com", "title": "Example Title", "status": 200},
        )
        self.assertTrue(self.factory.last_context.closed)
        self.assertTrue(self.factory.last_browser.closed)
        self.assertEqual(self.factory.launch_headless_values[-1], True)

    async def test_extract_text_action_returns_page_text(self):
        self.factory.next_text = "A" * 12000

        result = await self.tool.run({"action": "extract_text", "url": "https://example.com"})

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["text"], "A" * 10000)

    async def test_click_action_clicks_selector(self):
        result = await self.tool.run(
            {"action": "click", "url": "https://example.com", "selector": "#submit"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(self.factory.last_page.last_click_selector, "#submit")

    async def test_type_action_types_text(self):
        result = await self.tool.run(
            {
                "action": "type",
                "url": "https://example.com",
                "selector": "#search",
                "text": "playwright",
                "headless": False,
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(self.factory.last_page.last_fill, ("#search", "playwright"))
        self.assertEqual(self.factory.launch_headless_values[-1], False)

    async def test_screenshot_action_returns_tmp_path(self):
        result = await self.tool.run({"action": "screenshot", "url": "https://example.com"})

        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["path"].startswith("/tmp/browser-auto-"))
        self.assertEqual(self.factory.last_page.last_screenshot_path, result["data"]["path"])

    async def test_navigate_with_invalid_url_returns_error(self):
        result = await self.tool.run({"action": "navigate", "url": "not-a-url"})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid url")

    async def test_returns_error_when_playwright_is_not_installed(self):
        browser_auto_module.async_playwright = None

        result = await self.tool.run({"action": "navigate", "url": "https://example.com"})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "playwright not installed")


class BrowserAutoRegistryTests(unittest.TestCase):
    def test_browser_auto_tool_is_registered(self):
        registry.load_default_tools()

        tool = registry.get("browser_auto")

        self.assertIsNotNone(tool)
        self.assertIsInstance(tool, BrowserAutoTool)


if __name__ == "__main__":
    unittest.main()
