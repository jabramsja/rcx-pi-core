# Deferred Consolidation E5/E6 Closeout

Date: 2026-04-30
Status: COMMIT_READY
Task: [DEFERRED-CONSOLIDATION]
Wave ID: deferred-consolidation-e5-e6-closeout-2026-04-30
Wave-ID: deferred-consolidation-e5-e6-closeout-2026-04-30
Class: L4_ENABLER
Lane: control-surface (deferred cleanup)

## Scope

- `mu/tools/observability/_pane_prci.sh`
- `mu/tests/tools/test_pane_prci_observability.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tests/tools/test_commit_executor_receipt.py`
- `TASKS.md`
- `reports/control_plane/plan_deferred_consolidation_e5_e6_2026_04_02_2026-04-06.md`
- `reports/control_plane/wave1b_pipeline_cleanup_2026-03-31.md`
- `reports/deferred/non_blocking/wave1_pipeline_consolidated_2026-03-31.md`
- `reports/deferred/non_blocking/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06_bridge_nonblockers.md`
- `reports/deferred/archive/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06_bridge_nonblockers_CLOSED_by_deferred-consolidation-e5-e6-closeout-2026-04-30.md`
- `reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json`

## Work Items

1. Close the remaining E5 deferred non-blocking finding by stripping C1 controls from displayed PR/CI pane bot comments.
2. Add targeted regression coverage proving `U+009B` does not survive pane rendering.
3. Refresh active tracker/report surfaces so E5/E6 are landed and D1 remains the only open code-backed [DEFERRED-CONSOLIDATION] residue.
4. Archive the active E5/E6 deferred non-blocking packet as closed with validation evidence.
5. Make commit-executor staging idempotent for already-staged deleted handoff paths discovered while rerunning this closeout through the commit path.

## Constraints

- Do not reopen PR #843 implementation scope.
- Do not implement D1 dialectic `max_rounds` in this closeout wave.
- Do not widen beyond the PR/CI pane sanitizer, tests, and tracker/report cleanup needed to remove stale E5/E6 active truth.
- Commit-executor changes are limited to the stage-files deletion rerun gap surfaced by this wave's commit path.

## Acceptance Criteria

- `sanitize_pane_text()` strips C1 controls (`U+0080..U+009F`) before displayed bot comments reach the tmux pane.
- `mu/tests/tools/test_pane_prci_observability.py` covers the C1 sanitizer regression.
- `TASKS.md` and Wave 1B report surfaces mark E5/E6 landed while leaving D1 open.
- The active E5/E6 non-blocking packet is archived as CLOSED.
- Re-running Step 4 against a handoff path that is already staged as deleted does not fail on a plain `git add <missing path>` pathspec error.
- L4 indicator artifact exists for this closeout wave.

## Grounding / Authorization

FOUNDER_OVERRIDE:deferred-consolidation-e5-e6-closeout-2026-04-30

Authorization: narrow founder-directed tracker cleanup and pipeline hardening follow-through under [DEFERRED-CONSOLIDATION]. The first direct root cause for this packet is the commit executor evidence from `python3 mu/tools/executors/commit_executor.py --handoff .agent_bus/executors/deferred_consolidation_e5_e6_closeout_handoff.json --json`: `refresh_commit_packet_truth` failed because the handoff wave id was `deferred-consolidation-e5-e6-closeout-2026-04-30` while the active tracked packet was the older E5/E6 packet with a different Wave ID. This packet gives the closeout wave a matching tracked-packet authority surface instead of reusing a mismatched historical packet. The second direct root cause is the rerun evidence from the same command after adding this packet: `stage_files` failed with `fatal: pathspec 'reports/deferred/non_blocking/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06_bridge_nonblockers.md' did not match any files`; `git status --short --branch` showed that path as `D` staged, and `git ls-files --stage -- <path>` returned no index entry. The commit-executor fix makes staged deletion handling idempotent for reruns by skipping already staged deletes and using `git add -u` for unstaged tracked deletes.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pane_prci_observability.py` -> `9 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_stage_handoff_paths_is_idempotent_for_staged_deletion` -> passed.
- `git diff --check` -> passed.
- `bash tools/checks/check_stale_next_items.sh` -> all merged PR references in NEXT are marked.
- `./tools/checks/check_docs_consistency.sh` -> all checks passed, with the standing STATUS freshness warning.
- `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id deferred-consolidation-e5-e6-closeout-2026-04-30 --output reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json --range HEAD` -> indicator artifact written.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `deferred-consolidation-e5-e6-closeout-2026-04-30`
- Active packet: `reports/control_plane/deferred_consolidation_e5_e6_closeout_2026-04-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c59c6f4d0227a72a4844c95965f6bd68f83e54984311fc1dfb24e21eb16a2c72`
- Indicator artifact: `reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipt.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pane_prci_observability.py mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_stage_handoff_paths_is_idempotent_for_staged_deletion && python3 -m py_compile mu/tools/executors/commit_executor.py && git diff --check && bash tools/checks/check_stale_next_items.sh && ./tools/checks/check_docs_consistency.sh`.
- Evidence delta: (1) `_pane_prci.sh` sanitizer strips C1 controls (`U+0080..U+009F`) in addition to ESC/C0/DEL before rendering bot comments. (2) `test_displayed_bot_comment_text_strips_c1_controls` proves `U+009B` no longer reaches pane output. (3) `commit_executor` Step 4 now treats missing handoff paths that are already staged deletions as idempotent and uses `git add -u` for unstaged tracked deletes. (4) TASKS.md and Wave 1B report surfaces now mark E5/E6 landed while leaving D1 dialectic max_rounds as the remaining code-backed residue. (5) The active E5/E6 deferred nonblocking packet is archived as CLOSED with validation evidence, and the closeout has a matching tracked packet for commit truth refresh.
- Evidence handles:
  - `archived_nonblocker`: `reports/deferred/archive/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06_bridge_nonblockers_CLOSED_by_deferred-consolidation-e5-e6-closeout-2026-04-30.md`
  - `indicator`: `reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipt.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_pane_prci_observability.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/observability/_pane_prci.sh`
  - `reports/control_plane/deferred_consolidation_e5_e6_closeout_2026-04-30.md`
  - `reports/control_plane/plan_deferred_consolidation_e5_e6_2026_04_02_2026-04-06.md`
  - `reports/control_plane/wave1b_pipeline_cleanup_2026-03-31.md`
  - `reports/deferred/archive/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06_bridge_nonblockers_CLOSED_by_deferred-consolidation-e5-e6-closeout-2026-04-30.md`
  - `reports/deferred/non_blocking/plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/wave1_pipeline_consolidated_2026-03-31.md`
  - `reports/l4_wave_indicators/deferred-consolidation-e5-e6-closeout-2026-04-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
