# CLOSED: commit_executor step 15 detects P1/P2 badges in COMMENTED bot reviews

**Date filed**: 2026-04-17
**Observed on**: PR #789 (bot-findings-false-positive-fix) -- bot P1 merged unaddressed
**Severity**: BLOCKING (allowed a P1 safety regression to auto-merge)
**Closed**: 2026-04-29 by `commit-executor-step15-review-body-detection-2026-04-29`

## Closure Evidence

Current code now requests top-level PR review bodies in
`mu/tools/executors/commit_executor.py::PR_REVIEW_QUERY`, scans current-head
`chatgpt-codex-connector` review bodies for `P1` / `P2` badge markers in
`_extract_review_findings()`, and returns `bot_findings` before merge when a
blocking badge appears on a `COMMENTED` review. Old-head review badges remain
ignored.

Regression coverage lives in
`mu/tests/tools/test_commit_executor_receipt.py::TestReviewFindingExtraction`:

- `test_pr_review_query_fetches_top_level_review_body`
- `test_commented_current_head_connector_review_badge_blocks_merge[P1]`
- `test_commented_current_head_connector_review_badge_blocks_merge[P2]`
- `test_commented_connector_review_without_blocking_badge_stays_clean`
- `test_stale_connector_review_badge_on_old_head_is_ignored`

Validation run:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReviewFindingExtraction --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short
python3 -m py_compile mu/tools/executors/commit_executor.py mu/tests/tools/test_commit_executor_receipt.py
git diff --check -- mu/tools/executors/commit_executor.py mu/tests/tools/test_commit_executor_receipt.py
```

## Original Symptom

`commit_executor` step 15 review-detection path did not detect a bot review
posted with `state: COMMENTED` carrying a P1 Badge marker in its body. The PR
was auto-merged past the finding. The P1 flagged a real safety regression
(auto-defer catching 5 exception types instead of just TimeoutError), requiring
hotfix PR #790 to remediate.

## Original Evidence

- `gh api repos/jabramsja/rcx-pi-core/pulls/789/reviews` returned the bot
  review with `state: "COMMENTED"` and a body containing:
  `![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) Restrict auto-defer path to timeout-only failures`.
- `gh api repos/jabramsja/rcx-pi-core/pulls/789/comments` returned empty; the
  finding was a PR-level review, not a line-specific comment.
- Wave E `commit_executor` log showed `Step 15: checking review state for PR
  #789...` and then immediately `Step 15: merged, HEAD=e67fd6fd, clean tree
  verified`, so no bot-remediation round fired.

## Original Root Cause

The review-state GraphQL query did not request top-level review body text, and
`_extract_review_findings()` converted review state plus review-thread comments
into outcome buckets without inspecting `COMMENTED` review bodies for blocking
badge markers.

## Original Acceptance Criteria

- Parse top-level connector review bodies for `P1 Badge` / `P2 Badge`.
- Treat current-head blocking badge bodies as `bot_findings`, regardless of
  review `state`.
- Keep old-head review bodies from blocking the current merge.
- Add regression tests around the classifier and query shape.
