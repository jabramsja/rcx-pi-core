# Anti-Drift-Enforcement: Bot Findings + Pipeline Fixes

Date: 2026-04-13
Task: [ANTI-DRIFT-ENFORCEMENT] + [PIPELINE-RECOVERY]
Wave class: L4_ENABLER
Target gate: G8
Governing packet: This file

## Authorization

TASKS.md [ANTI-DRIFT-ENFORCEMENT] (line 171): "Remaining: open bot comments on PRs #757-765 + #769-771 (tracked in `reports/deferred/non_blocking/`). Next sub-wave: address P1/P2 bot findings + --task-id forwarding to phase_b_executor + learning.md entry ordering."

TASKS.md [PIPELINE-RECOVERY] (line 186): "Remaining: P1 --task-id forwarding to phase_b_executor, P2 entry ordering fix."

Both items explicitly authorize this wave's scope.

## Scope

Address 2 bot findings from PR #771 and triage remaining deferred findings from PRs #760-761.

### Files in scope

1. `mu/tools/executors/executor_dispatch.py` — forward `args.task_id` in `build_surface_command()` for phase-b surface
2. `mu/tools/executors/recovery_gate.py` — sort learning.md entries by date descending in `_load_learning_md_entries()`
3. `mu/tests/tools/test_executor_dispatch.py` — test --task-id forwarding in build_surface_command
4. `reports/deferred/non_blocking/pr760_late_bot_p1_2026-04-12.md` — triage (review status)
5. `reports/deferred/non_blocking/pr761_force_mcp_sqlite_missing_2026-04-12.md` — triage (hook now tracked via PR #769)

### Work items

**A. P1: Forward --task-id in build_surface_command() (PR #771 bot finding)**
- `build_surface_command()` at `executor_dispatch.py:266-282` builds the Phase B command without `--task-id`
- `phase_b_executor.py` ALREADY accepts `--task-id` (verified: `phase_b_executor.py --help` shows it)
- Fix: add `if getattr(args, 'task_id', ''): cmd.extend(['--task-id', args.task_id])` at line 282
- Acceptance: `build_surface_command()` output includes `--task-id` when `args.task_id` is non-empty

**B. P2: Sort learning.md entries newest-first (PR #771 bot finding)**
- `_load_learning_md_entries()` at `recovery_gate.py` reads top-to-bottom but `_export_to_learning_md()` appends at EOF
- Fix: `entries.sort(key=lambda e: e.get("date", ""), reverse=True)` before return
- Acceptance: `load_relevant_learnings()` returns entries sorted by date descending

**C. Triage deferred findings from PRs #760-761**
- `pr760_late_bot_p1_2026-04-12.md`: review finding, reclassify or fix
- `pr761_force_mcp_sqlite_missing_2026-04-12.md`: hook is now force-tracked via PR #769 — verify resolved, update deferred file

## Constraints

- No runtime file changes (mu/host/python/rcx_pi/ or mu/host/js/)
- No new subsystems
- `phase_b_executor.py` argparse is NOT modified (already has --task-id)

## Stop conditions

1. `build_surface_command()` includes --task-id for phase-b when provided
2. Learning.md entries sorted newest-first in load_relevant_learnings output
3. All deferred bot findings reviewed (fixed, reclassified, or re-deferred with evidence)
4. All affected tests pass
5. Pre-push-fast clean

## Acceptance criteria

1. Unit test verifies `build_surface_command()` includes `--task-id` in phase-b output
2. `load_relevant_learnings('adversary', ...)` returns entries with newest date first
3. Deferred files for PRs #760-761 updated with current status
4. 318+ executor_dispatch tests pass
5. 795+ recovery_gate tests pass
