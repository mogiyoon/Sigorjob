# Testing Strategy

## Purpose

Tests in this project serve a specific regression-prevention contract:
if a rule-based path works today without AI, tests must prove it still works
without AI after any change. This is not just quality — it protects the product's core identity.

---

## Test Categories

### 1. Intent normalization tests (`test_intent_router.py`)

Verify that `detect_intent`, `normalize_command`, `build_last_resort_intent`,
and `allows_browser_fallback` produce the correct output for given Korean/English inputs.

These are pure unit tests — no DB, no AI, no async.

### 2. Router tests (`test_intent_router.py`, `test_plugins.py`)

Verify that `intent_router.route(command)` returns the correct `Task` structure:
- Correct tool in `task.steps[0].tool`
- Correct params in `task.steps[0].params`
- `task.used_ai == False` for all non-AI routed commands

These are async tests using `IsolatedAsyncioTestCase`.
AI calls and trace recording must be stubbed out.

### 3. Plugin tests (`test_plugins.py`)

- Plugin loads via `load_plugins()`
- Plugin appears in `describe_plugins()`
- Plugin `run()` returns the expected data shape

### 4. Orchestrator tests (`test_orchestrator_ai_review.py`)

- Tool execution flows through the orchestrator correctly
- AI review is called only when `quality.needs_ai_review == True`
- Retry steps are inserted correctly
- Error paths set the correct `task.status`

### 5. API / integration tests (`test_api.py`, `test_connection_manager.py`)

- HTTP endpoints return correct status codes
- Connection manager stores and retrieves connection state

### 6. Quality and result tests (`test_result_quality.py`, `test_shopping_helper.py`)

- `result_quality.evaluate()` returns the correct quality status
- Plugin-level output passes quality evaluation

---

## Coverage Map

### Currently covered

| Module | Test file | Coverage |
|--------|-----------|---------|
| `intent/normalizer.py` | `test_intent_router.py` | High |
| `intent/router.py` | `test_intent_router.py`, `test_plugins.py` | High |
| `plugins/*/plugin.py` | `test_plugins.py` | Medium (route only) |
| `plugins/calendar_helper` | `test_plugins.py` | High (run + route) |
| `plugins/shopping_helper` | `test_shopping_helper.py` | Medium |
| `orchestrator/result_quality.py` | `test_result_quality.py` | Medium |
| `orchestrator/engine.py` | `test_orchestrator_ai_review.py` | Partial |
| `connections/manager.py` | `test_connection_manager.py` | Medium |

### Currently missing (priority order)

| Module | What to test | Priority |
|--------|-------------|---------|
| `policy/engine.py` | Blocked commands blocked; allowed commands pass; shell pattern blocking | High |
| `orchestrator/engine.py` | Full sequential execution; approval-required flow; `_maybe_enqueue_mobile_notification` | High |
| `intent/risk_evaluator.py` | Risk levels correctly assigned per tool | High |
| `custom_commands.py` | `match_custom_command` with `contains` and `exact` match types | High |
| `ai/summarizer.py` | Summary returned when `allow_ai=False`; AI not called when not allowed | Medium |
| `tools/file/tool.py` | Read, write, copy, move, delete operations | Medium |
| `tools/shell/tool.py` | Allowed command runs; blocked command raises error | Medium |
| `tools/crawler/tool.py` | URL fetch returns content | Medium |
| `scheduler/service.py` | Schedule created; schedule fires route | Low |

---

## Test Patterns

### Stubbing AI (required for any test that calls `route()`)

```python
async def asyncSetUp(self):
    self._orig_plan = intent_router.ai_agent.plan
    self._orig_record = intent_router.record_task_trace

    async def noop_record(*args, **kwargs):
        return None

    intent_router.record_task_trace = noop_record
    # If AI should not be called at all:
    # intent_router.ai_agent.plan = ... (raise AssertionError if called)

async def asyncTearDown(self):
    intent_router.ai_agent.plan = self._orig_plan
    intent_router.record_task_trace = self._orig_record
```

### Stubbing config store

```python
self.config_data: dict = {}
config_store.get = lambda key, default=None: self.config_data.get(key, default)
config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
config_store.delete = lambda key: self.config_data.pop(key, None)
config_store.all = lambda: dict(self.config_data)
```

### Asserting non-AI routing

```python
task = await intent_router.route("내일 오후 3시 팀 회의 캘린더에 일정 추가해줘")
self.assertEqual(task.steps[0].tool, "calendar_helper")
self.assertFalse(task.used_ai)  # This is the key assertion
```

### Asserting AI was NOT called

```python
async def fail_if_called(command, history):
    raise AssertionError("AI should not have been called")

intent_router.ai_agent.request_clarification = fail_if_called
task = await intent_router.route("4월 11일 16시에 벚꽃 일정 추가해줘")
# If we reach here, AI was not called
self.assertEqual(task.steps[0].tool, "calendar_helper")
```

---

## Rules for Writing New Tests

1. **Every new plugin must have a route test proving `used_ai=False`.**
   This is the non-negotiable regression guard for the non-AI-first contract.

2. **Every new plugin must have a `run()` test.**
   Test the success case with realistic params.
   Test the failure case (missing required param or invalid state).

3. **Every new rule in `rules.yaml` must have a pattern match test and a non-match test.**
   Pattern match test: the trigger phrase routes to the correct tool.
   Non-match test: a similar-but-different phrase does NOT match.

4. **AI must be stubbed in all router tests.**
   Router tests must not make real API calls.
   If a test requires AI to produce a result, fake it explicitly.

5. **Tests must not rely on external services.**
   No real HTTP calls, no real DB writes (use in-memory stubs or `persist=False`).

6. **Restore stubs in `tearDown` / `asyncTearDown`.**
   Always restore the original to avoid cross-test contamination.

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v

# Run a specific file
python -m pytest tests/test_plugins.py -v

# Run a specific test
python -m pytest tests/test_plugins.py::PluginRouteTests::test_calendar_plugin_route -v
```

All tests must pass before any PR is merged.
