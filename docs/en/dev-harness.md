# Dev Harness

## What it is

The dev harness is an orchestrator script that automates the **spec → implement → test → review → PR** loop.
It calls Codex CLI to implement code, runs tests to validate, and optionally runs code review — all without manual intervention.

This follows the SWE-bench / SWE-Agent pattern:
**orchestrator sends structured input → agent executes in sandbox → tests validate → orchestrator judges → retry or finalize.**

---

## Architecture

```text
Claude Code (planner)
    │
    │  writes spec JSON
    ↓
scripts/dev-harness.py
    │
    ├── 1. SETUP     git checkout -b {branch}
    │
    ├── 2. IMPLEMENT  codex exec --full-auto --json --ephemeral
    │                  (sends AGENTS.md + spec as prompt)
    │
    ├── 3. TEST       python3 -m unittest (focus + full suite)
    │
    ├── 4. REVIEW     codex exec review --uncommitted (optional)
    │
    └── 5. JUDGE
            ├── pass → git commit → (optional) gh pr create
            └── fail → build retry prompt with failure details → go to 2
                       (max N retries)
```

---

## Harness = structured I/O control loop

The harness is defined by this pattern:

```
Orchestrator ──structured input──→ Executor
     ↑                                 │
     └────structured output────────────┘
     → judgment → next instruction or done
```

It doesn't matter whether the executor is Codex, Claude sub-agent, or any other tool.
What matters is: **structured data in, structured data out, orchestrator decides what's next.**

---

## File structure

```
scripts/
  dev-harness.py              # Main harness script (~400 lines, stdlib only)
  harness-specs/              # Input spec JSON files
    01-mcp-client.json
    02-browser-auto.json
    03-orchestrator-dynamic.json
    04-google-api-drivers.json
    05-expanded-permissions.json
    example-spec.json
  harness-results/            # Output results (gitignored)
    {spec-id}_result.json
    {spec-id}_codex_output.txt
    {spec-id}_review_output.txt
```

---

## Spec JSON format

```json
{
  "id": "feat-my-feature",
  "title": "Short description of what to build",
  "goal": "One paragraph: what and why",
  "implementation_locations": {
    "new_files": ["backend/path/to/new.py"],
    "modified_files": ["backend/path/to/existing.py"]
  },
  "test_requirements": [
    {"case": "What to test", "expected": "What should happen"}
  ],
  "constraints": [
    "What must NOT be changed",
    "What patterns to follow"
  ],
  "branch_name": "feat/my-feature",
  "base_branch": "main",
  "max_retries": 3,
  "codex_model": "",
  "test_command": "cd backend && python3 -m unittest discover -s tests -v",
  "test_focus_command": "cd backend && python3 -m unittest tests.test_my_feature -v"
}
```

---

## CLI usage

```bash
# Dry run — see the prompt that will be sent to Codex
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json --dry-run

# Run implementation + tests (skip review)
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json --no-review

# Full run with review
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json

# Run + create PR
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json --pr

# Override model or retries
python3 scripts/dev-harness.py --spec my-spec.json --model gpt-4o --max-retries 5
```

---

## Result JSON format

```json
{
  "spec_id": "feat-my-feature",
  "status": "done",
  "attempts": [
    {
      "attempt": 1,
      "test_result": {
        "focus": {"passed": 5, "failed": 0, "all_passed": true},
        "full_suite": {"passed": 57, "failed": 0, "all_passed": true}
      },
      "review_result": {"passed": true},
      "outcome": "passed"
    }
  ],
  "final_commit": "abc1234",
  "pr_url": "https://github.com/...",
  "files_changed": ["backend/..."]
}
```

---

## How retry works

When tests fail or review rejects:
1. The harness builds a retry prompt containing:
   - The original AGENTS.md + spec
   - The failure type (test_failed or review_rejected)
   - The failure details (pytest output or review feedback)
   - Explicit instruction: "fix, don't rewrite from scratch"
2. Codex reads the files from the previous attempt (still on disk)
3. Codex patches only what's broken
4. Tests run again

Max retries default: 3. Configurable per spec or via CLI.

---

## Codex CLI flags used

| Flag | Purpose |
|------|---------|
| `--full-auto` | Sandbox workspace-write + auto-approval |
| `--json` | JSONL structured event output |
| `--ephemeral` | No session persistence (clean each run) |
| `-C dir` | Set working directory |
| `-o file` | Save last agent message to file |
| `-` (stdin) | Read prompt from stdin (for long prompts) |

---

## Integration with dev workflow

The harness fits into the three-role workflow (see `docs/en/dev-workflow.md`):

1. **Claude Code (planner)** writes the spec JSON
2. **Harness** runs Codex as implementer and reviewer
3. **Result** is a committed branch or PR ready for final human review

The harness replaces the manual copy-paste step between planner and implementer.
