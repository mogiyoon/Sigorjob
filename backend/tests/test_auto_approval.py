import os
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.store import config_store
from db import session as db_session
from db.models import Task as TaskModel, TaskStatus
from gateway.app import app
from orchestrator import engine as orchestrator_engine
from orchestrator.task import Step, Task
from policy import auto_approval
from scheduler import service as scheduler_service
from tools.base import BaseTool
from tools import registry


class AutoApprovalTestTool(BaseTool):
    name = "test_auto_approval_tool"
    description = "Tool used by auto approval tests."

    async def run(self, params: dict) -> dict:
        return {"success": True, "data": {"params": params}}


class AutoApprovalTests(unittest.IsolatedAsyncioTestCase):
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

        await db_session.init_db()
        registry.register(AutoApprovalTestTool())

        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000")

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        config_store.delete = self._orig_config_delete
        config_store.all = self._orig_config_all
        await self.client.aclose()
        await self.engine.dispose()
        self.tmpdir.cleanup()

    def _build_task(self, params: dict, *, task_risk: str, step_risk: str) -> Task:
        return Task(
            command="auto approval test",
            risk_level=task_risk,
            approval_reason="승인이 필요한 작업입니다.",
            steps=[
                Step(
                    tool=AutoApprovalTestTool.name,
                    params=params,
                    description="auto approval step",
                    risk_level=step_risk,
                )
            ],
        )

    async def _task_row(self, task_id: str) -> TaskModel:
        async with self.session_maker() as session:
            result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
            row = result.scalar_one_or_none()
        self.assertIsNotNone(row)
        return row

    async def test_first_medium_risk_requires_manual_approval_and_records_pattern(self):
        task = self._build_task({"path": "/tmp/example.txt"}, task_risk="medium", step_risk="medium")

        self.assertTrue(orchestrator_engine.requires_manual_approval(task))
        await orchestrator_engine.save_approval_request(task)
        self.assertEqual(task.status, "approval_required")

        row = await self._task_row(task.id)
        self.assertEqual(row.status, TaskStatus.approval_required)

        response = await self.client.post(f"/approval/{task.id}", json={"action": "approve"})
        self.assertEqual(response.status_code, 200)

        stored = self.config_data["auto_approval_patterns"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["tool"], AutoApprovalTestTool.name)
        self.assertEqual(stored[0]["pattern_hash"], auto_approval.params_hash({"path": "/tmp/example.txt"}))

    async def test_same_medium_risk_pattern_is_auto_approved_on_second_request(self):
        first_task = self._build_task({"path": "/tmp/example.txt"}, task_risk="medium", step_risk="medium")
        await orchestrator_engine.save_approval_request(first_task)
        approve = await self.client.post(f"/approval/{first_task.id}", json={"action": "approve"})
        self.assertEqual(approve.status_code, 200)

        second_task = self._build_task({"path": "/tmp/example.txt"}, task_risk="medium", step_risk="medium")
        self.assertFalse(orchestrator_engine.requires_manual_approval(second_task))

        await orchestrator_engine.run(second_task)
        self.assertNotEqual(second_task.status, "approval_required")
        self.assertEqual(second_task.status, "done")

    async def test_different_params_for_same_tool_still_require_manual_approval(self):
        first_task = self._build_task({"path": "/tmp/example.txt"}, task_risk="medium", step_risk="medium")
        await orchestrator_engine.save_approval_request(first_task)
        approve = await self.client.post(f"/approval/{first_task.id}", json={"action": "approve"})
        self.assertEqual(approve.status_code, 200)

        second_task = self._build_task({"path": "/tmp/other.txt"}, task_risk="medium", step_risk="medium")
        self.assertTrue(orchestrator_engine.requires_manual_approval(second_task))

        await orchestrator_engine.save_approval_request(second_task)
        self.assertEqual(second_task.status, "approval_required")

    async def test_high_risk_is_never_auto_approved(self):
        auto_approval.record_approved_pattern(AutoApprovalTestTool.name, {"path": "/tmp/example.txt"})
        task = self._build_task({"path": "/tmp/example.txt"}, task_risk="high", step_risk="high")

        self.assertTrue(orchestrator_engine.requires_manual_approval(task))
        await orchestrator_engine.save_approval_request(task)
        self.assertEqual(task.status, "approval_required")

    async def test_get_auto_approvals_returns_patterns(self):
        task = self._build_task({"path": "/tmp/example.txt"}, task_risk="medium", step_risk="medium")
        await orchestrator_engine.save_approval_request(task)
        approve = await self.client.post(f"/approval/{task.id}", json={"action": "approve"})
        self.assertEqual(approve.status_code, 200)

        response = await self.client.get("/approvals/auto")
        self.assertEqual(response.status_code, 200)
        patterns = response.json()["patterns"]
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["tool"], AutoApprovalTestTool.name)
        self.assertEqual(patterns[0]["pattern_hash"], auto_approval.params_hash({"path": "/tmp/example.txt"}))
        self.assertIn("approved_at", patterns[0])
        self.assertEqual(patterns[0]["count"], 1)

    async def test_delete_auto_approval_removes_pattern_and_requires_manual_approval_again(self):
        task = self._build_task({"path": "/tmp/example.txt"}, task_risk="medium", step_risk="medium")
        await orchestrator_engine.save_approval_request(task)
        approve = await self.client.post(f"/approval/{task.id}", json={"action": "approve"})
        self.assertEqual(approve.status_code, 200)

        pattern_id = self.config_data["auto_approval_patterns"][0]["id"]
        deleted = await self.client.delete(f"/approvals/auto/{pattern_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.config_data["auto_approval_patterns"], [])

        next_task = self._build_task({"path": "/tmp/example.txt"}, task_risk="medium", step_risk="medium")
        self.assertTrue(orchestrator_engine.requires_manual_approval(next_task))

    async def test_low_risk_behavior_is_unchanged(self):
        task = self._build_task({"path": "/tmp/example.txt"}, task_risk="low", step_risk="low")

        self.assertFalse(orchestrator_engine.requires_manual_approval(task))
        await orchestrator_engine.run(task)
        self.assertEqual(task.status, "done")


if __name__ == "__main__":
    unittest.main()
