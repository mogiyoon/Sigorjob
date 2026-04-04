import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.base import BaseTool
from tools.registry import load_default_tools, list_tools


class _DummyTool(BaseTool):
    async def run(self, params: dict) -> dict:
        return {"success": True, "data": None, "error": None}


class ToolI18NTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        cls._orig_registry = registry_module._registry.copy()
        registry_module._registry.clear()
        load_default_tools()

    @classmethod
    def tearDownClass(cls) -> None:
        registry_module = __import__("tools.registry", fromlist=["_registry"])
        registry_module._registry.clear()
        registry_module._registry.update(cls._orig_registry)

    def test_base_tool_has_bilingual_description_defaults(self):
        self.assertTrue(hasattr(BaseTool, "description_ko"))
        self.assertTrue(hasattr(BaseTool, "description_en"))
        self.assertEqual(BaseTool.description_ko, "")
        self.assertEqual(BaseTool.description_en, "")

    def test_schema_with_korean_locale_returns_korean_description(self):
        tool = _DummyTool()
        tool.name = "sample"
        tool.description = "English fallback description"
        tool.description_ko = "한국어 설명"
        tool.description_en = "English description"

        schema = tool.schema(locale="ko")

        self.assertEqual(schema["description"], "한국어 설명")
        self.assertNotIn("English", schema["description"])

    def test_schema_with_english_locale_returns_english_description(self):
        tool = _DummyTool()
        tool.name = "sample"
        tool.description = "English fallback description"
        tool.description_ko = "한국어 설명"
        tool.description_en = "English description"

        schema = tool.schema(locale="en")

        self.assertEqual(schema["description"], "English description")
        self.assertIsNone(re.search(r"[\uac00-\ud7a3]", schema["description"]))

    def test_all_tools_have_korean_and_english_descriptions(self):
        for tool in __import__("tools.registry", fromlist=["_registry"])._registry.values():
            self.assertTrue(tool.description_ko.strip(), f"{tool.name} missing description_ko")
            self.assertTrue(tool.description_en.strip(), f"{tool.name} missing description_en")

    def test_list_tools_with_korean_locale_returns_korean_descriptions(self):
        tools = list_tools(locale="ko")

        self.assertTrue(tools)
        for tool in tools:
            self.assertIsNotNone(re.search(r"[\uac00-\ud7a3]", tool["description"]))

    def test_korean_descriptions_contain_no_english_words(self):
        for tool in __import__("tools.registry", fromlist=["_registry"])._registry.values():
            self.assertIsNone(
                re.search(r"[A-Za-z]", tool.description_ko),
                f"{tool.name} description_ko should not contain English letters",
            )

    def test_english_descriptions_contain_no_korean_characters(self):
        for tool in __import__("tools.registry", fromlist=["_registry"])._registry.values():
            self.assertIsNone(
                re.search(r"[\uac00-\ud7a3]", tool.description_en),
                f"{tool.name} description_en should not contain Hangul",
            )


if __name__ == "__main__":
    unittest.main()
