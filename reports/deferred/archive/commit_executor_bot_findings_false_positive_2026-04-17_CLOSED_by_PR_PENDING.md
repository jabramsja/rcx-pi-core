# BLOCKING: commit_executor bot-finding resolution cannot handle false positives

**Date filed**: 2026-04-17
**Observed on**: PR #783 (observability-pane-and-deferred-doc-cleanup-2026-04-17)
**Severity**: BLOCKING (paired with CI-poll timeout bug, guarantees cascade on any false-positive bot P2)

## Symptom

When a bot (`chatgpt-codex-connector`) posts a P2 finding that is a FALSE POSITIVE
(references a symbol that does not exist in source, or a pattern already satisfied
by a prior commit), commit_executor step 15's remediation loop has no way to
detect "this is not fixable because there's nothing to fix". The adapter may produce
an empty or cosmetic diff; commit_executor re-checks bot findings after the push;
the bot has not updated or retracted its comment; the finding stays listed
indefinitely; commit_executor concludes `bot_findings_pending` status.

## Root cause (file:line)

- `mu/tools/executors/commit_executor.py:1751-2093` — `_attempt_bot_finding_remediation()`
  runs up to `BOT_REMEDIATION_MAX_ROUNDS` (2). After each round, re-fetches findings
  from GitHub and treats "finding still listed" as "not resolved".
- `mu/tools/executors/commit_executor.py:1671-1748` — `_auto_defer_bot_findings()` DOES
  handle the false-positive case: writes a deferred report + resolves bot review threads
  via GraphQL mutation `resolveReviewThread`. But this path only fires when the
  remediation adapter returns `no_changes_produced=True`, AND only if the preceding
  CI check didn't classify as failure.

## Interaction with CI-poll timeout bug

When commit_executor falsely concludes "CI failed after remediation round 1" (due to
`commit_executor_step15_ci_poll_timeout_2026-04-17.md`), it skips directly from
remediation push → `status=bot_findings_pending` without ever invoking auto-defer.
Tier-3 recovery then runs 3 × codex-xhigh iterations on an unactionable finding
and exhausts. Fixing CI-poll alone may mask this bug by making auto-defer fire
more often, but the underlying gap remains: **there is no "false positive" signal
for genuinely unactionable findings where the adapter DOES attempt a fix and DOES
push changes (as in round 1 of PR #783).**

## Reproduction (verified 2026-04-17)

Wave A: bot P2 referenced `codex_count` which does not exist in source (verified via
`grep -nw 'codex_count' mu/tools/observability/_pane_processes.sh` → 0 matches).
Remediation round 1 produced cosmetic changes (string wording + OR-guard) and
pushed `a87ba2c0`. Bot did not update its comment. commit_executor detected
the same P2 on re-fetch and would have proceeded to round 2. (CI-poll timeout
preempted that flow, but the underlying logic gap would have reproduced.)

## Structural fix candidates

1. **Commit-SHA-scoped finding comparison**: capture bot findings BEFORE remediation
   push as baseline. After push, compare NEW findings against baseline. Only NEW
   findings (posted AFTER remediation commit SHA) count as unresolved. Existing
   findings are treated as "not retracted" but not blocking.

2. **Diff-relevance check**: if remediation adapter produces no changes OR cosmetic-only
   changes that don't touch the file/line the finding references, invoke
   `_auto_defer_bot_findings` immediately instead of treating as failure.

3. **Tier-3 short-circuit**: when recovery_gate receives `bot_findings_pending` and
   detects "adapter has no actionable fix" (e.g., prompt history shows 3 "no changes"
   iterations), skip codex-xhigh invocation and auto-defer.

## Acceptance criteria for the fix wave

- Pick one of the 3 candidates (preferably #1 as it's the cleanest semantic fix).
- Regression test in `mu/tests/tools/test_commit_executor_receipt.py` or new
  `test_commit_executor_bot_findings.py`: simulate false-positive finding + empty
  remediation diff → assert `_auto_defer_bot_findings` is called.
- No runtime/substrate/host/projection/seed touches. L4_ENABLER class.
