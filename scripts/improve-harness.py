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

    # Pass through the real API key so AI-first router works
    real_api_key = secret_store.get("anthropic_api_key")
    if real_api_key:
        secret_data["anthropic_api_key"] = real_api_key

    orig = {
        "config_get": config_store.get, "config_set": config_store.set,
        "config_delete": config_store.delete, "config_all": config_store.all,
        "secret_get": secret_store.get,
        "db_engine": db_session.engine, "db_session": db_session.AsyncSessionLocal,
        "orch_session": orchestrator_engine.AsyncSessionLocal,
        "router_trace": intent_router.record_task_trace,
        "orch_trace": orchestrator_engine.record_task_trace,
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

    intent_router.record_task_trace = noop
    orchestrator_engine.record_task_trace = noop

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
    cal_plugin.connection_manager.execute_capability = orig["cal_execute"]

    return results


# ---------------------------------------------------------------------------
# 3. Evaluator Agent — grades results
# ---------------------------------------------------------------------------

async def evaluate_results(commands: list[dict], results: list[dict]) -> list[dict]:
    """Codex evaluates: did the system actually help the user?"""
    evaluations = []

    # Build evaluation payload
    items = []
    for cmd, res in zip(commands, results):
        items.append({
            "id": cmd["id"],
            "command": cmd["command"],
            "status": res["status"],
            "tools": res.get("tools_used", []),
            "error": res.get("error"),
            "summary": res.get("summary", ""),
        })

    eval_prompt = f"""You are evaluating an AI assistant's responses to user commands.
For each command below, grade how well the system handled it.

Commands and results:
{json.dumps(items, ensure_ascii=False, indent=2)}

For each item, respond with:
- grade: "good" (user would be satisfied), "partial" (did something but incomplete), "bad" (failed or unhelpful)
- reason: one sentence explaining why
- fix_suggestion: if grade is "bad" or "partial", what should the system do differently? null if "good"

Respond ONLY with a JSON array:
[{{"grade": "...", "reason": "...", "fix_suggestion": "..."}}]"""

    # Write prompt to temp file for Codex
    import tempfile
    prompt_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    prompt_file.write(eval_prompt)
    prompt_file.close()

    output_file = str(RESULTS_DIR / "eval-codex-output.txt")

    try:
        proc = subprocess.run(
            ["npx", "@openai/codex", "exec", "--full-auto", "--json", "--ephemeral",
             "-o", output_file, "-"],
            stdin=open(prompt_file.name),
            capture_output=True, text=True, timeout=120,
        )
        os.unlink(prompt_file.name)

        # Read Codex output
        eval_text = ""
        if Path(output_file).exists():
            eval_text = Path(output_file).read_text().strip()
        if not eval_text:
            eval_text = proc.stdout or ""

        # Extract JSON from response
        if "```" in eval_text:
            eval_text = eval_text.split("```")[1]
            if eval_text.startswith("json"):
                eval_text = eval_text[4:]
            eval_text = eval_text.strip()

        # Try to find JSON array in text
        start = eval_text.find("[")
        end = eval_text.rfind("]")
        if start >= 0 and end > start:
            eval_text = eval_text[start:end+1]

        parsed = json.loads(eval_text)
        for j, ev in enumerate(parsed):
            if j < len(commands):
                ev["id"] = commands[j]["id"]
                ev["command"] = commands[j]["command"]
                evaluations.append(ev)

    except Exception as e:
        print(f"  WARNING: Codex evaluation failed ({e}), using heuristic")
        os.unlink(prompt_file.name) if os.path.exists(prompt_file.name) else None

    # Fill remaining with heuristic
    evaluated_ids = {e["id"] for e in evaluations}
    for cmd, res in zip(commands, results):
        if cmd["id"] not in evaluated_ids:
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
# Dual evaluation — Claude Opus + Codex, conservative merge
# ---------------------------------------------------------------------------

async def evaluate_dual(commands: list[dict], results: list[dict]) -> list[dict]:
    """Both Claude and Codex evaluate. If either says bad, it's bad."""
    print("    Codex evaluating...")
    codex_evals = await evaluate_results(commands, results)  # Codex via CLI

    print("    Claude evaluating...")
    claude_evals = await _evaluate_claude(commands, results)  # Claude via API

    merged = []
    for i, cmd in enumerate(commands):
        codex_ev = codex_evals[i] if i < len(codex_evals) else _heuristic_eval(cmd, results[i])
        claude_ev = claude_evals[i] if i < len(claude_evals) else _heuristic_eval(cmd, results[i])

        # Conservative merge: worst grade wins
        grade_order = {"bad": 0, "partial": 1, "good": 2}
        codex_grade = codex_ev.get("grade", "bad")
        claude_grade = claude_ev.get("grade", "bad")

        if grade_order.get(codex_grade, 0) <= grade_order.get(claude_grade, 0):
            final = codex_ev.copy()
        else:
            final = claude_ev.copy()

        final["codex_grade"] = codex_grade
        final["claude_grade"] = claude_grade
        final["id"] = cmd["id"]
        final["command"] = cmd["command"]
        # Use fix_suggestion from whichever said bad
        if codex_grade == "bad" and codex_ev.get("fix_suggestion"):
            final["fix_suggestion"] = codex_ev["fix_suggestion"]
        elif claude_grade == "bad" and claude_ev.get("fix_suggestion"):
            final["fix_suggestion"] = claude_ev["fix_suggestion"]
        merged.append(final)

    return merged


async def _evaluate_claude(commands: list[dict], results: list[dict]) -> list[dict]:
    """Claude API evaluation."""
    from ai.runtime import get_client, has_api_key

    if not has_api_key():
        return [_heuristic_eval(cmd, res) for cmd, res in zip(commands, results)]

    client = get_client()
    if client is None:
        return [_heuristic_eval(cmd, res) for cmd, res in zip(commands, results)]

    evaluations = []
    for i in range(0, len(commands), 5):
        batch_cmds = commands[i:i+5]
        batch_res = results[i:i+5]
        items = [{"command": c["command"], "status": r["status"], "tools": r.get("tools_used", []),
                  "error": r.get("error"), "summary": r.get("summary", "")}
                 for c, r in zip(batch_cmds, batch_res)]

        prompt = f"""Evaluate these AI assistant results. For each, give:
- grade: "good" / "partial" / "bad"
- reason: one sentence
- fix_suggestion: what to fix (null if good)

{json.dumps(items, ensure_ascii=False, indent=2)}

Respond ONLY with a JSON array."""

        try:
            msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024,
                                         messages=[{"role": "user", "content": prompt}])
            text = msg.content[0].text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                text = text[start:end+1]
            batch_evals = json.loads(text)
            for j, ev in enumerate(batch_evals):
                ev["id"] = batch_cmds[j]["id"]
                ev["command"] = batch_cmds[j]["command"]
                evaluations.append(ev)
        except Exception as e:
            for c, r in zip(batch_cmds, batch_res):
                evaluations.append(_heuristic_eval(c, r))

    return evaluations


# ---------------------------------------------------------------------------
# Main loop — big cycle + small cycle
# ---------------------------------------------------------------------------

async def run_small_cycle(commands: list[dict], round_num: int, cycle_num: int,
                          auto_fix: bool, max_small_cycles: int,
                          evaluator: str = "both") -> dict:
    """Small cycle: execute �� evaluate → fix → regression → re-execute until pass."""
    print(f"\n  --- Small cycle {cycle_num}/{max_small_cycles} ---")

    # Execute
    print(f"    Executing {len(commands)} commands...")
    results = await execute_commands(commands)
    done = sum(1 for r in results if r["status"] == "done")
    failed = sum(1 for r in results if r["status"] in ("failed", "crash"))
    print(f"    Done: {done}  Failed: {failed}  Other: {len(results)-done-failed}")

    # Evaluate based on --evaluator option
    if evaluator == "both":
        print(f"    Dual evaluation (Claude + Codex)...")
        evaluations = await evaluate_dual(commands, results)
    elif evaluator == "codex":
        print(f"    Codex evaluation...")
        evaluations = await evaluate_results(commands, results)
    else:
        print(f"    Claude evaluation...")
        evaluations = await _evaluate_claude(commands, results)
    good = sum(1 for e in evaluations if e["grade"] == "good")
    partial = sum(1 for e in evaluations if e["grade"] == "partial")
    bad = sum(1 for e in evaluations if e["grade"] == "bad")
    print(f"    Good: {good}  Partial: {partial}  Bad: {bad}")

    for ev in evaluations:
        icon = {"good": "✓", "partial": "△", "bad": "✗"}.get(ev["grade"], "?")
        c_icon = {"good": "✓", "partial": "△", "bad": "✗"}.get(ev.get("claude_grade", "?"), "?")
        x_icon = {"good": "✓", "partial": "△", "bad": "✗"}.get(ev.get("codex_grade", "?"), "?")
        print(f"    {icon} {ev['id']}: Claude={c_icon} Codex={x_icon} {ev.get('reason','')[:50]}")

    # If all good or no auto-fix, stop
    if bad == 0 or not auto_fix:
        return {"cycle": cycle_num, "good": good, "partial": partial, "bad": bad,
                "evaluations": evaluations, "results": results, "fixed": False}

    # Fix
    print(f"    Fixing {bad} failures...")
    specs = generate_fix_specs(evaluations, results, round_num)
    fix_results = []
    for spec in specs:
        spec_path = SPECS_DIR / f"{spec['id']}.json"
        with open(spec_path, "w") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        fix_result = run_dev_harness(str(spec_path))
        fix_results.append({"spec_id": spec["id"], "exit_code": fix_result["exit_code"]})
        status = "✓" if fix_result["exit_code"] == 0 else "✗"
        print(f"      {status} {spec['id']}")

    # Regression
    print(f"    Regression check...")
    regression = run_regression()
    print(f"    Regression: {regression['pass_rate']}")

    return {"cycle": cycle_num, "good": good, "partial": partial, "bad": bad,
            "evaluations": evaluations, "results": results, "fixed": True,
            "fix_results": fix_results, "regression": regression["pass_rate"]}


async def run_big_cycle(round_num: int, num_commands: int, dry_run: bool,
                        auto_fix: bool, max_small_cycles: int,
                        evaluator: str = "both") -> dict:
    """Big cycle: generate commands → small cycles until all pass or max reached."""
    print(f"\n{'='*60}")
    print(f"  BIG CYCLE {round_num}")
    print(f"{'='*60}")

    # Generate commands (once per big cycle)
    print(f"\n  Generating {num_commands} user commands...")
    commands = await generate_commands(num_commands)
    if dry_run:
        for cmd in commands:
            print(f"    {cmd['id']}: [{cmd.get('difficulty','?')}] {cmd['command']}")
        return {"round": round_num, "status": "dry_run"}

    for cmd in commands:
        print(f"    {cmd['id']}: {cmd['command'][:50]}")

    # Small cycles — re-run same commands until pass
    small_results = []
    for cycle_num in range(1, max_small_cycles + 1):
        result = await run_small_cycle(commands, round_num, cycle_num, auto_fix, max_small_cycles, evaluator)
        small_results.append(result)

        if result["bad"] == 0:
            print(f"\n  All commands pass after {cycle_num} cycle(s)!")
            break
        if not result.get("fixed"):
            print(f"\n  {result['bad']} failures remain (auto-fix {'disabled' if not auto_fix else 'exhausted'})")
            break

    # Final score
    last = small_results[-1]
    total = last["good"] + last["partial"] + last["bad"]
    score = last["good"]

    # Save report
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {
        "round": round_num,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commands": commands,
        "small_cycles": small_results,
        "final_score": f"{score}/{total}",
    }
    report_path = RESULTS_DIR / f"improve-round-{round_num:02d}-{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Report: {report_path}")
    print(f"  Final score: {score}/{total} good ({score/max(total,1)*100:.0f}%)")
    print(f"  Small cycles used: {len(small_results)}")

    return report


async def main_async(args):
    for round_num in range(1, args.rounds + 1):
        await run_big_cycle(round_num, args.commands, args.dry_run,
                            args.auto_fix, args.max_small_cycles, args.evaluator)
        if args.dry_run:
            break

    print(f"\n{'='*60}")
    print(f"  IMPROVE HARNESS COMPLETE — {args.rounds} big cycle(s)")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Improve harness — AI discovers and fixes product gaps")
    parser.add_argument("--rounds", type=int, default=1, help="Number of big cycles (new commands each)")
    parser.add_argument("--commands", type=int, default=10, help="Commands per big cycle")
    parser.add_argument("--max-small-cycles", type=int, default=3, help="Max fix-retry cycles per big cycle")
    parser.add_argument("--no-fix", action="store_true", help="Skip auto-fix (evaluate only)")
    parser.add_argument("--dry-run", action="store_true", help="Generate commands only, don't execute")
    parser.add_argument("--evaluator", default="both", choices=["both", "codex", "claude"],
                        help="Who evaluates: both (default), codex only, claude only")
    args = parser.parse_args()
    args.auto_fix = not args.no_fix
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
