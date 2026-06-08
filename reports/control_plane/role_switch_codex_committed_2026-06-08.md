# Role Switch Codex Committed

Date: 2026-06-08
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: role-switch-codex-committed-2026-06-08
Phase-A-Lock: UNLOCKED
Purpose: Commit the role switch: make codex the committed implementer (reviewer already codex) and de-brittle the two dispatcher-config tests so set_roles is a true one-shot switch. Change is ALREADY APPLIED + VERIFIED in this worktree (2 files): (1) mu/tools/executors/executor_config.json role_agents implementer claude->codex (+ derived backends phase_a_executor/phase_b_executor/bot_remediation claude->codex), written by the set_roles.py builder; (2) mu/tests/tools/test_executor_dispatch.py TestDispatcherConfig: test_load_default_config + test_bridge_reviewer_override_does_not_retarget_implementers now derive expected roles from the LIVE committed executor_config.json (authoritative source of truth) instead of DEFAULT_EXECUTOR_CONFIG, so a set_roles flip to any provider keeps them green. Verified: 999 flagged-file tests pass + audit_fast passes with the codex config; configured_role_agents returns implementer display_name 'Codex 5.5 xhigh' so the tmux/dashboard panes (which read configured_role_agents) show Codex, not claude/opus-4.8. L4_ENABLER: pipeline tooling/config only; no runtime/substrate dir; no host_semantics.

## Scope

role-switch-codex-committed (L4_ENABLER): commit role_agents=codex/codex (set_roles builder flips executor_config.json + materializes backends/bridge_reviewers/bridge_config) and de-brittle the two TestDispatcherConfig live-config tests to derive expected roles from the committed config rather than DEFAULT_EXECUTOR_CONFIG. Completes the #21 gap: set_roles is now a true one-shot switch (any provider stays green) and the tmux/dashboard implementer label shows 'Codex 5.5 xhigh'. Scope = 2 files: executor_config.json + test_executor_dispatch.py. Verified 999 tests + audit_fast green with codex.

## Request from Post-Merge Supervisor

Commit the role switch: make codex the committed implementer (reviewer already codex) and de-brittle the two dispatcher-config tests so set_roles is a true one-shot switch. Change is ALREADY APPLIED + VERIFIED in this worktree (2 files): (1) mu/tools/executors/executor_config.json role_agents implementer claude->codex (+ derived backends phase_a_executor/phase_b_executor/bot_remediation claude->codex), written by the set_roles.py builder; (2) mu/tests/tools/test_executor_dispatch.py TestDispatcherConfig: test_load_default_config + test_bridge_reviewer_override_does_not_retarget_implementers now derive expected roles from the LIVE committed executor_config.json (authoritative source of truth) instead of DEFAULT_EXECUTOR_CONFIG, so a set_roles flip to any provider keeps them green. Verified: 999 flagged-file tests pass + audit_fast passes with the codex config; configured_role_agents returns implementer display_name 'Codex 5.5 xhigh' so the tmux/dashboard panes (which read configured_role_agents) show Codex, not claude/opus-4.8. L4_ENABLER: pipeline tooling/config only; no runtime/substrate dir; no host_semantics.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `role-switch-codex-committed-2026-06-08`
- Active packet: `reports/control_plane/role_switch_codex_committed_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `559ef8882924596792c396704cf1dfaa4d426e661e388027accf086641724b2e`
- Indicator artifact: `reports/l4_wave_indicators/role-switch-codex-committed-2026-06-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherConfig mu/tests/tools/test_set_roles.py mu/tests/tools/test_phase_b_executor.py::TestLoadExecutorConfig`.
- Evidence delta: De-brittles the two live-config-loading TestDispatcherConfig tests to derive expected roles from the committed executor_config.json (authoritative) + assert the derivation invariant (backends/bridge_reviewers derived from role_agents), so committing role_agents implementer=codex via the set_roles builder no longer breaks them. Verified: the 6 role-pinned test files (999 tests) + audit_fast pass with the codex config, and configured_role_agents returns implementer display_name 'Codex 5.5 xhigh' (what the tmux/dashboard panes render)..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/role-switch-codex-committed-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/role_switch_codex_committed_2026-06-08.md`
  - `reports/l4_wave_indicators/role-switch-codex-committed-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
