# Pipeline Monitor Watcher Staleness (Deferred)

**Date:** 2026-04-17
**Wave:** Ad-hoc diagnosis during PR #781 session
**Status:** CLOSED by `pipeline-monitor-heartbeat-2026-04-30` — the live
recurrence was not recaptured, but the concrete source-level freeze path in the
generated pane-1 watcher was closed mechanically.
**Classification:** DEBT — observability/monitoring robustness

## Reclassification Evidence (2026-04-17)

Per founder directive 2026-04-11, verified pipeline impact:
- **(1) Preflight Step 12** explicitly invokes `tools/observability/pipeline_monitor.sh start --detach` (see `.claude/skills/preflight/SKILL.md` Step 12). When the monitor renders blank panes, the observability contract that preflight establishes is violated.
- **(2) Silent-regression risk**: the oversight loop relies on tmux panes to surface wave failures. Blank panes → user does not notice failing waves → wave failure is silently missed. Empirically observed this session: 11h of accumulated wave-state debt went undetected because the monitor panes that would surface it were blank.

Blocking per directive until 2026-04-30. The exact historical tmux/pty state was
not recoverable after the original processes were killed, but the source path
that allowed an alive watcher to stop redrawing pane 1 is now fixed and tested.

---

## Observed Symptom

tmux session `rcx-pipeline` had 4 watcher panes whose shell/bash processes (pane 1 PID 73966/73971, pane 2 analog, pane 3 analog, pane 4 analog) remained alive — `ps` confirmed running status — but panes 1, 2, and (partially) 3 emitted no output when inspected via `tmux capture-pane -p`. Pane 4 (session timeline) continued rendering correctly across the same window. The session was started at 03:52:10 and the blank state was observed at ~15:09, roughly 11 hours later.

## What Was Verified

- Worktree resolution is NOT the cause: `bash mu/tools/observability/_resolve_live_root.sh` correctly returned `/private/tmp/workingrcx_pipeline_agent_pager_20260416` (the active PR worktree) via its score-by-freshest-scratch-mtime walk.
- The third linked worktree `/private/tmp/rcx_ci_repro_781` (pre-existing, detached HEAD at `34db5be7`) has no `.scratch/` activity (score 0) and does NOT pollute the resolution result.
- All three worktrees' scratch logs were outside the watcher's `IDLE_WINDOW_SECONDS=3600` budget; correct behavior is to render the idle screen via `render_idle_screen()` in `/tmp/rcx_log_watcher.sh`.
- When the helper scripts were invoked directly (`bash mu/tools/observability/_pane_processes.sh`), they produced correct output — so the scripts themselves are not broken.
- `bash tools/observability/pipeline_monitor.sh stop && bash tools/observability/pipeline_monitor.sh start --detach` recovers cleanly: all 4 panes immediately render their expected initial content (idle screen with branch+worktree info, or last-known-state where applicable).

## What Was NOT Verified — Historical Root Cause

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

Only after those are captured can the original 2026-04-17 tmux/pty state be
proven. Without them the historical diagnosis remains bounded inference.

## Closure Evidence (2026-04-30)

- Source path fixed: `mu/tools/observability/pipeline_monitor.sh` generated
  watcher loop previously handled `newest == current_log` by doing nothing,
  leaving a long-running `tail -f` as the only pane writer. The fix adds a
  bounded heartbeat that restarts the same-log tail and re-emits the pane header
  on `RCX_LOG_WATCHER_HEARTBEAT_SECONDS` intervals.
- Regression: `mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_monitor_restarts_same_log_tail_on_heartbeat`
  proves a same-log heartbeat replaces the old tail process, leaves the old pid
  dead, and preserves `current_log`.
- Scope: pane-1 observability only. No executor, recovery, runtime, substrate,
  or pager delivery semantics changed.

## Workaround (Known-Good)

`bash tools/observability/pipeline_monitor.sh stop && bash tools/observability/pipeline_monitor.sh start --detach` — verified 2026-04-17 during this session. Pane 1 went from blank to rendering the idle screen immediately (Branch: `jabramsja/pipeline-agent-pager-2026-04-16`, Worktree: `/private/tmp/workingrcx_pipeline_agent_pager_20260416`). All 4 panes functional after restart.

## Historical Recommendation Status

- The prior recommendation to add a health-check that re-emits the pane header
  is implemented by the 2026-04-30 heartbeat fix in the generated watcher source.
- If a future blank-pane recurrence appears, capture the live diagnostics above
  before stopping the monitor so any remaining tmux/pty state can be traced.
- Orphan third worktree `/private/tmp/rcx_ci_repro_781` is NOT related to this issue but is unrelated debt — prune via `git worktree remove /private/tmp/rcx_ci_repro_781` when no longer needed.

## Severity

Closed as a blocking observability debt item. The direct executor/commit path was
not blocked, but preflight monitor observability and unattended failure
visibility were blocked until the pane redraw path had a mechanical refresh.
