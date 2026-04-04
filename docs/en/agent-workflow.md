# Agent Workflow

How AI requests flow through the system — from user input to final execution.

---

## Overview

```text
User command ("캘린더에 내일 3시 회의 추가해줘")
    │
    ▼
┌──────────────────────────────────────────────┐
│  1. GATEWAY  (FastAPI)                       │
│     Auth check → rate limit → route          │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  2. INTENT ROUTER                            │
│     Rules (YAML + plugin) → non-AI match?    │
│     ├── YES → Task with steps, used_ai=false │
│     └── NO  → AI agent plans steps           │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  3. RISK EVALUATOR                           │
│     Each step → low / medium / high          │
│     medium/high → approval_required          │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  4. ORCHESTRATOR                             │
│     Sequential step execution loop:          │
│     ┌─ execute step                          │
│     ├─ evaluate quality                      │
│     ├─ AI review (budget: 3)                 │
│     ├─ resolve ${template} params            │
│     ├─ evaluate step condition               │
│     └─ insert retry/continuation steps       │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  5. TOOLS / PLUGINS / CONNECTORS             │
│     file, shell, crawler, time, system_info  │
│     browser, browser_auto (Playwright)       │
│     mcp (external MCP servers)               │
│     calendar_helper, gmail, shopping, etc.   │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  6. RESULT + SUMMARY                         │
│     Summarize → notify → persist to DB       │
└──────────────────────────────────────────────┘
```

---

## Step 1: Gateway

**Where**: `backend/gateway/app.py`, `backend/gateway/routes/command.py`

User sends `POST /command` with `{"command": "..."}`.

- Local requests (127.0.0.1) pass without auth
- Remote requests require pairing token
- Command string forwarded to Intent Router

---

## Step 2: Intent Router

**Where**: `backend/intent/router.py`, `backend/intent/normalizer.py`, `backend/intent/rules/rules.yaml`

The router tries to resolve the command **without AI first**:

```text
1. Custom commands (user-defined triggers)
2. YAML rules (regex patterns → tool + params)
3. Plugin rules (each plugin registers patterns)
4. Intent normalizer (Korean NLP: URL extraction, time parsing, service detection)
5. ── all above failed ──
6. AI clarification (is the request ambiguous?)
7. AI agent plan (generate steps from scratch)
8. AI browser/automation assist (fallback classifiers)
9. Last resort: Google search link
```

**Output**: a `Task` object with `steps: [Step(tool, params, description)]`

Key flag: `task.used_ai` — false if resolved by rules, true if AI was needed.

---

## Step 3: Risk Evaluator

**Where**: `backend/intent/risk_evaluator.py`

Each step is assigned a risk level based on the tool and params:

| Tool | Risk |
|------|------|
| time, system_info | low |
| file (read), crawler | low |
| git, cat, grep | low |
| curl, wget | medium |
| pip install | medium |
| file (write/delete), shell (non-trivial) | medium |
| browser_auto | medium |
| mcp (external calls) | medium |

If any step is medium/high → `task.risk_level` = highest step level.
Medium/high tasks require user approval before execution.

---

## Step 4: Orchestrator

**Where**: `backend/orchestrator/engine.py`

The orchestrator runs the task's steps sequentially with these capabilities:

### Basic execution
```text
for each step in task.steps:
    tool = registry.get(step.tool)
    result = tool.run(step.params)
    evaluate quality
```

### Conditional execution (new)
```python
# Step with condition
Step(tool="crawler", params={...}, condition="${steps[0].result.success}")
# → only executes if step 0 succeeded
```

### Dynamic parameter templates (new)
```python
# Step that references previous result
Step(
    tool="browser",
    params={"url": "${steps[0].result.data.url}"},
    param_template=True
)
# → ${steps[0].result.data.url} resolves to actual URL from step 0
```

### AI review and continuation
```text
After each step:
  1. Quality evaluation (sufficient / partial / insufficient)
  2. If needs_ai_review → AI reviewer judges (budget: 3 per task)
  3. If not acceptable → AI plans continuation steps
  4. Inserted steps execute in sequence
```

### Status transitions
```text
pending → running → done
                  → failed (tool error, quality block)
                  → approval_required (risk gate)
                  → needs_clarification (ambiguous request)
```

---

## Step 5: Tools and Connectors

### Core tools

| Tool | What it does |
|------|-------------|
| `file` | Read, write, copy, move, delete files |
| `shell` | Execute whitelisted shell commands (24 commands) |
| `crawler` | HTTP fetch + parse (text, links, RSS, search results) |
| `time` | Return current time |
| `system_info` | Return platform/host info |
| `browser` | Validate + prepare URL for user to open |
| `browser_auto` | **Playwright**: navigate, click, type, screenshot, extract text |
| `mcp` | **MCP protocol**: call tools on external MCP servers |

### Connection-based execution

Plugins like `calendar_helper` use the connection manager:

```text
Plugin receives parsed command
  → connection_manager.execute_capability("create_calendar_event", payload)
  → Manager finds a ready driver
     ├── GoogleCalendarConnectorDriver (OAuth → real Calendar API)
     ├── TemplateConnectorDriver (generates URL link)
     └── MCP client (routes to MCP server)
  → Returns result to plugin
```

### MCP tool flow

```text
AI plans: Step(tool="mcp", params={"server": "calendar", "tool": "create_event", "arguments": {...}})
  → MCPTool.run()
  → MCPClient connects to configured MCP server (stdio transport)
  → JSON-RPC: tools/call with tool name and arguments
  → Response parsed and returned
```

---

## Step 6: Result and Summary

**Where**: `backend/ai/summarizer.py`, `backend/orchestrator/engine.py`

After all steps complete:
1. AI summarizer generates a natural language summary (if `used_ai=true`)
2. Non-AI summarizer extracts key data (if `used_ai=false`)
3. Task persisted to SQLite with status, results, logs
4. Mobile notification enqueued if applicable
5. Result returned to gateway → user

---

## Example: End-to-end flow

**Request**: "내일 오후 3시 팀 회의 캘린더에 추가해줘"

```text
1. Gateway receives POST /command
2. Intent Router:
   - Plugin rule matches: calendar_helper pattern
   - Step: {tool: "calendar_helper", params: {text: "내일 오후 3시 팀 회의"}}
   - used_ai = false
3. Risk: low (calendar read/write with known params)
4. Orchestrator:
   - calendar_helper.run() parses "내일 오후 3시 팀 회의"
   - Extracts: title="팀 회의", datetime=tomorrow 15:00
   - Calls connection_manager.execute_capability("create_calendar_event")
   - GoogleCalendarDriver creates event via Calendar API (if OAuth token exists)
   - Fallback: returns Google Calendar template link
5. Quality: sufficient (event created or link generated)
6. Summary: "내일 15시에 팀 회의 일정을 추가했습니다."
```

**Request**: "네이버에서 드럼스틱 최저가 검색해서 링크 보내줘"

```text
1. Gateway receives POST /command
2. Intent Router:
   - No exact rule match
   - AI plans: [
       Step(tool="browser_auto", params={action: "navigate", url: "https://search.shopping.naver.com/..."}),
       Step(tool="browser_auto", params={action: "extract_text"}, param_template=true),
     ]
   - used_ai = true
3. Risk: medium (browser automation)
4. Orchestrator:
   - Step 1: Playwright navigates to Naver Shopping
   - Step 2: Extracts search results text
   - Dynamic params: URL from step 1 result passed to step 2
5. Quality: AI reviews extracted content → sufficient
6. Summary: "네이버 쇼핑에서 드럼스틱 최저가 검색 결과입니다: ..."
```
