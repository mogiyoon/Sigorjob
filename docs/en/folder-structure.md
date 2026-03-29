# Folder Structure

## Top-Level Layout

```text
Agent/
├── backend/        # FastAPI backend, CLI, orchestration, tools
├── frontend/       # Next.js web UI
├── mobile/         # React Native WebView wrapper
├── src-tauri/      # Desktop shell
├── scripts/        # dev/build/CLI helper scripts
└── docs/           # documentation
```

## Main Areas

### `backend/`

- `main.py`: unified entrypoint (`serve/run/repl/tools`)
- `cli.py`: headless CLI entrypoint
- `gateway/routes/`: HTTP endpoints
- `intent/`: rules-first routing and AI fallback
- `orchestrator/`: task execution
- `tools/`: tool implementations
- `scheduler/`: recurring job execution
- `tunnel/`: Cloudflare Tunnel and pairing token management
- `db/`: SQLite models and sessions

### `frontend/`

- `src/app/page.tsx`: main UI
- `src/app/pair/page.tsx`: mobile pairing information
- `src/app/setup/page.tsx`: Cloudflare setup
- `src/components/ApprovalPanel.tsx`: approval queue UI
- `src/components/SchedulePanel.tsx`: schedule UI

### `mobile/`

- `App.tsx`: screen switching
- `QRScanScreen.tsx`: QR pairing flow
- `ManualPairScreen.tsx`: manual URL/token pairing
- `MainScreen.tsx`: WebView wrapper

### `src-tauri/`

- `main.rs`: automatically starts the Python sidecar in release builds

## Folder Principles

| Folder | Role | AI usage |
|------|------|---------|
| `gateway/` | request intake, auth, exposure boundary | none |
| `intent/` | rules first, AI only when needed | conditional |
| `orchestrator/` | execution order, status, approval-required state, result persistence, summary calls | none |
| `ai/` | intent planning and result summarization only | conditional |
| `tools/` | independent executable plugins | tool-specific |
| `policy/` | allow/block rule enforcement | none |
| `scheduler/` | cron-based recurring execution | none |
| `tunnel/` | remote access tunnel state and pairing token management | none |
| `cli.py` | headless execution entrypoint | none |
