import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import runtime
from tools.registry import get, load_default_tools
from tools.summarize.tool import MAX_INPUT_CHARS, SummarizeTool


class _FakeResponseText:
    def __init__(self, text: str):
        self.text = text


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeResponseText(text)]


class _CapturingMessages:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self.response_text)


class _FakeClient:
    def __init__(self, response_text: str):
        self.messages = _CapturingMessages(response_text)


class SummarizeToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = SummarizeTool()
        self._orig_has_api_key = runtime.has_api_key
        self._orig_get_client = runtime.get_client
        self._orig_registry = __import__("tools.registry", fromlist=["_registry"])._registry.copy()

    async def asyncTearDown(self):
        runtime.has_api_key = self._orig_has_api_key
        runtime.get_client = self._orig_get_client
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        registry_module._registry.clear()
        registry_module._registry.update(self._orig_registry)

    async def test_summarize_tool_with_text_param_returns_summary(self):
        client = _FakeClient("Short summary")
        runtime.has_api_key = lambda: True
        runtime.get_client = lambda: client

        result = await self.tool.run({"text": "Long input text.", "language": "en"})

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["summary"], "Short summary")
        self.assertEqual(result["data"]["language"], "en")
        self.assertIsNone(result["error"])

    async def test_summarize_tool_without_text_param_returns_error(self):
        result = await self.tool.run({})

        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertIn("missing text", result["error"])

    async def test_summarize_tool_without_api_key_uses_extractive_fallback(self):
        runtime.has_api_key = lambda: False
        runtime.get_client = lambda: None
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."

        result = await self.tool.run({"text": text})

        self.assertTrue(result["success"])
        self.assertEqual(
            result["data"]["summary"],
            "First sentence. Second sentence. Third sentence.",
        )
        self.assertEqual(result["data"]["language"], "auto-detect")

    async def test_summarize_tool_registered_in_registry(self):
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        registry_module._registry.clear()

        load_default_tools()

        self.assertIsNotNone(get("summarize"))

    async def test_summarize_tool_with_language_param_respects_language(self):
        client = _FakeClient("요약")
        runtime.has_api_key = lambda: True
        runtime.get_client = lambda: client

        result = await self.tool.run({"text": "긴 입력입니다.", "language": "ko"})

        self.assertTrue(result["success"])
        prompt = client.messages.calls[0]["messages"][0]["content"]
        self.assertIn("Respond in ko.", prompt)

    async def test_summarize_tool_truncates_very_long_input_before_sending_to_ai(self):
        client = _FakeClient("summary")
        runtime.has_api_key = lambda: True
        runtime.get_client = lambda: client
        text = "a" * (MAX_INPUT_CHARS + 50)

        result = await self.tool.run({"text": text})

        self.assertTrue(result["success"])
        prompt = client.messages.calls[0]["messages"][0]["content"]
        self.assertIn("a" * MAX_INPUT_CHARS, prompt)
        self.assertNotIn("a" * (MAX_INPUT_CHARS + 1), prompt)


if __name__ == "__main__":
    unittest.main()
