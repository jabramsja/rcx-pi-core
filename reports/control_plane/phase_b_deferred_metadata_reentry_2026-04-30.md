# Phase B Deferred Metadata Re-entry - 2026-04-30

Wave ID: phase-b-deferred-metadata-reentry-2026-04-30
Task: [PIPELINE-RECOVERY]
Class: L4_ENABLER
Lane: control-surface
target_gate_id: G8

## Authorization

Standing pipeline-bug-fix authorization applies to control-surface hardening.
This packet is bounded to Phase B deferred non-blocking packet metadata during
NEEDS_PHASE_B re-entry and cleanup of the matching stale deferred finding.

FOUNDER_OVERRIDE:phase-b-deferred-metadata-reentry-2026-04-30

## Root Cause Evidence

- `reports/deferred/non_blocking/pipeline-control-surface-split-2026-04-14_bridge_nonblockers.md`
  recorded: "Phase B re-entry deferred-packet refresh still drops wave metadata
  to unknown".
- Direct code evidence before this fix: the normal Phase B GO/review paths in
  `mu/tools/executors/phase_b_executor.py` passed `wave_class=wave_class` and
  `target_gate_id=target_gate_id` into `_sync_deferred_non_blocking_state()`.
  The two re-entry paths called the same helper without those keyword
  arguments, causing `_write_deferred_packet()` to render `Class: unknown` and
  `Target Gate: unknown`.

## Fix

- Threaded `wave_class` and `target_gate_id` through both Phase B re-entry
  deferred-packet refresh call sites.
- Added a regression that forces a NEEDS_PHASE_B re-entry where the second
  bridge review returns GO with a non-blocking finding, then verifies the
  refreshed deferred packet contains `Class: L4_ENABLER` and `Target Gate: G8`.
- Cleaned the active `pipeline-control-surface-split-2026-04-14` deferred
  packet so the now-fixed metadata finding is closed and only the still-open
  dashboard labeling finding remains.

## Validation

- `python3 -m py_compile mu/tools/executors/phase_b_executor.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestResumeNeedsPhaseB::test_reentry_go_preserves_deferred_packet_wave_metadata mu/tests/tools/test_phase_b_executor.py::TestResumeNeedsPhaseB::test_reentry_go_without_non_blocking_clears_stale_deferred_packet`
  - Result: `2 passed in 0.45s`
- `./tools/checks/check_docs_consistency.sh`
  - Result: all checks passed; existing STATUS freshness warning remained.

## Scope

- `mu/tools/executors/phase_b_executor.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `reports/deferred/non_blocking/pipeline-control-surface-split-2026-04-14_bridge_nonblockers.md`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-deferred-metadata-reentry-2026-04-30`
- Active packet: `reports/control_plane/phase_b_deferred_metadata_reentry_2026-04-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f2b1ec0e0cd5e2d7938583265991a2b434b083f16789f54fd4faf6b8b52ba28c`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-deferred-metadata-reentry-2026-04-30.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipt.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Routed commit handoff scopes 6 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/phase-b-deferred-metadata-reentry-2026-04-30.json..
- Evidence handles:
  - `docs_consistency`: `all checks passed; existing STATUS freshness warning only`
  - `indicator`: `reports/l4_wave_indicators/phase-b-deferred-metadata-reentry-2026-04-30.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipt.json`
  - `targeted_pytest`: `2 passed`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase_b_deferred_metadata_reentry_2026-04-30.md`
  - `reports/deferred/non_blocking/pipeline-control-surface-split-2026-04-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-b-deferred-metadata-reentry-2026-04-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
