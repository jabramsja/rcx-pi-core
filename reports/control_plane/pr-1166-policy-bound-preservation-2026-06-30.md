# PR #1166 Policy-Bound Preservation Packet

Date: 2026-06-30
Status: POLICY_BOUND / PRESERVE AND EXTRACT
Parent wave: `pr-preservation-neverbehind-wip-reconciliation-2026-06-30`
PR: #1166, https://github.com/jabramsja/rcx-pi-core/pull/1166
Head branch: `jabramsja/claude-roles-claude-2026-06-27`
Head SHA: `5061f270355521ecb33db2aaf8c5f771d64d4b17`
Base: `dev`
Disposition: preserve branch and review useful deltas, but do not directly land
Claude role defaults while founder direction requires Codex / Codex 5.5 xhigh
for implementer, reviewer, pager, autoping, and tmux.

## Live Metadata

- Title: `feat: Land Claude pipeline roles (role_agents + DEFAULT role_agents =`
- URL: https://github.com/jabramsja/rcx-pi-core/pull/1166
- State: open, unmerged, non-mergeable against current `dev`
- Required checks: GitHub status API returned no legacy statuses; Actions
  workflow runs `Fixture Gates` and `rcx-green-gate` completed `success` for
  head SHA `5061f270355521ecb33db2aaf8c5f771d64d4b17`.
- Files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/l4_wave_indicators/claude-roles-claude-2026-06-27.json`

## Preservation Rule

- Do not delete, prune, or overwrite the PR branch or linked worktree before a
  later merged packet explicitly retires it.
- Do not land Claude defaults for implementer, reviewer, pager, autoping, or
  tmux under the current founder direction.
- Codex-compatible extraction may keep de-brittled role/config test logic only
  if it derives from the committed Codex route truth and does not reintroduce a
  Claude default.

## Blocker / Next Action

Direct landing is POLICY_BOUND because the PR's valuable test/config cleanup is
currently coupled to Claude role defaults. The next executable owner is a
Codex-routed pipeline extraction/rewrite packet outside this Phase B
implementer.

FOUNDER_OVERRIDE:pr-preservation-neverbehind-wip-reconciliation-2026-06-30
