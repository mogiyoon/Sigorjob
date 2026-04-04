import os
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.store import config_store
from db import session as db_session
from gateway.app import app
from intent import router as intent_router
from orchestrator import engine as orchestrator_engine
from scheduler import service as scheduler_service
from tools.registry import load_default_tools


class ApiFlowTests(unittest.IsolatedAsyncioTestCase):
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
        self._orig_has_api_key = intent_router.has_api_key
        intent_router.has_api_key = lambda: False

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
        intent_router.has_api_key = self._orig_has_api_key
        await self.client.aclose()
        await scheduler_service.stop()
        await self.engine.dispose()
        self.tmpdir.cleanup()

    async def test_file_write_requires_approval_and_can_be_rejected(self):
        response = await self.client.post(
            "/command",
            json={"text": "/tmp/agent-test.txt 파일에 hello 써줘", "context": {}},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "approval_required")
        task_id = payload["task_id"]

        approvals = await self.client.get("/approvals")
        self.assertEqual(approvals.status_code, 200)
        approval_items = approvals.json()["approvals"]
        self.assertEqual(len(approval_items), 1)
        self.assertEqual(approval_items[0]["task_id"], task_id)

        reject = await self.client.post(
            f"/approval/{task_id}",
            json={"action": "reject", "reason": "not allowed during test"},
        )
        self.assertEqual(reject.status_code, 200)
        self.assertEqual(reject.json()["status"], "cancelled")

        task = await self.client.get(f"/task/{task_id}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertEqual(task_payload["status"], "cancelled")
        self.assertEqual(task_payload["result"]["summary"], "not allowed during test")

    async def test_schedule_create_list_and_delete(self):
        response = await self.client.post(
            "/schedule",
            json={
                "name": "Morning check",
                "command": "현재 시간",
                "cron": "0 9 * * *",
            },
        )
        self.assertEqual(response.status_code, 200)
        schedule_id = response.json()["schedule_id"]

        schedules = await self.client.get("/schedules")
        self.assertEqual(schedules.status_code, 200)
        items = schedules.json()["schedules"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["schedule_id"], schedule_id)
        self.assertEqual(items[0]["status"], "active")
        self.assertIsNotNone(items[0]["next_run_at"])

        deleted = await self.client.delete(f"/schedule/{schedule_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["status"], "deleted")

        schedules_after_delete = await self.client.get("/schedules")
        self.assertEqual(schedules_after_delete.status_code, 200)
        self.assertEqual(schedules_after_delete.json()["schedules"], [])

    async def test_custom_command_create_list_delete_and_route(self):
        created = await self.client.post(
            "/custom-commands",
            json={
                "trigger": "합주 준비",
                "action_text": "현재 시간",
                "match_type": "contains",
            },
        )
        self.assertEqual(created.status_code, 200)
        payload = created.json()
        self.assertTrue(payload["success"])
        rule_id = payload["custom_command"]["id"]

        listed = await self.client.get("/custom-commands")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["custom_commands"]), 1)

        response = await self.client.post(
            "/command",
            json={"text": "합주 준비 좀 해줘", "context": {}},
        )
        self.assertEqual(response.status_code, 200)
        task_id = response.json()["task_id"]

        task = await self.client.get(f"/task/{task_id}")
        self.assertEqual(task.status_code, 200)
        task_payload = task.json()
        self.assertIn(task_payload["status"], {"pending", "done"})

        deleted = await self.client.delete(f"/custom-commands/{rule_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["success"])


if __name__ == "__main__":
    unittest.main()
