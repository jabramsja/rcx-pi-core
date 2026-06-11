# Add Fable5 To Agent Menu 2026-06-11

Date: 2026-06-11
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: add-fable5-to-agent-menu-2026-06-11
Phase-A-Lock: UNLOCKED
Purpose: Add a third selectable agent 'fable' (Claude Fable 5, effort max) to the pipeline agent menu and set it as the active implementer while keeping codex as reviewer. Scope is control-surface tooling only (no runtime dirs). Changes: (1) executor_config.json bridge_agent_defaults gains a 'fable' entry {display_name 'Claude Fable 5 max', model claude-fable-5, effort max}; (2) bridge_config.example.json gains a 'fable' agent (a claude cmd template with --model claude-fable-5) so a fresh bus seed can invoke it; (3) executor_common.DEFAULT_AGENT_DISPLAY_NAMES gains a 'fable' display fallback; (4) set_roles writes role_agents implementer=fable reviewer=codex with the derived backends/bridge_reviewers; (5) test_executor_config_alignment is de-brittled so the valid-role-agent set is derived from the live bridge_agent_defaults menu rather than a hardcoded claude/codex pair, and the bridge_agent_defaults default-vs-live check is relaxed from equality to live-is-a-superset-of-default, matching the role-switch A2 contract. The switch is manual via set_roles only; there is no automatic per-wave-class model selection. Fable 5 is available until 2026-06-22; this wave keeps it in the menu.

## Scope

Add 'fable' (claude-fable-5 max) to the agent menu + activate implementer=fable (reviewer codex) via set_roles; de-brittle the config-alignment tests to derive the valid agent set from the live menu and relax default==live to live-superset. Control-surface L4_ENABLER, no runtime dirs.

## Request from Post-Merge Supervisor

Add a third selectable agent 'fable' (Claude Fable 5, effort max) to the pipeline agent menu and set it as the active implementer while keeping codex as reviewer. Scope is control-surface tooling only (no runtime dirs). Changes: (1) executor_config.json bridge_agent_defaults gains a 'fable' entry {display_name 'Claude Fable 5 max', model claude-fable-5, effort max}; (2) bridge_config.example.json gains a 'fable' agent (a claude cmd template with --model claude-fable-5) so a fresh bus seed can invoke it; (3) executor_common.DEFAULT_AGENT_DISPLAY_NAMES gains a 'fable' display fallback; (4) set_roles writes role_agents implementer=fable reviewer=codex with the derived backends/bridge_reviewers; (5) test_executor_config_alignment is de-brittled so the valid-role-agent set is derived from the live bridge_agent_defaults menu rather than a hardcoded claude/codex pair, and the bridge_agent_defaults default-vs-live check is relaxed from equality to live-is-a-superset-of-default, matching the role-switch A2 contract. The switch is manual via set_roles only; there is no automatic per-wave-class model selection. Fable 5 is available until 2026-06-22; this wave keeps it in the menu.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/add-fable5-to-agent-menu-2026-06-11.json.
- `indicator_collection_command`: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id add-fable5-to-agent-menu-2026-06-11 --output reports/l4_wave_indicators/add-fable5-to-agent-menu-2026-06-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_bridge_config_model_sync.py`.
- `evidence_delta`: fable agent added to bridge_agent_defaults + bridge_config.example.json seed + DEFAULT_AGENT_DISPLAY_NAMES; set_roles activated implementer=fable/reviewer=codex; config-alignment tests de-brittled to derive the valid agent set from the live menu and relax default==live to live-superset-of-default..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: add-fable5-to-agent-menu-2026-06-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `add-fable5-to-agent-menu-2026-06-11`
- Active packet: `reports/control_plane/add_fable5_to_agent_menu_2026-06-11_2026-06-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8d6b987389bf15b627938921768bf7dcdd0f1b1aa74158af4daee4fc3e0cea24`
- Indicator artifact: `reports/l4_wave_indicators/add-fable5-to-agent-menu-2026-06-11.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_bridge_config_model_sync.py`.
- Evidence delta: fable agent added to bridge_agent_defaults + bridge_config.example.json seed + DEFAULT_AGENT_DISPLAY_NAMES; set_roles activated implementer=fable/reviewer=codex; config-alignment tests de-brittled to derive the valid agent set from the live menu and relax default==live to live-superset-of-default..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/add-fable5-to-agent-menu-2026-06-11.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tools/executors/executor_common.py`
  - `reports/control_plane/add_fable5_to_agent_menu_2026-06-11_2026-06-11.md`
  - `reports/l4_wave_indicators/add-fable5-to-agent-menu-2026-06-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
