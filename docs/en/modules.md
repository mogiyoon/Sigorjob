# Modules

## Module Separation Principles

- Each module should keep a narrow responsibility whenever possible.
- HTTP entrypoints live in `gateway/`, while execution flows through `intent/` and `orchestrator/`.
- AI code is isolated in `ai/`.
- This document describes what already exists in the codebase today.

## Module Responsibilities

### `gateway/`

- Creates the FastAPI app and lifecycle hooks
- Applies CORS and auth middleware
- Enables rate limiting when `slowapi` is installed
- Receives and responds to HTTP requests
- Exposes local-only and remote-safe routes
- Serves the static frontend

Currently implemented main routes:

- `/command`
- `/task/{task_id}`
- `/tools`
- `/approvals`
- `/approval/{task_id}`
- `/schedule`
- `/schedules`
- `/pair/data`
- `/pair/status`
- `/pair/rotate`
- `/setup/status`
- `/setup/cloudflare`
- `/widget/summary`

### `intent/`

- Matches commands with YAML rules first
- Calls `ai/agent.py` only when no rule matches
- Produces executable `Task` and `Step` objects
- Computes simple risk levels for approval gating

### `orchestrator/`

- Manages `Task` status
- Executes steps sequentially
- Resolves and runs tools
- Persists task results
- Persists execution logs
- Calls the summarizer
- Stores approval-required state and reruns approved tasks

The current implementation is a sequential executor. Task graphs and retry policies are not implemented yet.

### `ai/`

- `agent.py`: generates execution plans for requests that rules cannot handle
- `summarizer.py`: produces short natural-language summaries of execution results

Important behavior:

- If `anthropic_api_key` is missing, the system falls back without AI calls.
- AI is a limited decision layer, not the default execution path.

### `tools/`

Current default tools:

- `file`
- `shell`
- `crawler`
- `time`
- `system_info`

Examples of tools planned but not yet implemented:

- `calendar`
- `message`

### `policy/`

- Checks blocked commands and blocked shell patterns
- Restricts file access to allowed paths
- Blocks internal sensitive files
- Works together with simple risk-based approval gating

### `db/`

- Stores `Task`, `TaskLog`, `ApprovalRequest`, and `Schedule`
- Uses SQLite

### `scheduler/`

- Loads recurring jobs with APScheduler
- Executes commands according to cron schedules
- Reuses the same `intent -> orchestrator -> tools` pipeline

### `tunnel/`

- Starts and stops `cloudflared`
- Extracts tunnel URLs
- Creates, verifies, and rotates pairing tokens
- Acts as an optional runtime dependency for remote/mobile access rather than a requirement for local-only usage

### `cli.py`

- `serve`: runs the FastAPI server
- `run`: runs one command
- `repl`: starts an interactive CLI session
- `tools`: lists registered tools

## Current Dependency Flow

```text
gateway -> intent -> orchestrator -> tools
intent -> ai
orchestrator -> ai.summarizer
orchestrator -> db
gateway -> tunnel
gateway -> config
cli -> intent -> orchestrator -> tools
scheduler -> intent -> orchestrator -> tools
```

## Planned But Not Yet Implemented

- WebSocket real-time updates
- Multi-step dependency graph execution
- JWT authentication
