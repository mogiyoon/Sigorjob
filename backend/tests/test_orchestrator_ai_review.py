import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import engine as orchestrator_engine
from orchestrator.task import Step, Task
from tools.base import BaseTool
from tools import registry


class PartialTool(BaseTool):
    name = "partial_test_tool"
    description = "Returns a partial result for orchestrator tests"

    async def run(self, params: dict) -> dict:
        return {
            "success": True,
            "data": {"url": "https://example.com/partial"},
            "error": None,
        }


class FinishTool(BaseTool):
    name = "finish_test_tool"
    description = "Returns a finished result for orchestrator tests"

    async def run(self, params: dict) -> dict:
        return {
            "success": True,
            "data": {"action": "open_url", "url": "https://example.com/final"},
            "error": None,
        }


class OrchestratorAiReviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.partial_tool = PartialTool()
        self.finish_tool = FinishTool()
        registry.register(self.partial_tool)
        registry.register(self.finish_tool)

        self._orig_evaluate = orchestrator_engine.result_quality.evaluate
        self._orig_review = orchestrator_engine.ai_reviewer.review
        self._orig_continue_task = orchestrator_engine.ai_agent.continue_task
        self._orig_summarize = orchestrator_engine.summarizer.summarize
        self._orig_record_task_trace = orchestrator_engine.record_task_trace

        async def noop_trace(*args, **kwargs):
            return None

        orchestrator_engine.record_task_trace = noop_trace

    async def asyncTearDown(self):
        orchestrator_engine.result_quality.evaluate = self._orig_evaluate
        orchestrator_engine.ai_reviewer.review = self._orig_review
        orchestrator_engine.ai_agent.continue_task = self._orig_continue_task
        orchestrator_engine.summarizer.summarize = self._orig_summarize
        orchestrator_engine.record_task_trace = self._orig_record_task_trace

    async def test_ai_review_can_continue_non_ai_task_with_planned_steps(self):
        def fake_evaluate(tool: str, params: dict, result: dict):
            if tool == "partial_test_tool":
                return orchestrator_engine.result_quality.QualityEvaluation(
                    status="insufficient",
                    message="partial result",
                    issues=["not enough"],
                    needs_ai_review=True,
                    blocking=True,
                )
            return orchestrator_engine.result_quality.QualityEvaluation(
                status="sufficient",
                message="done",
                issues=[],
            )

        async def fake_review(command: str, step: dict, result: dict, quality: dict):
            return {
                "acceptable": False,
                "reason": "계속 진행이 필요합니다.",
                "retry_step": None,
            }

        async def fake_continue_task(command: str, current_result: dict):
            return {
                "intent": command,
                "summary": "AI가 남은 작업을 계획했습니다.",
                "steps": [
                    {
                        "tool": "finish_test_tool",
                        "params": {"source": "ai_continuation"},
                        "description": "finish the job",
                    }
                ],
            }

        async def fake_summarize(command: str, results: list[dict], *, allow_ai: bool = True):
            return "AI continuation finished the job."

        orchestrator_engine.result_quality.evaluate = fake_evaluate
        orchestrator_engine.ai_reviewer.review = fake_review
        orchestrator_engine.ai_agent.continue_task = fake_continue_task
        orchestrator_engine.summarizer.summarize = fake_summarize

        task = Task(
            command="non ai first, then ai continue",
            steps=[Step(tool="partial_test_tool", params={}, description="partial step")],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertTrue(result.used_ai)
        self.assertEqual(len(result.results), 2)
        self.assertEqual(result.results[1]["data"]["url"], "https://example.com/final")
        self.assertEqual(result.summary, "AI continuation finished the job.")

