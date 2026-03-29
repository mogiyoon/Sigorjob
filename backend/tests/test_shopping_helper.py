import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugins.shopping_helper.plugin import ShoppingHelperTool


class ShoppingHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_purchase_intent_requires_permission(self):
        tool = ShoppingHelperTool()
        with patch("plugins.shopping_helper.plugin._is_permission_granted", return_value=False):
            result = await tool.run(
                {
                    "platform": "naver",
                    "query": "드럼스틱",
                    "prefer_lowest_price": True,
                    "purchase_intent": True,
                }
            )
        self.assertFalse(result["success"])
        self.assertIn("권한", result["error"])

    async def test_purchase_intent_returns_checkout_ready_link_when_granted(self):
        tool = ShoppingHelperTool()
        with patch("plugins.shopping_helper.plugin._is_permission_granted", return_value=True):
            result = await tool.run(
                {
                    "platform": "naver",
                    "query": "드럼스틱",
                    "prefer_lowest_price": True,
                    "purchase_intent": True,
                }
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["action"], "open_url")
        self.assertIn("sort=price_asc", result["data"]["url"])
        self.assertTrue(result["data"]["purchase_intent"])


if __name__ == "__main__":
    unittest.main()
