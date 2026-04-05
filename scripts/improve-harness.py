#!/usr/bin/env python3
"""Improve harness: AI agents loop to discover and fix product gaps.

Loop:
  1. User agent — generates realistic commands a human would ask an AI assistant
  2. Execute — runs each command through the live pipeline
  3. Evaluator agent — grades each result (did it actually help the user?)
  4. Developer agent — implements fixes via dev-harness for failed items
  5. Regression — runs eval-harness to ensure nothing broke
  6. → repeat

Usage:
    python3 scripts/improve-harness.py                     # 1 round, 10 commands
    python3 scripts/improve-harness.py --rounds 5          # 5 rounds
    python3 scripts/improve-harness.py --commands 20       # 20 commands per round
    python3 scripts/improve-harness.py --dry-run           # show generated commands only
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
RESULTS_DIR = PROJECT_ROOT / "scripts" / "harness-results"
SPECS_DIR = PROJECT_ROOT / "scripts" / "harness-specs"
sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# 1. User Agent — generates realistic commands
# ---------------------------------------------------------------------------

async def generate_commands(count: int) -> list[dict]:
    """AI generates commands a real user would ask an AI assistant."""
    from ai.runtime import get_client, has_api_key

    if not has_api_key():
        return _fallback_commands(count)

    client = get_client()
    if client is None:
        return _fallback_commands(count)

    prompt = f"""You are simulating a real user of an AI personal assistant app.
Generate exactly {count} commands that a real person would naturally ask.

Mix these categories:
- Daily life: weather, schedule, reminders, alarms
- Information: news, search, translation, summarization
- Productivity: email, calendar, file management, notes
- Shopping: price comparison, product search, ordering
- Navigation: directions, restaurant recommendations
- Multi-step: "do X then Y", "search and summarize", "check and notify"
- Casual: greetings, jokes, vague requests

Rules:
- Write in Korean (70%) and English (30%)
- Be natural — include typos, casual speech, abbreviations
- Include some ambiguous or hard requests that might fail
- Include some multi-step requests that chain actions
- Each command should be something a real person would actually say

Respond with a JSON array of objects:
[{{"command": "...", "category": "...", "difficulty": "easy|medium|hard"}}]

Only output the JSON array, nothing else."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        commands = json.loads(text)
        for i, cmd in enumerate(commands):
            cmd["id"] = f"user_{i:03d}"
        return commands[:count]
    except Exception as e:
        print(f"  WARNING: AI command generation failed ({e}), using fallback")
        return _fallback_commands(count)


def _fallback_commands(count: int) -> list[dict]:
    """Deterministic fallback when AI is unavailable."""
    pool = [
        {"command": "내일 오후 2시에 치과 예약 캘린더에 추가해줘", "category": "calendar", "difficulty": "easy"},
        {"command": "오늘 날씨 어때?", "category": "weather", "difficulty": "easy"},
        {"command": "https://news.hada.io 크롤링해서 요약해줘", "category": "multi_step", "difficulty": "hard"},
        {"command": "네이버에서 에어팟 최저가 찾아줘", "category": "shopping", "difficulty": "medium"},
        {"command": "지금 몇 시야", "category": "time", "difficulty": "easy"},
        {"command": "강남역 맛집 추천해줘", "category": "navigation", "difficulty": "medium"},
        {"command": "제주도 항공권 알아봐줘", "category": "travel", "difficulty": "medium"},
        {"command": "send an email to test@example.com about the meeting", "category": "email", "difficulty": "medium"},
        {"command": "translate 안녕하세요 to English", "category": "translation", "difficulty": "easy"},
        {"command": "매일 아침 9시에 뉴스 요약해서 알림 보내줘", "category": "schedule", "difficulty": "hard"},
        {"command": "/tmp 폴더에 뭐가 있어?", "category": "file", "difficulty": "easy"},
        {"command": "오늘 일정 정리해줘", "category": "productivity", "difficulty": "medium"},
        {"command": "유튜브에서 코딩 강의 찾아줘", "category": "search", "difficulty": "medium"},
        {"command": "ㅋㅋ 심심해", "category": "casual", "difficulty": "hard"},
        {"command": "민수한테 오늘 10분 늦는다고 문자 초안 써줘", "category": "draft", "difficulty": "medium"},
    ]
    for i, cmd in enumerate(pool):
        cmd["id"] = f"user_{i:03d}"
    return pool[:count]


# ---------------------------------------------------------------------------
# 2. Execute — run commands through the pipeline
# ---------------------------------------------------------------------------

async def execute_commands(commands: list[dict]) -> list[dict]:
    """Run each command through route() → run()."""
    from config.secret_store import secret_store
    from config.store import config_store
    from connections.base import ConnectionExecutionResult
    from db import session as db_session
    from intent import router as intent_router
    from orchestrator import engine as orchestrator_engine
    from plugins import load_plugins
    from tools import registry
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    import tempfile

    # Setup (same pattern as eval-harness)
    tmpdir = tempfile.mkdtemp()
    engine = create_async_engine(f"sqlite+aiosqlite:///{os.path.join(tmpdir, 'improve.db')}", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    config_data = {
        "custom_commands": [],
        "granted_permissions": [
            "external_connection_access", "calendar_event_creation",
            "email_send_access", "mcp_runtime_access", "shopping_checkout_assist",
        ],
    }
    secret_data = {"google_oauth_tokens:google_calendar": '{"access_token":"fake"}'}

    orig = {
        "config_get": config_store.get, "config_set": config_store.set,
        "config_delete": config_store.delete, "config_all": config_store.all,
        "secret_get": secret_store.get,
        "db_engine": db_session.engine, "db_session": db_session.AsyncSessionLocal,
        "orch_session": orchestrator_engine.AsyncSessionLocal,
        "router_trace": intent_router.record_task_trace,
        "orch_trace": orchestrator_engine.record_task_trace,
        "orch_continue": orchestrator_engine.ai_agent.continue_task,
        "summarize": orchestrator_engine.summarizer.summarize,
        "review": orchestrator_engine.ai_reviewer.review,
    }

    config_store.get = lambda key, default=None: config_data.get(key, default)
    config_store.set = lambda key, value: config_data.__setitem__(key, value)
    config_store.delete = lambda key: config_data.pop(key, None)
    config_store.all = lambda: dict(config_data)
    secret_store.get = lambda key: secret_data.get(key)
    db_session.engine = engine
    db_session.AsyncSessionLocal = session_maker
    orchestrator_engine.AsyncSessionLocal = session_maker
    await db_session.init_db()

    async def noop(*a, **kw): return None
    async def fake_summarize(cmd, results, *, allow_ai=True): return "done"

    intent_router.record_task_trace = noop
    orchestrator_engine.record_task_trace = noop
    orchestrator_engine.ai_agent.continue_task = noop
    orchestrator_engine.summarizer.summarize = fake_summarize
    orchestrator_engine.ai_reviewer.review = noop

    registry.load_default_tools()
    load_plugins()
    intent_router._rules = []

    # Mock calendar connector
    from plugins.calendar_helper import plugin as cal_plugin
    orig["cal_execute"] = cal_plugin.connection_manager.execute_capability

    async def fake_cal(capability, payload):
        return ConnectionExecutionResult(
            success=True, handled=True,
            data={"calendar_event_id": "mock", "title": payload.get("title", "")},
        )
    cal_plugin.connection_manager.execute_capability = fake_cal

    # Execute
    results = []
    for cmd in commands:
        start = time.monotonic()
        try:
            task = await intent_router.route(cmd["command"])
            if task.steps and task.status in ("pending", "running"):
                task = await orchestrator_engine.run(task, persist=False)
            elif task.status == "pending" and not task.steps:
                task.status = "failed"

            results.append({
                "id": cmd["id"],
                "command": cmd["command"],
                "category": cmd.get("category", "unknown"),
                "difficulty": cmd.get("difficulty", "unknown"),
                "status": task.status,
                "tools_used": [s.tool for s in task.steps],
                "used_ai": task.used_ai,
                "error": task.error,
                "summary": task.summary,
                "step_count": len(task.steps),
                "result_count": len(task.results),
                "elapsed_ms": round((time.monotonic() - start) * 1000),
            })
        except Exception as e:
            results.append({
                "id": cmd["id"],
                "command": cmd["command"],
                "category": cmd.get("category", "unknown"),
                "status": "crash",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "elapsed_ms": round((time.monotonic() - start) * 1000),
            })

    # Teardown
    config_store.get = orig["config_get"]
    config_store.set = orig["config_set"]
    config_store.delete = orig["config_delete"]
    config_store.all = orig["config_all"]
    secret_store.get = orig["secret_get"]
    db_session.engine = orig["db_engine"]
    db_session.AsyncSessionLocal = orig["db_session"]
    orchestrator_engine.AsyncSessionLocal = orig["orch_session"]
    intent_router.record_task_trace = orig["router_trace"]
    orchestrator_engine.record_task_trace = orig["orch_trace"]
    orchestrator_engine.ai_agent.continue_task = orig["orch_continue"]
    orchestrator_engine.summarizer.summarize = orig["summarize"]
    orchestrator_engine.ai_reviewer.review = orig["review"]
    cal_plugin.connection_manager.execute_capability = orig["cal_execute"]

    return results


# ---------------------------------------------------------------------------
# 3. Evaluator Agent — grades results
# ---------------------------------------------------------------------------

async def evaluate_results(commands: list[dict], results: list[dict]) -> list[dict]:
    """AI evaluates: did the system actually help the user?"""
    from ai.runtime import get_client, has_api_key

    evaluations = []

    if not has_api_key():
        for cmd, res in zip(commands, results):
            evaluations.append(_heuristic_eval(cmd, res))
        return evaluations

    client = get_client()
    if client is None:
        for cmd, res in zip(commands, results):
            evaluations.append(_heuristic_eval(cmd, res))
        return evaluations

    # Batch evaluate (5 at a time to save tokens)
    for i in range(0, len(commands), 5):
        batch_cmds = commands[i:i+5]
        batch_res = results[i:i+5]

        items = []
        for cmd, res in zip(batch_cmds, batch_res):
            items.append({
                "command": cmd["command"],
                "status": res["status"],
                "tools": res.get("tools_used", []),
                "error": res.get("error"),
                "summary": res.get("summary", ""),
            })

        prompt = f"""You are evaluating an AI assistant's responses to user commands.
For each command, grade how well the system handled it.

Commands and results:
{json.dumps(items, ensure_ascii=False, indent=2)}

For each item, respond with:
- grade: "good" (user would be satisfied), "partial" (did something but incomplete), "bad" (failed or unhelpful)
- reason: one sentence explaining why
- fix_suggestion: if grade is "bad" or "partial", what should the system do differently? null if "good"

Respond with a JSON array:
[{{"grade": "...", "reason": "...", "fix_suggestion": "..."}}]

Only output the JSON array."""

        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            batch_evals = json.loads(text)
            for j, ev in enumerate(batch_evals):
                ev["id"] = batch_cmds[j]["id"]
                ev["command"] = batch_cmds[j]["command"]
                evaluations.append(ev)
        except Exception as e:
            print(f"  WARNING: AI evaluation failed ({e}), using heuristic")
            for cmd, res in zip(batch_cmds, batch_res):
                evaluations.append(_heuristic_eval(cmd, res))

    return evaluations


def _heuristic_eval(cmd: dict, res: dict) -> dict:
    """Fallback evaluation without AI."""
    status = res.get("status", "unknown")
    if status == "done" and not res.get("error"):
        return {"id": cmd["id"], "command": cmd["command"], "grade": "good", "reason": "completed successfully", "fix_suggestion": None}
    if status == "crash":
        return {"id": cmd["id"], "command": cmd["command"], "grade": "bad", "reason": f"crashed: {res.get('error','')[:80]}", "fix_suggestion": "fix crash"}
    if status == "failed":
        return {"id": cmd["id"], "command": cmd["command"], "grade": "bad", "reason": f"failed: {res.get('error','')[:80]}", "fix_suggestion": "handle this command type"}
    if status in ("needs_setup", "needs_clarification", "approval_required"):
        return {"id": cmd["id"], "command": cmd["command"], "grade": "partial", "reason": f"status: {status}", "fix_suggestion": None}
    return {"id": cmd["id"], "command": cmd["command"], "grade": "partial", "reason": f"unclear status: {status}", "fix_suggestion": None}


# ---------------------------------------------------------------------------
# 4. Developer Agent — generates fix specs
# ---------------------------------------------------------------------------

def generate_fix_specs(evaluations: list[dict], results: list[dict], round_num: int) -> list[dict]:
    """Generate dev-harness specs for bad evaluations."""
    specs = []
    bad_evals = [e for e in evaluations if e["grade"] == "bad" and e.get("fix_suggestion")]

    for i, ev in enumerate(bad_evals[:5]):  # max 5 fixes per round
        res = next((r for r in results if r["id"] == ev["id"]), {})
        spec = {
            "id": f"improve-r{round_num:02d}-fix-{i:02d}",
            "title": f"Fix: {ev['command'][:40]}",
            "goal": f"Command '{ev['command']}' failed with: {ev['reason']}. Suggestion: {ev['fix_suggestion']}",
            "implementation_locations": {"new_files": [], "modified_files": []},
            "test_requirements": [{"case": f"route and execute '{ev['command'][:30]}...'", "expected": "status=done, no error"}],
            "constraints": ["Do not break existing tests", "Follow AGENTS.md conventions"],
            "branch_name": f"improve/r{round_num:02d}-fix-{i:02d}",
            "base_branch": "feat/phase0-ai-capabilities",
            "max_retries": 2,
            "codex_model": "",
            "test_command": "cd backend && python3 -m unittest discover -s tests -v",
            "test_focus_command": "cd backend && python3 -m unittest discover -s tests -v",
        }
        specs.append(spec)
    return specs


def run_dev_harness(spec_path: str) -> dict:
    """Run the dev-harness for a spec."""
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "dev-harness.py"),
         "--spec", spec_path, "--no-review"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=600,
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout[-500:], "stderr": proc.stderr[-500:]}


# ---------------------------------------------------------------------------
# 5. Regression — run eval-harness
# ---------------------------------------------------------------------------

def run_regression() -> dict:
    """Run eval-harness to check nothing broke."""
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "eval-harness.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=120,
    )
    output = proc.stdout + proc.stderr
    pass_rate = "?"
    for line in output.splitlines():
        if "Pass rate:" in line:
            pass_rate = line.split("Pass rate:")[1].strip()
    return {"exit_code": proc.returncode, "pass_rate": pass_rate, "output": output[-500:]}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_round(round_num: int, num_commands: int, dry_run: bool, auto_fix: bool) -> dict:
    print(f"\n{'='*60}")
    print(f"  ROUND {round_num}")
    print(f"{'='*60}")

    # 1. Generate commands
    print(f"\n  [1/5] Generating {num_commands} user commands...")
    commands = await generate_commands(num_commands)
    if dry_run:
        for cmd in commands:
            print(f"    {cmd['id']}: [{cmd.get('difficulty','?')}] {cmd['command']}")
        return {"round": round_num, "status": "dry_run", "commands": len(commands)}

    for cmd in commands:
        print(f"    {cmd['id']}: {cmd['command'][:50]}")

    # 2. Execute
    print(f"\n  [2/5] Executing {len(commands)} commands...")
    results = await execute_commands(commands)
    done = sum(1 for r in results if r["status"] == "done")
    failed = sum(1 for r in results if r["status"] in ("failed", "crash"))
    other = len(results) - done - failed
    print(f"    Done: {done}  Failed: {failed}  Other: {other}")

    # 3. Evaluate
    print(f"\n  [3/5] Evaluating results...")
    evaluations = await evaluate_results(commands, results)
    good = sum(1 for e in evaluations if e["grade"] == "good")
    partial = sum(1 for e in evaluations if e["grade"] == "partial")
    bad = sum(1 for e in evaluations if e["grade"] == "bad")
    print(f"    Good: {good}  Partial: {partial}  Bad: {bad}")

    for ev in evaluations:
        icon = {"good": "✓", "partial": "△", "bad": "✗"}.get(ev["grade"], "?")
        print(f"    {icon} {ev['id']}: {ev['reason'][:60]}")

    # 4. Fix (if auto_fix)
    fix_results = []
    if auto_fix and bad > 0:
        print(f"\n  [4/5] Generating fixes for {bad} failures...")
        specs = generate_fix_specs(evaluations, results, round_num)
        for spec in specs:
            spec_path = SPECS_DIR / f"{spec['id']}.json"
            with open(spec_path, "w") as f:
                json.dump(spec, f, indent=2, ensure_ascii=False)
            print(f"    Running dev-harness: {spec['id']}...")
            fix_result = run_dev_harness(str(spec_path))
            fix_results.append({"spec_id": spec["id"], "exit_code": fix_result["exit_code"]})
            status = "done" if fix_result["exit_code"] == 0 else "failed"
            print(f"    → {status}")
    else:
        print(f"\n  [4/5] {'No fixes needed' if bad == 0 else 'Auto-fix disabled (use --auto-fix)'}")

    # 5. Regression
    print(f"\n  [5/5] Running regression check...")
    regression = run_regression()
    print(f"    Regression pass rate: {regression['pass_rate']}")

    # Save report
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {
        "round": round_num,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commands_generated": len(commands),
        "execution": {"done": done, "failed": failed, "other": other},
        "evaluation": {"good": good, "partial": partial, "bad": bad},
        "fixes_attempted": len(fix_results),
        "fixes_succeeded": sum(1 for f in fix_results if f["exit_code"] == 0),
        "regression_pass_rate": regression["pass_rate"],
        "commands": commands,
        "results": results,
        "evaluations": evaluations,
        "fix_results": fix_results,
    }
    report_path = RESULTS_DIR / f"improve-round-{round_num:02d}-{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Report: {report_path}")
    print(f"  Score: {good}/{len(commands)} good ({good/max(len(commands),1)*100:.0f}%)")

    return report


async def main_async(args):
    for round_num in range(1, args.rounds + 1):
        report = await run_round(round_num, args.commands, args.dry_run, args.auto_fix)
        if args.dry_run:
            break

    print(f"\n{'='*60}")
    print(f"  IMPROVE HARNESS COMPLETE — {args.rounds} round(s)")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Improve harness — AI discovers and fixes product gaps")
    parser.add_argument("--rounds", type=int, default=1, help="Number of improvement rounds")
    parser.add_argument("--commands", type=int, default=10, help="Commands per round")
    parser.add_argument("--auto-fix", action="store_true", help="Auto-generate and run fix specs")
    parser.add_argument("--dry-run", action="store_true", help="Generate commands only, don't execute")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
