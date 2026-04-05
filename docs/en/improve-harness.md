# Improve Harness — Self-Improving AI Loop

Automatically discovers product gaps and fixes them without human intervention.

---

## Architecture

```
python3 scripts/improve-harness.py --rounds N --commands M

Big Cycle (× N rounds, new commands each)
  │
  │  [1] User Agent (Claude API)
  │      Generates M realistic commands a human would ask
  │
  └─→ Small Cycle (repeat until all pass or max reached)
        │
        ├── [2] Execute (local, route() → run())
        │       Runs each command through the real pipeline
        │
        ├── [3] Dual Evaluation (Claude + Codex)
        │       Both grade independently, worst wins
        │       good / partial / bad per command
        │
        ├── [4] Auto-Fix (dev-harness → Codex)
        │       Generate spec for each failure → Codex implements
        │
        ├── [5] Regression (eval-harness)
        │       Verify existing 37+ scenarios still pass
        │
        └── Re-execute same commands → back to [2]
            (until all pass or max small cycles reached)
```

---

## Big Cycle vs Small Cycle

| | Big Cycle | Small Cycle |
|---|---|---|
| Purpose | Discover new gaps | Fix known gaps |
| Commands | New (AI generates fresh) | Same (re-run after fix) |
| Exit condition | All rounds completed | All commands pass OR max cycles |
| Contains | 1+ small cycles | Execute → Eval → Fix → Regression |

---

## Dual Evaluation

Both Claude and Codex grade each result independently.
Rule: **worst grade wins** — prevents self-evaluation bias.

---

## CLI

```bash
python3 scripts/improve-harness.py                          # 1 round, 10 commands
python3 scripts/improve-harness.py --rounds 3 --commands 20 # 3 rounds, 20 each
python3 scripts/improve-harness.py --no-fix                 # evaluate only
python3 scripts/improve-harness.py --evaluator codex        # Codex only evaluation
```

---

## Harness Connections

```
improve-harness.py  ← orchestrates everything
    ├── Direct: route() → run()   (app pipeline)
    ├── Calls: dev-harness.py     (Codex implements fixes)
    └── Calls: eval-harness.py    (regression check)
```
