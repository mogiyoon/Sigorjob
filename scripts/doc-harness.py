#!/usr/bin/env python3
"""Doc harness: AI agents loop to keep documentation in sync with code.

Loop:
  1. Analyze — scan code + git diff + existing docs → identify add/update/delete
  2. Execute — apply doc changes
  3. Verify  — check code↔doc consistency (Sonnet)
  4. Re-verify — higher model quality check (Opus)
  5. → if failed, loop back to step 2 (max 3 retries)
  6. → if passed, show summary and wait for user approval

Usage:
    python3 scripts/doc-harness.py                         # analyze all recent changes
    python3 scripts/doc-harness.py --since "3 days ago"    # changes since date
    python3 scripts/doc-harness.py --files backend/ai/agent.py  # specific files
    python3 scripts/doc-harness.py --dry-run               # show plan only
    python3 scripts/doc-harness.py --full                  # full code↔doc audit
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
DOCS_DIR = PROJECT_ROOT / "docs"
RESULTS_DIR = PROJECT_ROOT / "scripts" / "harness-results"
sys.path.insert(0, str(BACKEND_DIR))

ANALYZE_MODEL = "claude-sonnet-4-6"
VERIFY_MODEL = "claude-sonnet-4-6"
REVERIFY_MODEL = "claude-opus-4-6"
MAX_RETRIES = 3


def _parse_json(text: str, fallback=None):
    """Safely parse JSON from AI response, handling markdown fences and malformed output."""
    cleaned = text.strip()
    if "```" in cleaned:
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    # Try array
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"    WARNING: Failed to parse AI response as JSON, using fallback")
        return fallback


# ---------------------------------------------------------------------------
# 1. Analyze — scan code + docs, produce change plan
# ---------------------------------------------------------------------------

def get_code_changes(since: str | None, files: list[str] | None) -> str:
    """Get recent code changes via git diff."""
    if files:
        cmd = ["git", "diff", "HEAD", "--", *files]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if not result.stdout.strip():
            cmd = ["git", "diff", "HEAD~5", "HEAD", "--", *files]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        return result.stdout[:15000]

    if since:
        cmd = ["git", "log", f"--since={since}", "--oneline", "--stat"]
        log = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        cmd2 = ["git", "diff", f"HEAD@{{'{since}'}}", "HEAD", "--stat"]
        diff_stat = subprocess.run(cmd2, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        return f"Recent commits:\n{log.stdout[:5000]}\n\nDiff stat:\n{diff_stat.stdout[:5000]}"

    # Default: last 5 commits
    cmd = ["git", "log", "-5", "--oneline", "--stat"]
    log = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    cmd2 = ["git", "diff", "HEAD~5", "HEAD", "--stat"]
    diff_stat = subprocess.run(cmd2, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    return f"Recent commits:\n{log.stdout[:5000]}\n\nDiff stat:\n{diff_stat.stdout[:5000]}"


def scan_existing_docs() -> dict[str, str]:
    """Read all existing documentation files."""
    docs = {}
    for lang in ["en", "ko"]:
        lang_dir = DOCS_DIR / lang
        if not lang_dir.exists():
            continue
        for md_file in sorted(lang_dir.glob("*.md")):
            rel = f"docs/{lang}/{md_file.name}"
            docs[rel] = md_file.read_text(encoding="utf-8")[:3000]

    # Root docs
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        rel = f"docs/{md_file.name}"
        docs[rel] = md_file.read_text(encoding="utf-8")[:3000]

    # CLAUDE.md and AGENTS.md
    for name in ["CLAUDE.md", "AGENTS.md"]:
        p = PROJECT_ROOT / name
        if p.exists():
            docs[name] = p.read_text(encoding="utf-8")[:3000]

    return docs


def scan_code_structure() -> str:
    """Scan key code files for module-level docstrings and structure."""
    summary_parts = []

    # Backend modules
    for py_file in sorted((PROJECT_ROOT / "backend").rglob("*.py")):
        if "__pycache__" in str(py_file) or "test" in py_file.name:
            continue
        rel = str(py_file.relative_to(PROJECT_ROOT))
        try:
            content = py_file.read_text(encoding="utf-8")
            # Extract class/function names
            lines = content.split("\n")
            defs = [l.strip() for l in lines if l.strip().startswith(("class ", "async def ", "def ")) and not l.strip().startswith("def _")]
            if defs:
                summary_parts.append(f"{rel}: {', '.join(d[:60] for d in defs[:8])}")
        except Exception:
            pass

    # Frontend pages
    for tsx_file in sorted((PROJECT_ROOT / "frontend" / "src").rglob("*.tsx")):
        rel = str(tsx_file.relative_to(PROJECT_ROOT))
        summary_parts.append(f"{rel}")

    # Scripts
    for script in sorted((PROJECT_ROOT / "scripts").glob("*.py")):
        rel = str(script.relative_to(PROJECT_ROOT))
        summary_parts.append(f"{rel}")

    return "\n".join(summary_parts[:100])


def analyze(client, code_changes: str, existing_docs: dict[str, str], code_structure: str, full_audit: bool) -> list[dict]:
    """AI analyzes code vs docs and produces a change plan."""
    doc_index = "\n".join(f"- {path}: {content[:150]}..." for path, content in existing_docs.items())

    mode = "FULL AUDIT" if full_audit else "INCREMENTAL UPDATE"

    prompt = f"""You are a documentation analyst for a software project.
Mode: {mode}

Your job:
1. Compare the current code state with existing documentation
2. Identify documents that need to be ADDED, UPDATED, or DELETED
3. For DELETE: identify docs that describe features/modules that no longer exist in code

Code changes:
{code_changes}

Code structure (current modules and functions):
{code_structure}

Existing documentation index:
{doc_index}

Return a JSON array of change actions:
[
  {{
    "action": "add" | "update" | "delete",
    "file": "docs/en/filename.md",
    "reason": "why this change is needed",
    "summary": "brief description of what to write/change/remove",
    "priority": "high" | "medium" | "low"
  }}
]

Rules:
- Only suggest changes that are genuinely needed based on code evidence
- DELETE docs that reference removed/renamed modules, deprecated features, or contain outdated information
- UPDATE docs where code behavior has changed but doc still describes old behavior
- ADD docs only for significant new features that have no documentation
- Each doc should exist in both en/ and ko/ — if one language is missing, suggest adding it
- Do NOT suggest trivial formatting changes
- Sort by priority (high first)

Respond ONLY with the JSON array."""

    message = client.messages.create(
        model=ANALYZE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text, fallback=[])


# ---------------------------------------------------------------------------
# 2. Execute — apply doc changes
# ---------------------------------------------------------------------------

def execute_changes(client, plan: list[dict], existing_docs: dict[str, str], code_structure: str) -> list[dict]:
    """Apply each planned doc change."""
    results = []

    for item in plan:
        action = item["action"]
        file_path = item["file"]
        abs_path = PROJECT_ROOT / file_path

        if action == "delete":
            if abs_path.exists():
                abs_path.unlink()
                results.append({**item, "status": "deleted"})
                print(f"    - [DELETE] {file_path}")
            else:
                results.append({**item, "status": "skipped", "note": "file not found"})
                print(f"    - [SKIP]   {file_path} (not found)")
            continue

        # add or update — generate content
        existing_content = existing_docs.get(file_path, "")
        lang = "Korean" if "/ko/" in file_path else "English"

        prompt = f"""Write documentation for: {file_path}
Language: {lang}
Action: {action}
Reason: {item['reason']}
Summary: {item['summary']}

Current code structure:
{code_structure[:5000]}

{"Existing content to update:" if existing_content else "This is a new document."}
{existing_content[:3000] if existing_content else ""}

Rules:
- Write in {lang}
- Use markdown format
- Be concise but complete
- Include relevant code references (file paths, function names)
- Match the style of existing project documentation
- Do not include meta-commentary about the writing process

Output ONLY the markdown content."""

        try:
            message = client.messages.create(
                model=ANALYZE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            content = message.content[0].text.strip()

            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content, encoding="utf-8")
            results.append({**item, "status": "applied"})
            print(f"    - [{action.upper():6s}] {file_path}")
        except Exception as e:
            results.append({**item, "status": "failed", "error": str(e)})
            print(f"    - [FAIL]   {file_path}: {e}")

    return results


# ---------------------------------------------------------------------------
# 3. Verify — code↔doc consistency check (Sonnet)
# ---------------------------------------------------------------------------

def verify(client, results: list[dict], code_structure: str) -> dict:
    """Sonnet checks if the applied changes are consistent with code."""
    applied = [r for r in results if r["status"] == "applied"]
    if not applied:
        return {"passed": True, "issues": [], "reason": "No changes to verify"}

    changed_docs = {}
    for r in applied:
        abs_path = PROJECT_ROOT / r["file"]
        if abs_path.exists():
            changed_docs[r["file"]] = abs_path.read_text(encoding="utf-8")[:3000]

    doc_contents = "\n\n---\n\n".join(
        f"### {path}\n{content}" for path, content in changed_docs.items()
    )

    prompt = f"""You are verifying documentation accuracy against actual code.

Changed documents:
{doc_contents}

Current code structure:
{code_structure[:5000]}

Check for:
1. Incorrect function/class names referenced in docs
2. Wrong file paths
3. Description that doesn't match actual code behavior
4. Missing critical information
5. Inconsistency between en/ and ko/ versions

Return JSON:
{{
  "passed": true/false,
  "issues": ["issue 1", "issue 2"],
  "fixes": [
    {{"file": "docs/en/file.md", "problem": "...", "suggestion": "..."}}
  ]
}}"""

    message = client.messages.create(
        model=VERIFY_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text, fallback={"passed": True, "issues": [], "fixes": []})


# ---------------------------------------------------------------------------
# 4. Re-verify — higher model quality check (Opus)
# ---------------------------------------------------------------------------

def reverify(client, results: list[dict], code_structure: str) -> dict:
    """Opus does final quality/accuracy check."""
    applied = [r for r in results if r["status"] in ("applied", "deleted")]
    if not applied:
        return {"passed": True, "issues": [], "reason": "No changes to re-verify"}

    changed_docs = {}
    for r in applied:
        if r["status"] == "deleted":
            changed_docs[r["file"]] = "(DELETED)"
            continue
        abs_path = PROJECT_ROOT / r["file"]
        if abs_path.exists():
            changed_docs[r["file"]] = abs_path.read_text(encoding="utf-8")[:4000]

    doc_contents = "\n\n---\n\n".join(
        f"### {path}\n{content}" for path, content in changed_docs.items()
    )

    prompt = f"""You are the FINAL reviewer for documentation changes.
Your job is to catch issues the previous reviewer missed.

Changed documents:
{doc_contents}

Current code structure:
{code_structure[:8000]}

Evaluate:
1. ACCURACY: Do the docs correctly describe the code?
2. COMPLETENESS: Are important details missing?
3. DELETIONS: Were the right docs deleted? Should any deleted doc be kept?
4. QUALITY: Is the writing clear, concise, and useful?
5. CONSISTENCY: Do en/ and ko/ versions match in content?

Return JSON:
{{
  "passed": true/false,
  "score": 1-10,
  "issues": ["issue 1", ...],
  "fixes": [
    {{"file": "...", "problem": "...", "suggestion": "..."}}
  ]
}}

Be strict. Only pass if the documentation is genuinely accurate and useful."""

    message = client.messages.create(
        model=REVERIFY_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text, fallback={"passed": False, "score": 0, "issues": ["Failed to parse re-verification response"], "fixes": []})


# ---------------------------------------------------------------------------
# 5. Apply fixes from verification
# ---------------------------------------------------------------------------

def apply_fixes(client, fixes: list[dict], code_structure: str) -> list[dict]:
    """Apply fixes suggested by verifier/re-verifier."""
    results = []
    for fix in fixes:
        file_path = fix.get("file", "")
        abs_path = PROJECT_ROOT / file_path
        if not abs_path.exists():
            continue

        existing = abs_path.read_text(encoding="utf-8")
        lang = "Korean" if "/ko/" in file_path else "English"

        prompt = f"""Fix this documentation issue.

File: {file_path}
Problem: {fix['problem']}
Suggestion: {fix['suggestion']}

Current content:
{existing[:5000]}

Code structure:
{code_structure[:3000]}

Rules:
- Write in {lang}
- Only fix the identified problem, don't rewrite everything
- Output the COMPLETE fixed markdown content

Output ONLY the markdown content."""

        try:
            message = client.messages.create(
                model=ANALYZE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            content = message.content[0].text.strip()
            abs_path.write_text(content, encoding="utf-8")
            results.append({**fix, "status": "fixed"})
            print(f"    - [FIX]    {file_path}")
        except Exception as e:
            results.append({**fix, "status": "failed", "error": str(e)})
            print(f"    - [FAIL]   {file_path}: {e}")

    return results


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def print_summary(plan: list[dict], results: list[dict], verification: dict, reverification: dict):
    """Print human-readable summary for approval."""
    print(f"\n{'='*60}")
    print("  DOC HARNESS — CHANGE SUMMARY")
    print(f"{'='*60}\n")

    adds = [r for r in results if r["action"] == "add" and r["status"] == "applied"]
    updates = [r for r in results if r["action"] == "update" and r["status"] == "applied"]
    deletes = [r for r in results if r["action"] == "delete" and r["status"] == "deleted"]
    skipped = [r for r in results if r["status"] in ("skipped", "failed")]

    if adds:
        print("  Added:")
        for r in adds:
            print(f"    + {r['file']}  — {r['reason']}")
    if updates:
        print("  Updated:")
        for r in updates:
            print(f"    ~ {r['file']}  — {r['reason']}")
    if deletes:
        print("  Deleted:")
        for r in deletes:
            print(f"    - {r['file']}  — {r['reason']}")
    if skipped:
        print("  Skipped/Failed:")
        for r in skipped:
            print(f"    ? {r['file']}  — {r.get('note', r.get('error', ''))}")

    print(f"\n  Verification: {'PASS' if verification.get('passed') else 'FAIL'}")
    print(f"  Re-verification: {'PASS' if reverification.get('passed') else 'FAIL'} (score: {reverification.get('score', '?')}/10)")

    if reverification.get("issues"):
        print("  Remaining issues:")
        for issue in reverification["issues"]:
            print(f"    ! {issue}")

    print(f"\n{'='*60}")


def run(args):
    from ai.runtime import get_client, has_api_key

    if not has_api_key():
        print("ERROR: ANTHROPIC_API_KEY is required")
        sys.exit(1)

    client = get_client()
    if client is None:
        print("ERROR: Failed to initialize AI client")
        sys.exit(1)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Analyze
    print("\n  [1/4] Analyzing code vs documentation...")
    code_changes = get_code_changes(args.since, args.files)
    existing_docs = scan_existing_docs()
    code_structure = scan_code_structure()
    plan = analyze(client, code_changes, existing_docs, code_structure, args.full)

    if not plan:
        print("  No documentation changes needed.")
        return

    print(f"\n  Planned changes ({len(plan)}):")
    for item in plan:
        icon = {"add": "+", "update": "~", "delete": "-"}.get(item["action"], "?")
        print(f"    {icon} [{item['priority']}] {item['file']}  — {item['reason']}")

    if args.dry_run:
        print("\n  (dry-run mode — no changes applied)")
        return

    # Loop: execute → verify → re-verify → fix
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n  [2/4] Applying changes (attempt {attempt}/{MAX_RETRIES})...")
        results = execute_changes(client, plan, existing_docs, code_structure)

        print(f"\n  [3/4] Verifying consistency (Sonnet)...")
        verification = verify(client, results, code_structure)
        v_status = "PASS" if verification.get("passed") else "FAIL"
        print(f"    Result: {v_status}")
        if verification.get("issues"):
            for issue in verification["issues"]:
                print(f"    ! {issue}")

        print(f"\n  [4/4] Re-verifying quality (Opus)...")
        reverification = reverify(client, results, code_structure)
        rv_status = "PASS" if reverification.get("passed") else "FAIL"
        rv_score = reverification.get("score", "?")
        print(f"    Result: {rv_status} (score: {rv_score}/10)")
        if reverification.get("issues"):
            for issue in reverification["issues"]:
                print(f"    ! {issue}")

        if reverification.get("passed"):
            break

        # Apply fixes and retry
        all_fixes = (verification.get("fixes") or []) + (reverification.get("fixes") or [])
        if all_fixes and attempt < MAX_RETRIES:
            print(f"\n  Applying {len(all_fixes)} fix(es) before retry...")
            apply_fixes(client, all_fixes, code_structure)
        elif attempt < MAX_RETRIES:
            print("  No specific fixes suggested, retrying full execution...")

    # Show summary and wait for approval
    print_summary(plan, results, verification, reverification)

    # Save report
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "results": results,
        "verification": verification,
        "reverification": reverification,
    }
    report_path = RESULTS_DIR / f"doc-harness-{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Report: {report_path}")

    # User approval
    print("\n  변경사항을 승인하시겠습니까?")
    try:
        answer = input("  [y/N] > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer in ("y", "yes"):
        # Stage and commit
        changed_files = [r["file"] for r in results if r["status"] in ("applied", "deleted", "fixed")]
        if changed_files:
            subprocess.run(["git", "add"] + changed_files, cwd=str(PROJECT_ROOT))
            subprocess.run(
                ["git", "commit", "-m", f"docs: Auto-update documentation via doc-harness\n\nChanged {len(changed_files)} file(s).\nScore: {rv_score}/10"],
                cwd=str(PROJECT_ROOT),
            )
            print("  Committed!")
        else:
            print("  No files to commit.")
    else:
        # Rollback
        print("  Rolling back changes...")
        subprocess.run(["git", "checkout", "--", "docs/"], cwd=str(PROJECT_ROOT))
        print("  Rolled back.")


def main():
    parser = argparse.ArgumentParser(description="Doc harness — keep docs in sync with code")
    parser.add_argument("--since", type=str, default=None, help="Analyze changes since date (e.g. '3 days ago')")
    parser.add_argument("--files", nargs="+", default=None, help="Specific files to analyze")
    parser.add_argument("--dry-run", action="store_true", help="Show plan only, don't apply")
    parser.add_argument("--full", action="store_true", help="Full code↔doc audit (not just recent changes)")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
