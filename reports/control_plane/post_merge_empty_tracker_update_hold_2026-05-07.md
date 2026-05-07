# Post-Merge Empty Tracker Update Hold

Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-merge-empty-tracker-update-hold-2026-05-07
Class: L4_ENABLER
Target Gate: G8
Lane: control-surface (dispatcher / commit automation)
Founder authorization: standing pipeline-bug-fix authorization.
Founder override: FOUNDER_OVERRIDE:post-merge-empty-tracker-update-hold-2026-05-07
Tracked packet: reports/control_plane/post_merge_empty_tracker_update_hold_2026-05-07.md

## Problem

After PR #898, the refreshed post-merge package correctly preserved the
`/mu` structural hard stop by writing no `next_candidates`, but the post-merge
supervisor still emitted an `UPDATE_TRACKER_ONLY` routing record. The dispatcher
then routed that empty tracker update into `commit_executor`, which synthesized
a `TASKS.md`-only handoff and reached the L4 gate as a fresh maintenance wave
instead of holding at the terminal queue boundary.

Root-cause evidence:

- `.agent_bus/meta/post_merge_package.json` had `next_candidates: []` and the
  tracker summary said the next open queue packet was a hard stop.
- `.agent_bus/meta/post_merge_routing.json` had
  `decision: UPDATE_TRACKER_ONLY` with no `next_candidates`,
  `files_to_stage`, `force_add_files`, or `tracker_note_text`.
- `mu/tools/executors/executor_dispatch.py:121-127` mapped
  `UPDATE_TRACKER_ONLY` to `commit_executor`.
- `mu/tools/executors/executor_dispatch.py:2751-2754` passed
  `UPDATE_TRACKER_ONLY` records to commit executor with `--routing-record`.
- `mu/tools/executors/commit_executor.py:5260-5275` defaulted empty
  tracker-only records to `files_to_stage = ["TASKS.md"]`.
- The reproduced live dispatch before this repair failed at the L4 contract:
  `Non-structural adjacency cap violated` and `Rolling structural quota
  violated`, because the synthesized tracker-only wave had no founder override.

## Mechanical Fix

- `executor_dispatch.py` now treats an `UPDATE_TRACKER_ONLY` record with no
  explicit tracker note, file scope, force-add scope, tracked packet, or
  candidate files as a terminal held outcome before invoking any executor.
- `commit_executor.py` now applies the same defense when called directly with an
  empty non-standalone tracker-only routing record, so the dispatcher is not the
  only fail-closed layer.
- The commit-executor direct-call guard uses nonblank scope semantics for
  `tracker_note_text`, `files_to_stage`, and `force_add_files`, matching the
  dispatcher guard instead of accepting whitespace-only strings or blank list
  entries as actionable scope.
- Existing valid tracker-only handoffs remain routable when the routing record
  declares explicit `files_to_stage`, candidate files, `force_add_files`,
  `tracker_note_text`, or a tracked packet.

## Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_receipt.py -q`
  exited `0` and reached `[100%]`.
- `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --json -v`
  exited `0` and returned `status: held` with
  `Refusing to synthesize a TASKS.md-only handoff.`
- Pre-commit supervisor Round 1 returned `NEEDS_PHASE_B` because the direct
  commit-executor guard was truthiness-based; same-wave repair added direct
  regressions for whitespace-only `tracker_note_text`, blank `files_to_stage`,
  and blank `force_add_files`.

## Boundary

- No `/mu` structural runtime, substrate, Stage0, seed, scheduler, registry, or
  production semantics are changed.
- This wave is control-plane tooling only.
- The hard stop before implementing
  `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
  remains in force.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-empty-tracker-update-hold-2026-05-07`
- Active packet: `reports/control_plane/post_merge_empty_tracker_update_hold_2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2cf6a9c36abc17106fd543b78cc42a2fdab33e9d60690cfdb24e7a10f1f9f85c`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-empty-tracker-update-hold-2026-05-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 7 wave-owned file(s). (2) Evidence gate exercises 2 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/post-merge-empty-tracker-update-hold-2026-05-07.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-empty-tracker-update-hold-2026-05-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/post_merge_empty_tracker_update_hold_2026-05-07.md`
  - `reports/l4_wave_indicators/post-merge-empty-tracker-update-hold-2026-05-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
