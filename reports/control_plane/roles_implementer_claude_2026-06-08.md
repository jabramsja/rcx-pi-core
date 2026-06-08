# Roles Implementer Claude

Date: 2026-06-08
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: roles-implementer-claude-2026-06-08
Phase-A-Lock: UNLOCKED
Purpose: Founder 2026-06-08: change the committed implementer to claude (Claude Opus 4.8 max), leave the reviewer at codex (Codex 5.5 xhigh). Change ALREADY APPLIED via the set_roles.py builder (executor_config.json role_agents implementer codex->claude; reviewer stays codex; derived backends phase_a/phase_b/bot_remediation -> claude, post_merge_supervisor/dialectic stay codex; bridge_reviewers stay codex). The PR #1081 de-brittle makes the dispatcher-config tests derive expected roles from the live committed config, so this flip does not break them. Verified: audit_fast green with the claude/codex config; configured_role_agents returns implementer 'Claude Opus 4.8 max' + reviewer 'Codex 5.5 xhigh' (the tmux/dashboard labels). L4_ENABLER: pipeline config only; no runtime/substrate dir; no host_semantics.

## Scope

roles-implementer-claude (L4_ENABLER): commit role_agents implementer codex->claude (reviewer stays codex) via the set_roles builder, so the committed implementer is Claude Opus 4.8 max and the reviewer is Codex 5.5 xhigh; the per-render tmux labels (configured_role_agents) follow. De-brittled dispatcher-config tests (PR #1081) derive from the live config so no breakage. Scope = executor_config.json. Verified audit_fast green.

## Request from Post-Merge Supervisor

Founder 2026-06-08: change the committed implementer to claude (Claude Opus 4.8 max), leave the reviewer at codex (Codex 5.5 xhigh). Change ALREADY APPLIED via the set_roles.py builder (executor_config.json role_agents implementer codex->claude; reviewer stays codex; derived backends phase_a/phase_b/bot_remediation -> claude, post_merge_supervisor/dialectic stay codex; bridge_reviewers stay codex). The PR #1081 de-brittle makes the dispatcher-config tests derive expected roles from the live committed config, so this flip does not break them. Verified: audit_fast green with the claude/codex config; configured_role_agents returns implementer 'Claude Opus 4.8 max' + reviewer 'Codex 5.5 xhigh' (the tmux/dashboard labels). L4_ENABLER: pipeline config only; no runtime/substrate dir; no host_semantics.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `roles-implementer-claude-2026-06-08`
- Active packet: `reports/control_plane/roles_implementer_claude_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `d46cb4f90aff08798a9418f938d5ccae8f7b54341dbe7823df925ecb940a9f86`
- Indicator artifact: `reports/l4_wave_indicators/roles-implementer-claude-2026-06-08.json`
- Evidence command: `python3 -c "import json,sys; d=json.load(open('mu/tools/executors/executor_config.json'))['role_agents']; sys.exit(0 if d=={'implementer':'claude','reviewer':'codex'} else 1)"`.
- Evidence delta: Flips role_agents implementer codex->claude (reviewer stays codex) via the set_roles builder, which materializes the derived backends + bridge_reviewers. Verified: audit_fast green with the committed claude/codex config (the PR #1081 de-brittle derives expected roles from the live config), and configured_role_agents returns implementer display_name 'Claude Opus 4.8 max' + reviewer 'Codex 5.5 xhigh' (the values the tmux/dashboard panes render per render cycle). Evidence reads the committed config file, not env-aware set_roles --show..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/roles-implementer-claude-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/roles_implementer_claude_2026-06-08.md`
  - `reports/l4_wave_indicators/roles-implementer-claude-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
