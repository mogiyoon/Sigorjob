import os
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import session as db_session
from gateway.app import app
from orchestrator import engine as orchestrator_engine
from scheduler import service as scheduler_service
from tools.registry import load_default_tools


class ApiFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.tmpdir.name, "test.db")
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

        db_session.engine = self.engine
        db_session.AsyncSessionLocal = self.session_maker
        orchestrator_engine.AsyncSessionLocal = self.session_maker
        scheduler_service.AsyncSessionLocal = self.session_maker

        await db_session.init_db()
        load_default_tools()
        await scheduler_service.start()

        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000")

    async def asyncTearDown(self):
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

    async def test_task_delete_removes_single_task_from_listing(self):
        created = await self.client.post(
            "/command",
            json={"text": "현재 시간", "context": {}},
        )
        self.assertEqual(created.status_code, 200)
        task_id = created.json()["task_id"]

        for _ in range(20):
            task = await self.client.get(f"/task/{task_id}")
            self.assertEqual(task.status_code, 200)
            if task.json()["status"] in {"done", "failed", "cancelled"}:
                break
        else:
            self.fail("task did not finish in time")

        deleted = await self.client.delete(f"/task/{task_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["success"])

        task_after_delete = await self.client.get(f"/task/{task_id}")
        self.assertEqual(task_after_delete.status_code, 404)

        tasks = await self.client.get("/tasks")
        self.assertEqual(tasks.status_code, 200)
        self.assertNotIn(task_id, [item["task_id"] for item in tasks.json()["tasks"]])

    async def test_task_bulk_delete_removes_all_selected_tasks(self):
        task_ids: list[str] = []
        for text in ["현재 시간", "pwd"]:
            created = await self.client.post("/command", json={"text": text, "context": {}})
            self.assertEqual(created.status_code, 200)
            task_ids.append(created.json()["task_id"])

        for task_id in task_ids:
            for _ in range(20):
                task = await self.client.get(f"/task/{task_id}")
                self.assertEqual(task.status_code, 200)
                if task.json()["status"] in {"done", "failed", "cancelled"}:
                    break
            else:
                self.fail(f"task {task_id} did not finish in time")

        deleted = await self.client.post("/tasks/delete", json={"task_ids": task_ids})
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["success"])

        tasks = await self.client.get("/tasks")
        self.assertEqual(tasks.status_code, 200)
        remaining_ids = [item["task_id"] for item in tasks.json()["tasks"]]
        for task_id in task_ids:
            self.assertNotIn(task_id, remaining_ids)


if __name__ == "__main__":
    unittest.main()
