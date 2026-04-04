import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import engine as orchestrator_engine
from orchestrator.task import Step, Task
from tools import registry
from tools.base import BaseTool


class EmitDataTool(BaseTool):
    name = "emit_data_test_tool"
    description = "Emits static data for orchestrator dynamic tests"

    async def run(self, params: dict) -> dict:
        return {
            "success": True,
            "data": {
                "url": "https://example.com/from-step-0",
                "items": ["alpha", "beta"],
            },
            "error": None,
        }


class EchoParamsTool(BaseTool):
    name = "echo_params_test_tool"
    description = "Echoes params for orchestrator dynamic tests"

    async def run(self, params: dict) -> dict:
        return {
            "success": True,
            "data": params,
            "error": None,
        }


class ReviewTool(BaseTool):
    name = "review_budget_test_tool"
    description = "Returns a result that always triggers AI review"

    async def run(self, params: dict) -> dict:
        return {
            "success": True,
            "data": {"sequence": params.get("sequence")},
            "error": None,
        }


class OrchestratorDynamicTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        registry.register(EmitDataTool())
        registry.register(EchoParamsTool())
        registry.register(ReviewTool())

        self._orig_evaluate = orchestrator_engine.result_quality.evaluate
        self._orig_review = orchestrator_engine.ai_reviewer.review
        self._orig_continue_task = orchestrator_engine.ai_agent.continue_task
        self._orig_summarize = orchestrator_engine.summarizer.summarize
        self._orig_record_task_trace = orchestrator_engine.record_task_trace

        async def noop_trace(*args, **kwargs):
            return None

        async def fake_summarize(command: str, results: list[dict], *, allow_ai: bool = True):
            return "done"

        async def fake_continue_task(command: str, current_result: dict):
            return None

        orchestrator_engine.record_task_trace = noop_trace
        orchestrator_engine.summarizer.summarize = fake_summarize
        orchestrator_engine.ai_agent.continue_task = fake_continue_task

    async def asyncTearDown(self):
        orchestrator_engine.result_quality.evaluate = self._orig_evaluate
        orchestrator_engine.ai_reviewer.review = self._orig_review
        orchestrator_engine.ai_agent.continue_task = self._orig_continue_task
        orchestrator_engine.summarizer.summarize = self._orig_summarize
        orchestrator_engine.record_task_trace = self._orig_record_task_trace

    async def test_false_condition_skips_step_and_task_completes(self):
        task = Task(
            command="skip false condition",
            steps=[Step(tool="echo_params_test_tool", params={"value": "x"}, condition=False)],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertIsNone(result.steps[0].result)
        self.assertEqual(result.results, [])

    async def test_true_condition_executes_step(self):
        task = Task(
            command="run true condition",
            steps=[Step(tool="echo_params_test_tool", params={"value": "x"}, condition=True)],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertTrue(result.steps[0].result["success"])

    async def test_param_template_resolves_direct_step_result_value(self):
        task = Task(
            command="resolve url",
            steps=[
                Step(tool="emit_data_test_tool", params={}),
                Step(
                    tool="echo_params_test_tool",
                    params={"url": "${steps[0].result.data.url}"},
                    param_template=True,
                ),
            ],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertEqual(result.steps[1].params["url"], "https://example.com/from-step-0")
        self.assertEqual(result.steps[1].result["data"]["url"], "https://example.com/from-step-0")

    async def test_param_template_resolves_nested_list_index(self):
        task = Task(
            command="resolve nested item",
            steps=[
                Step(tool="emit_data_test_tool", params={}),
                Step(
                    tool="echo_params_test_tool",
                    params={"item": "${steps[0].result.data.items[0]}"},
                    param_template=True,
                ),
            ],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertEqual(result.steps[1].params["item"], "alpha")
        self.assertEqual(result.steps[1].result["data"]["item"], "alpha")

    async def test_invalid_template_reference_becomes_empty_string_without_crash(self):
        task = Task(
            command="resolve invalid template",
            steps=[
                Step(
                    tool="echo_params_test_tool",
                    params={"missing": "${steps[0].result.data.missing}"},
                    param_template=True,
                )
            ],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertEqual(result.steps[0].params["missing"], "")
        self.assertEqual(result.steps[0].result["data"]["missing"], "")

    async def test_review_budget_allows_three_ai_reviews(self):
        review_calls: list[int] = []

        def fake_evaluate(tool: str, params: dict, result: dict):
            return orchestrator_engine.result_quality.QualityEvaluation(
                status="partial",
                message="needs review",
                issues=[],
                needs_ai_review=True,
                blocking=False,
            )

        async def fake_review(command: str, step: dict, result: dict, quality: dict):
            review_calls.append(step["params"]["sequence"])
            return {"acceptable": True}

        orchestrator_engine.result_quality.evaluate = fake_evaluate
        orchestrator_engine.ai_reviewer.review = fake_review

        task = Task(
            command="three reviews",
            steps=[
                Step(tool="review_budget_test_tool", params={"sequence": 1}),
                Step(tool="review_budget_test_tool", params={"sequence": 2}),
                Step(tool="review_budget_test_tool", params={"sequence": 3}),
            ],
        )

        result = await orchestrator_engine.run(task, persist=False)

        self.assertEqual(result.status, "done")
        self.assertEqual(review_calls, [1, 2, 3])
