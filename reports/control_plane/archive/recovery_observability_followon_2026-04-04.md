# Recovery Observability Follow-On

Date: 2026-04-04
Status: Local proof complete; live tmux clarity refresh verified; routed closeout pending
Task: [PIPELINE-RECOVERY/recovery-observability-followon-2026-04-04]
Wave ID: recovery-observability-followon-2026-04-04

## Scope

Finish the founder-facing tmux/dashboard cleanup exposed by the live routed recovery work:

1. stop pane 1 from sitting on the last completed log forever when the pipeline
   is idle
2. put the pane number and a short plain-English job description at the top of
   each pane so reconnecting founders can tell what they are looking at
3. launch pane scripts directly in tmux instead of opening an interactive shell
   and typing commands into it, which removes shell banners and echoed script
   paths from the live dashboard
4. keep the recovery/process pane phrased in layman terms and suppress raw
   internal recovery tokens when better human-readable text is available

No runtime/substrate semantics change. This is control-surface observability and
test hardening only.

## Changed surfaces

- `mu/tests/tools/test_recovery_gate.py`
- `mu/tools/observability/pipeline_monitor.sh`
- `mu/tools/observability/_pane_findings.sh`
- `mu/tools/observability/_pane_processes.sh`
- `mu/tools/observability/_pane_timeline.sh`
- `mu/tools/observability/pipeline_dashboard.py`
- `reports/control_plane/recovery_observability_followon_2026-04-04.md`

## Proof points

1. `pipeline_monitor.sh`'s generated watcher now drops stale tails and renders
   an explicit idle screen:
   - `PANE 1 · LIVE PIPELINE LOG`
   - `No active pipeline log in the last 5 minutes.`
   - `This pane will switch automatically when the next phase starts.`
2. `pipeline_monitor.sh` now starts each pane with the pane script as the tmux
   command itself instead of using `send-keys`, which removes the old
   interactive-shell banner and the echoed script path noise.
3. `_pane_findings.sh`, `_pane_timeline.sh`, and `_pane_processes.sh` now
   advertise both the pane number and the pane purpose at the top of the pane.
4. `_pane_processes.sh` now uses more founder-readable status lines such as:
   - `No pipeline step is running. Waiting for the next wave.`
   - `Last gate decision: approved to commit and merge`
   - `Bridge is clear`
5. `pipeline_dashboard.py` now suppresses low-value internal reason tokens such
   as `"hold_check"` and avoids awkward summaries like `via exhausted`,
   preferring clean plain-English outcome text.
6. `mu/tests/tools/test_recovery_gate.py` now locks the idle-screen wording,
   the plain-English recovery wording, and the pane header wording so these
   surfaces do not silently drift back.
7. Live tmux proof on `/private/tmp/workingrcx_merge_recovery_fix.AMmqIw`:
   - all four panes remained pinned to that same worktree
   - pane 1 showed the explicit idle screen instead of an old merge log
   - pane 2/3/4 showed `PANE 2`, `PANE 3`, and `PANE 4` headers with
     plain-English explanations
   - restarting the monitor no longer produced the old shell banner / echoed
     command junk in panes 2 and 4

## Validation

- `bash -n mu/tools/observability/pipeline_monitor.sh`
- `bash -n mu/tools/observability/_pane_findings.sh`
- `bash -n mu/tools/observability/_pane_processes.sh`
- `bash -n mu/tools/observability/_pane_timeline.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`
- `bash mu/tools/observability/pipeline_monitor.sh stop`
- `bash mu/tools/observability/pipeline_monitor.sh start --detach`
- `tmux capture-pane -p -t %0 -S -30`
- `tmux capture-pane -p -t %1 -S -30`
- `tmux capture-pane -p -t %2 -S -30`
- `tmux capture-pane -p -t %3 -S -40`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; observability/test-only
