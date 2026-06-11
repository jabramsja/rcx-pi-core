# Fable-Claude-Bridge-Adapter-Max-Turns-100-2026-06-11

Date: 2026-06-11
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: fable-claude-bridge-adapter-max-turns-100-2026-06-11
Phase-A-Lock: LOCKED
Purpose: Bump the bridge_config.example.json claude and fable implementer adapter cmds from --max-turns 50 to --max-turns 100 (matching the live opus implementer budget) and current the example claude model/display from opus-4-7 to opus-4-8. The fable implementer exhausted its 50-turn budget at turn 51 during a heavy Phase B implementation because the fable adapter inherited the stale example --max-turns 50 rather than the opus 100; the example claude entry carried the same stale 50. The migration that seeds a newly-added menu adapter copies the example adapter cmd, so the example is the source of the turn budget for seeded agents. Control-surface tooling only; no runtime dirs touched.

## Scope

Bump claude + fable bridge adapter --max-turns 50 -> 100 in bridge_config.example.json (match opus budget; the seeded fable adapter exhausted 50 turns on a heavy Phase B) + current the example claude model to opus-4-8. Control-surface L4_ENABLER, no runtime.

## Request from Post-Merge Supervisor

Bump the bridge_config.example.json claude and fable implementer adapter cmds from --max-turns 50 to --max-turns 100 (matching the live opus implementer budget) and current the example claude model/display from opus-4-7 to opus-4-8. The fable implementer exhausted its 50-turn budget at turn 51 during a heavy Phase B implementation because the fable adapter inherited the stale example --max-turns 50 rather than the opus 100; the example claude entry carried the same stale 50. The migration that seeds a newly-added menu adapter copies the example adapter cmd, so the example is the source of the turn budget for seeded agents. Control-surface tooling only; no runtime dirs touched.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/fable-claude-bridge-adapter-max-turns-100-2026-06-11.json.
- `indicator_collection_command`: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id fable-claude-bridge-adapter-max-turns-100-2026-06-11 --output reports/l4_wave_indicators/fable-claude-bridge-adapter-max-turns-100-2026-06-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `grep -q 'max-turns", "100' mu/tools/agents/bridge_config.example.json && ! grep -q 'max-turns", "50' mu/tools/agents/bridge_config.example.json && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_bridge_config_model_sync.py`.
- `evidence_delta`: bridge_config.example.json claude+fable --max-turns 50->100, AND sync_bridge_config_agents_from_defaults now updates --max-turns on EXISTING bus adapters from the example (not only newly-seeded ones), so a bus already at 50 is migrated to 100..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: fable-claude-bridge-adapter-max-turns-100-2026-06-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `fable-claude-bridge-adapter-max-turns-100-2026-06-11`
- Active packet: `reports/control_plane/fable-claude-bridge-adapter-max-turns-100-2026-06-11_2026-06-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5246456799061fed9f918fed01a4396e75fcdc7ac5a5aeda543e0bcf8819d7b4`
- Indicator artifact: `reports/l4_wave_indicators/fable-claude-bridge-adapter-max-turns-100-2026-06-11.json`
- Evidence command: `grep -q 'max-turns", "100' mu/tools/agents/bridge_config.example.json && ! grep -q 'max-turns", "50' mu/tools/agents/bridge_config.example.json && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_bridge_config_model_sync.py`.
- Evidence delta: bridge_config.example.json claude+fable --max-turns 50->100, AND sync_bridge_config_agents_from_defaults now updates --max-turns on EXISTING bus adapters from the example (not only newly-seeded ones), so a bus already at 50 is migrated to 100..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/fable-claude-bridge-adapter-max-turns-100-2026-06-11.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tools/executors/executor_common.py`
  - `reports/control_plane/fable-claude-bridge-adapter-max-turns-100-2026-06-11_2026-06-11.md`
  - `reports/l4_wave_indicators/fable-claude-bridge-adapter-max-turns-100-2026-06-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
