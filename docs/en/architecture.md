# Architecture

## Overview

This project is an automation platform that uses the local PC as the execution hub.
Users send commands from the web UI, mobile app, or CLI.
The system tries to handle requests with rules-based automation first,
and only uses AI at decision points where it is truly needed.

Core direction:

- the default execution path is non-AI automation
- minimizing AI usage is a product differentiator, not just a cost optimization
- the local PC is the actual execution authority
- mobile acts as a thin WebView-based remote control
- headless servers reuse the same backend through CLI mode
- if non-AI logic misses, AI should still be able to continue the task instead of falling back to generic search-only behavior
- AI should also be able to lightly validate the first and last action without owning the whole pipeline
- external services should be represented through one shared connection and capability model

Practical runtime boundary:

- local use does not require Cloudflare Tunnel
- packaged desktop builds can bundle `cloudflared` for remote/mobile use
- source-based remote and mobile use still require `cloudflared` on the host machine
- remote access can use either Quick Tunnel or a named Cloudflare tunnel
- source-based execution still requires Python and project dependencies

## Current Implementation

### Runtime Surfaces

There are currently three main runtime surfaces:

1. Desktop app
   Tauri starts the Python backend sidecar automatically in release builds and now picks an available local port at runtime.
2. Web UI
   FastAPI serves the exported Next.js frontend.
3. CLI
   Non-GUI environments can use the same backend via `serve`, `run`, `repl`, and `tools`.

### Current Layer Model

```text
Client (Web / Mobile WebView / CLI)
    ->
Gateway (FastAPI, auth, local-only route guard, static serving)
    ->
Intent Router (rules first, AI fallback only when needed)
    ->
AI review layer (light preflight/postflight validation and continuation)
    ->
Connection / Capability Registry (mobile, AI, Gmail, Calendar, future MCP tools)
    ->
Orchestrator (task status, approval-required state, sequential tool execution)
    ->
Tools (file / shell / crawler / time / system_info)
    ->
Local resources (SQLite / filesystem / cloudflared / external HTTP)
```

### Current Request Flows

#### Standard command

```text
User request
  -> Intent Router
  -> rule match generates steps
  -> optional AI preflight sanity check
  -> Orchestrator
  -> tool execution
  -> optional AI postflight sanity check
  -> persistence and summary
```

#### AI fallback command

```text
User request
  -> no rule match
  -> AI agent produces a plan
  -> Orchestrator
  -> tool execution
  -> persistence and summary
```

#### AI takeover after a weak final result

```text
User request
  -> non-AI step runs first
  -> AI postflight decides the result is not good enough
  -> AI continuation produces the next steps
  -> Orchestrator keeps executing from there
```

#### Approval-required command

```text
User request
  -> Intent Router computes risk
  -> medium/high risk becomes approval_required
  -> user approves through API
  -> Orchestrator reruns the stored plan
```

#### Scheduled command

```text
Schedule created
  -> APScheduler fires on cron
  -> Intent Router
  -> Orchestrator
  -> tool execution
```

## Current Auth and Remote Access Model

### Local requests

- Requests from `127.0.0.1` or `localhost` are allowed without authentication.
- Sensitive setup and pairing routes are still protected as local-only endpoints.

### Remote requests

- The local backend is exposed through Cloudflare Tunnel.
- Remote mode can be either Quick Tunnel or a named Cloudflare tunnel.
- Packaged desktop builds are intended to ship with `cloudflared`.
- Source-based environments still need `cloudflared` on the host machine.
- Remote access uses pairing-token-based authentication.
- The first remote load can bootstrap with `?_token=`.
- After bootstrap, auth continues through an auth cookie or bearer token.
- When `cloudflared` is missing, setup and pairing now expose that state explicitly in the UI and API.

### Pairing flow

```text
Local PC UI
  -> exposes tunnel URL + token
  -> mobile app stores them through QR or manual input
  -> mobile WebView loads the remote UI
```

### Mobile share-to-app flow

```text
Shared text from another mobile app
  -> mobile app receives it
  -> paired desktop backend gets /command
  -> normal router/orchestrator pipeline runs
```

## Current Key Components

### Gateway

- receives HTTP requests
- enforces authentication and local-only route boundaries
- exposes `/command`, `/task`, `/approvals`, `/schedules`, `/pair`, `/setup`, and `/widget`

### Intent Router

- YAML-rule-based matching
- AI fallback only when rules fail
- optional AI preflight for first-step sanity checking
- risk annotation for steps

### Connection / Capability Registry

- tracks core connections such as mobile access and AI access
- provides a shared home for external services such as Gmail and Google Calendar
- is intended to become the same integration surface used by future MCP runtimes
- avoids one-off popup flows for each external feature

### Orchestrator

- sequential execution
- state persistence
- approval-required persistence
- rerun after approval
- AI postflight result checking
- AI continuation handoff when the final non-AI result is judged insufficient
- result summarization

### Tools

- `file`
- `shell`
- `crawler`
- `time`
- `system_info`

Note:

- helper plugins already cover several calendar, communication, route, reminder, weather, travel, and shopping-style requests even if the low-level tool list above stays small

### Scheduler

- APScheduler-based cron execution

### Tunnel

- start/stop `cloudflared`
- extract tunnel URLs
- create/verify/rotate pairing tokens

## Security Principles

- local-only and remote-safe routes are separated
- remote requests require token-based authentication
- shell execution uses an allowlist and argv-based execution
- file access is restricted to allowed directories
- sensitive internal files are blocked
- `medium` and `high` risk work requires approval

## Future Expansion

The following directions are intentionally planned, but not fully implemented in the current codebase.

### Real-time updates

- WebSocket-based task state and log streaming

### More advanced orchestration

- task graphs
- parallel execution
- conditional branches
- stronger retry policies

### Additional tools

- `calendar`
- `message`
- install/package management tools

### UX expansion

- actual mobile widget implementation
- richer approval and schedule UI
- more Tauri-safe handling for external links, clipboard, and other browser-assumed behaviors
- stronger open-source onboarding docs and operating guides

### Authentication evolution

- stronger token lifecycle management
- more extensible session and user models

### External connection expansion

- real Gmail send / read integration
- real calendar event creation through connected providers
- MCP runtime setup, install, and capability discovery
- shared approval and permission flows for external actions

## Technology Stack

| Area | Technology |
|------|------|
| Desktop runtime | Tauri 2 |
| Backend | Python / FastAPI / uvicorn |
| Scheduler | APScheduler |
| Database | SQLite |
| Frontend | Next.js 15 / TypeScript |
| Mobile | React Native + WebView |
| Tunnel | Cloudflare Tunnel (`cloudflared`) |
| AI | Anthropic API, used only when needed |
