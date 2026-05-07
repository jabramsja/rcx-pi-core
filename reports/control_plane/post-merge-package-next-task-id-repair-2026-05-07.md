# Post-Merge Package Next Task-ID Repair 2026-05-07

Date: 2026-05-07
Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-merge-package-next-task-id-repair-2026-05-07
Class: L4_ENABLER
Category: tooling/control-plane pipeline repair
Source authorization: FOUNDER_OVERRIDE:post-merge-package-next-task-id-repair-2026-05-07

## Scope

This repair is limited to commit-executor post-merge package construction for
the founder-ordered remediation queue. It does not authorize `/mu` structural
implementation or Claude-related edits.

## Root-Cause Evidence

After the queue-selection repair merge, `.agent_bus/meta/post_merge_package.json`
correctly selected
`deferred-non-mu-docs-control-plane-remediation-2026-05-07` as the next wave,
but kept the just-merged repair handoff task id:
`[deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07]`.

The post-merge supervisor then refreshed
`.agent_bus/meta/post_merge_routing.json` to `CONTINUE_DIALECTIC` instead of
`ROUTE_PHASE_A`; the validation errors were:

- `tracker_consistency: task_id [deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07] not found in NOW or NEXT sections`
- `rollout_packet_canonical: task_id [deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07] not found in TASKS.md NOW/NEXT`

Direct code inspection tied the mismatch to
`mu/tools/executors/commit_executor.py`, where Step 15b selected the next queue
entry for `wave_name` and `next_candidates`, but copied `task_id` from the
completed commit handoff.

## Implemented Fix

- Post-merge queue packages now use the canonical founder-ordered queue task id
  `[NEXT-CODEX-POST-REDTEAM]` instead of the just-merged handoff task id.
- Existing next-wave selection still comes from the open queue entry.
- A regression proves that a completed repair-wave handoff does not leak its
  task id into the next docs/control-plane post-merge package.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_routes_open_tracker_packet_before_hard_stop`
- `python3 -m py_compile mu/tools/executors/commit_executor.py`

## Stop Boundary

After this pipeline repair lands, rerun dispatcher from the refreshed
post-merge package. Hard stop before implementing either `/mu` structural
packet.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-package-next-task-id-repair-2026-05-07`
- Active packet: `reports/control_plane/post-merge-package-next-task-id-repair-2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ceec6bb2bf5de7551da4469bb7d42f4718b9bd65822b15dd5be1af8c1e31858b`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-package-next-task-id-repair-2026-05-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/post-merge-package-next-task-id-repair-2026-05-07.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-package-next-task-id-repair-2026-05-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/post-merge-package-next-task-id-repair-2026-05-07.md`
  - `reports/l4_wave_indicators/post-merge-package-next-task-id-repair-2026-05-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
