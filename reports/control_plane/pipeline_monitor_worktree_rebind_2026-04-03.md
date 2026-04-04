# Pipeline Monitor Linked-Worktree Rebind

Date: 2026-04-03
Status: Implementation ready for routed supervisor
Task: [PIPELINE-RECOVERY/pipeline-monitor-worktree-rebind-2026-04-03]
Wave ID: pipeline-monitor-worktree-rebind-2026-04-03

## Scope

Make the tmux monitor and one-shot pipeline status surfaces bind to the real
live linked worktree instead of stale root state, and surface recent recovery
attempt details directly in the terminal dashboard.

## Changed surfaces

- `mu/tools/observability/pipeline_monitor.sh`
- `mu/tools/observability/pipeline_status.sh`
- `mu/tools/observability/pipeline_dashboard.py`
- `mu/tests/tools/test_recovery_gate.py`

## Proof points

1. `pipeline_monitor.sh` and `pipeline_status.sh` no longer trust the current
   worktree merely because `git rev-parse --show-toplevel` succeeds; if the
   current root is quiet and another linked worktree has recent live pipeline
   state, observability rebinds to that live worktree instead.
2. tmux panes now launch as `cd <linked-worktree> && bash ...`, so they no
   longer expand to broken absolute paths like `/mu/tools/observability/...`.
3. Non-final executor state files and continuation markers are only treated as
   live when they are recent enough to plausibly belong to the current run, so
   ancient `post_commit_pending` artifacts in the root worktree stop masking the
   real active pipeline elsewhere.
4. `pipeline_dashboard.py --render-recovery` now includes recent matching
   recovery attempts from `.agent_bus/recovery/recovery_log.json`, so the tmux
   recovery block shows loop actions and outcomes instead of only the latest
   status snapshot.
5. Live root-path smoke now rebinds to the replay worktree instead of showing
   the ancient `#706` root state, and `pipeline_monitor.sh status` follows the
   same route.
5. Both entrypoints now implement the same resolver rules: first prefer the
   exact current-branch worktree, then fall back to the one uniquely active
   pipeline worktree, then a sole linked worktree, then the unique linked
   `dev` worktree, and only then fail closed instead of guessing the current
   directory or a random feature branch.
6. Regression coverage in `mu/tests/tools/test_recovery_gate.py` proves the
   exact linked-worktree success path, the stale-branch active-worktree
   fallback, the sole-linked-worktree fallback, the unique-`dev` fallback, and
   the unresolved-branch fail-closed path, plus recent-attempt recovery
   rendering for the terminal dashboard.

## Validation

- `bash -n mu/tools/observability/pipeline_monitor.sh mu/tools/observability/pipeline_status.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`
- `cd /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX && tmp_state=/private/tmp/workingrcx_meta_bridge_fix.9cb3Xv/.agent_bus/executors/commit_executor_smoke.json && mkdir -p "$(dirname "$tmp_state")" && printf '{"status":"post_commit_pending","target_branch":"jabramsja/pipeline-monitor-worktree-rebind-replay-2026-04-04"}\n' > "$tmp_state" && env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR bash /private/tmp/workingrcx_meta_bridge_fix.9cb3Xv/mu/tools/observability/pipeline_status.sh && rm -f "$tmp_state"`
- `cd /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX && tmp_state=/private/tmp/workingrcx_meta_bridge_fix.9cb3Xv/.agent_bus/executors/commit_executor_smoke.json && mkdir -p "$(dirname "$tmp_state")" && printf '{"status":"post_commit_pending","target_branch":"jabramsja/pipeline-monitor-worktree-rebind-replay-2026-04-04"}\n' > "$tmp_state" && env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR bash /private/tmp/workingrcx_meta_bridge_fix.9cb3Xv/mu/tools/observability/pipeline_monitor.sh status && rm -f "$tmp_state"`
