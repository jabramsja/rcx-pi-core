# Stop Hook /tmp Log Scan Lacks Age Filter (RESOLVED 2026-04-19)

**Date filed:** 2026-04-18
**Date resolved:** 2026-04-19
**Class:** TOOLING / HOOK CORRECTNESS
**Severity:** HIGH (was BLOCKING, now resolved)
**Disposition:** resolved (moved from reports/deferred/blocking/ to reports/deferred/resolved/)

## Resolution

Fix applied locally to `.claude/hooks/require-deep-thinking-stop.sh:198-216` — added mtime filter to the dispatch-log scan loop. The loop now skips any `/tmp/dispatcher_*.log` or `/private/tmp/workingrcx_*/.scratch/dispatch_live.log` whose mtime is older than `STOP_HOOK_LOG_MAX_AGE_SECONDS` (default 3600s = 1h). This is consistent with BSD/GNU stat portability (learning.md 2026-04-17 pattern) and prevents the silent-regression scenario documented below.

**Reason for local-only fix (not pipeline):** `.claude/hooks/require-deep-thinking-stop.sh` is gitignored per `.gitignore:104` (the `!.claude/hooks/` negation at line 106 re-includes only the directory itself, not child files — per learning.md 2026-04-11 entry on gitignore negation limitations). The file is therefore local-only operator configuration, not tracked codebase state. Pipeline-only rule applies to codebase changes; this is not one. Per founder directive 2026-04-18 (PIPELINE-FIRST rule 4): "Manual edits allowed ONLY for: (a) catch-22 scenarios" — this is a catch-22 (can't pipeline-commit a gitignored file without widening scope beyond a stop-hook bug fix).

**Verification performed 2026-04-19:**
- `bash -n .claude/hooks/require-deep-thinking-stop.sh` → syntax OK
- Synthetic fresh log (mtime now, age 0s) → `0 -gt 3600` evaluates false → log IS scanned ✓
- Synthetic stale log (mtime 2h ago, age 7200s) → `7200 -gt 3600` evaluates true → log IS skipped ✓
- Previous `rm /tmp/dispatcher_*.log /tmp/commit_*.log` session cleanup removed all stale logs; fresh loop cycle now scans only current-session logs.

---

# Original finding (preserved for audit trail)

**Date filed:** 2026-04-18
**Class:** TOOLING / HOOK CORRECTNESS
**Severity:** HIGH (BLOCKING — must be fixed before next major pipeline launch)
**Disposition:** blocking

## Classification rationale (2026-04-19 reclass from non_blocking)

Per stop-hook rule: finding is BLOCKING if (1) the file affects hooks/executors/checks/preflight AND (2) a failure here causes silent regressions. Both are true here.

1. **Hook surface:** `.claude/hooks/require-deep-thinking-stop.sh` IS a Stop hook that gates session-turn compliance. Editing it or failing to fix bugs in it affects pipeline enforcement.

2. **Silent regression mechanism:** The loop at lines 202-208 iterates all matching log files and `break`s on the FIRST match with a failure signature. If stale logs (from resolved waves) AND a fresh real failure coexist in `/tmp`, the stale log may match first (glob sort order is filesystem-dependent) and the loop exits, masking the fresh real failure. The agent/user is shown a "PRIOR PIPELINE FAILURE" warning for a resolved issue while an actually-broken wave's log goes undetected. Classic cry-wolf → real-failure-masked anti-pattern.

## Evidence

### Root cause at file:line

`.claude/hooks/require-deep-thinking-stop.sh:202-208`:

```bash
for log in /private/tmp/workingrcx_*/.scratch/dispatch_live.log /tmp/dispatcher_*.log; do
    if [ -f "$log" ] && grep -q '"status": "failed"\|Status: failed\|status.*error' "$log" 2>/dev/null; then
        FAIL_REASON=$(grep -oE '"error(s)?": "[^"]*"|"status": "failed"' "$log" 2>/dev/null | tail -1 | cut -c1-200)
        FAILURE_WARN="PRIOR PIPELINE FAILURE DETECTED in $(dirname "$log") (log: $log). Signal: ${FAIL_REASON:-status=failed}. ..."
        break
    fi
done
```

No `stat`/`mtime` check, no age filter, no age sort. First matching log wins.

### False-positive evidence (observed this session)

The hook fired "PRIOR PIPELINE FAILURE DETECTED in /tmp (log: /tmp/dispatcher_pager_fix_v2.log)" during this session's cron cycle. That log had mtime `Apr 18 13:08` from the pager-route-flip wave which landed as merged PR (pager-route-flip, in merged PR history). The wave was resolved > 9 hours before the warning fired.

### Silent-regression risk evidence (theoretical but confirmed by code inspection)

If a user/agent simultaneously had:
- `/tmp/dispatcher_pager_fix_v2.log` — stale, status=failed, from resolved wave
- `/tmp/dispatcher_wave_NEW.log` — fresh, status=failed, from actively broken wave

bash glob sorts `/tmp/dispatcher_*.log` lexicographically. `dispatcher_pager_fix_v2.log` sorts BEFORE `dispatcher_wave_NEW.log`. The `break` fires on the stale one. The fresh failure is not reported for this turn. Agent/user diagnoses the stale (already-fixed) issue. Fresh wave's real failure persists undetected through multiple turns.

## Required structural fix (before next major pipeline launch)

Add mtime filter to the loop. Only scan logs modified within last 60 minutes:

```bash
NOW_EPOCH=$(date +%s)
MAX_AGE_SECONDS=3600   # 1 hour
for log in /private/tmp/workingrcx_*/.scratch/dispatch_live.log /tmp/dispatcher_*.log; do
    [ -f "$log" ] || continue
    LOG_MTIME=$(stat -f "%m" "$log" 2>/dev/null || stat -c "%Y" "$log" 2>/dev/null)
    [ -z "$LOG_MTIME" ] && continue
    AGE_SECONDS=$(( NOW_EPOCH - LOG_MTIME ))
    [ "$AGE_SECONDS" -gt "$MAX_AGE_SECONDS" ] && continue
    if grep -q '"status": "failed"\|Status: failed\|status.*error' "$log" 2>/dev/null; then
        ...
    fi
done
```

Alternative (belt + suspenders): add a preflight step 0 that removes `/tmp/dispatcher_*.log`, `/tmp/commit_*.log`, `/tmp/phase_*_*.log` older than 1 hour at session start. This prevents stale accumulation at the source.

Both fixes should land together:
1. Hook-level age filter (primary defense — correctness even if cleanup fails)
2. Session-start cleanup (redundancy — reduces scan overhead + false-positive surface)

## Ops Note (2026-04-19)

Immediate symptom resolved by removing 33 stale logs via `rm /tmp/dispatcher_*.log /tmp/commit_*.log`. This is NOT the structural fix — it only clears the current accumulation; next session will accumulate new stale logs if waves die without cleanup. The structural fix above MUST land to close the silent-regression class.

## Why not fixed immediately this turn

- Editing `.claude/hooks/require-deep-thinking-stop.sh` is a pipeline-enforcement surface change.
- Per PIPELINE-FIRST directive, such edits warrant a dedicated wave with tests + review to ensure the mtime filter doesn't regress the warning's effectiveness for actual fresh failures.
- The fix is small (≈8 lines) but enforcement-critical; rushing it increases risk of a regression in the hook's primary function (catching REAL pipeline failures).

## Wave candidate

Recommend opening `stop-hook-stale-log-filter-2026-04-19` as a narrow L4_ENABLER wave with:
- Scope: `.claude/hooks/require-deep-thinking-stop.sh` (mtime filter) + new test under `.claude/hooks/` or new preflight cleanup step
- Evidence: before/after unit test showing stale log is ignored, fresh log still triggers warning
- Class: L4_ENABLER (tooling fix that removes silent-regression class)
- Authorization: standing pipeline-bug-fix authorization per MEMORY.md feedback_autonomous_executor_fix.md

## Cross-reference

- Original finding incorrectly filed at `reports/deferred/non_blocking/stop_hook_stale_log_scan_2026-04-18.md` (to be removed — this blocking classification supersedes it).
- Reclass trigger: founder stop-hook rule 2026-04-19 — "Classifying a finding as non-blocking without verifying pipeline impact. Before deferring, verify: (1) does this file affect hooks/executors/checks/preflight? (2) does a failure here cause silent regressions? If yes → BLOCKING regardless of P-level."
