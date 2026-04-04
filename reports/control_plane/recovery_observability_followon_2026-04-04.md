# Recovery Observability Follow-On

Date: 2026-04-04
Status: Local proof complete; live tmux rebind verified; routed closeout pending
Task: [PIPELINE-RECOVERY/recovery-observability-followon-2026-04-04]
Wave ID: recovery-observability-followon-2026-04-04

## Scope

Finish the tmux/dashboard cleanup exposed by the live routed recovery work:

1. keep each pane bound to the worktree that actually owns the live pipeline
   data, including the correct branch label for that worktree
2. rank multiple recently-active worktrees instead of failing closed on
   ambiguity caused by old but still-recent pipeline state
3. keep the pane surfaces rebinding every refresh cycle instead of only at
   startup, so stale worktree labels and stale file reads self-correct
4. keep recovery status phrased in plain English so the founder can tell what is
   happening without reading internal status codes

No runtime/substrate semantics change. This is control-surface observability and
test hardening only.

## Changed surfaces

- `mu/tools/observability/pipeline_status.sh`
- `mu/tools/observability/pipeline_monitor.sh`
- `mu/tools/observability/_pane_findings.sh`
- `mu/tools/observability/_pane_prci.sh`
- `mu/tools/observability/_pane_processes.sh`
- `mu/tools/observability/_pane_timeline.sh`
- `mu/tests/tools/test_recovery_gate.py`

## Proof points

1. `pipeline_status.sh` now exposes a branch-for-root helper so panes can ask
   for the branch that belongs to the resolved live worktree instead of reusing
   the original shell branch.
2. `pipeline_status.sh` now ranks candidate worktrees by live-process ownership
   and freshest pipeline signal instead of erroring whenever several recent
   worktrees exist.
3. `pipeline_monitor.sh` now uses `pipeline_status.sh --print-root` as the only
   repo-root authority, and the live log watcher also re-resolves that root on
   each loop.
4. The findings, PR/CI, processes, and timeline panes now all render
   `Watching:` from that resolved worktree/branch pair, which removes the
   previous mixed state where the pane could read one worktree’s files while
   labeling them with another branch.
5. The findings, PR/CI, processes, and timeline panes now re-resolve the live
   worktree every refresh cycle instead of binding once at startup.
6. `mu/tests/tools/test_recovery_gate.py` now locks the multi-worktree ranking
   behavior directly, along with the active-worktree branch labeling and the
   requirement that the resolver prefer the freshest live worktree signal.
7. Live tmux proof: after restarting the dashboard, touching
   `/private/tmp/workingrcx_recovery_live.5T1YFI/.scratch/commit_executor_live.log`
   caused the panes to switch their `Watching:` header to `dev`, and touching
   `/private/tmp/workingrcx_merge_recovery_fix.AMmqIw/.scratch/commit_executor_live.log`
   caused them to switch back to
   `jabramsja/pipeline-monitor-live-rebind-2026-04-04` on the next refresh.

## Validation

- `bash -n mu/tools/observability/pipeline_status.sh mu/tools/observability/_pane_findings.sh mu/tools/observability/_pane_prci.sh mu/tools/observability/_pane_processes.sh mu/tools/observability/_pane_timeline.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; observability/test-only
