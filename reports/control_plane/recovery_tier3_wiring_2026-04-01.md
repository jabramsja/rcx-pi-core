# Recovery Tier 3 Wiring

Date: 2026-04-01
Status: Closed on `dev` — all 9 work items landed
Phase-A-Lock: UNLOCKED
Task: [RECOVERY-TIER3-WIRING]
Purpose: Wire Tier 3 recovery live into dispatcher execution and close the immediate pipeline hardening residue from PR #706.

## Scope

All 9 TASKS.md work items for `[RECOVERY-TIER3-WIRING]` have been verified as landed in current code. This packet now records the closed state and the final implementation boundary for item (7).

**Files verified:**

| File | Status |
|------|--------|
| `mu/tools/executors/recovery_gate.py` | Items (1), (2), (4), (5), (8) landed |
| `mu/tools/executors/executor_dispatch.py` | Items (3), (6), (7) landed |
| `mu/tools/executors/commit_executor.py` | Item (9) landed |

**Directories verified:** `mu/tools/executors/`, `mu/tests/tools/`

## Already-Landed Work Items

The following TASKS.md work items are landed in current code and are not pending:

1. **(1) Wire `run_recovery_loop()` into `attempt_recovery()`** — Landed in `recovery_gate.py`; Tier 3 now calls the live recovery loop.
2. **(2) Reclassify `needs_phase_b` as Tier 3 recoverable** — Landed in `recovery_gate.py`; `needs_phase_b` no longer escalates as a terminal Tier 4 outcome.
3. **(3) Fix Tier 2 sequential timeout cap** — Landed across recovery override handling; timeout bumps re-base on the original baseline instead of compounding.
4. **(4) Expand Tier 3 denylist to pattern-based** — Landed in `recovery_gate.py`; destructive git forms and shell-obfuscation patterns are denied.
5. **(5) Block edits to repo-internal sensitive paths** — Landed in `recovery_gate.py`; `.git/config` and `.git/hooks/` mutations are blocked.
6. **(6) Surface command routing through dispatcher recovery** — Landed in `executor_dispatch.py`; `phase-a` and `phase-b` route through recovery-aware execution.
7. **(7) Process-tree cleanup before timeout retry** — Landed in `executor_dispatch.py`; see **Layer Correction** below.
8. **(8) Timeout bump cap re-base on original baseline** — Landed with item (3); both fixes share the same preserved-baseline logic.
9. **(9) Commit executor pytest gate** — Landed in `commit_executor.py`; commit execution runs targeted pytest on affected test files before commit.

**Adjacent residue also landed:**
- Tier 3 durable recovery logging persists every iteration to `recovery_log.json`.

## Layer Correction

Item (7) was initially described as a `recovery_gate.py` change, but code truth shows that timeout cleanup belongs at the timed subprocess boundary, not inside the retry-policy fix functions.

The actual implementation lives in `executor_dispatch.py` via `_run_executor_in_group()`, which:

1. starts executor subprocesses in their own process group,
2. kills the process group on timeout,
3. walks remaining descendants with process-tree cleanup,
4. kills the direct child as a final fallback, and
5. reaps the process before retry propagation.

`fix_process_timeout()` and `fix_implementer_stale()` in `recovery_gate.py` correctly stay at the policy layer: they adjust timeout parameters for the next attempt and do not own a live process handle.

## Pending Work Items

None. `[RECOVERY-TIER3-WIRING]` is closed.

## Constraints

1. No new bootstrap/runtime host semantics were introduced; this wave stayed in the Python control surface.
2. No learning-store behavior was added here; that remains future `[PIPELINE-RECOVERY]` scope.

## Stop Conditions

No implementation remains in this packet. Re-open only if verification exposes a regression in the landed recovery surfaces.

## Acceptance Criteria

Closeout verification for this packet:

1. Tier 3 recovery is live in dispatcher execution.
2. `phase-a` and `phase-b` surfaces route through recovery-aware execution.
3. Timeout cleanup occurs at the dispatcher subprocess boundary before retry.
4. Targeted pytest gating runs before commit execution.
5. Recovery/dispatcher tests and docs consistency continue to pass.

## Grounding

- **Authorization source:** `[RECOVERY-TIER3-WIRING]` in `TASKS.md` (founder-authorized 2026-03-31; closed 2026-04-01).
- **Parent task:** `[PIPELINE-RECOVERY]` remains in progress for the learning-store follow-on only.
- **Depends on:** PR #706 (`Tier 2 auto-retry + Tier 3 recovery loop function`) landed before this closeout.
- **Tracker sync note:** `TASKS.md` tracker sync note dated 2026-04-01 (`recovery-tier3-wiring-closeout-2026-04-01`).
- **Design reference:** `mu/docs/agents/PipelineRecovery.v0.md`.
