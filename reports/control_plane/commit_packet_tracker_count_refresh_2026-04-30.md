---
DOC_STATUS: tracked_packet
wave_id: commit-packet-tracker-count-refresh-2026-04-30
wave_class: L4_ENABLER
target_gate_id: G8
created: 2026-04-30
status: Commit-ready local implementation
---

# Commit Packet Tracker Count Refresh

Date: 2026-04-30
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: commit-packet-tracker-count-refresh-2026-04-30
Phase-A-Lock: LOCKED
Wave class: L4_ENABLER
Target gate: G8
Lane: control-surface
Authorization: standing pipeline-bug-fix authorization for bounded control-surface L4_ENABLER pipeline hardening; commit automation may derive `FOUNDER_OVERRIDE:commit-packet-tracker-count-refresh-2026-04-30` for L4 adjacency/rolling-cap clearance.

FOUNDER_OVERRIDE:commit-packet-tracker-count-refresh-2026-04-30

## Purpose

Mechanize the tracker-note count repair that was still manual after the prior
commit packet truth-refresh hardening. When `commit_executor` refreshes a
packet-bound handoff after Step 5 adds generated scope such as the L4 indicator
and tracked packet, the rebuilt handoff must carry tracker-note file counts that
match the actual refreshed staged scope.

This wave also hardens the post-remediation merge path observed while landing
this patch: `gh pr checks --watch --required` returned before GitHub branch
protection considered required checks complete, so the executor now performs a
separate required-check green verification before merge.

The same landing attempt exposed that the centralized Step 11 `pre_push_fast`
timeout was too narrow for the real `audit_fast.sh` path in this environment:
`pytest -n auto` was still active after 11:14 elapsed and the executor killed
the gate at the 900-second budget. The timeout is now raised in the shared
executor config instead of bypassing the pre-push gate.

The follow-up Step 8 targeted pytest gate then exposed stale dispatcher test
doubles for the new pre-merge CI guard. The failing evidence was an unexpected
`gh pr checks 673 --required` command in
`test_post_commit_ignores_prior_cycle_unresolved_bot_threads`, and a class-wide
run later showed the remaining affected post-commit tests. The tests now fake
the required-check registration, watch, and JSON green-snapshot paths instead
of letting the guard loop on empty stdout.

This is control-surface hardening only. It does not change runtime, substrate,
seed, Stage0, or Mu semantics.

## Observed Failure Truth

- During the `pager-lifecycle-event-coverage-2026-04-23` landing path, the
  supervisor noted that the staged package and diff carried 7 changed files while
  the tracker/control-plane text still said the handoff carried 11 wave-owned
  files.
- The code path that requires a structural fix is
  `mu/tools/executors/commit_executor.py` packet refresh:
  `_rebuild_handoff_after_packet_truth_refresh()` rebuilds through
  `build_commit_handoff()` with the refreshed `staged_paths`, but before this
  wave the rebuilt handoff reused the original tracker note prose unchanged.
- The default tracker note count phrases originate in
  `_build_default_tracker_note_text()` and are consumed by Gate 8 tracker-note
  validation. Leaving those phrases stale after a packet refresh makes the
  refreshed packet block accurate while the tracker note remains false.
- While landing this wave on PR #844, `commit_executor` reached merge after
  logging remediation CI green, but `merge_pr.sh` failed with
  `GraphQL: 2 of 2 required status checks are in progress`; direct
  `gh pr checks 844 --required --json name,state,link,bucket,startedAt,completedAt`
  showed `test` and `green-gate` as `IN_PROGRESS`.
- The next landing attempt reached Step 11 and failed with executor output
  `pre-push-fast timed out`; process inspection showed
  `pre-push-fast -> dev.sh -> tools/audits/audit_fast.sh -> pytest -n auto`
  still active after 11:14 elapsed while `pre_push_fast` was configured at
  900 seconds.
- The next follow-up attempt reached Step 8 and failed with executor output
  `targeted pytest gate failed (exit=-1): pytest timed out`; direct focused
  pytest output then identified the stale fake-run root at
  `mu/tests/tools/test_executor_dispatch.py:5100`, where the post-commit test
  rejected `['gh', 'pr', 'checks', '673', '--required']`.

## Scope

Admitted files:

1. `TASKS.md`
2. `mu/tools/executors/commit_executor.py`
3. `mu/tools/executors/executor_common.py`
4. `mu/tools/executors/executor_config.json`
5. `mu/tests/tools/test_commit_executor_receipt.py`
6. `mu/tests/tools/test_executor_dispatch.py`
7. `reports/control_plane/commit_packet_tracker_count_refresh_2026-04-30.md`
8. `reports/l4_wave_indicators/commit-packet-tracker-count-refresh-2026-04-30.json`

## Work Items

1. Add a bounded helper that updates only the generated wave-owned file-count
   phrases in a tracker note after packet truth refresh.
2. Call that helper from `_rebuild_handoff_after_packet_truth_refresh()` using
   the refreshed `len(staged_paths)` value before rebuilding the handoff through
   `build_commit_handoff()`.
3. Add a regression test that starts with a stale tracker note count, runs the
   packet truth refresh path, and proves the rebuilt handoff count matches the
   refreshed staged set.
4. Preserve existing idempotence and packet refresh behavior for other fields.
5. Add a required-check green guard that parses
   `gh pr checks --required --json name,state,bucket` after `gh --watch`
   returns.
6. Reuse the guard in remediation CI waits and immediately before merge so a
   stale/premature watch result cannot advance to `merge_pr.sh`.
7. Raise the centralized `pre_push_fast` timeout and cover that minimum in the
   executor config tests so recovery does not require a manual bypass.
8. Update dispatcher post-commit test doubles so recovery and commit executor
   targeted gates exercise the new required-check guard without hanging on
   empty fake check output.

## Constraints

- Do not replace `build_commit_handoff()` or introduce a second handoff format.
- Do not broaden markdown rewriting beyond the known generated count phrases.
- Do not bypass Gate 8, pre-commit supervisor review, L4 indicator collection,
  pre-push checks, or GitHub review/merge checks.
- Do not touch runtime, substrate, seed, Stage0, or parity surfaces.

## Acceptance Criteria

1. The packet truth refresh path updates stale tracker note file counts to the
   refreshed staged-file count before supervisor packaging.
2. Existing packet truth refresh tests remain green.
3. The implementation is validated by `py_compile` and focused
   `test_commit_executor_receipt.py` packet-refresh tests.
4. The remediation/pre-merge CI path waits until required checks are green and
   has regression coverage for a watch-zero/pending-required-check state.
5. Step 11 keeps enforcing `pre-push-fast` instead of bypassing it, with a
   timeout budget that covers the observed local fast-audit runtime.
6. Step 8 targeted dispatcher pytest passes with the pre-merge guard active,
   including the post-commit continuation class that previously carried stale
   fake `gh pr checks` behavior.

## Validation Evidence

- `python3 -m py_compile mu/tools/executors/commit_executor.py` passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_packet_truth_refresh_updates_rebuilt_handoff_file_count mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_packet_truth_refresh_is_idempotent mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_packet_truth_refresh_rebinds_packet_and_handoff_before_supervisor` passed: 3 passed in 2.52s.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_packet_truth_refresh_updates_rebuilt_handoff_file_count mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_packet_truth_refresh_rebinds_packet_and_handoff_before_supervisor` passed: 2 passed in 1.61s after the supervisor-requested TASKS/packet evidence follow-up.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py -k "commit_packet_truth_refresh"` passed: 6 passed, 73 deselected in 3.89s.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py` passed: 79 passed in 13.59s.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py -k "RequiredCIGreenGuard or CIPollFallbackTimeout or commit_packet_truth_refresh"` passed: 10 passed, 71 deselected in 4.08s.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py` passed: 81 passed in 13.79s.
- `git diff --check` passed after the CI/pre-merge guard patch.
- `./tools/checks/check_docs_consistency.sh` passed after the CI/pre-merge guard patch.
- `PYTHONHASHSEED=0 python3 -m pytest -q --import-mode=importlib mu/tests/tools/test_executor_dispatch.py::TestCommitContinuationAndBotFreshness` passed: 37 passed in 3.04s after updating the post-commit `gh pr checks` test doubles.
- `PYTHONHASHSEED=0 time python3 -m pytest -q --import-mode=importlib mu/tests/tools/test_executor_dispatch.py` passed: 413 passed in 52.79s.
- `python3 -m py_compile mu/tools/executors/commit_executor.py mu/tools/executors/executor_common.py` passed after the Step 8 test-double follow-up.
- `python3 -m json.tool mu/tools/executors/executor_config.json >/dev/null` passed after the Step 8 test-double follow-up.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/tools/test_executor_dispatch.py::TestDispatcherConfig::test_load_default_config tests/tools/test_executor_config_alignment.py::TestCommitExecutorConfigBinding::test_pre_push_fast_timeout_from_config` passed: 2 passed in 0.10s.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py -k 'RequiredCIGreenGuard'` passed: 2 passed, 79 deselected in 0.04s.
- `PYTHONHASHSEED=0 python3 -m pytest -q --import-mode=importlib mu/tests/tools/test_executor_dispatch.py::TestCommitContinuationAndBotFreshness` passed: 37 passed in 2.60s.
- `git diff --check` passed after the Step 8 test-double follow-up.
- `./tools/checks/check_docs_consistency.sh` passed after the packet/test follow-up: all checks passed.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `commit-packet-tracker-count-refresh-2026-04-30`
- Active packet: `reports/control_plane/commit_packet_tracker_count_refresh_2026-04-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2c98c5684090e2958be2c574f38d1994493cefaa5de4180f7adbce5eacef5b6e`
- Indicator artifact: `reports/l4_wave_indicators/commit-packet-tracker-count-refresh-2026-04-30.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipt.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 6 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/commit-packet-tracker-count-refresh-2026-04-30.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/commit-packet-tracker-count-refresh-2026-04-30.json`
  - `packet`: `reports/control_plane/commit_packet_tracker_count_refresh_2026-04-30.md`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipt.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/commit_packet_tracker_count_refresh_2026-04-30.md`
  - `reports/l4_wave_indicators/commit-packet-tracker-count-refresh-2026-04-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
