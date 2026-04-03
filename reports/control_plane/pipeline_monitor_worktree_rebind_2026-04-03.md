# Pipeline Monitor Linked-Worktree Rebind

Date: 2026-04-03
Status: Implementation ready for routed supervisor
Task: [PIPELINE-RECOVERY]
Wave ID: pipeline-monitor-worktree-rebind-2026-04-03

## Scope

Make the tmux monitor and one-shot pipeline status surfaces work from the
bare/common repo path by rebinding them to the real linked worktree before they
launch pane scripts or read `.agent_bus` state.

## Changed surfaces

- `mu/tools/observability/pipeline_monitor.sh`
- `mu/tools/observability/pipeline_status.sh`

## Proof points

1. `pipeline_monitor.sh` now resolves a linked worktree when `git rev-parse
   --show-toplevel` fails in the bare/common repo path.
2. tmux panes now launch as `cd <linked-worktree> && bash ...`, so they no
   longer expand to broken absolute paths like `/mu/tools/observability/...`.
3. `pipeline_status.sh` uses the same resolver, so one-shot status reads the
   real `.agent_bus` state from the linked worktree instead of the bare/common
   directory.
4. Live tmux smoke from the bare/common repo path no longer errors with
   `No such file or directory`, and pane 1.2 can show the normal status surface
   again instead of an immediate launch failure.

## Validation

- `bash -n mu/tools/observability/pipeline_monitor.sh mu/tools/observability/pipeline_status.sh`
- `cd /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX && bash /private/tmp/workingrcx_meta_bridge_fix.9cb3Xv/mu/tools/observability/pipeline_monitor.sh stop && bash /private/tmp/workingrcx_meta_bridge_fix.9cb3Xv/mu/tools/observability/pipeline_monitor.sh start --detach`
- `cd /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX && bash /private/tmp/workingrcx_meta_bridge_fix.9cb3Xv/mu/tools/observability/pipeline_status.sh`
- `tmux capture-pane -pt rcx-pipeline:1.2 -S -20`
