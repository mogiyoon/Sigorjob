# MVP

## Current MVP State

The project has moved into a stage where the core pipeline works as a real MVP.

Current usage boundary:

- local desktop, local web, and CLI workflows are the lowest-friction path
- remote and mobile workflows can use either Quick Tunnel or a named Cloudflare tunnel
- packaged desktop builds can bundle `cloudflared` for end users
- source-based remote workflows still depend on host `cloudflared`
- source checkout still needs the normal development toolchain and dependencies

Already implemented:

- command input -> task creation -> tool execution -> result retrieval
- rules-first routing with AI fallback
- lightweight AI preflight/postflight review around the non-AI path
- `file`, `shell`, `crawler`, `time`, and `system_info` tools
- approval-required branching
- cron-based schedule registration
- remote access through Cloudflare Tunnel
- mobile WebView wrapper
- Android share-to-app command submission
- headless CLI for non-GUI servers
- shared connection model groundwork for mobile access, AI access, Gmail, Google Calendar, and future MCP-based tools

## Work That Still Comes After the Current MVP

- WebSocket-based real-time updates
- more advanced orchestration
- more tools such as `calendar` and `message`
- actual mobile widget implementation
- final packaging and deployment validation

## Completion View

The following items are already complete or mostly complete:

- commands defined by rules run without AI
- ambiguous commands can be interpreted through AI
- failed non-AI paths can hand work off to AI continuation
- weak final non-AI results can be re-routed into AI continuation instead of always failing
- risky work is routed into approval or blocked by policy
- execution results are persisted
- the frontend can submit commands and display results
- the same pipeline can be used from CLI environments
