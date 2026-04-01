# Debug Regressions

This document tracks runtime issues that have repeatedly regressed.

Goals:

- avoid reintroducing the same bug
- create a shared checklist before touching runtime code
- reduce "we already fixed this, why is it back?" moments

Read this first before changing:

- Tauri startup or shutdown
- backend sidecar launch behavior
- `cloudflared` / mobile quick connect
- local API port handling
- packaging order
- UI that works in the browser but not in Tauri

## Always Verify

1. Check whether port assumptions are hardcoded
2. Check whether startup cleanup or readiness logic can kill a healthy sidecar
3. Check whether `backend` and `cloudflared` actually exit on shutdown
4. Check whether packaged builds include static frontend files and default plugins
5. Check whether browser-only APIs are being used without a Tauri-safe path

## Repeated Regressions

### 1. Claimed dynamic port support but actual code still assumes 8000

The current code still directly assumes `8000` in:

- [src-tauri/src/main.rs](/Users/nohgiyoon/Coding/AI/Agent/src-tauri/src/main.rs)
- [backend/tunnel/manager.py](/Users/nohgiyoon/Coding/AI/Agent/backend/tunnel/manager.py)
- [frontend/src/lib/api.ts](/Users/nohgiyoon/Coding/AI/Agent/frontend/src/lib/api.ts)
- [backend/cli.py](/Users/nohgiyoon/Coding/AI/Agent/backend/cli.py)

Meaning:

- Do not claim dynamic port support unless startup probing, frontend base URL resolution, and tunnel target all share the same runtime port.

### 2. Tauri startup is much more complex than the initial commit

In the initial commit `b62d24cb`, [src-tauri/src/main.rs](/Users/nohgiyoon/Coding/AI/Agent/src-tauri/src/main.rs) mostly just spawned the `backend` sidecar.

The current version adds:

- app lock
- stale process cleanup
- startup log capture
- readiness waiting
- shutdown cleanup

Meaning:

- When startup fails, suspect the Tauri startup path before blaming tunnel behavior.
- When nothing shows up, first verify whether `backend` is actually alive.

### 3. Readiness failures can mask shutdown races

Observed pattern:

- the app stays open for a long time
- the user closes it and reopens it
- readiness fails because an old `backend` or `cloudflared` is still shutting down

Meaning:

- When startup times out, also inspect whether the previous session actually finished shutting down.

### 4. Mobile quick connect issues often start with backend health, not the tunnel

Observed pattern:

- mobile pairing appears broken
- the real issue is that `backend` never came up, or `/pair` was 404

Meaning:

- Always check in this order: `backend -> /setup/status -> /pair -> tunnel`

### 5. Bad packaging order can make `/pair` and `/setup` return 404

Observed pattern:

- frontend static files were missing from the packaged backend bundle

Meaning:

- Keep the packaging order as `frontend -> backend -> tauri`

### 6. Missing bundled plugins cause `tool not found`

Observed pattern:

- source runs worked
- packaged builds failed because default plugins like `calendar_helper` were missing

Meaning:

- Always verify that `backend/plugins` is included in packaged backend builds.

### 7. UI that works in the browser but fails in Tauri

Repeated offenders:

- `window.confirm`
- `<a target="_blank">`
- `navigator.clipboard`
- `window.location` branching that assumes browser semantics

Meaning:

- Browser success is not enough. Every new interaction needs a Tauri-safe path.

### 8. Task results can appear to disappear

Observed pattern:

- completed tasks move sections too quickly and look lost
- failures show up only in the console, not in the UI

Meaning:

- State transitions should remain visible to the user.
- Failures must be visible in the UI, not only in logs.

## Runtime Inspection Order

When something breaks, inspect in this order:

1. `lsof -nP -iTCP -sTCP:LISTEN` for `backend`, `cloudflared`, and `8000`
2. confirm the app is the latest packaged bundle
3. check `/setup/status`
4. check that `/pair` and `/setup` are not 404
5. look for stale sidecars
6. only then inspect the tunnel and mobile app

## Pre-change Checklist

Before changing runtime behavior, verify:

- does this make startup more complex?
- can this create cleanup races?
- are port assumptions still hardcoded?
- does it work in the packaged app, not just source mode?
- is any browser-only behavior being reused in Tauri?
- if this regresses later, have we added it to this document?

