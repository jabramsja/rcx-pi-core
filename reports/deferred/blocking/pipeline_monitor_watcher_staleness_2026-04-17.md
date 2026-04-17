# Pipeline Monitor Watcher Staleness (Deferred)

**Date:** 2026-04-17
**Wave:** Ad-hoc diagnosis during PR #781 session
**Status:** BLOCKING — affects preflight Step 12 (monitor start) and pipeline observability loop; deferred pending live-recurrence diagnostic capture because the root cause cannot be traced post-mortem (stuck watcher processes were killed via `stop` before live diagnostic evidence could be captured)
**Classification:** DEBT — observability/monitoring robustness

## Reclassification Evidence (2026-04-17)

Per founder directive 2026-04-11, verified pipeline impact:
- **(1) Preflight Step 12** explicitly invokes `tools/observability/pipeline_monitor.sh start --detach` (see `.claude/skills/preflight/SKILL.md` Step 12). When the monitor renders blank panes, the observability contract that preflight establishes is violated.
- **(2) Silent-regression risk**: the oversight loop relies on tmux panes to surface wave failures. Blank panes → user does not notice failing waves → wave failure is silently missed. Empirically observed this session: 11h of accumulated wave-state debt went undetected because the monitor panes that would surface it were blank.

Blocking per directive. Root cause still not traced (diagnosis requires catching a live stuck watcher — the processes from this session were killed via `stop` before capture).

---

## Observed Symptom

tmux session `rcx-pipeline` had 4 watcher panes whose shell/bash processes (pane 1 PID 73966/73971, pane 2 analog, pane 3 analog, pane 4 analog) remained alive — `ps` confirmed running status — but panes 1, 2, and (partially) 3 emitted no output when inspected via `tmux capture-pane -p`. Pane 4 (session timeline) continued rendering correctly across the same window. The session was started at 03:52:10 and the blank state was observed at ~15:09, roughly 11 hours later.

## What Was Verified

- Worktree resolution is NOT the cause: `bash mu/tools/observability/_resolve_live_root.sh` correctly returned `/private/tmp/workingrcx_pipeline_agent_pager_20260416` (the active PR worktree) via its score-by-freshest-scratch-mtime walk.
- The third linked worktree `/private/tmp/rcx_ci_repro_781` (pre-existing, detached HEAD at `34db5be7`) has no `.scratch/` activity (score 0) and does NOT pollute the resolution result.
- All three worktrees' scratch logs were outside the watcher's `IDLE_WINDOW_SECONDS=3600` budget; correct behavior is to render the idle screen via `render_idle_screen()` in `/tmp/rcx_log_watcher.sh`.
- When the helper scripts were invoked directly (`bash mu/tools/observability/_pane_processes.sh`), they produced correct output — so the scripts themselves are not broken.
- `bash tools/observability/pipeline_monitor.sh stop && bash tools/observability/pipeline_monitor.sh start --detach` recovers cleanly: all 4 panes immediately render their expected initial content (idle screen with branch+worktree info, or last-known-state where applicable).

## What Was NOT Verified — Root Cause

I have not traced to file:line why the long-lived watcher bash processes stopped emitting output to their tmux ptys. Candidates not excluded (cannot verify post-mortem because I killed the processes via `stop` before capturing live diagnostic evidence):

1. `/tmp/rcx_log_watcher.sh` main loop at lines 157-173 — reachable in a dead branch when `newest` is non-empty AND equals `current_log` (neither `switch_tail` nor `render_idle_screen` fires), leaving the pane stuck on whatever the last `tail -f` printed. Hypothesis — unverified.
2. Long-running `tail -f` buffered its final output into the kernel pty buffer after the process stopped writing, leaving whatever was last on screen frozen. Hypothesis — unverified.
3. Cross-pane output contention or a shared stdin/stdout fd issue peculiar to tmux ptys that survived a long idle period on macOS with Rosetta bash (`libRosettaRuntime` was in the watcher's lsof at diagnosis time). Hypothesis — unverified.

## Next Diagnostic Step (when recurrence captured live)

If the same blank-pane symptom reappears during a future session:

1. Before calling `stop`: capture `cat /proc/<pid>/status` (Linux) or `sample <pid> 2 -file /tmp/watcher.spl` (macOS) for each watcher PID to see whether it is in a syscall wait or a busy loop.
2. `lsof -p <pid>` for each watcher to confirm stdout fd is still pointing to the tmux pty (e.g., `/dev/ttys00N`) rather than a detached descriptor.
3. `tmux capture-pane -p -S -2000` to capture scroll history — verifies whether the pane ever rendered content or was blank from the moment of the stall.
4. `echo test > /dev/ttys00N` (pty from step 2) — tests whether the pane pty accepts new writes; if yes, watcher stdout is detached from it somehow; if no, tmux's pty layer is wedged.

Only after those are captured can the root cause be pinned at file:line. Without them the diagnosis is inference.

## Workaround (Known-Good)

`bash tools/observability/pipeline_monitor.sh stop && bash tools/observability/pipeline_monitor.sh start --detach` — verified 2026-04-17 during this session. Pane 1 went from blank to rendering the idle screen immediately (Branch: `jabramsja/pipeline-agent-pager-2026-04-16`, Worktree: `/private/tmp/workingrcx_pipeline_agent_pager_20260416`). All 4 panes functional after restart.

## Recommendation

- If the session is expected to run >4 hours, add a `monitor_restart` cron or a health-check that re-emits the pane header every N minutes so a stuck state is self-recoverable.
- When diagnosed on live recurrence, implement the root-cause fix in `/tmp/rcx_log_watcher.sh` (or its source — the script is generated by `tools/observability/pipeline_monitor.sh`'s `write_log_watcher` function).
- Orphan third worktree `/private/tmp/rcx_ci_repro_781` is NOT related to this issue but is unrelated debt — prune via `git worktree remove /private/tmp/rcx_ci_repro_781` when no longer needed.

## Severity

NON-BLOCKING. User can see current pipeline state via: (a) direct scripts (`bash mu/tools/observability/_pane_processes.sh`), (b) monitor restart, (c) `gh pr checks <N>` for remote CI, (d) `git log` + file mtimes directly. The broken-pane-symptom is an observability-UX issue; no commit/push/merge action is blocked by it.
