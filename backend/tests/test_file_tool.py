import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.file.tool import FileTool


class FileToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = FileTool()
        self.paths_to_cleanup: list[Path] = []

    async def asyncTearDown(self):
        for path in self.paths_to_cleanup:
            try:
                if path.exists():
                    path.unlink()
            except FileNotFoundError:
                pass

    def _tmp_path(self, suffix: str = ".txt") -> Path:
        path = Path("/tmp") / f"codex-file-tool-{uuid4().hex}{suffix}"
        self.paths_to_cleanup.append(path)
        return path

    async def test_read_existing_file_returns_content(self):
        path = self._tmp_path()
        content = "hello from file tool"
        path.write_text(content, encoding="utf-8")

        result = await self.tool.run({"operation": "read", "path": str(path)})

        self.assertTrue(result["success"])
        self.assertEqual(result["data"], content)
        self.assertIsNone(result["error"])

    async def test_read_nonexistent_file_returns_error(self):
        path = self._tmp_path()

        result = await self.tool.run({"operation": "read", "path": str(path)})

        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertIsInstance(result["error"], str)
        self.assertTrue(result["error"])

    async def test_write_creates_file_in_allowed_dir(self):
        path = self._tmp_path()
        content = "written content"

        result = await self.tool.run(
            {"operation": "write", "path": str(path), "content": content}
        )

        self.assertTrue(result["success"])
        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(encoding="utf-8"), content)

    async def test_write_to_blocked_path_returns_error(self):
        path = Path("/etc") / f"codex-blocked-{uuid4().hex}.txt"

        result = await self.tool.run(
            {"operation": "write", "path": str(path), "content": "blocked"}
        )

        self.assertFalse(result["success"])
        self.assertIsNone(result["data"])
        self.assertIsInstance(result["error"], str)
        self.assertTrue(result["error"])
        self.assertFalse(path.exists())

    async def test_copy_copies_file_contents(self):
        src = self._tmp_path()
        dst = self._tmp_path()
        content = "copy me"
        src.write_text(content, encoding="utf-8")

        result = await self.tool.run(
            {"operation": "copy", "src": str(src), "dst": str(dst)}
        )

        self.assertTrue(result["success"])
        self.assertTrue(dst.exists())
        self.assertEqual(dst.read_text(encoding="utf-8"), content)

    async def test_delete_removes_file(self):
        path = self._tmp_path()
        path.write_text("delete me", encoding="utf-8")

        result = await self.tool.run({"operation": "delete", "path": str(path)})

        self.assertTrue(result["success"])
        self.assertFalse(path.exists())
        self.assertIsNone(result["error"])
