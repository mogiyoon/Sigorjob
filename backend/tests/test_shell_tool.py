import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.shell.tool import ShellTool


class ShellToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = ShellTool()

    async def test_allowed_command_executes(self):
        result = await self.tool.run({"command": "echo hello-shell"})

        self.assertTrue(result["success"])
        self.assertIn("hello-shell", result["data"])
        self.assertIsNone(result["error"])

    async def test_blocked_command_returns_error(self):
        result = await self.tool.run({"command": "rm /tmp/test-file"})

        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertIn("policy blocked", result["error"])
        self.assertTrue(
            "blocked command: rm" in result["error"]
            or "command not in allowlist: rm" in result["error"]
        )

    async def test_dangerous_pattern_is_blocked(self):
        result = await self.tool.run({"command": "echo safe && rm -rf /tmp/not-run"})

        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertIn("policy blocked", result["error"])
        self.assertIn("blocked pattern: rm -rf", result["error"])
