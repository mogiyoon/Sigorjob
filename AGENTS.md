# AGENTS.md — Codex Implementation Guide

This file is the primary reference for Codex (AI coding agent) when implementing features in this project.
Read this before writing any code.

---

## Project Identity

This is an automation platform that uses the local PC as the execution hub.
Users send natural-language commands from mobile or web.
The system resolves requests via rule-based non-AI paths first, and falls back to AI only when rules fail.

**Core invariant**: every code change must preserve the non-AI-first execution contract.
Never route to AI in a path where a rule-based or plugin-based resolution already works.

---

## Architecture Flow

```text
User command
  → Gateway (FastAPI)
  → Intent Router  (rules.yaml + plugin rules → non-AI path)
                   (AI fallback only when rules fail)
  → Orchestrator   (sequential tool execution, approval gating, logging)
  → Tools / Plugins
  → Result + Summary
```

Key constraint: the orchestrator owns all execution. Tools must never call each other directly.

---

## Repository Layout

```text
backend/
  ai/             # AI layer — agent.py, reviewer.py, summarizer.py
  config/         # Config/secret store
  connections/    # Shared connector registry (Google Calendar, etc.)
  db/             # SQLite models and session
  debug_trace.py  # Structured execution trace logging
  gateway/        # FastAPI app + routes + auth middleware
  intent/         # Rules YAML, normalizer, router, risk evaluator
  logger/         # Structured logger
  notifications/  # Mobile notification queue
  orchestrator/   # engine.py (executor), task.py, result_quality.py
  permissions.py  # Allowed paths, blocked commands
  plugins/        # Plugin directory — one folder per plugin
  policy/         # Policy engine (blocked commands, shell patterns)
  scheduler/      # APScheduler cron runner
  tools/          # Default tools: file, shell, crawler, time, system_info
  tunnel/         # Cloudflare Tunnel manager
  tests/          # All tests live here
frontend/         # Next.js 15 frontend
src-tauri/        # Tauri desktop shell
docs/             # Architecture, module, API, and workflow docs
```

---

## Module Responsibilities (do not violate)

| Module | What it does | What it must NOT do |
|--------|-------------|---------------------|
| `gateway/` | HTTP, auth, routing | Execute tools directly |
| `intent/` | Resolve command → Task | Call orchestrator directly |
| `orchestrator/` | Execute Task steps in order | Call AI by default |
| `ai/` | Plan, review, summarize | Be called before rule check |
| `tools/` | Execute a single atomic action | Call other tools |
| `plugins/` | Register routes + tools for a domain | Bypass the orchestrator |
| `policy/` | Enforce allowed/blocked operations | Allow unsafe defaults |

---

## How to Add a New Plugin

Each plugin lives in `backend/plugins/<plugin_name>/plugin.py`.

Required interface:

```python
from tools.base import BaseTool
from plugins import PluginBase

class MyPlugin(BaseTool, PluginBase):
    name = "my_plugin"
    description = "One sentence describing what this plugin does."

    @classmethod
    def get_rules(cls) -> list[dict]:
        """Return YAML-style rules for the intent router."""
        return [
            {
                "name": "my_plugin_trigger",
                "pattern": r"(pattern to match)",
                "tool": cls.name,
                "params": {"text": "{match_1}"},
            }
        ]

    async def run(self, params: dict) -> dict:
        text = params.get("text", "")
        # non-AI logic first
        # ...
        return {"success": True, "data": {...}}
```

After creating the plugin, it is auto-discovered by `plugins/loader.py`.
No manual registration is needed.

---

## How to Add a New Tool

Create `backend/tools/<tool_name>/tool.py`:

```python
from tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "One sentence."

    async def run(self, params: dict) -> dict:
        # ...
        return {"success": True, "data": {...}}
```

Register it in `tools/registry.py` via `load_default_tools()`.

---

## How to Add Intent Rules (non-AI path)

Edit `backend/intent/rules/rules.yaml`:

```yaml
rules:
  - name: my_rule
    pattern: "(regex pattern)"
    tool: tool_name
    params:
      key: "{match_1}"
```

Patterns are matched with `re.search(..., re.IGNORECASE)`.
`{match_1}`, `{match_2}` are filled from capture groups.

---

## Coding Conventions

- All async functions use `async def` / `await`. No sync blocking in async paths.
- Type hints on function signatures (input and return types).
- Return shape for tools and plugins: always `{"success": bool, "data": any, "error"?: str}`.
- No print statements — use `get_logger(__name__)` from `logger/logger.py`.
- No hardcoded secrets — use `config/secret_store.py`.
- Do not import from `gateway/` inside `intent/` or `orchestrator/`.
- Do not import from `ai/` inside `tools/` or `plugins/`.

---

## Test Requirements

**Every new logic unit must have a corresponding test in `backend/tests/`.**

Test file naming: `test_<module_name>.py`.

Patterns from existing tests to follow:

### Stubbing AI calls

```python
async def fake_plan(command: str):
    return {"intent": command, "steps": [...]}

intent_router.ai_agent.plan = fake_plan
```

### Stubbing DB (config store)

```python
self.config_data: dict = {}
config_store.get = lambda key, default=None: self.config_data.get(key, default)
config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
```

### Stubbing trace recording

```python
async def noop_record_task_trace(*args, **kwargs):
    return None
intent_router.record_task_trace = noop_record_task_trace
```

### Async tests

```python
class MyTests(unittest.IsolatedAsyncioTestCase):
    async def test_something(self):
        ...
```

### Minimum test coverage for new code

| New code | Required tests |
|----------|---------------|
| New plugin | Rule match → correct tool routed; `run()` returns expected shape |
| New tool | `run()` with valid params; `run()` with missing params |
| New intent rule | Pattern matches expected commands; doesn't match unrelated commands |
| New router logic | Happy path; fallback path |
| New orchestrator logic | Step executed; error path; status transitions |

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
# or
python -m unittest discover tests/
```

All tests must pass before submitting code.
Do not stub out tests that fail — fix the underlying code.

---

## What Not to Do

- Do not add AI calls to the non-AI execution path (rules, plugins, tools).
- Do not call `ai/agent.py` from inside a plugin or tool.
- Do not skip writing tests for new logic.
- Do not hardcode user-specific values (emails, paths, API keys).
- Do not break existing test assertions — if a refactor changes behavior, update tests intentionally and note it.
- Do not add features beyond the scope of the task spec.
- Do not add docstrings or comments to code you didn't touch.
- Do not use `print()` — use the logger.

---

## Submitting Work

1. All existing tests pass.
2. New tests cover the new logic (see table above).
3. Code follows the conventions above.
4. No hardcoded values.
5. PR description explains **why** the change was made, not just what.

The PR will be reviewed by a separate Claude Code review instance using `docs/en/dev-workflow.md` as the review guide.
