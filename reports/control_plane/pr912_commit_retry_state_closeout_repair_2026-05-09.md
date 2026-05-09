# PR 912 Commit Retry State Closeout Repair

Date: 2026-05-09
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pr912-commit-retry-state-closeout-repair-2026-05-09
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: control-plane pipeline closeout
Severity: BLOCKING
Founder override: FOUNDER_OVERRIDE:pr912-commit-retry-state-closeout-repair-2026-05-09

## Scope

- `mu/tools/executors/commit_executor.py`
  - Restore retry-demoted packet and `TASKS.md` queue state before the final
    supervisor receipt review, then demote it again on any later failure before
    `git_commit`.
  - Keep the fix bounded to control-plane retry state; do not add Python or
    JavaScript runtime semantics.
- `mu/tests/tools/test_commit_executor_receipt.py`
  - Regressions for an `L4_STRUCTURAL` retry-demoted packet/TASKS pair restoring
    before receipt review, and for demoting back to retry-pending state when
    receipt validation or handoff persistence fails after restoration.
- `TASKS.md`
  - Close PR #912 structural blocking state and record this pipeline closeout
    repair.
- `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
  - Close the merged PR #912 packet and record the closeout-state repair.
- `reports/deferred/**`
  - Archive the now-closed blocking source snapshot and sync active deferred
    inventory.
- `tools/checks/check_stale_next_items.sh`
  - Make `--fix` apply the mechanical stale-NEXT repair advertised by the
    pre-push hook, while preserving canonical tracker-note prefixes.

## Root Cause

PR #912 merged successfully, but closeout verification found the merged packet
and matching `TASKS.md` queue entry still carried:

```text
IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
```

That state is intentionally not completed: `packet_status_is_completed()` treats
pending statuses as open so dispatcher can re-enter after a post-receipt,
pre-commit failure. The final structural retry path did not promote that
retry-demoted state before commit, so the post-merge package mechanically
selected the already-merged structural blocking packet as the next open queue
entry.

PR #913 bot review then found the first closeout repair restored retry-demoted
state before the final supervisor receipt chain had validated, while retry
demotion was only armed for post-validation failures. A Step 6 or early Step 7
failure could therefore leave packet/TASKS state completed without a fresh
commit. The same-wave repair keeps restoration before receipt review so the
receipt binds the restored staged content, and records `restore_commit_retry_state`
as the demotion arming point for any later failure before `git_commit`.

The next supervisor pass found one remaining ordering gap: restoration was
recorded only after the fallible durable handoff persist succeeded. A persist
failure after packet/TASKS restoration but before recording
`restore_commit_retry_state` could leave completed state restored without arming
the retry demotion wrapper.

## Mechanical Fix

`commit_executor.py` now restores retry-demoted packet and `TASKS.md` queue
state to `IMPLEMENTED / LOCAL EVIDENCE` before the final supervisor receipt
review. The executor records `restore_commit_retry_state` immediately after
restoration succeeds, before persisting the refreshed handoff scope or invoking
the supervisor; it also records the restored handoff sha and rekeys the
continuation when safe.

This keeps demotion available for dispatcher re-entry after the failure, but
prevents the committed branch from leaving the founder queue open after a
successful retry.

The retry-demotion guard now also treats `restore_commit_retry_state` as the
arming point for later failures before `git_commit`, so a post-restore
pre-commit or pre-push failure demotes packet/TASKS state back to
`IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT`.

Restoration is skipped when a legacy or standalone handoff has no tracked
control-plane packet, so receipt-chain paths without packet state do not fail
with a false `tracked_packet is empty` error.

The pre-push stale-NEXT checker now applies its advertised `--fix` mode instead
of only printing advice. The fixer marks merged PR references in the active
NEXT section as `**Landed**`, and preserves `- Tracker sync note` prefixes so
commit-executor tracker parsing remains canonical.

## Closeout Sync

- PR #912 merged the structural blocking remediation.
- The PR #912 packet status is now `CLOSED - MERGED BY PR #912 (2026-05-09)`.
- The matching `TASKS.md` queue state is closed.
- The closed blocking source snapshot moved from `reports/deferred/blocking/`
  to `reports/archive/deferred/`.
- Active deferred blocking inventory is now README-only.
- Remaining active deferred non-blocking packets are `/mu` structural advisory
  records and remain hard-stopped before production implementation.
- The stale PR #912 NEXT references are marked `**Landed**` by
  `bash tools/checks/check_stale_next_items.sh --fix`.

## Validation

```text
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_retry_pending_state_restored_before_receipt_review mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_retry_pending_state_demotes_again_when_receipt_validation_fails mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_retry_pending_state_demotes_again_when_handoff_persist_fails --tb=short
```

Result: exit `0`; `3 passed in 2.09s`.

```text
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short
```

Result: exit `0`; `110 passed in 22.96s`.

```text
python3 -m py_compile mu/tools/executors/commit_executor.py mu/tests/tools/test_commit_executor_receipt.py
```

Result: exit `0`.

```text
python3 mu/tools/checks/linters/check_private_attr_access.py mu/tests/tools/test_commit_executor_receipt.py
```

Result: exit `0`.

```text
./tools/checks/check_docs_consistency.sh
```

Result: exit `0`; all checks passed.

```text
bash -n tools/checks/check_stale_next_items.sh
```

Result: exit `0`.

```text
bash tools/checks/check_stale_next_items.sh --fix
```

Result: exit `0`; printed
`FIXED: marked 2 stale NEXT item(s) as Landed in TASKS.md`, then re-ran the
checker and printed `All NEXT items with merged PRs are properly marked`.

```text
git diff --check
```

Result: exit `0`.

## Stop Boundary

The next open founder-ordered queue item is `/mu` structural non-blocking and is
hard-stopped before production implementation. This packet does not authorize
that wave.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr912-commit-retry-state-closeout-repair-2026-05-09`
- Active packet: `reports/control_plane/pr912_commit_retry_state_closeout_repair_2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `17f93360a20e6f7dd4d38a2d7d38841aefd58ccfef1813d390d9118ef788f06d`
- Indicator artifact: `reports/l4_wave_indicators/pr912-commit-retry-state-closeout-repair-2026-05-09.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short && python3 -m py_compile mu/tools/executors/commit_executor.py mu/tests/tools/test_commit_executor_receipt.py && ./tools/checks/check_docs_consistency.sh && git diff --check`.
- Evidence delta: (1) Commit executor restores retry-demoted packet/TASKS state before final supervisor receipt review and records retry-demotion authority immediately after restoration succeeds, so the supervisor receipt binds the restored staged content and post-restoration handoff-persist, pre-commit, and pre-push failures demote state again before dispatcher re-entry. (2) Empty `tracked_packet` handoffs skip restoration instead of failing the full receipt-chain proof. (3) PR #912 structural blocking packet and TASKS queue state are closed. (4) The closed blocking source snapshot moved to `reports/archive/deferred/`, leaving `reports/deferred/blocking/` README-only and four active `/mu` structural non-blocking advisory packets.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr912-commit-retry-state-closeout-repair-2026-05-09.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr912_commit_retry_state_closeout_repair_2026-05-09.md`
  - `reports/l4_wave_indicators/pr912-commit-retry-state-closeout-repair-2026-05-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
