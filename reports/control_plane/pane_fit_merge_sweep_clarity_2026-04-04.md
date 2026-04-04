# Pane Fit And Merge Sweep Clarity

Date: 2026-04-04
Status: Local proof complete; routed closeout pending
Task: [PIPELINE-RECOVERY/pane-fit-merge-sweep-clarity-2026-04-04]
Wave ID: pane-fit-merge-sweep-clarity-2026-04-04

## Scope

Fix the remaining founder-facing control-surface problems exposed after the
previous tmux observability wave:

1. keep the live tmux session readable after a detached restart by giving tmux a
   sane default session size instead of the tiny 80x24 fallback
2. keep the plain-English status pane's header visible by sizing its output
   from tmux's real pane height, not stale terminal-size guesses
3. keep redraws cleaner by using full-screen clears instead of leaving repeated
   pane headers and shell residue behind
4. make the merge sweep explain the "bot comment still exists" case in plain
   English when the visible comment is only a historical top-level Codex note,
   not a live unresolved thread
5. align pane numbering with the visual screen order the founder actually sees:
   top-left `Pane 1`, top-right `Pane 2`, bottom-left `Pane 3`, bottom-right
   `Pane 4`
6. replace the repeated all-caps in-pane titles with simpler `Pane N: ...`
   headings so the border title and pane body do not feel duplicated
7. make the findings pane explain validation failures in plain English instead
   of dumping a raw meta-review summary line
8. bind tmux border titles to the actual pane bodies with stable pane ids so
   the founder-facing visual `Pane 1 / Pane 2 / Pane 3 / Pane 4` labels stay
   truthful even though tmux pane indexes follow split history

No runtime/substrate semantics change. This is control-surface observability,
merge-sweep clarity, and regression coverage only.

## Changed surfaces

- `TASKS.md`
- `mu/tools/observability/_pane_findings.sh`
- `mu/tools/observability/_pane_processes.sh`
- `mu/tools/observability/_pane_timeline.sh`
- `mu/tools/observability/pipeline_monitor.sh`
- `mu/tools/hooks/merge_pr.sh`
- `mu/tests/tools/test_recovery_gate.py`

## Proof points

1. `pipeline_monitor.sh` now starts detached tmux sessions at `240x70` and sets
   tmux pane titles in the founder-facing visual order:
   - `PANE 1 · LIVE PIPELINE LOG`
   - `PANE 2 · REVIEW FINDINGS`
   - `PANE 3 · PLAIN-ENGLISH STATUS`
   - `PANE 4 · SESSION TIMELINE`
   It now builds the split tree in row order and binds titles to stable pane
   ids, so tmux pane indexes, screen position, border title, and in-pane body
   label all agree in the founder-facing `1 / 2 / 3 / 4` reading order.
   It also resolves the new tmux window id and active pane id from tmux itself
   during startup, so the dashboard still launches on setups that use non-default
   `base-index` or `pane-base-index` values.
2. The live tmux session now reports pane geometry as:
   - top-left `120x34`
   - bottom-left `120x34`
   - top-right `119x34`
   - bottom-right `119x34`
   This prevents the detached restart from collapsing the dashboard into four
   unreadable `40x11` panes.
3. `_pane_processes.sh` now reads `#{pane_height}` from tmux via `TMUX_PANE`
   before trimming output, so the plain-English status pane keeps its header visible on the real live
   pane instead of using stale `tput lines` guesses.
4. `_pane_processes.sh` now collapses the idle worker section to plain English:
   - `Nobody is working right now.`
   and caps recovery detail with:
   - `More recovery detail is hidden to keep this pane readable.`
5. `_pane_findings.sh`, `_pane_timeline.sh`, `_pane_processes.sh`, and the live
   log watcher now use full-screen redraws so repeated pane headers and shell
   junk do not accumulate the same way across refreshes.
6. `merge_pr.sh --sweep-only` now explains visible top-level Codex comments in
   plain English. Real verification on merged PR `#727` now prints:
   - `PR #727 (sweep): no unresolved threads`
   - `latest top-level Codex comment says no major issues`
   - `This is historical record only, not a live unresolved thread.`
7. The live pane bodies now use simpler labels such as `Pane 2: review
   findings` and `Pane 3: plain-English status` so the body text no longer
   repeats the tmux border title verbatim.
8. The findings pane now explains validator stops in plain English. It now says
   what failed and what to do next in short operator language, for example:
   - `Why it stopped: TASKS.md does not list this wave as an active NOW or NEXT item yet.`
   - `Next fix: Add this wave's exact task id to active NOW or NEXT in TASKS.md.`
   The same path now also surfaces staged-package drift in plain English when a
   staged file is missing from the package scope.
9. Live tmux proof on `/private/tmp/workingrcx_merge_recovery_fix.AMmqIw` after
   restart:
   - tmux pane `1` is the top-left live log pane
   - tmux pane `2` is the top-right findings pane
   - tmux pane `3` is the bottom-left plain-English status pane
   - tmux pane `4` is the bottom-right timeline pane
   - each pane body starts with the matching `Pane N: ...` label

## Validation

- `bash -n mu/tools/observability/_pane_processes.sh`
- `bash -n mu/tools/observability/_pane_findings.sh`
- `bash -n mu/tools/observability/_pane_timeline.sh`
- `bash -n mu/tools/observability/pipeline_monitor.sh`
- `bash -n mu/tools/hooks/merge_pr.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short -k 'pane_processes or pipeline_monitor_status or render_recovery_lines or pane_findings'`
- `bash mu/tools/observability/pipeline_monitor.sh stop`
- `bash mu/tools/observability/pipeline_monitor.sh start --detach`
- `tmux list-panes -t rcx-pipeline:1 -F '#{pane_index} #{pane_left},#{pane_top} #{pane_width}x#{pane_height} :: #{pane_title}'`
- `tmux capture-pane -p -t rcx-pipeline:1.1`
- `tmux capture-pane -p -t rcx-pipeline:1.2`
- `tmux capture-pane -p -t rcx-pipeline:1.3`
- `tmux capture-pane -p -t rcx-pipeline:1.4`
- `bash mu/tools/hooks/merge_pr.sh 727 --sweep-only`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; observability/merge-sweep clarity/test-only
