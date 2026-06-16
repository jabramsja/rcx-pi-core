# Revert-Implementer-Fable-To-Opus-Access-Lost-2026-06-16

Date: 2026-06-16
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: revert-implementer-fable-to-opus-access-lost-2026-06-16
Phase-A-Lock: LOCKED
Purpose: Revert the pipeline implementer from fable to claude (opus-4-8) because the claude-fable-5 model is no longer accessible (the implementer subprocess errors is_error:true 'model may not exist or you may not have access'), which fails every Phase-A/B implementer round and blocks all waves. Config-only change to mu/tools/executors/executor_config.json, made via the set_roles builder, with EXACTLY these four value flips (the complete staged diff): role_agents.implementer fable->claude, AND the three set_roles-derived backends backends.phase_a_executor fable->claude, backends.phase_b_executor fable->claude, and backends.bot_remediation fable->claude. role_agents.reviewer (codex), backends.post_merge_supervisor (codex), backends.dialectic_executor (codex), and backends.commit_executor (null) are UNCHANGED. No runtime, test, seed, or doc change. The claude (opus-4-8 max) implementer is verified working.

## Scope

Revert implementer fable->claude (opus-4-8); claude-fable-5 access lost 2026-06-16; unblocks the pipeline.

## Request from Post-Merge Supervisor

Revert the pipeline implementer from fable to claude (opus-4-8) because the claude-fable-5 model is no longer accessible (the implementer subprocess errors is_error:true 'model may not exist or you may not have access'), which fails every Phase-A/B implementer round and blocks all waves. Config-only change to mu/tools/executors/executor_config.json, made via the set_roles builder, with EXACTLY these four value flips (the complete staged diff): role_agents.implementer fable->claude, AND the three set_roles-derived backends backends.phase_a_executor fable->claude, backends.phase_b_executor fable->claude, and backends.bot_remediation fable->claude. role_agents.reviewer (codex), backends.post_merge_supervisor (codex), backends.dialectic_executor (codex), and backends.commit_executor (null) are UNCHANGED. No runtime, test, seed, or doc change. The claude (opus-4-8 max) implementer is verified working.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/revert-implementer-fable-to-opus-access-lost-2026-06-16.json.
- `indicator_collection_command`: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id revert-implementer-fable-to-opus-access-lost-2026-06-16 --output reports/l4_wave_indicators/revert-implementer-fable-to-opus-access-lost-2026-06-16.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_dispatch.py`.
- `evidence_delta`: executor_config.json staged diff is EXACTLY four value flips (set_roles builder): role_agents.implementer fable->claude + the derived backends.phase_a_executor, backends.phase_b_executor, backends.bot_remediation all fable->claude; reviewer/codex backends (post_merge_supervisor, dialectic_executor) and commit_executor(null) unchanged. The claude (opus-4-8 max) implementer is verified working while claude-fable-5 returns model-access errors; config-alignment/set_roles/dispatch tests pass with implementer=claude derived from the live config..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: revert-implementer-fable-to-opus-access-lost-2026-06-16.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `revert-implementer-fable-to-opus-access-lost-2026-06-16`
- Active packet: `reports/control_plane/revert-implementer-fable-to-opus-access-lost-2026-06-16_2026-06-16.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `51c25802b656a31cc86c1f53c14e1a41b279e511334cae4fd3782af711a15979`
- Indicator artifact: `reports/l4_wave_indicators/revert-implementer-fable-to-opus-access-lost-2026-06-16.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: executor_config.json staged diff is EXACTLY four value flips (set_roles builder): role_agents.implementer fable->claude + the derived backends.phase_a_executor, backends.phase_b_executor, backends.bot_remediation all fable->claude; reviewer/codex backends (post_merge_supervisor, dialectic_executor) and commit_executor(null) unchanged. The claude (opus-4-8 max) implementer is verified working while claude-fable-5 returns model-access errors; config-alignment/set_roles/dispatch tests pass with implementer=claude derived from the live config..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/revert-implementer-fable-to-opus-access-lost-2026-06-16.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/revert-implementer-fable-to-opus-access-lost-2026-06-16_2026-06-16.md`
  - `reports/l4_wave_indicators/revert-implementer-fable-to-opus-access-lost-2026-06-16.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
