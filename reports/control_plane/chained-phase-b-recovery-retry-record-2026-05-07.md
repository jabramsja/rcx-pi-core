# Chained Phase B Recovery Retry Record Repair 2026-05-07

Date: 2026-05-07
Status: Implemented - pending commit
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: chained-phase-b-recovery-retry-record-2026-05-07
Class: L4_ENABLER
Category: tooling/control-plane pipeline repair
Source authorization: FOUNDER_OVERRIDE:chained-phase-b-recovery-retry-record-2026-05-07

## Scope

Repair the dispatcher recovery path discovered while executing
`deferred-non-mu-docs-control-plane-remediation-2026-05-07`.

In scope:

- Preserve the Phase B retry authority produced by the Phase A -> Phase B chain
  when Phase B recovers in process but needs to be retried before commit.
- Prevent recovered chained Phase B attempts from refreshing the post-merge
  package and re-entering Phase A for the same already-locked packet.
- Add focused dispatcher regression coverage for the reproduced loop.

Out of scope:

- `/mu` structural runtime, seed, Stage0, parity, or production changes.
- Claude-related residue.
- The docs/control-plane remediation implementation itself; its Phase A plan was
  preserved separately and must resume after this repair lands.

## Root-Cause Evidence

- Live dispatcher output reproduced the loop twice:
  `Phase A converged -> chaining to Phase B with plan ...`,
  `Recovery: class=stale_git_index_lock tier=2 recovered=True`,
  `Running: ... meta_bridge_supervisor.py --mode post-merge ...`, then
  `Auto-refresh succeeded: decision=ROUTE_PHASE_A`.
- Recovery status recorded the failed retry target as Phase B:
  `.agent_bus/recovery/recovery_status.json` carried
  `step: restore_branch_switch_stash`, `failure_class: stale_git_index_lock`,
  `retry_target: phase_b_executor`, `recovered: true`.
- Code truth before the fix: `mu/tools/executors/executor_dispatch.py:3247-3262`
  handled in-process recovery by clearing Phase B state and then reloading the
  explicit routing record or auto-refreshing post-merge routing. In the loop
  case, the post-merge package still selected the docs packet, so refresh
  correctly returned `ROUTE_PHASE_A` and repeated Phase A instead of retrying
  Phase B.

## Implemented Fix

- `mu/tools/executors/executor_dispatch.py` now attaches the Phase B routing
  record to recovered in-process Phase B results and consumes that retry record
  before explicit routing reload or post-merge auto-refresh.
- The same retry-record handling is applied to recovered retry attempts from the
  normal recovery branch, so recovered executor-owned retry authority wins before
  stale external routing authority.
- `mu/tests/tools/test_executor_dispatch.py` adds a regression proving a
  recovered chained Phase B retry runs with `ROUTE_PHASE_B` and does not call
  post-merge auto-refresh back to Phase A.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_in_process_phase_b_recovery_retries_retry_record_not_phase_a mu/tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_in_process_phase_b_recovery_retries_before_commit_chain mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_phase_b_surface_retries_when_phase_b_recovered_without_handoff -vv --tb=short`
  exited `0` with `3 passed in 0.07s`.
- `python3 -m py_compile mu/tools/executors/executor_dispatch.py` exited `0`.
- `git diff --check` exited `0`.
- `python3 mu/tools/checks/linters/check_private_attr_access.py mu/tests/tools/test_executor_dispatch.py`
  exited `0`.

## Resume Instruction

After this repair lands, restore the preserved docs Phase A plan and resume
`deferred-non-mu-docs-control-plane-remediation-2026-05-07` through the
dispatcher from Phase B or the full loop as appropriate. Stop before `/mu`
structural remediation.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `chained-phase-b-recovery-retry-record-2026-05-07`
- Active packet: `reports/control_plane/chained-phase-b-recovery-retry-record-2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `640c76838206acfadffb138a08c5ef35a371d30d1d7cea94ab9feda861100f49`
- Indicator artifact: `reports/l4_wave_indicators/chained-phase-b-recovery-retry-record-2026-05-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/chained-phase-b-recovery-retry-record-2026-05-07.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/chained-phase-b-recovery-retry-record-2026-05-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/chained-phase-b-recovery-retry-record-2026-05-07.md`
  - `reports/l4_wave_indicators/chained-phase-b-recovery-retry-record-2026-05-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
