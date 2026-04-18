# BLOCKING: commit_executor step 15 fails to detect P1/P2 badges in COMMENTED-state bot reviews

**Date filed**: 2026-04-17
**Observed on**: PR #789 (bot-findings-false-positive-fix) — bot P1 merged unaddressed
**Severity**: BLOCKING (allowed a P1 safety regression to auto-merge)

## Symptom

commit_executor's step 15 review-detection path did NOT detect a bot review
posted with `state: COMMENTED` carrying a P1 Badge marker in its body. The
PR was auto-merged past the finding. The P1 flagged a real safety regression
(auto-defer catching 5 exception types instead of just TimeoutError) —
required hotfix PR #790 to remediate.

## Evidence

- `gh api repos/jabramsja/rcx-pi-core/pulls/789/reviews` returned the bot
  review with `state: "COMMENTED"`, body containing
  `**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Restrict auto-defer path to timeout-only failures**`.
- `gh api repos/jabramsja/rcx-pi-core/pulls/789/comments` returned empty — the
  finding was a PR-level review, NOT a line-specific comment. Most
  bot-remediation code paths read from `/pulls/<N>/comments`, not
  `/pulls/<N>/reviews`.
- Wave E commit_executor log shows: `Step 15: checking review state for PR #789...`
  then immediately `Step 15: merged, HEAD=e67fd6fd, clean tree verified` — no
  bot-remediation round fired. Review detection classified the finding as
  non-blocking.

## Root cause (file:line)

Not yet fully traced — needs a walk through commit_executor.py step 15's
review-classification logic. Starting points:
- `commit_executor.py::_query_pr_review_state` — the GraphQL query and
  extraction helper
- `commit_executor.py::_extract_review_findings` — classifier that converts
  the PR state into findings / outcome buckets (clean / error / pending)
- `commit_executor.py::_has_fresh_connector_review` at `commit_executor.py:~1333+`
  — may treat `state: "COMMENTED"` as "fresh review observed" without
  reading the body for P1/P2 badges

Hypothesis: the path reads review `state` and treats `COMMENTED` as
acceptable clearance (vs `CHANGES_REQUESTED` which would block). The body
text containing `P1 Badge` / `P2 Badge` markers is ignored.

## Structural fix candidates

1. **Body-pattern inspection for COMMENTED reviews**: parse review body for
   `![P1 Badge]` or `![P2 Badge]` regex; if present, treat as a blocking
   finding regardless of review `state`.

2. **GraphQL threads-first**: already present for line comments. Extend the
   review-thread query to include top-level PR reviews and their body
   bodies; extract findings from both sources, not just `/pulls/<N>/comments`.

3. **Review state strict allowlist**: only `APPROVED` reviews should clear
   the review gate. `COMMENTED` / `DISMISSED` / any other state should
   require explicit body inspection.

## Acceptance criteria for the fix wave

- Pick #1 or #2. Update the review-detection classifier.
- Regression test: mock a GraphQL response with a COMMENTED review carrying
  a P1 Badge in body; assert commit_executor classifies as bot_findings +
  does NOT auto-merge.
- No runtime/substrate/host/projection/seed touches. L4_ENABLER class.

## Related

- `commit_executor_bot_findings_false_positive_2026-04-17.md` — now closed
  by PR #789's initial fix + PR #790 hotfix. The COMMENTED-review
  detection gap is orthogonal.
- Session memory: commit_executor auto-merged PR #789 despite this P1;
  the hotfix PR #790 was required to close the merged safety regression.
