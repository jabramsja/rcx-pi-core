# Stale Active Items Recovery Receipt Bypass 2026 05 12

Date: 2026-05-12
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stale-active-items-recovery-receipt-bypass-2026-05-12
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: Create a bounded tooling repair packet for stale-active-items recovery after the PR #933 commit handoff showed the recovery gate could repair and verify `TASKS.md` but could not complete its internal commit because the pre-commit receipt became stale after staged `TASKS.md` changed.

## Scope

In scope for the downstream implementation wave:

- `mu/tools/executors/recovery_gate.py`: update only the `fix_stale_active_items` commit path for the stale-active-items recovery flow.
- `mu/tests/tools/test_recovery_gate.py`: add or update focused tests for the stale-active-items recovery commit behavior.
- Generated control/tracker/indicator handoff required by the dispatcher, Phase B, commit executor, and L4 contract pipeline.

This Phase A rewrite changes only this governing packet.

## Work items

1. Preserve the existing stale-active-items recovery behavior: `fix_stale_active_items` must continue to run `check_stale_next_items.sh --fix`, then run the verification path before attempting the internal recovery commit.
2. Preserve the dirty-file guard: the internal recovery commit remains allowed only when the repair leaves `TASKS.md` as the sole dirty path.
3. Add `RCX_SKIP_RECEIPT_CHECK=1` only to the TASKS-only internal recovery commit environment so the stale pre-commit receipt check is skipped while the existing docs, tracker, and boot-layer checks still run.
4. Add focused regression coverage in `mu/tests/tools/test_recovery_gate.py` proving the stale-active-items recovery commit receives the receipt-skip environment only for the bounded TASKS-only recovery case and does not relax the non-TASKS dirty-path guard.
5. Route the downstream work through the dispatcher/Phase B/commit executor pipeline. The commit/closeout path must add the same-wave `TASKS.md` tracker entry and indicator handoff required by the active `[NEXT-CODEX-POST-REDTEAM]` queue directive.

## Constraints

- Do not modify runtime semantics, Stage0, seeds, scheduler, registries, parity surfaces, production `/mu` behavior, or structural VM doctrine.
- Do not modify Claude files.
- Do not modify `tools/hooks/pre-commit-doc-check` or `mu/tools/executors/commit_executor.py` for this wave unless Phase B reproduces a direct contradiction to the reviewer evidence. Their current behavior is grounding evidence, not implementation scope.
- Do not broaden the receipt bypass beyond the stale-active-items TASKS-only recovery commit.
- Do not use `RCX_SKIP_RECEIPT_CHECK=1` to bypass docs consistency, docs governance, tracker sync, boot-layer boundary checks, or L4 contract validation.
- Do not treat the active `[NEXT-CODEX-POST-REDTEAM]` task as substantive closure evidence for this specific wave until a same-wave tracker entry exists.

## Stop conditions

- Stop if Phase B proves the required behavior is already implemented in current code; convert the work to a closeout/tracker-sync packet instead of re-listing the implementation as unresolved.
- Stop if the stale-active-items recovery commit requires any dirty path other than `TASKS.md`.
- Stop if the fix would require modifying runtime, Stage0, seed, scheduler, registry, parity, production `/mu`, Claude, or unrelated hook/commit-executor surfaces.
- Stop if the only available implementation would skip pre-commit checks other than the stale receipt check.
- Stop if dispatcher/Phase B/commit executor routing cannot bind the wave to a same-wave `TASKS.md` tracker entry and L4 indicator handoff.
- Stop if focused recovery-gate tests cannot cover the behavior without broad unrelated executor or test-suite changes.

## Acceptance criteria

- This packet contains the required Phase A sections: Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization.
- The packet carries mechanically derivable same-wave L4_ENABLER authorization for `stale-active-items-recovery-receipt-bypass-2026-05-12`.
- Downstream implementation changes are limited to `mu/tools/executors/recovery_gate.py` and focused tests in `mu/tests/tools/test_recovery_gate.py`, plus generated tracker/indicator handoff required by the pipeline.
- `fix_stale_active_items` still runs stale-item repair and verification before commit.
- `fix_stale_active_items` still commits only when `TASKS.md` is the sole dirty path.
- The TASKS-only recovery commit sets `RCX_SKIP_RECEIPT_CHECK=1`, and the bypass is limited to the pre-commit receipt check.
- Focused recovery-gate tests pass with `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`.
- Strict downstream L4 closeout must include a same-wave `TASKS.md` tracker entry and indicator artifact before the wave is treated as closed.

## Grounding / Authorization

- `TASKS.md:471-479` marks `[NEXT-CODEX-POST-REDTEAM]` as UNPARKED, keeps the current phase OPEN, and directs the founder-ordered red-team wave queue through the dispatcher/pipeline.
- `TASKS.md:479` requires every wave to have a control-plane packet plus a `TASKS.md` tracker entry. It also allows manual pipeline repair only as an unblocker paired with a same-wave mechanical/automated fix in dispatcher, builder, recovery, commit, pre-commit, or another appropriate pipeline surface.
FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05
FOUNDER_OVERRIDE:stale-active-items-recovery-receipt-bypass-2026-05-12

The first override is the parent queue authorization from `TASKS.md:479`; the second is the same-wave control-surface authorization required for this L4_ENABLER packet.
- Governing packet: `reports/control_plane/stale_active_items_recovery_receipt_bypass_2026_05_12_2026-05-12.md`.
- Reviewer evidence for this Phase A rewrite is authoritative: the prior packet was a request echo without required plan sections, and `TASKS.md` did not contain a same-wave tracker entry for this wave at review time.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `stale-active-items-recovery-receipt-bypass-2026-05-12`
- Active packet: `reports/control_plane/stale_active_items_recovery_receipt_bypass_2026_05_12_2026-05-12.md`
- Indicator artifact: `reports/l4_wave_indicators/stale-active-items-recovery-receipt-bypass-2026-05-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/stale_active_items_recovery_receipt_bypass_2026_05_12_2026-05-12.md`
  - `reports/l4_wave_indicators/stale-active-items-recovery-receipt-bypass-2026-05-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `stale-active-items-recovery-receipt-bypass-2026-05-12`
- Active packet: `reports/control_plane/stale_active_items_recovery_receipt_bypass_2026_05_12_2026-05-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `e4d0fce7c2dddfddd951800b69f2307d84f476c8295748c01a9c3c95073f4016`
- Indicator artifact: `reports/l4_wave_indicators/stale-active-items-recovery-receipt-bypass-2026-05-12.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/stale_active_items_recovery_receipt_bypass_2026_05_12_2026-05-12.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/stale-active-items-recovery-receipt-bypass-2026-05-12.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/stale_active_items_recovery_receipt_bypass_2026_05_12_2026-05-12.md`
  - `reports/l4_wave_indicators/stale-active-items-recovery-receipt-bypass-2026-05-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
