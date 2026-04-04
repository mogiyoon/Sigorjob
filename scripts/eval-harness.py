#!/usr/bin/env python3
"""Eval harness: runs 50+ scenarios against the live pipeline, grades results, detects gaps.

Usage:
    python3 scripts/eval-harness.py
    python3 scripts/eval-harness.py --with-ai
    python3 scripts/eval-harness.py --category calendar
    python3 scripts/eval-harness.py --generate-specs
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
RESULTS_DIR = PROJECT_ROOT / "scripts" / "harness-results"
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    # time_system
    {"id": "time_01", "command": "지금 몇 시", "category": "time_system", "expected_tool": "time", "expected_status": "done"},
    {"id": "time_02", "command": "현재 시간", "category": "time_system", "expected_tool": "time", "expected_status": "done"},
    {"id": "time_03", "command": "what time is it", "category": "time_system", "expected_tool": "time", "expected_status": "done"},
    {"id": "time_04", "command": "오늘 날짜", "category": "time_system", "expected_tool": "time", "expected_status": "done"},
    {"id": "time_05", "command": "시스템 정보", "category": "time_system", "expected_tool": "system_info", "expected_status": "done"},
    {"id": "time_06", "command": "system info", "category": "time_system", "expected_tool": "system_info", "expected_status": "done"},

    # shell
    {"id": "shell_01", "command": "/tmp 폴더 목록 보여줘", "category": "shell", "expected_tool": "shell", "expected_status": "done"},
    {"id": "shell_02", "command": "pwd", "category": "shell", "expected_tool": "shell", "expected_status": "done"},

    # file_operations
    {"id": "file_01", "command": "/tmp/eval-test.txt 파일 읽어줘", "category": "file_operations", "expected_tool": "file", "expected_status": "done"},
    {"id": "file_02", "command": "/tmp/eval-write.txt 파일에 hello world 써줘", "category": "file_operations", "expected_tool": "file", "expected_status": "done"},
    {"id": "file_03", "command": "/tmp/eval-a.txt 를 /tmp/eval-b.txt 로 복사해줘", "category": "file_operations", "expected_tool": "file", "expected_status": "done"},
    {"id": "file_04", "command": "/tmp/eval-del.txt 파일 삭제해줘", "category": "file_operations", "expected_tool": "file", "expected_status": "done"},

    # web_crawl
    {"id": "crawl_01", "command": "https://example.com 읽어와", "category": "web_crawl", "expected_tool": "crawler", "expected_status": "done"},
    {"id": "crawl_02", "command": "https://example.com 크롤링해줘", "category": "web_crawl", "expected_tool": "crawler", "expected_status": "done"},

    # open_url
    {"id": "url_01", "command": "네이버 열어줘", "category": "open_url", "expected_tool": "browser", "expected_status": "done"},
    {"id": "url_02", "command": "유튜브 열어줘", "category": "open_url", "expected_tool": "browser", "expected_status": "done"},
    {"id": "url_03", "command": "mogiyoon@gmail.com으로 메일 보내줘", "category": "open_url", "expected_tool": "browser", "expected_status": "done"},
    {"id": "url_04", "command": "성수 카페 추천해줘", "category": "open_url", "expected_tool": "browser", "expected_status": "done"},

    # shopping
    {"id": "shop_01", "command": "네이버에서 드럼 스틱 사줘", "category": "shopping", "expected_tool": "shopping_helper", "expected_status": "done"},
    {"id": "shop_02", "command": "네이버에서 최저가 드럼스틱 찾아줘", "category": "shopping", "expected_tool": "shopping_helper", "expected_status": "done"},

    # calendar
    {"id": "cal_01", "command": "내일 오후 3시 팀 회의 캘린더에 일정 추가해줘", "category": "calendar", "expected_tool": "calendar_helper", "expected_status": "done"},
    {"id": "cal_02", "command": "5월 5일 오전 10시 치과 예약 일정 넣어줘", "category": "calendar", "expected_tool": "calendar_helper", "expected_status": "done"},

    # reminder_schedule
    {"id": "remind_01", "command": "아침 8시에 기상청에서 스크롤한 거 바탕으로 날씨 알림 보내줘", "category": "reminder_schedule", "expected_tool": "weather_alert_helper", "expected_status": "done"},
    {"id": "remind_02", "command": "8시 15분에 오늘 일정 요약해서 알람으로 보내줘", "category": "reminder_schedule", "expected_tool": "reminder_helper", "expected_status": "done"},

    # service_search
    {"id": "svc_01", "command": "유튜브에서 드럼 연습 영상 찾아줘", "category": "service_search", "expected_tool": "browser", "expected_status": "done"},
    {"id": "svc_02", "command": "네이버 지도에서 강남 맛집 찾아줘", "category": "service_search", "expected_tool": "browser", "expected_status": "done"},

    # route_navigation
    {"id": "route_01", "command": "성수에서 강남역까지 길찾아줘", "category": "route_navigation", "expected_tool": "route_helper", "expected_status": "done"},

    # translation
    {"id": "trans_01", "command": "이 문장 영어로 번역해줘", "category": "translation", "expected_tool": "translation_helper", "expected_status": "done", "requires_ai": True},

    # multi_step (requires AI for planning)
    {"id": "multi_01", "command": "https://example.com 읽어와서 요약해줘", "category": "multi_step", "expected_tool": "crawler", "expected_status": "done", "requires_ai": True},
    {"id": "multi_02", "command": "뉴스 검색해서 요약해줘", "category": "multi_step", "expected_tool": None, "expected_status": "done", "requires_ai": True},

    # ambiguous
    {"id": "amb_01", "command": "뭔가 해줘", "category": "ambiguous", "expected_tool": None, "expected_status": "failed"},
    {"id": "amb_02", "command": "ㅋㅋㅋ", "category": "ambiguous", "expected_tool": None, "expected_status": "failed"},

    # english
    {"id": "en_01", "command": "show me the current time", "category": "english", "expected_tool": "time", "expected_status": "done"},
    {"id": "en_02", "command": "open google", "category": "english", "expected_tool": "browser", "expected_status": "done", "requires_ai": True},

    # edge_cases
    {"id": "edge_01", "command": "", "category": "edge_cases", "expected_tool": None, "expected_status": "failed"},
    {"id": "edge_02", "command": "   ", "category": "edge_cases", "expected_tool": None, "expected_status": "failed"},

    # plugin routes
    {"id": "plug_01", "command": "성수 맛집 예약해줘", "category": "plugin_routes", "expected_tool": "reservation_helper", "expected_status": "done"},
    {"id": "plug_02", "command": "성수 피자 배달시켜줘", "category": "plugin_routes", "expected_tool": "delivery_helper", "expected_status": "done"},
    {"id": "plug_03", "command": "민수에게 메시지 초안 써줘 오늘 10분 늦을 것 같아", "category": "plugin_routes", "expected_tool": "draft_helper", "expected_status": "done"},
    {"id": "plug_04", "command": "010-1234-5678로 전화해줘", "category": "plugin_routes", "expected_tool": "communication_helper", "expected_status": "done"},
    {"id": "plug_05", "command": "제주도 항공권 찾아줘", "category": "plugin_routes", "expected_tool": "travel_helper", "expected_status": "done"},
]


# ---------------------------------------------------------------------------
# Runtime setup (mirrors test_e2e_smoke.py)
# ---------------------------------------------------------------------------

_originals = {}


async def setup_runtime(with_ai: bool = False):
    from config.secret_store import secret_store
    from config.store import config_store
    from db import session as db_session
    from intent import router as intent_router
    from orchestrator import engine as orchestrator_engine
    from plugins import load_plugins
    from tools import registry
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "eval.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    config_data = {
        "custom_commands": [],
        "granted_permissions": [
            "external_connection_access", "calendar_event_creation",
            "email_send_access", "mcp_runtime_access",
            "shopping_checkout_assist",
        ],
    }
    secret_data = {"google_oauth_tokens:google_calendar": '{"access_token":"fake"}'}

    # Save originals
    _originals.update({
        "config_get": config_store.get, "config_set": config_store.set,
        "config_delete": config_store.delete, "config_all": config_store.all,
        "secret_get": secret_store.get,
        "db_engine": db_session.engine, "db_session": db_session.AsyncSessionLocal,
        "orch_session": orchestrator_engine.AsyncSessionLocal,
        "router_trace": intent_router.record_task_trace,
        "orch_trace": orchestrator_engine.record_task_trace,
        "has_api_key": intent_router.has_api_key,
        "ai_plan": intent_router.ai_agent.plan,
        "ai_clarify": intent_router.ai_agent.request_clarification,
        "ai_auto": intent_router.ai_agent.automation_assist,
        "ai_browser": intent_router.ai_agent.browser_assist,
        "orch_continue": orchestrator_engine.ai_agent.continue_task,
        "summarize": orchestrator_engine.summarizer.summarize,
        "review": orchestrator_engine.ai_reviewer.review,
    })

    # Mock
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
    intent_router.has_api_key = lambda: with_ai
    if not with_ai:
        intent_router.ai_agent.request_clarification = noop
        intent_router.ai_agent.automation_assist = noop
        intent_router.ai_agent.browser_assist = noop
    orchestrator_engine.ai_agent.continue_task = noop
    orchestrator_engine.summarizer.summarize = fake_summarize
    orchestrator_engine.ai_reviewer.review = noop

    registry.load_default_tools()
    load_plugins()
    intent_router._rules = []

    # Mock calendar connector
    from plugins.calendar_helper import plugin as cal_plugin
    _originals["cal_execute"] = cal_plugin.connection_manager.execute_capability
    from connections.base import ConnectionExecutionResult

    async def fake_cal(capability, payload):
        return ConnectionExecutionResult(
            success=True, handled=True,
            data={"calendar_event_id": "mock", "title": payload.get("title", ""), "dates": payload.get("dates", "")},
        )
    cal_plugin.connection_manager.execute_capability = fake_cal

    # Pre-create test files
    Path("/tmp/eval-test.txt").write_text("eval test content")
    Path("/tmp/eval-a.txt").write_text("copy source")
    Path("/tmp/eval-del.txt").write_text("to delete")


async def teardown_runtime():
    from config.secret_store import secret_store
    from config.store import config_store
    from db import session as db_session
    from intent import router as intent_router
    from orchestrator import engine as orchestrator_engine
    from plugins.calendar_helper import plugin as cal_plugin

    config_store.get = _originals["config_get"]
    config_store.set = _originals["config_set"]
    config_store.delete = _originals["config_delete"]
    config_store.all = _originals["config_all"]
    secret_store.get = _originals["secret_get"]
    db_session.engine = _originals["db_engine"]
    db_session.AsyncSessionLocal = _originals["db_session"]
    orchestrator_engine.AsyncSessionLocal = _originals["orch_session"]
    intent_router.record_task_trace = _originals["router_trace"]
    orchestrator_engine.record_task_trace = _originals["orch_trace"]
    intent_router.has_api_key = _originals["has_api_key"]
    intent_router.ai_agent.plan = _originals["ai_plan"]
    intent_router.ai_agent.request_clarification = _originals["ai_clarify"]
    intent_router.ai_agent.automation_assist = _originals["ai_auto"]
    intent_router.ai_agent.browser_assist = _originals["ai_browser"]
    orchestrator_engine.ai_agent.continue_task = _originals["orch_continue"]
    orchestrator_engine.summarizer.summarize = _originals["summarize"]
    orchestrator_engine.ai_reviewer.review = _originals["review"]
    cal_plugin.connection_manager.execute_capability = _originals["cal_execute"]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

async def execute_scenario(scenario: dict) -> dict:
    from intent import router as intent_router
    from orchestrator import engine as orchestrator_engine

    start = time.monotonic()
    try:
        task = await intent_router.route(scenario["command"])
        if task.steps and task.status in ("pending", "running"):
            task = await orchestrator_engine.run(task, persist=False)
        elif task.status == "pending" and not task.steps:
            task.status = "failed"

        elapsed = time.monotonic() - start
        return {
            "id": scenario["id"],
            "status": task.status,
            "tools_used": [s.tool for s in task.steps],
            "used_ai": task.used_ai,
            "error": task.error or None,
            "elapsed_ms": round(elapsed * 1000),
        }
    except Exception as e:
        elapsed = time.monotonic() - start
        return {
            "id": scenario["id"],
            "status": "crash",
            "tools_used": [],
            "used_ai": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "elapsed_ms": round(elapsed * 1000),
        }


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(scenario: dict, result: dict) -> str:
    if result["status"] == "crash":
        return "crash"

    expected_status = scenario["expected_status"]
    actual_status = result["status"]

    # Status match for non-done statuses
    if expected_status in ("failed", "needs_setup", "needs_clarification"):
        return "pass" if actual_status == expected_status else "partial"

    # For expected done
    if expected_status == "done" and actual_status != "done":
        return "fail"

    # Tool check
    expected_tool = scenario.get("expected_tool")
    if expected_tool and result["tools_used"]:
        if result["tools_used"][0] != expected_tool:
            return "partial"
    elif expected_tool and not result["tools_used"]:
        return "fail"

    if result["error"] and expected_status == "done":
        return "fail"

    return "pass"


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def analyze_gaps(scenarios, results, grades):
    categories = defaultdict(lambda: {"pass": 0, "partial": 0, "fail": 0, "crash": 0, "total": 0})
    failures = []

    for scenario, result, grade in zip(scenarios, results, grades):
        cat = scenario["category"]
        categories[cat][grade] += 1
        categories[cat]["total"] += 1

        if grade in ("fail", "crash", "partial"):
            failures.append({
                "id": scenario["id"],
                "category": cat,
                "grade": grade,
                "command": scenario["command"],
                "expected_tool": scenario.get("expected_tool"),
                "expected_status": scenario["expected_status"],
                "actual_tool": result["tools_used"][0] if result.get("tools_used") else None,
                "actual_status": result["status"],
                "error": result.get("error"),
            })

    patterns = detect_patterns(failures)
    return dict(categories), failures, patterns


def detect_patterns(failures):
    patterns = []
    by_category = defaultdict(list)
    for f in failures:
        by_category[f["category"]].append(f)

    for cat, items in by_category.items():
        if len(items) >= 2:
            errors = [str(item.get("error") or "")[:80] for item in items]
            if len(set(errors)) == 1 and errors[0]:
                patterns.append({
                    "type": "category_systematic",
                    "category": cat,
                    "count": len(items),
                    "common_error": errors[0],
                    "affected_ids": [item["id"] for item in items],
                })

    for f in failures:
        if f["actual_tool"] is None and f["expected_tool"]:
            patterns.append({"type": "intent_not_recognized", "command": f["command"], "expected_tool": f["expected_tool"]})
        elif f["actual_tool"] and f["expected_tool"] and f["actual_tool"] != f["expected_tool"]:
            patterns.append({"type": "misrouted", "command": f["command"], "expected_tool": f["expected_tool"], "actual_tool": f["actual_tool"]})

    return patterns


# ---------------------------------------------------------------------------
# Spec generation
# ---------------------------------------------------------------------------

def generate_specs(patterns):
    specs = []
    for i, p in enumerate(patterns):
        if p["type"] == "intent_not_recognized":
            specs.append({
                "id": f"eval-fix-{i:02d}",
                "title": f"Add intent for: {p['command'][:40]}",
                "goal": f"'{p['command']}' should route to '{p['expected_tool']}' but produces no steps.",
                "implementation_locations": {"new_files": [], "modified_files": ["backend/intent/normalizer.py"]},
                "test_requirements": [{"case": f"route '{p['command']}'", "expected": f"tool == '{p['expected_tool']}'"}],
                "constraints": ["Do not break existing tests"],
                "branch_name": f"eval-fix/intent-{i:02d}",
                "base_branch": "feat/phase0-ai-capabilities",
                "max_retries": 2,
                "codex_model": "",
                "test_command": "cd backend && python3 -m unittest discover -s tests -v",
                "test_focus_command": "cd backend && python3 -m unittest discover -s tests -v",
            })
        elif p["type"] == "misrouted":
            specs.append({
                "id": f"eval-fix-{i:02d}",
                "title": f"Fix routing: {p['command'][:40]}",
                "goal": f"'{p['command']}' routes to '{p['actual_tool']}' but should route to '{p['expected_tool']}'.",
                "implementation_locations": {"new_files": [], "modified_files": ["backend/intent/normalizer.py"]},
                "test_requirements": [{"case": f"route '{p['command']}'", "expected": f"tool == '{p['expected_tool']}'"}],
                "constraints": ["Do not break existing tests"],
                "branch_name": f"eval-fix/route-{i:02d}",
                "base_branch": "feat/phase0-ai-capabilities",
                "max_retries": 2,
                "codex_model": "",
                "test_command": "cd backend && python3 -m unittest discover -s tests -v",
                "test_focus_command": "cd backend && python3 -m unittest discover -s tests -v",
            })
    return specs


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_results(scenarios, results, grades, categories, failures, patterns, elapsed_total):
    total = len(scenarios)
    counts = {"pass": 0, "partial": 0, "fail": 0, "crash": 0, "skip": 0}
    for g in grades:
        counts[g] = counts.get(g, 0) + 1

    print(f"\n{'='*70}")
    print(f"  EVAL HARNESS — {total} scenarios")
    print(f"{'='*70}")
    print(f"  PASS: {counts['pass']}  PARTIAL: {counts['partial']}  FAIL: {counts['fail']}  CRASH: {counts['crash']}  SKIP: {counts['skip']}")
    print(f"  Pass rate: {counts['pass']/max(total-counts['skip'],1)*100:.0f}%")
    print(f"  Time: {elapsed_total:.1f}s")
    print(f"{'='*70}\n")

    # Per-category
    print(f"{'Category':<20} {'Pass':>5} {'Part':>5} {'Fail':>5} {'Crash':>5} {'Total':>5}")
    print("-" * 55)
    for cat in sorted(categories.keys()):
        c = categories[cat]
        print(f"{cat:<20} {c['pass']:>5} {c['partial']:>5} {c['fail']:>5} {c['crash']:>5} {c['total']:>5}")

    if failures:
        print(f"\n{'='*70}")
        print(f"  FAILURES ({len(failures)})")
        print(f"{'='*70}")
        for f in failures:
            print(f"  [{f['grade']:>7}] {f['id']:<20} {f['command'][:40]}")
            print(f"           expected: {f['expected_tool']}/{f['expected_status']} → got: {f['actual_tool']}/{f['actual_status']}")
            if f.get("error"):
                print(f"           error: {str(f['error'])[:80]}")
            print()

    if patterns:
        print(f"  PATTERNS ({len(patterns)})")
        print(f"  {'-'*50}")
        for p in patterns:
            print(f"  [{p['type']}] {json.dumps(p, ensure_ascii=False)[:120]}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_eval(args):
    with_ai = args.with_ai
    category_filter = args.category

    filtered = [s for s in SCENARIOS if not category_filter or s["category"] == category_filter]
    if not with_ai:
        filtered = [s for s in filtered if not s.get("requires_ai")]

    print(f"Running {len(filtered)} scenarios (ai={'on' if with_ai else 'off'})...")

    await setup_runtime(with_ai=with_ai)
    try:
        results = []
        grades = []
        start_total = time.monotonic()

        for scenario in filtered:
            result = await execute_scenario(scenario)
            grade = evaluate(scenario, result)
            results.append(result)
            grades.append(grade)

            icon = {"pass": "✓", "partial": "△", "fail": "✗", "crash": "💥"}.get(grade, "?")
            print(f"  {icon} {scenario['id']:<25} {grade:<8} {result['elapsed_ms']:>5}ms  {scenario['command'][:40]}")

        elapsed_total = time.monotonic() - start_total
        categories, failures, patterns = analyze_gaps(filtered, results, grades)

        print_results(filtered, results, grades, categories, failures, patterns, elapsed_total)

        # Save report
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(filtered),
            "pass": sum(1 for g in grades if g == "pass"),
            "partial": sum(1 for g in grades if g == "partial"),
            "fail": sum(1 for g in grades if g == "fail"),
            "crash": sum(1 for g in grades if g == "crash"),
            "pass_rate": f"{sum(1 for g in grades if g=='pass')/max(len(filtered),1)*100:.0f}%",
            "categories": categories,
            "failures": failures,
            "patterns": patterns,
            "elapsed_seconds": round(elapsed_total, 1),
        }
        report_path = RESULTS_DIR / f"eval-report-{ts}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  Report: {report_path}")

        # Generate fix specs
        if args.generate_specs and patterns:
            specs = generate_specs(patterns)
            for spec in specs:
                spec_path = PROJECT_ROOT / "scripts" / "harness-specs" / f"{spec['id']}.json"
                with open(spec_path, "w") as f:
                    json.dump(spec, f, indent=2, ensure_ascii=False)
                print(f"  Spec: {spec_path}")

    finally:
        await teardown_runtime()


def main():
    parser = argparse.ArgumentParser(description="Eval harness")
    parser.add_argument("--with-ai", action="store_true", help="Include AI-requiring scenarios")
    parser.add_argument("--category", default=None, help="Filter by category")
    parser.add_argument("--generate-specs", action="store_true", help="Generate fix specs for failures")
    args = parser.parse_args()
    asyncio.run(run_eval(args))


if __name__ == "__main__":
    main()
