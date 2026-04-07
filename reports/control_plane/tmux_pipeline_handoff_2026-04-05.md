# TMUX + Pipeline Handoff

Date: 2026-04-05
Repo root: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX`

## Executive Summary

This handoff is focused on two tracks:

1. tmux observability panes
2. real pipeline end-to-end proving

The tmux work is **not complete**. I fixed part of the wrong-worktree behavior and simplified the pane scripts, but the live `rcx-pipeline` window still has a real failure: pane 1 and pane 2 can go blank/stale in the actual tmux session, and pane 3 can still show stale recovery text instead of only current live state.

The pipeline work is **partially proved but not complete**. The routed path now gets much farther than before, but the current live proving run is still blocked in/around the Phase A bridge review path.

## What I Changed For TMUX

Files edited:

- `mu/tools/observability/pipeline_monitor.sh`
- `mu/tools/observability/_pane_findings.sh`
- `mu/tools/observability/_pane_processes.sh`
- `mu/tools/observability/_pane_timeline.sh`
- `mu/tools/observability/_resolve_live_root.sh` (new)

Main changes:

1. Stopped pinning panes to the launcher worktree.
   - I removed the behavior that forced panes to stay on the repo where tmux was started.
   - Pane commands now `unset RCX_OBS_REPO_ROOT`.
   - A fast helper now resolves the freshest live worktree.

2. Added a lightweight live-root helper.
   - New helper: `mu/tools/observability/_resolve_live_root.sh`
   - It chooses the freshest worktree by looking at recent executor logs, recovery state, and agent/reviewer artifacts.
   - This was meant to replace the heavier `pipeline_status.sh --print-root` path.

3. Simplified pane scripts.
   - `_pane_findings.sh`, `_pane_processes.sh`, and `_pane_timeline.sh` now use the fast root helper.
   - They no longer use the old self-reexec block I suspected was contributing to pane churn.

4. Made pane 1 less eager to declare idle.
   - `IDLE_WINDOW_SECONDS` in `pipeline_monitor.sh` was raised to `3600` so recent logs stay visible longer.

5. Hid one stale recovery/receipt surface in pane 3.
   - I suppressed old Phase B receipt/checkpoint text that was clearly not current.

## What TMUX Is Still Doing Wrong

These are real current failures, not guesses:

1. Pane 1 is blank in the live tmux window.
2. Pane 2 is blank in the live tmux window.
3. Pane 3 still shows stale recovery text:
   - `LAST RECOVERY — Tier 3 recovery`
   - `Problem: a review subprocess crashed`
   - `Recovery run: #4 in this wave · step failure #3`
   - this is not acceptable as a "live state" surface
4. Pane 4 renders, but it is mostly historical timeline, not enough current truth by itself.

## What I Verified About TMUX

Current session:

- session: `rcx-pipeline`
- window: `1`
- panes:
  - pane 1: `PANE 1 · LIVE PIPELINE LOG`
  - pane 2: `PANE 2 · REVIEW FINDINGS`
  - pane 3: `PANE 3 · PLAIN-ENGLISH STATUS`
  - pane 4: `PANE 4 · SESSION TIMELINE`

Live capture of the actual tmux window showed:

- pane 1: blank
- pane 2: blank
- pane 3: rendered but stale
- pane 4: rendered

That means the problem is not just wording or labels. The live display is still wrong.

Important diagnostic fact:

- Running pane 2 directly in one-shot mode outside tmux works and prints valid content.
- Running pane 1's watcher in one-shot mode outside tmux prints the correct recent Phase A log.

So the current failure is specifically in the live tmux execution path or live-loop behavior, not simply "the scripts cannot render at all."

## Most Important TMUX Evidence

### Live tmux capture

Observed in the actual `rcx-pipeline` window:

- pane 1: blank
- pane 2: blank
- pane 3: stale recovery text still present

### One-shot pane 2 worked

Direct run of `_pane_findings.sh` in one-shot mode printed:

- branch: `jabramsja/post-commit-roundtrip-2026-04-04`
- worktree: `/private/tmp/workingrcx_recovery_live.5T1YFI`
- latest round: `phase-a-r1-f3814fb1`
- state: `In progress...`

### One-shot pane 1 watcher worked

Direct run of the watcher printed the real last Phase A log:

- `Plan draft: reports/control_plane/post_commit_roundtrip_2026-04-04.md`
- `Running SDK agent review on plan (depth=quick)...`
- `Agent review returned semantic blocker findings ... continuing to bridge`
- `Bridge design review round 1/15 (job=phase-a-r1-f3814fb1)...`
- `Bridge exit code: 1`
- `Bridge: SYNTHETIC — fail-closed`

That means the live data exists. The problem is the tmux-pane live loop, not absence of underlying artifacts.

## Current Pipeline State

Proving worktree:

- `/private/tmp/workingrcx_recovery_live.5T1YFI`

Tracked packet:

- `reports/control_plane/post_commit_roundtrip_2026-04-04.md`

What is working:

1. The routed pipeline gets far beyond the old early failures.
2. The packet was corrected so it no longer lies about already-landed prerequisite work.
3. SDK review is completing and returning real outputs instead of the earlier broken path.
4. Phase A gets into bridge review rather than failing immediately on packet/auth problems.

What is not working:

1. The current live proving run is still not completing end-to-end.
2. The current observed blocker is the Phase A bridge path.
3. The bridge path is ending up in a synthetic/fail-closed result instead of clean completion.

Most recent concrete Phase A log:

- `Bridge design review round 1/15 (job=phase-a-r1-f3814fb1)...`
- `Bridge exit code: 1`
- `Bridge: SYNTHETIC — fail-closed`

## Pipeline Root-Cause Lead I Was Following

This is the main lead I had before stopping to write this handoff:

- the raw reviewer artifact for the active bridge run appears to contain a real reviewer envelope
- but the bridge supervisor path is still ending up with a synthetic-only decision
- my working suspicion is that the parser/supervisor path is not accepting the real reviewer result in the form it is being emitted during this run

In plain English:

- the reviewer may actually be saying something real
- but the pipeline is still treating that as "no usable review came back"
- so it fail-closes as synthetic instead of progressing normally

I did **not** finish that bridge-path fix in this turn.

## What I Would Do Next

If the next model/operator wants the fastest path:

1. Fix the tmux live-loop first, not the wording.
   - Focus on why pane 1 and pane 2 render in one-shot mode but go blank in the actual tmux session.
   - The likely area is the long-running shell/watcher loop behavior inside the pane process, not the data source itself.

2. After tmux is truthful, go back to the bridge path.
   - Inspect the active raw reviewer artifact for `phase-a-r1-f3814fb1`
   - trace exactly why the bridge supervisor reduces it to `SYNTHETIC`

3. Then rerun the end-to-end proof.
   - target remains: post-merge supervisor -> recovery -> phase retry -> back to post-merge supervisor

## Files Most Relevant For Pickup

TMUX / observability:

- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/observability/pipeline_monitor.sh`
- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/observability/_pane_findings.sh`
- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/observability/_pane_processes.sh`
- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/observability/_pane_timeline.sh`
- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/observability/_resolve_live_root.sh`

Pipeline / bridge:

- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/agents/bridge_supervisor.py`
- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/executors/phase_a_executor.py`
- `/private/tmp/workingrcx_recovery_live.5T1YFI/reports/control_plane/post_commit_roundtrip_2026-04-04.md`

## Bottom Line

TMUX is not fully fixed.

Pipeline is not fully fixed.

The strongest real progress from this slice is:

- wrong-worktree handling was partially corrected
- pane scripts can now resolve the active proving worktree
- direct one-shot pane runs can show the correct live worktree and recent live data
- the pipeline gets deep into Phase A bridge review

The biggest remaining failures are:

- live tmux panes still going blank/stale
- Phase A bridge path still fail-closing as synthetic instead of completing the run
