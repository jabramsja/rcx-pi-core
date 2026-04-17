# Wave Packet: phase-b-severity-floor-fix-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Close defect 1 from `reports/deferred/blocking/deferred_consolidation_phaseb_fail_closed_hardening_2026-04-02.md`:
the phase_b_executor classification logic ran the governance/doc-path
downgrade BEFORE the critical/high severity floor, so a critical
`POLICY_BOUND` finding on a governance path (e.g.
`reports/control_plane/example.md`) was downgraded to non-blocking
instead of failing the bridge review. Repro (from the deferred doc)
returns `len(blocking) == 0` today; after this fix it returns
`len(blocking) == 1`.

Defect 2 from the same blocker (`_stage_files` `git add -f` retry) is
already resolved in current main (`mu/tools/executors/phase_b_executor.py:1845-1874`
has no `-f` retry and fails closed via `return False`), so this wave
only addresses defect 1.

## Scope

Control-surface only. No runtime, substrate, host, projection, or seed changes.

**Files (2):**
- `mu/tools/executors/phase_b_executor.py` — reorder
  `_disposition_for_finding`: severity floor (critical/high always
  blocking) now runs BEFORE governance downgrade. Governance downgrade
  for `POLICY_BOUND`/`DOC_ACCURACY` on governance paths now only applies
  at medium/low severity.
- `mu/tests/tools/test_phase_b_executor.py` — invert
  `test_governance_path_downgrades_even_high_severity` (renamed to
  `test_high_critical_governance_findings_stay_blocking`) to assert the
  new severity-floor-first contract. Existing 37 disposition + governance
  tests continue to pass.

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel,
projection, seed, or runtime file.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`
- **Evidence delta:**
  1. Fixes the severity-floor-bypass defect: critical/high
     `POLICY_BOUND`/`DOC_ACCURACY` findings on governance paths now
     block the bridge review instead of being silently downgraded.
  2. Closes the blocking-deferred entry
     `deferred_consolidation_phaseb_fail_closed_hardening_2026-04-02.md`
     (defect 1; defect 2 was already fixed).
  3. 38 classification/governance tests pass (37 existing + 1 inverted);
     full phase_b executor test module (254 tests) stays green.
- **Indicator artifact:** `reports/l4_wave_indicators/phase-b-severity-floor-fix-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:phase-b-severity-floor-fix-2026-04-17
  (founder authorized in-session via "do both waves" + "be autonomous
  with both waves try to use pipeline with dispatcher as much as you
  can ... structurally, root issue")

## Verification Plan

Pre-push-fast (commit_executor step 11) runs the full ratchet sweep and
enforce_l4_execution_contract.py.

Step 8b runs targeted pytest on `mu/tests/tools/test_phase_b_executor.py`
(254 tests, 2:14 runtime locally).

## Stop Conditions

- Abort if any phase_b_executor test regresses.
- Abort if host-semantics or authority-inventory ratchet changes.

## Closeout

On merge, archive
`reports/deferred/blocking/deferred_consolidation_phaseb_fail_closed_hardening_2026-04-02.md`
to `reports/deferred/archive/` with `_CLOSED_by_PR<N>` suffix. commit_executor's
step 16 (from PR #782) automatically cleans up this wave's worktree +
branch post-merge when the full flow completes.
