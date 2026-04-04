# Dev Workflow

This project uses a three-role development workflow to maintain code quality
and keep the planning, implementation, and review phases separate.

---

## Roles

| Role | Agent | Responsibility |
|------|-------|---------------|
| Planner | Claude Code (this instance) | Requirements analysis, architecture decisions, writing implementation specs |
| Implementer | Codex | Writing code and tests per spec, following `AGENTS.md` |
| Reviewer | Separate Claude Code instance | Code review against architecture principles and test coverage |

The planner does not write production code.
The implementer does not make architecture decisions.
The reviewer does not implement fixes — they flag issues and return to Codex.

---

## Workflow Steps

```text
1. Planner (Claude Code)
   - Receives a feature request or bug report
   - Reads current code to understand scope
   - Writes an implementation spec (see spec template below)
   - Hands spec to Codex

2. Implementer (Codex)
   - Reads AGENTS.md and the spec
   - Implements code + tests
   - Opens a PR

3. Reviewer (Claude Code)
   - Reviews the PR against the review checklist below
   - Returns feedback to Codex if issues found
   - Approves when all criteria pass
```

---

## Implementation Spec Template

Use this format when handing work to Codex:

```markdown
## Spec: <title>

### Goal
One sentence: what is being built and why.

### Non-AI path (primary)
What rule / plugin / tool handles this without AI?
- Rule pattern: `(regex)`
- Tool/plugin: `plugin_name`
- Params shape: `{"key": "value"}`

### AI fallback path
What happens when non-AI path fails or doesn't match?
- How AI should interpret the request
- Which tool AI should call as fallback

### Implementation locations
- New file: `backend/plugins/my_plugin/plugin.py`
- Modified file: `backend/intent/rules/rules.yaml` — add rule `my_rule`
- Modified file: `backend/plugins/loader.py` — if manual registration needed

### Test requirements
| Case | Expected result |
|------|----------------|
| Exact trigger phrase matches | Routed to `my_plugin`, `used_ai=False` |
| Partial phrase matches | Same result |
| Unrelated command | Not matched |
| Plugin `run()` with valid params | `{"success": True, "data": {...}}` |
| Plugin `run()` with missing params | Handles gracefully |

### Constraints
- Must not touch: `orchestrator/engine.py` (unless explicitly in scope)
- Must not add AI calls inside the plugin
- Must not break existing tests
```

---

## Review Checklist {#review}

When reviewing a PR as the reviewer Claude Code, check the following:

### Architecture compliance

- [ ] Non-AI path is tried first before any AI call
- [ ] AI is not called from inside a tool or plugin
- [ ] The orchestrator is the only place that executes tool steps in sequence
- [ ] No direct cross-module imports that violate the dependency flow:
      `gateway → intent → orchestrator → tools` (one direction only)

### Code quality

- [ ] No `print()` statements — logger is used
- [ ] No hardcoded secrets, paths, or user-specific values
- [ ] All tool/plugin `run()` methods return `{"success": bool, "data": ..., "error"?: ...}`
- [ ] All async functions use `async def` / `await`
- [ ] Type hints on all new function signatures

### Test coverage

- [ ] New plugin has: route test (correct tool matched), run() test (success + error case)
- [ ] New tool has: run() test with valid params, run() with missing/invalid params
- [ ] New rule has: pattern match test, non-match test
- [ ] New orchestrator logic has: step execution test, error path test
- [ ] All existing tests still pass (no regressions)

### Spec compliance

- [ ] Implementation matches what the spec described
- [ ] No features added beyond the spec scope
- [ ] Constraints from the spec were respected

### Return to Codex if

Any checklist item fails. State specifically which items fail and why.
Do not approve partial implementations.

---

## Communication Pattern

### Planner → Codex
Deliver the spec using the template above.
Include the exact file paths and pattern/param shapes.
Be explicit about what must NOT be changed.

### Codex → Reviewer
Open a PR with:
- Title: `feat: <what>` / `fix: <what>` / `refactor: <what>`
- Body: Link to the spec, list of files changed, how to run the new tests

### Reviewer → Codex
If changes needed: list each failing checklist item with a specific line reference.
If approved: state "Review passed. All checklist items confirmed."

---

## Example: Adding a New Plugin

**Planner writes:**

> Spec: Reminder helper — schedule a notification at a given time
>
> Goal: Route "X시에 Y 알려줘" commands to reminder_helper without AI.
>
> Non-AI path: Rule pattern `(\d+)시(?: \d+분)?에 (.+) 알려줘`, tool `reminder_helper`, params `{"time": "{match_1}", "text": "{match_2}"}`.
>
> Test requirements: Route test confirms `used_ai=False`. Run test with `{"time": "8", "text": "약 먹기"}` returns `{"success": True, ...}`.
>
> Constraints: Do not modify intent/router.py main logic. Do not add AI inside the plugin.

**Codex implements:**
- `backend/plugins/reminder_helper/plugin.py`
- Adds rule to `rules.yaml`
- Writes `backend/tests/test_reminder_helper.py`

**Reviewer checks:**
- Route test present and passing
- No AI call inside plugin
- Returns correct data shape
