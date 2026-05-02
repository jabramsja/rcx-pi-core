# PR #771 Bot Findings (2026-04-13) [FIXED]

Triage status: FIXED (2026-04-13). Both findings addressed in wave
anti-drift-bot-findings-2026-04-13.

## P1: Forward phase-b --task-id to executor invocation (executor_dispatch.py:227)

**Finding:** `build_surface_command()` at `executor_dispatch.py:266-282` doesn't forward `args.task_id` to the `phase_b_executor.py` command when Phase B is launched directly. The `--task-id` flag is accepted but silently dropped.

**Impact:** Only affects direct `phase-b` dispatch launches (rare — Phase B is normally chained from Phase A, where `task_id` flows via the routing record at `executor_dispatch.py:815`). The chained path works correctly. Direct Phase B launches without a routing record would still have empty `task_id`.

**Pipeline impact:** Yes, affects executors. However, direct Phase B launches are rare — normal workflow chains A→B. Non-blocking for the chained path.

**Fix:** Add `if getattr(args, 'task_id', ''): cmd.extend(['--task-id', args.task_id])` at `executor_dispatch.py:282`. Also requires Phase B executor to accept `--task-id` arg.

## P2: Emit newest learning.md entries before applying size cap (recovery_gate.py:4239)

**Finding:** `_load_learning_md_entries()` reads top-to-bottom, but entries in learning.md are newest-first (manual entries at top) AND `_export_to_learning_md()` appends at EOF. So the parser returns entries in file order (newest manual entries first, then appended promoted entries at the bottom). Under the 4000-char budget, this is mostly correct for manually-written entries (newest at top = consumed first). The issue is that promoted entries appended at EOF would be consumed last and potentially truncated.

**Pipeline impact:** Affects learning delivery to subagents. Minimal impact currently — no promoted entries exist at EOF yet. The 43 curated entries are all at the top of the file in newest-first order, so they're consumed correctly.

**Fix:** Sort entries by date descending in `_load_learning_md_entries()` return value, or reverse the list before consumption in `load_relevant_learnings()`.
