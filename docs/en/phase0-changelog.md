# Phase 0 Changelog — Making the AI agent capable of everything

Date: 2026-04-04

---

## Summary

5 feature branches implemented via the dev harness (automated Codex pipeline).
Goal: transform the system from "limited tool executor" to "AI agent that can handle any request."

| Branch | Attempts | New Tests | Status |
|--------|----------|-----------|--------|
| `feat/expanded-permissions` | 1 | 7 | done |
| `feat/orchestrator-dynamic` | 1 | 6 | done |
| `feat/mcp-client` | 2 | 6 | done |
| `feat/browser-auto` | 1 | 8 | done |
| `feat/google-api-drivers` | 1 | 8 | done |

35 new tests total. Zero regressions across all runs.

---

## Feature 1: Expanded Execution Scope

**Branch**: `feat/expanded-permissions`
**Files**: `settings.py`, `policy/engine.py`, `risk_evaluator.py` + test

### Before
- Shell: only `ls`, `pwd`, `echo` allowed
- Files: only `/tmp` and app data dir accessible
- Risk: naive string split, no categorized levels

### After
- Shell: 24 commands — `pip`, `npm`, `node`, `python3`, `git`, `curl`, `wget`, `cat`, `grep`, `find`, `mkdir`, `cp`, `mv`, `touch`, `head`, `tail`, `wc`, `sort`, `uniq`, `diff`
- Files: user home directory + project root added
- Risk: `shlex.split()` parsing, categorized levels (low/medium per command)
- Dangerous patterns still blocked: `rm -rf`, `sudo`, `| bash`, `| sh`

### Impact
AI agent can now run real shell commands (git, curl, python3) and access files across the project. This is the foundation for all other features.

---

## Feature 2: Dynamic Orchestrator

**Branch**: `feat/orchestrator-dynamic`
**Files**: `orchestrator/task.py`, `orchestrator/engine.py` + test

### Before
- Linear step execution only
- No data passing between steps
- Fixed params at planning time
- 1 AI review per task

### After
- **Conditional steps**: `Step(condition="${steps[0].result.success}")` — skip if false
- **Template parameters**: `Step(params={"url": "${steps[0].result.data.url}"}, param_template=True)` — resolves at runtime
- **Nested references**: supports `${steps[0].result.data.items[0]}` with dot and bracket notation
- **Safe fallback**: invalid template references become empty string, no crash
- **AI review budget**: increased from 1 to 3 per task

### Impact
AI can now plan multi-step workflows where later steps use results from earlier steps. Conditional logic enables branching flows. More AI reviews mean better error recovery.

---

## Feature 3: MCP Client Integration

**Branch**: `feat/mcp-client`
**Files**: `tools/mcp/tool.py`, `connections/drivers/mcp_client.py`, `connections/registry.py`, `tools/registry.py` + test

### Before
- MCP listed as "planned" in connection registry
- No MCP protocol implementation
- External tools required custom driver per service

### After
- **MCPClient class**: connects to MCP servers via stdio transport (JSON-RPC 2.0)
  - `list_tools()` — discover available tools on server
  - `call_tool(name, arguments)` — invoke tool and get result
  - Protocol handshake, message framing, error handling
- **MCPTool**: registered in tool registry as `mcp`
  - `run({"server": "name", "tool": "tool_name", "arguments": {...}})`
  - Looks up server config from config_store
  - Validates tool exists before calling
- **Registry**: MCP connection status changed from `planned` to `configurable`
- **Config-driven**: MCP server configs stored in config_store, not hardcoded

### Impact
One integration enables unlimited external tools. Configure a Google Calendar MCP server → AI can create events. Configure a Gmail MCP server → AI can send email. Any MCP-compatible tool becomes available without writing custom drivers.

---

## Feature 4: Playwright Browser Automation

**Branch**: `feat/browser-auto`
**Files**: `tools/browser_auto/tool.py` + test

### Before
- Crawler: HTTP fetch only, no JavaScript, no interaction
- Browser: just validates URLs and returns links

### After
- **BrowserAutoTool**: Playwright-based real browser automation
  - `navigate` — load page, return URL/title/status
  - `extract_text` — get all text content (max 10,000 chars)
  - `click` — click element by CSS selector
  - `type` — fill text input by CSS selector
  - `screenshot` — capture page to PNG in /tmp
- Headless Chrome by default, configurable via params
- 30-second timeout per action
- Fresh browser context per call (no session leaking)
- Graceful degradation if Playwright not installed

### Impact
AI can now interact with JavaScript-heavy sites: search Naver Shopping, fill forms, extract dynamic content, take screenshots. This covers the "동적 웹 브라우징" gap that blocked many real-world requests.

---

## Feature 5: Google Calendar + Gmail API Drivers

**Branch**: `feat/google-api-drivers`
**Files**: `connections/oauth.py`, `connections/drivers/gmail.py`, `connections/drivers/google_calendar.py` + tests

### Before
- Google Calendar: generates template URL links only
- Gmail: registered in system but no driver implementation
- No OAuth flow

### After

**OAuth module** (`connections/oauth.py`):
- `exchange_code_for_tokens()` — authorization code → access + refresh tokens
- `refresh_access_token()` — silent token refresh
- `get_access_token()` — smart getter with auto-refresh (30s buffer)
- Tokens stored in `secret_store` (never config_store or plain files)

**GoogleCalendarConnectorDriver** (enhanced):
- OAuth token → real Calendar API calls (`events.insert`)
- Parses ISO datetime range → event with start/end
- Falls back to template link when no token (backward compatible)

**GmailConnectorDriver** (new):
- `send_email` — creates MIME message, base64 encodes, sends via Gmail API
- `read_email` — lists messages with metadata (subject, from, snippet)
- Query support for Gmail search syntax
- Lazy imports for google-api-python-client

### Impact
When OAuth is configured, the system can create real calendar events and send real emails — not just open links. This is the critical bridge from "suggest action" to "execute action."

---

## Architecture Before vs After

### Before (limited executor)
```
User request → rules match? → simple tool (fetch/open URL/read file) → link or text
                   └─ AI plans → same limited tools → still just links
```

### After (capable agent)
```
User request → rules match? → tools + connectors → real actions
                   └─ AI plans → dynamic multi-step → real browser + real APIs + MCP
                                   ├─ step 1 result feeds step 2 params
                                   ├─ conditions skip irrelevant steps
                                   └─ AI reviews and adjusts (3x budget)
```

---

## What's now possible that wasn't before

| Request | Before | After |
|---------|--------|-------|
| "캘린더에 내일 3시 회의 추가" | Google Calendar link | Real event created via API |
| "mogiyoon@gmail.com으로 메일 보내줘" | mailto: link | Real email sent via Gmail API |
| "네이버 쇼핑에서 드럼스틱 최저가" | HTTP fetch (JS fails) | Playwright extracts real results |
| "이 페이지 스크린샷 찍어줘" | Not possible | Playwright screenshot to /tmp |
| "git status 보여줘" | Blocked | Allowed (low risk) |
| "curl로 API 호출해줘" | Blocked | Allowed (medium risk, approval) |
| "MCP 서버의 tool 호출" | Not possible | MCPTool routes to any MCP server |
| "검색 결과로 메일 보내줘" (multi-step) | Params hardcoded | Step 2 uses ${steps[0].result} |
