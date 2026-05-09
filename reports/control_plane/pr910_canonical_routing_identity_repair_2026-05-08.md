# PR #910 Canonical Routing Identity Repair

Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Date: 2026-05-08
Wave ID: founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06
Repair ID: pr910-canonical-routing-identity-repair-2026-05-08
Class: L4_ENABLER
Target gate: G8
Source wave: founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06

## Scope

Repair the dispatcher control-plane path surfaced by the PR #910 bot review during commit-executor Step 15.

This packet does not authorize new `/mu` production implementation, Python/JavaScript host runtime semantics, Stage0 changes, seed changes, scheduler changes, registry changes, or Claude-related edits.

## Root-Cause Evidence

The PR #910 bot review flagged `mu/tools/executors/executor_dispatch.py:2830`: dispatcher enriched a stale inline routing record from `TASKS.md` before checking whether the inline record still matched the canonical routing file. When `tracked_packet` was backfilled, the in-memory record no longer matched `.agent_bus/meta/post_merge_routing.json`, so a stale canonical record could be misclassified as caller-owned and refused before auto-refresh.

The commit executor then attempted the bot remediation, but pre-commit rejected the commit because `mu/tools/executors/executor_dispatch.py` changed without a staged tracker update:

```text
TRACKER SYNC VIOLATION
Tracker-relevant files changed, but STATUS.md/TASKS.md were not updated.
Tracker-relevant files changed:
  - mu/tools/executors/executor_dispatch.py
```

## Implemented Repair

`mu/tools/executors/executor_dispatch.py` now preserves the pre-enrichment routing record for canonical identity comparison and still uses the enriched record for downstream completed-packet/task and plan-name selection.

`mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_canonical_inline_record_matches_before_tracked_packet_enrichment` locks the regression: a stale inline record that byte-matches the canonical routing file before `TASKS.md` enrichment still auto-refreshes, while the existing caller-owned inline tests remain fail-closed.

## PR #911 Follow-Up

The PR #911 bot review flagged the same-wave commit-retry demotion path in `mu/tools/executors/commit_executor.py`. The repair narrows demotion so pre-validation failures cannot rewrite completed packet or TASKS state: `_maybe_demote_completed_handoff_state_for_commit_retry` now requires `steps_completed` to be a list and to contain `validate_receipt` before demoting, in addition to the existing `git_commit`/`commit_sha` stop.

`mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_pre_validation_failure_does_not_demote_completed_packet_state` proves an early `validate_inputs` error leaves a completed packet and matching TASKS entry unchanged.

## Evidence

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_canonical_inline_record_matches_before_tracked_packet_enrichment --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_pre_validation_failure_does_not_demote_completed_packet_state --tb=short
python3 -m py_compile mu/tools/executors/executor_dispatch.py mu/tests/tools/test_executor_dispatch.py
bash tools/checks/enforce_tracker_sync.sh --files mu/tools/executors/executor_dispatch.py mu/tests/tools/test_executor_dispatch.py TASKS.md
```

Observed local results:

- focused regression: `1 passed in 0.52s`
- syntax compile: exit `0`
- tracker sync: `Tracker sync OK: core changes include STATUS.md/TASKS.md update.`

## Acceptance

- Canonical routing identity is compared against the original inline record before enrichment.
- TASKS-derived `tracked_packet` enrichment remains available for downstream packet selection.
- Caller-owned inline stale routing records remain fail-closed.
- The repair is committed as `L4_ENABLER`, not as a false `/mu` structural runtime delta.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/pr910_canonical_routing_identity_repair_2026-05-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `55b915cca3ff3e0206abd86c6b2efa2db9ba2257462aaf8d13da16be41d305ce`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_canonical_inline_record_matches_before_tracked_packet_enrichment --tb=short && python3 -m py_compile mu/tools/executors/executor_dispatch.py mu/tests/tools/test_executor_dispatch.py && bash tools/checks/enforce_tracker_sync.sh --files mu/tools/executors/executor_dispatch.py mu/tests/tools/test_executor_dispatch.py TASKS.md`.
- Evidence delta: PR #910 bot review showed dispatcher compared canonical identity after `_enrich_founder_ordered_tracked_packets` had backfilled `tracked_packet`; dispatcher now preserves the pre-enrichment record for `_matches_canonical_routing_record`, and the regression proves canonical inline records missing `tracked_packet` still auto-refresh while noncanonical caller-owned inline records remain fail-closed.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/pr910_canonical_routing_identity_repair_2026-05-08.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
