# PR #760 Late Bot P1 Findings (Post-Merge)

Date: 2026-04-12
PR: #760 (merged)
Classification: NON-BLOCKING (deferred — post-merge findings)

## Finding 4: Treat non-success CI conclusions as failed in fallback poll
- **File:** `mu/tools/executors/commit_executor.py:1488`
- **Issue:** `_poll_ci_checks_fallback` checks `conclusion == "FAILURE"` but misses CANCELLED, TIMED_OUT, ACTION_REQUIRED
- **Fix:** Change to `conclusion not in ("SUCCESS", "")` or `conclusion not in ("SUCCESS", None, "")`

## Finding 5: Auto-defer report not committed before merge
- **File:** `mu/tools/executors/commit_executor.py:1707`
- **Issue:** `_auto_defer_bot_findings` writes deferred report to worktree but returns None (success) without staging/committing it. Report is lost on merge.
- **Fix:** Stage the deferred report file + amend the commit before returning None, OR include it in the merge commit scope

## Triage (2026-04-13)

Status: RE-DEFERRED. Both findings are genuine pipeline-hardening items (CI
fallback polling + auto-defer staging). Neither is addressed in the current wave
(anti-drift-bot-findings-2026-04-13) because they are in commit_executor.py, not
in the wave's scoped files (executor_dispatch.py, recovery_gate.py). Bundle into
next pipeline-hardening wave under [PIPELINE-RECOVERY] authorization.

## Scope estimate
~10 lines each. Bundle into next pipeline-hardening wave.
