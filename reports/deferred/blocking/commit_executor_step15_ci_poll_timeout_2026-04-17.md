# BLOCKING: commit_executor step 15 CI-poll timeout too short for bot-remediation push

**Date filed**: 2026-04-17
**Observed on**: PR #783 (observability-pane-and-deferred-doc-cleanup-2026-04-17)
**Severity**: BLOCKING (turns every false-positive bot finding into a tier-3 cascade)

## Symptom

After `commit_executor.py` step 15 pushes a bot-remediation round, it polls GitHub CI
for completion. When `gh pr checks` encounters a `CalledProcessError` (intermittent),
the executor falls back to internal polling with a 300s budget. `green-gate` can take
5m7s (307s) after a remediation push — exceeds the budget — so the executor classifies
the run as "CI failed after remediation round 1" even though CI actually passes
shortly after. This preempts `_auto_defer_bot_findings` and triggers tier-3 recovery.

## Root cause (file:line)

- `mu/tools/executors/commit_executor.py:~1628` — fallback polling loop with hardcoded
  300s budget (exact constant not yet verified; may be symbolic name like
  `_CI_POLL_TIMEOUT_S` or inline literal).
- Trigger precondition: `gh pr checks <PR> --watch --required` exits non-zero
  (CalledProcessError) → polling fallback engaged.

## Reproduction (verified 2026-04-17)

Wave A (`observability-pane-and-deferred-doc-cleanup-2026-04-17`, PR #783):
1. Step 14 CI passed on first push.
2. Bot P2 posted (false positive on `codex_count` that does not exist in source).
3. Step 15 remediation round 1 pushed commit `a87ba2c0` with cosmetic changes.
4. `gh pr checks` exited with CalledProcessError.
5. Polling fallback started at 22:13:27Z.
6. `test` completed at ~4m54s PASS; `green-gate` at ~5m7s PASS.
7. Polling fallback timed out at 300s (22:18:27Z) → "CI failed after remediation round 1".
8. Tier-3 recovery gate invoked → 3 × codex-xhigh iterations → `exhausted`.
9. commit_executor exited 1. PR unmerged despite all 7 checks GREEN.

## Structural fix candidates

1. **Bump polling budget** from 300 → 600 or 900s. Matches observed green-gate max.
   Quick fix, narrow scope.

2. **Fall back to authoritative state** on poll timeout: `gh pr view <PR> --json statusCheckRollup`
   and decide pass/fail from the rollup rather than concluding failure. Handles the
   case where internal polling stalls but actual GitHub state is already correct.

3. **Externalize the budget** to `executor_config.json` under a new `ci_poll_timeout_s`
   key so ops can tune without code changes.

## Related

- Learning entry `2026-04-17 PIPELINE | commit_executor tier-3 recovery exhausted bot_findings_pending false positive ...` documents the cascade-unblock recipe.
- See `commit_executor_bot_findings_false_positive_2026-04-17.md` (same session) for
  the downstream symptom: even if CI-poll were correct, bot-finding resolution logic
  cannot detect false-positive findings that bots never retract.

## Acceptance criteria for the fix wave

- Pick one of the 3 candidates above (or a superset). Update `commit_executor.py`.
- Add a regression test in `mu/tests/tools/test_commit_executor*.py` that simulates
  CI-poll timeout (mocked clock) and verifies the executor falls back to
  authoritative state check rather than concluding failure.
- No runtime/substrate/host/projection/seed touches. L4_ENABLER class.
