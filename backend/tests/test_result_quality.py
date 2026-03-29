import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.result_quality import evaluate


class ResultQualityTests(unittest.TestCase):
    def test_crawler_interstitial_is_blocking(self):
        result = {
            "success": True,
            "data": {
                "url": "https://www.google.com/search?q=test",
                "text": "Google Search 몇 초 안에 이동하지 않는 경우 여기 를 클릭하세요.",
            },
            "error": None,
        }
        evaluation = evaluate("crawler", {}, result)
        self.assertEqual(evaluation.status, "insufficient")
        self.assertTrue(evaluation.blocking)
        self.assertTrue(evaluation.needs_ai_review)

    def test_crawler_links_are_sufficient(self):
        result = {
            "success": True,
            "data": {
                "url": "https://news.google.com/rss/search?q=test",
                "text": "1. 기사 A\n2. 기사 B\n3. 기사 C",
                "links": [
                    {"title": "기사 A", "url": "https://example.com/a"},
                    {"title": "기사 B", "url": "https://example.com/b"},
                    {"title": "기사 C", "url": "https://example.com/c"},
                ],
            },
            "error": None,
        }
        evaluation = evaluate("crawler", {}, result)
        self.assertEqual(evaluation.status, "sufficient")
        self.assertFalse(evaluation.blocking)

    def test_file_read_empty_is_partial(self):
        result = {"success": True, "data": "", "error": None}
        evaluation = evaluate("file", {"operation": "read"}, result)
        self.assertEqual(evaluation.status, "partial")
        self.assertFalse(evaluation.blocking)


if __name__ == "__main__":
    unittest.main()
