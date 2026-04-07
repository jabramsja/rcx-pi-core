# Findings Pane Fallback

Date: 2026-04-04
Status: Local proof complete; routed closeout pending
Task: [PIPELINE-RECOVERY/findings-pane-fallback-2026-04-04]
Wave ID: findings-pane-fallback-2026-04-04

## Scope

Keep the tmux findings pane informative even when the active control-surface
work is outside Phase A / Phase B bridge rounds. The pane should render a
plain-English fallback instead of a blank shell prompt, and it should show the
latest meta-review decision plus the latest commit-path state when those are
the active review surfaces.

## Trigger

Live tmux audit after PR #719 merge:

- pane `1.3` was still running `_pane_findings.sh`, but it rendered only the
  shell prompt because the script hit a `continue` path before painting any
  fallback output when `.agent_bus/raw/phase-?-r*` had no active rounds
- the one-shot pane snapshot proved the observability mismatch: the log,
  status, and timeline panes were all healthy, but the findings pane looked
  dead during a commit-surface / meta-review wave

## Changed surfaces

- `mu/tools/observability/_pane_findings.sh`
- `mu/tests/tools/test_recovery_gate.py`

## Proof points

1. `_pane_findings.sh` no longer exits the render loop early when there is no
   bridge-round directory or no reviewer envelope yet. It now always paints a
   fallback state.
2. When bridge rounds are idle, the pane now shows:
   - `No active Phase A/Phase B bridge rounds`
   - the latest meta-review decision and summary, when present
   - the latest meaningful commit-path line from `commit_executor_live.log`
3. `RCX_PANE_ONESHOT=1` renders the pane once and exits, which creates a stable
   automated proof surface for a formerly interactive-only pane.
4. The live tmux pane now shows the repaired fallback after an explicit respawn
   in the current `dev` worktree.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short -k 'pane_findings or pipeline_monitor_status_prefers_unique_active_worktree_over_quiet_current_root'`
- `RCX_PANE_ONESHOT=1 TERM=xterm bash mu/tools/observability/_pane_findings.sh`
- live tmux proof:
  `tmux respawn-pane -k -t rcx-pipeline:1.3 "cd '/private/tmp/workingrcx_meta_taskid_safety.vTXECZ' && bash '/private/tmp/workingrcx_meta_taskid_safety.vTXECZ/mu/tools/observability/_pane_findings.sh'"`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; observability/control-surface only
