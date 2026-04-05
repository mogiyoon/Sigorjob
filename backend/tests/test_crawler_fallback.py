import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import engine as orchestrator_engine
from orchestrator.task import Step, Task
from tools import registry
from tools.base import BaseTool


class FakeCrawlerTool(BaseTool):
    name = "crawler"
    description = "Fake crawler for testing"

    def __init__(self):
        self.fail_mode: str | None = None  # "error", "short_text", "captcha"

    async def run(self, params: dict) -> dict:
        if self.fail_mode == "error":
            return {"success": False, "data": None, "error": "HTTP 403"}
        if self.fail_mode == "short_text":
            return {"success": True, "data": {"url": params["url"], "text": "짧은"}, "error": None}
        if self.fail_mode == "captcha":
            return {
                "success": True,
                "data": {"url": params["url"], "text": "unusual traffic detected. captcha required."},
                "error": None,
            }
        return {
            "success": True,
            "data": {"url": params["url"], "text": "x" * 200},
            "error": None,
        }


class FakeBrowserAutoTool(BaseTool):
    name = "browser_auto"
    description = "Fake browser_auto for testing"

    def __init__(self):
        self.called = False
        self.last_params: dict = {}
        self.fail = False

    async def run(self, params: dict) -> dict:
        self.called = True
        self.last_params = params
        if self.fail:
            return {"success": False, "data": None, "error": "playwright not installed"}
        return {
            "success": True,
            "data": {"text": "Playwright로 가져온 본문 텍스트입니다. " * 10},
            "error": None,
        }


class CrawlerFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.crawler = FakeCrawlerTool()
        self.browser_auto = FakeBrowserAutoTool()
        registry.register(self.crawler)
        registry.register(self.browser_auto)

        self._orig_evaluate = orchestrator_engine.result_quality.evaluate
        self._orig_review = orchestrator_engine.ai_reviewer.review
        self._orig_continue_task = orchestrator_engine.ai_agent.continue_task
        self._orig_summarize = orchestrator_engine.summarizer.summarize
        self._orig_record_task_trace = orchestrator_engine.record_task_trace

        async def noop_trace(*args, **kwargs):
            return None

        async def fake_summarize(command: str, results: list[dict], *, allow_ai: bool = True):
            return "done"

        async def fake_continue_task(command: str, current_result: dict):
            return None

        async def fake_review(command: str, step: dict, result: dict, quality: dict):
            return {"acceptable": True}

        orchestrator_engine.record_task_trace = noop_trace
        orchestrator_engine.summarizer.summarize = fake_summarize
        orchestrator_engine.ai_agent.continue_task = fake_continue_task
        orchestrator_engine.ai_reviewer.review = fake_review

    async def asyncTearDown(self):
        orchestrator_engine.result_quality.evaluate = self._orig_evaluate
        orchestrator_engine.ai_reviewer.review = self._orig_review
        orchestrator_engine.ai_agent.continue_task = self._orig_continue_task
        orchestrator_engine.summarizer.summarize = self._orig_summarize
        orchestrator_engine.record_task_trace = self._orig_record_task_trace

    async def test_crawler_http_error_falls_back_to_browser_auto(self):
        """Crawler HTTP failure → auto-insert browser_auto extract_text step."""
        self.crawler.fail_mode = "error"
        task = Task(
            command="오늘 날씨 알려줘",
            steps=[Step(tool="crawler", params={"url": "https://weather.example.com"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertTrue(self.browser_auto.called)
        self.assertEqual(self.browser_auto.last_params["action"], "extract_text")
        self.assertEqual(self.browser_auto.last_params["url"], "https://weather.example.com")
        # Should have 2 steps: original crawler + fallback browser_auto
        self.assertEqual(len(result.steps), 2)
        self.assertEqual(result.steps[1].tool, "browser_auto")

    async def test_crawler_short_text_falls_back_to_browser_auto(self):
        """Crawler returns too-short text → auto-fallback to browser_auto."""
        self.crawler.fail_mode = "short_text"
        task = Task(
            command="뉴스 가져와",
            steps=[Step(tool="crawler", params={"url": "https://news.example.com"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertTrue(self.browser_auto.called)
        self.assertEqual(len(result.steps), 2)
        self.assertEqual(result.steps[1].tool, "browser_auto")

    async def test_crawler_captcha_falls_back_to_browser_auto(self):
        """Crawler hits CAPTCHA → auto-fallback to browser_auto."""
        self.crawler.fail_mode = "captcha"
        task = Task(
            command="검색 결과 가져와",
            steps=[Step(tool="crawler", params={"url": "https://search.example.com"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertTrue(self.browser_auto.called)
        self.assertEqual(len(result.steps), 2)

    async def test_crawler_success_does_not_fallback(self):
        """Crawler succeeds normally → no fallback triggered."""
        self.crawler.fail_mode = None
        task = Task(
            command="페이지 크롤",
            steps=[Step(tool="crawler", params={"url": "https://example.com"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertFalse(self.browser_auto.called)
        self.assertEqual(len(result.steps), 1)

    async def test_fallback_browser_auto_also_fails_results_in_task_failure(self):
        """When both crawler and browser_auto fail, task fails gracefully."""
        self.crawler.fail_mode = "error"
        self.browser_auto.fail = True
        task = Task(
            command="데이터 가져와",
            steps=[Step(tool="crawler", params={"url": "https://example.com"})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "failed")
        self.assertTrue(self.browser_auto.called)
        self.assertIn("playwright", result.error.lower())

    async def test_crawler_without_url_does_not_fallback(self):
        """Crawler step without URL param should not attempt fallback."""
        self.crawler.fail_mode = "error"
        task = Task(
            command="크롤",
            steps=[Step(tool="crawler", params={})],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "failed")
        self.assertFalse(self.browser_auto.called)


class BuildCrawlerFallbackStepTests(unittest.TestCase):
    def test_builds_correct_browser_auto_step(self):
        crawler_step = Step(tool="crawler", params={"url": "https://example.com"})
        fallback = orchestrator_engine._build_crawler_fallback_step(crawler_step)

        self.assertIsNotNone(fallback)
        self.assertEqual(fallback.tool, "browser_auto")
        self.assertEqual(fallback.params["action"], "extract_text")
        self.assertEqual(fallback.params["url"], "https://example.com")
        self.assertTrue(fallback.params["headless"])

    def test_returns_none_when_no_url(self):
        crawler_step = Step(tool="crawler", params={})
        fallback = orchestrator_engine._build_crawler_fallback_step(crawler_step)

        self.assertIsNone(fallback)


if __name__ == "__main__":
    unittest.main()
