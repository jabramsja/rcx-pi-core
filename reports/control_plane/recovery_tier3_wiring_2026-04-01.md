# Recovery Tier 3 Wiring

Date: 2026-04-01
Status: In progress — 7/9 items landed, 3 remaining (items 2, 4 partial, 5)
Phase-A-Lock: LOCKED
Task: [RECOVERY-TIER3-WIRING]
Purpose: Wire Tier 3 recovery live into dispatcher execution and close the immediate pipeline hardening residue from PR #706.

## Scope

- `mu/tools/executors/recovery_gate.py` — items (2), (4), (5)
- `mu/tests/tools/test_recovery_gate.py` — regression tests for remaining items

## Landed Work Items (verified 2026-04-06 against current code)

1. **(1) Wire `run_recovery_loop()` into `attempt_recovery()`** — LANDED (recovery_gate.py:1512)
2. **(3) Fix Tier 2 sequential timeout cap** — LANDED (executor_dispatch.py:421)
3. **(6) Surface command routing through dispatcher recovery** — LANDED (executor_dispatch.py:406)
4. **(7) Process-tree cleanup before timeout retry** — LANDED (executor_dispatch.py via _run_executor_in_group)
5. **(8) Timeout bump cap re-base on original baseline** — LANDED (executor_dispatch.py:421-522)
6. **(9) Commit executor pytest gate** — LANDED (commit_executor.py:261)

## Remaining Work Items

1. **(2) Reclassify `needs_phase_b` from Tier 4 terminal to Tier 3 recoverable** — `needs_phase_b` is still in `_TERMINAL_STATUSES` at recovery_gate.py:77. Move it to a Tier 3 classification so the recovery loop can retry Phase B instead of escalating to founder.

2. **(4) Expand Tier 3 denylist to pattern-based** — PARTIAL. `_DANGEROUS_COMMANDS` at recovery_gate.py:592 has exact string matches (`git reset --hard`, `git checkout .`, `git restore .`). Missing: broader subcommand patterns for `git reset`, `git checkout`, `git restore` that would catch variations like `git reset --mixed`, `git checkout -- file`, `git restore --staged`.

3. **(5) Block edits to repo-internal sensitive paths** — NOT LANDED. No mechanism in recovery_gate.py blocks Tier 3 shell/edit actions from targeting `.git/config`, `.git/hooks/`, or other repo-internal paths. `_is_repo_escape` only checks if paths resolve outside the repo root, not if they target sensitive paths within it.

## Constraints

- No new bootstrap/runtime host semantics.
- No learning-store behavior (remains future [PIPELINE-RECOVERY] scope).

## Stop Conditions

- Stop if remaining items require design decisions beyond the scope of this task.

## Acceptance Criteria

- `needs_phase_b` is Tier 3 recoverable, not Tier 4 terminal.
- Denylist catches `git reset`, `git checkout`, `git restore` subcommand variations.
- Sensitive repo-internal paths (`.git/config`, `.git/hooks/`) are blocked from Tier 3 actions.

## Grounding

- **Authorization source:** `[RECOVERY-TIER3-WIRING]` in `TASKS.md` (founder-authorized 2026-03-31).
- **Governing packet:** `reports/control_plane/recovery_tier3_wiring_2026-04-01.md` (this file; tracked in TASKS.md:506).
- **Packet sequence:** `[PIPELINE-RECOVERY]` Phase 3 — Tier 3 wiring + hardening (TASKS.md:593).
- **Parent task:** `[PIPELINE-RECOVERY]` IN PROGRESS.
- **Depends on:** PR #706 (Tier 2+3 code) landed.
- **Design reference:** `mu/docs/agents/PipelineRecovery.v0.md`.
