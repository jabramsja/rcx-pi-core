# Recovery Observability Follow-On

Date: 2026-04-04
Status: Local proof complete; routed closeout pending
Task: [PIPELINE-RECOVERY/recovery-observability-followon-2026-04-04]
Wave ID: recovery-observability-followon-2026-04-04

## Scope

Finish the tmux/dashboard cleanup exposed by the live routed recovery work:

1. keep each pane bound to the worktree that actually owns the live pipeline
   data, including the correct branch label for that worktree
2. stop the processes pane from surfacing unrelated global Codex session logs as
   if they belonged to the current repo
3. keep recovery status phrased in plain English so the founder can tell what is
   happening without reading internal status codes

No runtime/substrate semantics change. This is control-surface observability and
test hardening only.

## Changed surfaces

- `TASKS.md`
- `mu/tools/observability/pipeline_status.sh`
- `mu/tools/observability/_pane_findings.sh`
- `mu/tools/observability/_pane_prci.sh`
- `mu/tools/observability/_pane_processes.sh`
- `mu/tools/observability/_pane_timeline.sh`
- `mu/tools/observability/pipeline_dashboard.py`
- `mu/tests/tools/test_recovery_gate.py`

## Proof points

1. `pipeline_status.sh` now exposes a branch-for-root helper so panes can ask
   for the branch that belongs to the resolved live worktree instead of reusing
   the original shell branch.
2. The findings, PR/CI, processes, and timeline panes now all render
   `Watching:` from that resolved worktree/branch pair, which removes the
   previous mixed state where the pane could read one worktree’s files while
   labeling them with another branch.
3. `_pane_processes.sh` no longer reads the newest global
   `$HOME/.codex/sessions/...` file, so unrelated Codex activity elsewhere on
   the machine stops appearing as fake live review work for this repo.
4. `_pane_processes.sh` now supports `RCX_PANE_ONESHOT=1`, which creates a
   stable automated proof surface for a previously loop-only pane.
5. `pipeline_dashboard.py` keeps the recovery block in plain English, including
   the problem, tier, retry target, current loop, PID ownership, and recent
   recovery attempts for the current invocation.
6. `mu/tests/tools/test_recovery_gate.py` now locks both follow-ons directly:
   active-worktree branch labeling for the findings pane and the requirement
   that the processes pane ignore unrelated global Codex session logs.

## Validation

- `bash -n mu/tools/observability/pipeline_status.sh mu/tools/observability/_pane_findings.sh mu/tools/observability/_pane_prci.sh mu/tools/observability/_pane_processes.sh mu/tools/observability/_pane_timeline.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; observability/test-only
