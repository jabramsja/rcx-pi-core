# Pipeline-Impl-Claude-Max-2026-06-20

Date: 2026-06-20
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-impl-claude-max-2026-06-20
Phase-A-Lock: LOCKED
Purpose: Founder 2026-06-20: switch the committed pipeline + commit-executor implementers to claude (Claude Opus 4.8 max), leave the reviewers at codex (Codex 5.5 xhigh). Change ALREADY APPLIED via the set_roles.py builder (executor_config.json role_agents implementer codex->claude; reviewer stays codex; derived backends phase_a_executor/phase_b_executor/bot_remediation -> claude; post_merge_supervisor/dialectic_executor + bridge_reviewers stay codex; commit_executor stays null/mechanical). The de-brittled dispatcher-config tests derive expected roles from the live committed config so this flip does not break them (verified: 1015 config/role tests pass with the claude/codex config). configured_role_agents returns implementer 'Claude Opus 4.8 max' + reviewer 'Codex 5.5 xhigh' (the tmux/dashboard labels). L4_ENABLER: pipeline config only; no runtime/substrate dir; no host_semantics.

## Scope

pipeline-impl-claude-max (L4_ENABLER): commit role_agents implementer codex->claude (reviewer stays codex) via the set_roles builder, so the committed implementer is Claude Opus 4.8 max and the reviewer is Codex 5.5 xhigh; the per-render tmux labels (configured_role_agents) follow. De-brittled dispatcher-config tests derive from the live config so no breakage. Scope = mu/tools/executors/executor_config.json. Verified 1015 config/role tests green.

## Request from Post-Merge Supervisor

Founder 2026-06-20: switch the committed pipeline + commit-executor implementers to claude (Claude Opus 4.8 max), leave the reviewers at codex (Codex 5.5 xhigh). Change ALREADY APPLIED via the set_roles.py builder (executor_config.json role_agents implementer codex->claude; reviewer stays codex; derived backends phase_a_executor/phase_b_executor/bot_remediation -> claude; post_merge_supervisor/dialectic_executor + bridge_reviewers stay codex; commit_executor stays null/mechanical). The de-brittled dispatcher-config tests derive expected roles from the live committed config so this flip does not break them (verified: 1015 config/role tests pass with the claude/codex config). configured_role_agents returns implementer 'Claude Opus 4.8 max' + reviewer 'Codex 5.5 xhigh' (the tmux/dashboard labels). L4_ENABLER: pipeline config only; no runtime/substrate dir; no host_semantics.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_TYPED_FAIL_CLOSED_OUTCOMES.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-impl-claude-max-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-impl-claude-max-2026-06-20 --output reports/l4_wave_indicators/pipeline-impl-claude-max-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 -c "import json,sys; d=json.load(open('mu/tools/executors/executor_config.json'))['role_agents']; sys.exit(0 if d=={'implementer':'claude','reviewer':'codex'} else 1)"`.
- `evidence_delta`: Flips role_agents implementer codex->claude (reviewer stays codex) via the set_roles builder, which materializes the derived backends + bridge_reviewers. Verified: 1015 config/role tests pass with the committed claude/codex config (the de-brittle derives expected roles from the live config), and configured_role_agents returns implementer display_name 'Claude Opus 4.8 max' + reviewer 'Codex 5.5 xhigh' (the values the tmux/dashboard panes render). Evidence reads the committed config file, not env-aware set_roles --show..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-impl-claude-max-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-impl-claude-max-2026-06-20`
- Active packet: `reports/control_plane/pipeline-impl-claude-max-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `05ef130067597c3dbc30533fc60b9f3642f174091e760796385ae24dc279de3e`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-impl-claude-max-2026-06-20.json`
- Evidence command: `python3 -c "import json,sys; d=json.load(open('mu/tools/executors/executor_config.json'))['role_agents']; sys.exit(0 if d=={'implementer':'claude','reviewer':'codex'} else 1)"`.
- Evidence delta: Flips role_agents implementer codex->claude (reviewer stays codex) via the set_roles builder, which materializes the derived backends + bridge_reviewers. Verified: 1015 config/role tests pass with the committed claude/codex config (the de-brittle derives expected roles from the live config), and configured_role_agents returns implementer display_name 'Claude Opus 4.8 max' + reviewer 'Codex 5.5 xhigh' (the values the tmux/dashboard panes render). Evidence reads the committed config file, not env-aware set_roles --show..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-impl-claude-max-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/pipeline-impl-claude-max-2026-06-20_2026-06-20.md`
  - `reports/l4_wave_indicators/pipeline-impl-claude-max-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
