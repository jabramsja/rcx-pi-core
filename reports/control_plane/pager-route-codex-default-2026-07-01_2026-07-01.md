# Pager Route Codex Default 2026-07-01

Date: 2026-07-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [CONTROL-PLANE-ROOT-FIX]
Wave ID: pager-route-codex-default-2026-07-01

## Purpose

Close the narrow committed-fallback gap inside the queued
`pager-route-orchestrator-label-hardening-2026-06-30` root fix. The orchestrator
switch already writes bus-local `orchestrator_mode.json` and can narrow the
tracked pager route, but current dev still ships `pipeline_agent_pager.route` as
`both`. A clean checkout or resumed process without bus-local state can
therefore page Codex and Claude even when the committed orchestrator selection is
Codex.

## Scope

Control-plane/config/docs only:

- `mu/tools/executors/executor_config.json` -- set the shipped pager fallback to
  `codex`, matching committed Codex implementer/reviewer defaults.
- `mu/tests/tools/test_pipeline_agent_pager.py` -- lock the shipped fallback as
  `codex` while preserving the explicit `route=both` fan-out contract.
- `mu/docs/agents/AgentRunbook.v0.md` -- correct the operator docs: the
  orchestrator switch does narrow the tracked pager fallback for the selected
  orchestrator.
- `TASKS.md` and `reports/l4_wave_indicators/pager-route-codex-default-2026-07-01.json`
  -- tracker and indicator evidence for this slice.

No runtime, substrate, seed, projection, JavaScript parity implementation, or
Claude-owned file is in scope.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py::test_requested_targets_both_expands_to_codex_and_claude mu/tests/tools/test_pipeline_agent_pager.py::test_executor_config_default_pager_route_is_codex mu/tests/tools/test_orchestrator_mode_switch.py::test_apply_narrows_committed_pager_route_to_single_selected_orchestrator --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py::TestRoleAgentConfigAlignment mu/tests/tools/test_executor_config_alignment.py::TestBridgeAgentDefaultConfigAlignment --tb=short`
- `./tools/checks/check_docs_consistency.sh`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id pager-route-codex-default-2026-07-01 --wave-class L4_ENABLER`
- `git diff --check && git diff --staged --check`

## Proof Limit

This wave does not remove explicit `route=both` support. It only prevents
accidental fallback to `both` when no higher-precedence route state exists. If a
future pane/status renderer still displays stale Claude labels while the
effective route and role providers are Codex, keep that under the broader queued
`pager-route-orchestrator-label-hardening-2026-06-30` root fix.

FOUNDER_OVERRIDE:pager-route-codex-default-2026-07-01

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pager-route-codex-default-2026-07-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-route-codex-default-2026-07-01 --output reports/l4_wave_indicators/pager-route-codex-default-2026-07-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py::test_requested_targets_both_expands_to_codex_and_claude mu/tests/tools/test_pipeline_agent_pager.py::test_executor_config_default_pager_route_is_codex mu/tests/tools/test_orchestrator_mode_switch.py::test_apply_narrows_committed_pager_route_to_single_selected_orchestrator mu/tests/tools/test_executor_config_alignment.py::TestRoleAgentConfigAlignment mu/tests/tools/test_executor_config_alignment.py::TestBridgeAgentDefaultConfigAlignment --tb=short && ./tools/checks/check_docs_consistency.sh`.
- `evidence_delta`: (1) `executor_config.json` now ships `pipeline_agent_pager.route="codex"` with implementer/reviewer already Codex 5.5 xhigh, so clean checkouts and resumed processes without bus-local `orchestrator_mode.json` do not fall back to both-target paging. (2) The pager test keeps explicit `route=both` fan-out covered while asserting the shipped fallback is Codex. (3) AgentRunbook now matches code truth: `set_orchestrator_mode.py` writes bus-local state and narrows the tracked fallback, but still does not write role_agents/backends/bridge_reviewers. This closes the committed-fallback slice; the broader queued stale pane/status label root fix remains if renderer drift is reproduced.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pager-route-codex-default-2026-07-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-route-codex-default-2026-07-01`
- Active packet: `reports/control_plane/pager-route-codex-default-2026-07-01_2026-07-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ef30d6132385cba627c0f1f3deab1ffcbf76c2fcf8ae6e3624670383cb1eb405`
- Indicator artifact: `reports/l4_wave_indicators/pager-route-codex-default-2026-07-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py::test_requested_targets_both_expands_to_codex_and_claude mu/tests/tools/test_pipeline_agent_pager.py::test_executor_config_default_pager_route_is_codex mu/tests/tools/test_orchestrator_mode_switch.py::test_apply_narrows_committed_pager_route_to_single_selected_orchestrator mu/tests/tools/test_executor_config_alignment.py::TestRoleAgentConfigAlignment mu/tests/tools/test_executor_config_alignment.py::TestBridgeAgentDefaultConfigAlignment --tb=short && ./tools/checks/check_docs_consistency.sh`.
- Evidence delta: (1) `executor_config.json` now ships `pipeline_agent_pager.route="codex"` with implementer/reviewer already Codex 5.5 xhigh, so clean checkouts and resumed processes without bus-local `orchestrator_mode.json` do not fall back to both-target paging. (2) The pager test keeps explicit `route=both` fan-out covered while asserting the shipped fallback is Codex. (3) AgentRunbook now matches code truth: `set_orchestrator_mode.py` writes bus-local state and narrows the tracked fallback, but still does not write role_agents/backends/bridge_reviewers. This closes the committed-fallback slice; the broader queued stale pane/status label root fix remains if renderer drift is reproduced.
- Evidence handles:
  - `docs_consistency`: `local command output: all checks passed`
  - `focused_pytest`: `local command output: 8 passed in 0.06s`
  - `host_ratchets`: `local command output: host semantics and authority ratchets passed`
  - `indicator`: `reports/l4_wave_indicators/pager-route-codex-default-2026-07-01.json`
  - `l4_contract`: `local command output: L4_ENABLER compliant`
- Current staged files:
  - `TASKS.md`
  - `mu/docs/agents/AgentRunbook.v0.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/pager-route-codex-default-2026-07-01_2026-07-01.md`
  - `reports/l4_wave_indicators/pager-route-codex-default-2026-07-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
