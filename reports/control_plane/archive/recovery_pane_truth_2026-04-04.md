# Recovery Pane Truth

Date: 2026-04-04
Status: Local proof complete; routed closeout pending
Task: [PIPELINE-RECOVERY/recovery-pane-truth-2026-04-04]
Wave ID: recovery-pane-truth-2026-04-04

## Scope

Fix the stale recovery-pane behavior exposed during live routed commit work:

1. when recovery fires, fails, and a later retry eventually succeeds, stop
   presenting the old exhausted recovery record as the current truth
2. stop treating junk one-character recovery reasons like `R` as meaningful
   operator text
3. phrase inactive recovery state in plain English so the founder can tell at a
   glance whether recovery is still running or is only historical
4. keep the web recovery snapshot aligned with the same plain-English fallback
5. stop tmux monitor panes from drifting onto whichever linked worktree happens
   to be busiest at the moment
6. make recent recovery-attempt lines read like English instead of internal
   action tokens
7. stop timed-out recovery diagnosis subprocesses from leaking child process
   trees behind the panes

No runtime/substrate semantics change. This is control-surface recovery
observability only.

## Changed surfaces

- `mu/tools/executors/recovery_gate.py`
- `mu/tools/executors/executor_dispatch.py`
- `mu/tools/observability/pipeline_monitor.sh`
- `mu/tools/observability/pipeline_status.sh`
- `mu/tools/observability/_pane_processes.sh`
- `mu/tools/observability/pipeline_dashboard.py`
- `mu/tools/observability/pipeline_dashboard_web.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tests/tools/test_executor_dispatch.py`

## Proof points

1. `recovery_gate.py` now exposes
   `clear_stale_recovery_status_on_success()`, which marks an inactive matching
   recovery record as `resolved_by_later_success` when the later retry actually
   works.
2. `executor_dispatch.py` now calls that helper whenever a routed wave ends in
   `success` or `held`, so recovery status does not stay frozen on an older
   exhausted tuple after the pipeline has already recovered.
3. `pipeline_dashboard.py` now treats one- and two-character recovery reasons
   as noise, so garbage like `R` falls through to the actual human-readable
   detail.
4. `pipeline_dashboard.py` now renders inactive recovery in past-tense plain
   English:
   - `No recovery is running now.`
   - `Recovery sent work back to: Commit`
   - `Outcome: a later success cleared the earlier issue`
5. `pipeline_dashboard.py` now renders recent recovery attempts in layman terms,
   for example:
   - `Try 1: the recovery agent timed out -> failed`
   - `Try 2: ran a shell fix -> asked the pipeline to retry`
6. `pipeline_status.sh` now honors `RCX_OBS_REPO_ROOT`, which lets a tmux
   session stay pinned to the worktree it was started from instead of hopping to
   a different linked worktree mid-wave.
7. `pipeline_monitor.sh` now prefers the current worktree when launched from a
   linked checkout and injects that pinned root into every pane and the live-log
   watcher.
8. `recovery_gate.py` now starts the Tier 3 diagnosis subprocess in a fresh
   process group and kills the full process tree on timeout, so timed-out
   diagnosis loops do not leave orphaned children behind.
9. `pipeline_dashboard_web.py` uses the same junk-reason suppression, so web
   snapshot consumers see the same plain-English note instead of the raw junk
   token.
10. Live proof on the worktree:
    - the restart of `rcx-pipeline` now launches every pane with
      `RCX_OBS_REPO_ROOT=/private/tmp/workingrcx_merge_recovery_fix.AMmqIw`
    - pane 1’s watcher command shows the same pinned root injection
    - pane 4’s recovery block now renders `Try 1/2/3: the recovery agent timed
      out` instead of raw `tier3_iterN_timeout` tokens
    - focused pane/worktree tests and the full `test_recovery_gate.py` suite all
      pass on this branch

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_executor_dispatch.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short -k 'pipeline_status or pipeline_monitor or pane_findings or pane_processes or recent_attempts_rendered_for_matching_invocation or inactive_trivial_invocation_uses_detail_and_wave_history'`
- `bash mu/tools/observability/pipeline_status.sh`
- `bash mu/tools/observability/pipeline_monitor.sh stop`
- `bash mu/tools/observability/pipeline_monitor.sh start --detach`
- tmux live check:
  `tmux capture-pane -p -S -40 -t rcx-pipeline:1.1`
- tmux live check:
  `tmux capture-pane -p -S -40 -t rcx-pipeline:1.2`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; control-surface observability only
