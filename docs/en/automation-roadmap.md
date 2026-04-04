# Automation Roadmap

## Vision

The goal is a system where **every action the user wants can be executed fully automatically**,
without requiring approval or clarification for common tasks.

The reference model is fully-automated agent systems (like Open Interpreter / OpenClaw style execution),
where the system executes multi-step plans end-to-end without interrupting the user.
The key difference here: we get there by replacing AI-executed paths with
faster, cheaper non-AI automation — not by making AI more capable.

---

## Current State (April 2026)

```text
Coverage by execution path:

Rule-based (non-AI)       ████████░░  ~65% of common requests
Plugin-based (non-AI)     ████░░░░░░  ~30% of plugin-matched requests
AI fallback               ░░░░░░░░░░  still required for most open-ended requests
Full auto (no approval)   ████░░░░░░  works for low-risk read operations
```

Key limitations today:
- Most tasks still require human approval at `medium` / `high` risk level
- AI is still needed for ambiguous requests (even simple ones)
- Scheduler is limited — no conditional execution, no chaining
- External actions (calendar write, message send) require connector setup

---

## Phase 1 — Expand non-AI rule coverage (Q2 2026)

**Goal**: reduce the % of requests that reach the AI fallback path.

### What to build

| Task | How |
|------|-----|
| Add 20+ new rules to `rules.yaml` | Cover frequent ambiguous phrases by mapping them to existing plugins |
| Add intent normalization for time expressions | "내일", "다음주 월요일", "오후 3시" → ISO datetime without AI |
| Add intent normalization for contact references | "민수에게", "팀장한테" → extract recipient name |
| Expand `shopping_helper` rules | Cover more purchase/search phrases |
| Expand `calendar_helper` rules | Cover recurring events, multi-day events |
| Expand `reminder_helper` rules | Cover natural time expressions |
| Add `file_helper` plugin | Read/write/list files via natural language without shell |

**Success metric**: AI fallback rate drops below 20% of all routed requests.

---

## Phase 2 — Context-aware auto-approval (Q3 2026)

**Goal**: eliminate manual approval for safe, predictable actions.

### What to build

| Task | How |
|------|-----|
| Approval policy engine | Define per-tool rules: "calendar_helper write is auto-approved for known calendars" |
| User trust history | Track which tools the user has approved before; auto-approve repeat patterns |
| Risk level refinement | Downgrade risk for well-understood plugin operations (calendar add, reminder set) |
| Dry-run mode | Show the user what will happen before executing, then auto-execute after N seconds |
| Approval bypass for scheduled tasks | Recurring tasks auto-approved after first human approval |

**Success metric**: >80% of daily tasks execute without a human approval prompt.

---

## Phase 3 — Multi-step autonomous execution (Q4 2026)

**Goal**: the system can execute multi-step plans end-to-end without interrupting the user.

### What to build

| Task | How |
|------|-----|
| Task graph executor | Execute steps in parallel where possible; handle conditional branches |
| AI-to-rule absorption | When AI successfully handles a request type N times, auto-generate a rule/plugin for it |
| Connector completions | Real calendar write, real message send, real email via connected accounts |
| Proactive triggers | System initiates tasks based on time, location, or external events |
| Self-healing retry | Automatically retries failed steps with adjusted params before surfacing to user |

**Success metric**: the user can describe a multi-step goal ("set up my morning routine") and the system executes all steps without interruption.

---

## Phase 4 — Platform autonomy (2027+)

**Goal**: the system manages its own automation portfolio.

### What to build

| Task | How |
|------|-----|
| Automation learning loop | Observe what the user does repeatedly → propose new rules → get one-time approval |
| Plugin marketplace | Install community plugins via a single approval |
| MCP runtime integration | Connect external tools and APIs through the MCP protocol |
| Cross-device coordination | Mobile triggers → local PC executes → result delivered back to mobile |
| Long-running background agents | Tasks that run over hours/days with progress tracking |

**Success metric**: the system proactively handles 50%+ of user's daily automation needs
without being explicitly asked.

---

## Design Principle: AI Path Absorption

Every time AI successfully handles a request, we ask:
> "Can this path be replaced with a non-AI rule or plugin?"

The absorption cycle:

```text
1. AI handles new request type
2. Track frequency over time
3. When pattern is clear: write a rule or plugin
4. Route future identical requests through the non-AI path
5. AI call count for this pattern → 0
```

This is the only sustainable way to keep AI costs low while expanding coverage.
The goal is never "remove AI" but rather "absorb what AI proved works into automation."

---

## What Full Automation Does NOT Mean

- It does not mean removing approval for dangerous or irreversible actions.
- It does not mean the AI makes all decisions.
- It does not mean the user loses visibility into what the system is doing.

Full automation means: **routine, predictable, low-risk tasks complete without friction**.
Dangerous, novel, or high-stakes tasks still surface for human review.
