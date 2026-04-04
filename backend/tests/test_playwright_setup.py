import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as main_module
from config.store import config_store
from db import session as db_session
from gateway.app import app
from gateway.routes import setup as setup_module
from orchestrator import engine as orchestrator_engine
from scheduler import service as scheduler_service
from tools.browser_auto import tool as browser_auto_module
from tools.browser_auto.tool import BrowserAutoTool
from tools.registry import load_default_tools


class PlaywrightStatusTests(unittest.TestCase):
    def test_check_playwright_status_returns_installed_true_when_available(self):
        with patch.object(main_module.importlib.util, "find_spec", return_value=object()):
            status = main_module.check_playwright_status()

        self.assertTrue(status["installed"])
        self.assertTrue(status["browsers_installed"])

    def test_check_playwright_status_returns_installed_false_when_missing(self):
        with patch.object(main_module.importlib.util, "find_spec", return_value=None):
            status = main_module.check_playwright_status()

        self.assertFalse(status["installed"])
        self.assertIn("pip install playwright", status["install_command"])


class PlaywrightSetupApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.tmpdir.name, "test.db")
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
        self.config_data: dict = {}
        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_config_delete = config_store.delete
        self._orig_config_all = config_store.all
        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
        config_store.delete = lambda key: self.config_data.pop(key, None)
        config_store.all = lambda: dict(self.config_data)

        db_session.engine = self.engine
        db_session.AsyncSessionLocal = self.session_maker
        orchestrator_engine.AsyncSessionLocal = self.session_maker
        scheduler_service.AsyncSessionLocal = self.session_maker
        config_store.set("custom_commands", [])

        await db_session.init_db()
        load_default_tools()
        await scheduler_service.start()

        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000")

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        config_store.delete = self._orig_config_delete
        config_store.all = self._orig_config_all
        await self.client.aclose()
        await scheduler_service.stop()
        await self.engine.dispose()
        self.tmpdir.cleanup()

    async def test_setup_status_includes_playwright_status(self):
        expected_status = {
            "installed": False,
            "browsers_installed": False,
            "install_command": "pip install playwright",
            "browser_install_command": f"{sys.executable} -m playwright install chromium",
        }
        with patch.object(setup_module, "check_playwright_status", return_value=expected_status):
            response = await self.client.get("/setup/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["playwright"], expected_status)
        self.assertIsInstance(response.json()["playwright"]["installed"], bool)

    async def test_install_endpoint_runs_pip_install_and_playwright_install(self):
        with patch.object(
            setup_module.subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
                subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
            ],
        ) as run_mock:
            response = await self.client.post("/setup/playwright/install")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "risk_level": "medium"})
        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(
            run_mock.call_args_list[0].args[0],
            [sys.executable, "-m", "pip", "install", "playwright"],
        )
        self.assertEqual(
            run_mock.call_args_list[1].args[0],
            [sys.executable, "-m", "playwright", "install", "chromium"],
        )

    async def test_install_endpoint_returns_error_when_install_fails(self):
        with patch.object(
            setup_module.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="install failed",
            ),
        ):
            response = await self.client.post("/setup/playwright/install")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": False, "error": "install failed", "risk_level": "medium"},
        )


class BrowserAutoInstallMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_auto_returns_install_instructions_when_playwright_missing(self):
        tool = BrowserAutoTool()
        original_async_playwright = browser_auto_module.async_playwright
        browser_auto_module.async_playwright = None
        try:
            result = await tool.run({"action": "navigate", "url": "https://example.com"})
        finally:
            browser_auto_module.async_playwright = original_async_playwright

        self.assertFalse(result["success"])
        self.assertIn("pip install playwright", result["error"])


if __name__ == "__main__":
    unittest.main()
