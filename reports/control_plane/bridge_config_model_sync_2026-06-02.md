# Bridge Config Model Sync 2026-06-02

Date: 2026-06-02
Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: bridge-config-model-sync-2026-06-02
Phase-A-Lock: LOCKED
Purpose: Keep `.agent_bus/bridge_config.json`'s per-agent provider settings (model / effort / display_name) in sync with `executor_config.json`'s `bridge_agent_defaults`, so the live provider config cannot drift from the committed default (2026-06-02: bridge_config ran the claude implementer on claude-opus-4-7 while `bridge_agent_defaults.claude` said claude-opus-4-8). The precise, do-not-deviate approach is preserved verbatim under "Request from Post-Merge Supervisor" below and decomposed under "Work items".

## Scope

Tooling-only change (L4_ENABLER -- no runtime dir). In scope:

- `executor_common.py`: add a NEW repo_root-aware `sync_bridge_config_agents_from_defaults(repo_root, bus_dir=None)` that resolves the bridge_config path via the EXISTING `bridge_config_path(repo_root, bus_dir)` helper (the SINGLE primary bus -- NO discovery), reads `bridge_config.json` mirroring the EXISTING `load_bridge_agent_catalog` read pattern, overwrites each agent's model + effort + display_name from `executor_config`'s `bridge_agent_defaults`, then writes `bridge_config.json` back.
- `set_roles.py`: call the new function AFTER its `apply_role_agents` call (set_roles already resolves repo_root).
- `mu/tests/tools/`: a regression test for the drift-correction behavior.

`apply_role_agents` stays config-dict-only with UNCHANGED signature/behavior -- the sync is the SEPARATE repo_root-aware function. Cite code by function name only; no file:line in this packet.

## Work items

1. Add `sync_bridge_config_agents_from_defaults(repo_root, bus_dir=None)` to `executor_common.py`:
   - Resolve the bridge_config path via the EXISTING `bridge_config_path(repo_root, bus_dir)` (single primary `.agent_bus` by default; do NOT enumerate or "discover" multiple / lane buses).
   - Read `bridge_config.json` mirroring the EXISTING `load_bridge_agent_catalog` read pattern (same path resolution + json load).
   - For each agent present in BOTH `bridge_config['agents']` AND `executor_config`'s `bridge_agent_defaults`, overwrite ONLY: model (the token after `--model` or `-m` in the agent's `cmd` list), effort (the `--effort` value or the `model_reasoning_effort="..."` `-c` arg), and `display_name`, from the matching `bridge_agent_defaults` entry.
   - Write `bridge_config.json` back. Graceful no-op if `bridge_config.json` is absent or an agent is missing from `bridge_agent_defaults`.
2. Call the new function from `set_roles.py` AFTER its `apply_role_agents` call, so any role switch re-syncs model / effort / display.
3. Add a regression test in `mu/tests/tools/`: given `bridge_config.claude` model `claude-opus-4-7` and `bridge_agent_defaults.claude` model `claude-opus-4-8`, after the sync the `bridge_config.claude` `cmd` shows `claude-opus-4-8`.

## Constraints

What is NOT in scope:

- Do NOT change `apply_role_agents`'s signature or behavior -- it stays config-dict-only (it has no repo_root). The bridge_config sync is a SEPARATE repo_root-aware function.
- Sync model + effort + display_name ONLY. Do NOT touch any other `cmd` arg, `timeout_s`, `mode`, `prompt_via_stdin`, or `env`.
- SINGLE resolved bus only (via `bridge_config_path`). NO multi-bus / lane-bus discovery or enumeration.
- No runtime-dir changes (L4_ENABLER must not touch runtime dirs).
- No broader refactor of bridge-config loading or of `load_bridge_agent_catalog`.
- No file:line citations in this packet; cite code by function name only.

## Stop conditions

- Stop when the new function, the `set_roles.py` call site, and the regression test are implemented and the validation gate is green.
- Escalate (do NOT widen scope) if the change appears to require modifying `apply_role_agents`'s signature/behavior, multi-bus discovery, or touching any `cmd`/agent field beyond model / effort / display_name.
- Escalate if the live `bridge_config.json` `agents[].cmd` shape differs from the model/effort/display assumptions such that the sync cannot be done within the stated scope.
- Phase A is design-only: implementation does NOT begin until this packet is bridge-converged and Phase-A-Lock is LOCKED.

## Acceptance criteria

- `sync_bridge_config_agents_from_defaults(repo_root, bus_dir=None)` exists in `executor_common.py`, resolves via `bridge_config_path`, mirrors the `load_bridge_agent_catalog` read pattern, syncs model + effort + display_name only, and no-ops gracefully when `bridge_config.json` is absent or an agent is missing from `bridge_agent_defaults`.
- `set_roles.py` invokes the new function AFTER `apply_role_agents`; `apply_role_agents` is unchanged.
- Regression test proves drift correction: a `bridge_config.claude` model of `claude-opus-4-7` becomes `claude-opus-4-8` (the `bridge_agent_defaults.claude` model) in the `bridge_config.claude` `cmd` after the sync.
- Validation gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/ -k "set_roles or bridge_config or role_agents or bridge_agent"`.
- No multi-bus discovery; no other `cmd` / `timeout_s` / `mode` / `prompt_via_stdin` / `env` changes; no runtime-dir files touched.

## Grounding / Authorization

- Task: `[NEXT-CODEX-POST-REDTEAM]`, per the TASKS.md tracker sync note for `bridge-config-model-sync-2026-06-02` (2026-06-02).
- Governing packet: this file -- `reports/control_plane/bridge_config_model_sync_2026-06-02.md`.
- Class: `L4_ENABLER` (tooling prerequisite for a gate; MUST NOT touch runtime dirs). target_gate_id: G8.
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/ -k "set_roles or bridge_config or role_agents or bridge_agent"`.
- evidence_delta: new `executor_common.sync_bridge_config_agents_from_defaults(repo_root, bus_dir=None)` resolves the bridge_config path via `bridge_config_path` (single primary bus, no discovery) and overwrites each agent's model / effort / display_name from `executor_config` `bridge_agent_defaults`; called from `set_roles.py` after `apply_role_agents`; `apply_role_agents` unchanged; covered by a drift-correction regression test.
- primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION.
- indicator_artifact_ref: `reports/l4_wave_indicators/bridge-config-model-sync-2026-06-02.json`.
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id bridge-config-model-sync-2026-06-02 --output reports/l4_wave_indicators/bridge-config-model-sync-2026-06-02.json`.
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.
- Authorization: standing pipeline-bug-fix authorization per memory `feedback_autonomous_executor_fix.md` (this wave corrects live provider-config drift where the pipeline ran `claude-opus-4-7` against the committed `claude-opus-4-8` default), bound to this wave via `FOUNDER_OVERRIDE:bridge-config-model-sync-2026-06-02` so commit automation can derive the same-wave L4 override mechanically for commit-gate + pre-push adjacency-cap clearance.

## Request from Post-Merge Supervisor

Keep .agent_bus/bridge_config.json's per-agent provider settings in sync with executor_config.json's `bridge_agent_defaults`, so the live provider config cannot drift from the committed default (2026-06-02: bridge_config ran the claude implementer on claude-opus-4-7 while bridge_agent_defaults.claude said claude-opus-4-8). PRECISE APPROACH (read these functions first; do NOT deviate): (1) Add a NEW function in executor_common.py -- e.g. `sync_bridge_config_agents_from_defaults(repo_root, bus_dir=None)` -- that resolves the bridge_config path via the EXISTING `bridge_config_path(repo_root, bus_dir)` helper (the SINGLE resolved bus -- the primary `.agent_bus` by default; do NOT enumerate or 'discover' multiple/lane buses), reads that bridge_config.json, and for each agent present in BOTH bridge_config['agents'] AND executor_config's `bridge_agent_defaults`, overwrites ONLY that agent's model (the token after `--model` or `-m` in its `cmd` list), its effort (the `--effort` value or the `model_reasoning_effort="..."` `-c` arg), and its `display_name`, from the matching bridge_agent_defaults entry; then writes bridge_config.json back. Mirror the read pattern of the EXISTING `load_bridge_agent_catalog` (same path resolution + json load). (2) Call this new function from set_roles.py AFTER its apply_role_agents call (set_roles already resolves repo_root), so any role switch re-syncs model/effort/display too. (3) Do NOT change `apply_role_agents`'s signature or behavior -- it stays config-dict-only (it has no repo_root); the bridge_config sync is the SEPARATE repo_root-aware function. HARD SCOPE: sync model + effort + display_name ONLY; touch no other cmd arg, timeout_s, mode, prompt_via_stdin, or env; the SINGLE resolved bus only (bridge_config_path) -- no multi-bus discovery; graceful no-op if bridge_config.json is absent or an agent is missing from bridge_agent_defaults.

Routed next-candidate:
bridge-config-model-sync-2026-06-02

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `bridge-config-model-sync-2026-06-02`
- Active packet: `reports/control_plane/bridge_config_model_sync_2026-06-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `64a9a8ea09dc47c2d80f7fe479c540b5d6e66d4fd2f9eac346aaa929e91733b1`
- Indicator artifact: `reports/l4_wave_indicators/bridge-config-model-sync-2026-06-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_bridge_config_model_sync.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/bridge_config_model_sync_2026-06-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/bridge-config-model-sync-2026-06-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/set_roles.py`
  - `reports/control_plane/bridge_config_model_sync_2026-06-02.md`
  - `reports/l4_wave_indicators/bridge-config-model-sync-2026-06-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
