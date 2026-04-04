import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import runtime
from tools.ai_process.tool import AIProcessTool, MAX_INPUT_CHARS
from tools.registry import get, load_default_tools
from tools.summarize.tool import SummarizeTool


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


class AIProcessToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = AIProcessTool()
        self.summarize_tool = SummarizeTool()
        self._orig_has_api_key = runtime.has_api_key
        self._orig_get_client = runtime.get_client
        self._orig_registry = __import__("tools.registry", fromlist=["_registry"])._registry.copy()

    async def asyncTearDown(self):
        runtime.has_api_key = self._orig_has_api_key
        runtime.get_client = self._orig_get_client
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        registry_module._registry.clear()
        registry_module._registry.update(self._orig_registry)

    async def test_ai_process_with_summarize_instruction_returns_result(self):
        client = _FakeClient("Summarized text")
        runtime.has_api_key = lambda: True
        runtime.get_client = lambda: client

        result = await self.tool.run(
            {"text": "Long input text.", "instruction": "Summarize this text concisely"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["result"], "Summarized text")
        self.assertEqual(result["data"]["instruction"], "Summarize this text concisely")

    async def test_ai_process_with_translate_instruction_returns_result(self):
        client = _FakeClient("Hello world")
        runtime.has_api_key = lambda: True
        runtime.get_client = lambda: client

        result = await self.tool.run(
            {
                "text": "안녕하세요 세계",
                "instruction": "Translate this text to English",
                "language": "en",
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["result"], "Hello world")

    async def test_ai_process_with_custom_instruction_returns_result(self):
        client = _FakeClient("Filtered output")
        runtime.has_api_key = lambda: True
        runtime.get_client = lambda: client

        result = await self.tool.run(
            {"text": "raw content", "instruction": "Filter this text to key phrases only"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["result"], "Filtered output")

    async def test_ai_process_without_text_returns_error(self):
        result = await self.tool.run({"instruction": "Summarize this"})

        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertIn("missing text", result["error"])

    async def test_ai_process_without_instruction_returns_error(self):
        result = await self.tool.run({"text": "input"})

        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertIn("missing instruction", result["error"])

    async def test_ai_process_without_api_key_returns_fallback(self):
        runtime.has_api_key = lambda: False
        runtime.get_client = lambda: None
        text = "x" * 700

        result = await self.tool.run({"text": text, "instruction": "Summarize this"})

        self.assertTrue(result["success"])
        self.assertIn("AI processing unavailable", result["data"]["result"])
        self.assertIn("x" * 500, result["data"]["result"])
        self.assertNotIn("x" * 501, result["data"]["result"])

    async def test_ai_process_truncates_input_before_sending_to_ai(self):
        client = _FakeClient("Processed")
        runtime.has_api_key = lambda: True
        runtime.get_client = lambda: client
        text = "a" * (MAX_INPUT_CHARS + 50)

        result = await self.tool.run({"text": text, "instruction": "Summarize this"})

        self.assertTrue(result["success"])
        prompt = client.messages.calls[0]["messages"][0]["content"]
        self.assertIn("a" * MAX_INPUT_CHARS, prompt)
        self.assertNotIn("a" * (MAX_INPUT_CHARS + 1), prompt)

    async def test_ai_process_registered_in_registry(self):
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        registry_module._registry.clear()

        load_default_tools()

        self.assertIsNotNone(get("ai_process"))

    async def test_summarize_tool_delegates_to_ai_process(self):
        captured: dict = {}

        async def fake_run(params: dict) -> dict:
            captured["params"] = params
            return {
                "success": True,
                "data": {"result": "Delegated summary", "instruction": params["instruction"]},
                "error": None,
            }

        self.summarize_tool.ai_process_tool.run = fake_run

        result = await self.summarize_tool.run({"text": "Long input text."})

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["summary"], "Delegated summary")
        self.assertEqual(
            captured["params"]["instruction"].splitlines()[0],
            "Summarize this text concisely.",
        )


if __name__ == "__main__":
    unittest.main()
