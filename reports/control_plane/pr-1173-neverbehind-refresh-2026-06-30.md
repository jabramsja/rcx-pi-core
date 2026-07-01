# PR #1173 Never-Behind Refresh Packet

Date: 2026-06-30
Status: ACTIVE / BOUNDED REFRESH
Parent wave: `pr-preservation-neverbehind-wip-reconciliation-2026-06-30`
PR: #1173, https://github.com/jabramsja/rcx-pi-core/pull/1173
Head branch: `jabramsja/never-behind-dev-durable-signal-2026-06-28`
Head SHA: `1ad8c91c53d9718b5f86f059a26eeeda19e85b88`
Base: `dev`
Disposition: refresh first through the pipeline; no manual rebase, merge, push,
or direct branch surgery from Phase B.

## Live Metadata

- Title: `feat: never-behind-dev -- durable behind_dev signal on the primary bus`
- URL: https://github.com/jabramsja/rcx-pi-core/pull/1173
- State: open, unmerged, non-mergeable against current `dev`
- Required checks: GitHub status API returned no legacy statuses; Actions
  workflow runs `Fixture Gates` and `rcx-green-gate` completed `success` for
  head SHA `1ad8c91c53d9718b5f86f059a26eeeda19e85b88`.
- Files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-dev-durable-signal-2026-06-28_2026-06-28.md`
  - `reports/l4_wave_indicators/never-behind-dev-durable-signal-2026-06-28.json`

## Boundaries

- Preserve the durable `behind_dev.json` primary-bus signal and warning behavior.
- Keep WIP protection stronger, not weaker: dirty primary worktrees must not be
  fast-forwarded or overwritten.
- Resolve only bounded queue/tracker conflict text unless the pipeline creates a
  new explicit structural packet.
- Do not let this wait behind route/xdist hardening, Coinduction, Fixpoint, or
  Optimization.

## Blocker / Next Action

The Phase B implementer is not allowed to run dispatcher, commit, push, PR, or
merge commands inside this boundary. The next executable owner is the pipeline
launcher/commit path outside this implementer, with Codex implementer, Codex
reviewer, and Codex pager route only.

FOUNDER_OVERRIDE:pr-preservation-neverbehind-wip-reconciliation-2026-06-30
