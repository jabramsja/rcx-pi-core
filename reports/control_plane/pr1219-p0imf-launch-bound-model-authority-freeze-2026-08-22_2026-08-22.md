# PR 1219 P0IMF Launch-Bound Model Authority Freeze 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMF-LAUNCH-BOUND-MODEL-AUTHORITY-FREEZE]
Wave ID: pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22
Phase-A-Lock: LOCKED
Purpose: After exact P0IMQ merge and before P0IMRP/P0IM, prevent a staged candidate from changing the model or reasoning effort of its own pre-merge implementer/reviewer by making the launch-generated bus bridge_config.json command the immutable execution authority for that lane. Keep launch-time bridge-config seeding/sync responsible for new-lane defaults; do not read mutable target-worktree executor_config.json during adapter load.

## Scope

Strict successor to P0IMQ and predecessor to P0IMRP. Start and compare at exact P0IMQ PR #1229 merge 08060fb8c09aaef32f82b24ad76431db1fe657fd in a fresh unique lane/bus. Candidate code scope is only bridge_adapters.py and its existing focused supervisor test module, plus exact same-wave TASKS/packet/indicator/optional deferral artifacts. Do not change executor defaults, receipt schemas, Phase B, dispatcher, launch seeding, runtime, or substrate.

Files and surfaces in scope:

- mu/tools/agents/bridge_adapters.py (MODIFY) -- remove or fail-close the mutable target-worktree executor_config.json overlay when loading a launch-generated namespaced bus bridge_config.json; the persisted bus command remains authoritative for model, effort, display name, and other adapter arguments.
- mu/tests/tools/test_agent_bridge_supervisor.py (MODIFY) -- replace the unsafe overlay expectations with focused positive/negative proof that a persisted bus command survives staged/mutated executor defaults and that ordinary adapter parsing/validation remains unchanged.
- TASKS.md (MODIFY THROUGH PIPELINE) -- record exact P0IMQ landing, mark P0IMF current, keep P0IMRP immediately next and P0IM nonlaunchable until exact P0IMRP merge, preserve every TODO and queue row.
- reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json (GENERATED BEFORE REVIEW) -- same-wave indicator.
- reports/deferred/non_blocking/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblockers only.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reproduce the exact P0IM condition: persisted namespaced bus command gpt-5.5/xhigh, target-worktree executor_config.json changed to gpt-5.6-sol/ultra, and load_bridge_config() currently resolves the latter.
2. Make the launch-generated bus file the immutable execution authority. Do not silently fall back to or overlay mutable target-worktree executor defaults for model, effort, display name, or command bytes after launch.
3. Preserve launch-time configuration generation and explicit seed/sync behavior so a lane created after a committed default change begins with that current committed default. Do not add a second config store or host-only authority.
4. Add tests proving persisted command equality before/after executor-config mutation, missing/malformed config fail-closed behavior, ordinary non-model arguments preserved, and no regression in live adapter parsing.
5. Update TASKS queue truth without deleting or reordering any successor. Route implementation, review, providerless commit, CI, merge, and cleanup only through the pipeline.

## Constraints

- Exact P0IMQ PR #1229 merge 08060fb8c09aaef32f82b24ad76431db1fe657fd is the hard dependency; HEAD, origin/dev, comparison_commit, source, and target must all equal it.
- Candidate allowlist is only TASKS.md, bridge_adapters.py, test_agent_bridge_supervisor.py, exact same-wave packet/indicator, and optional same-wave deferral report. This external WaveConfig is excluded.
- Do not modify executor_common.py, executor_config.json, launch_wave.py, set_roles.py, bridge_config example, bridge supervisor/client, meta supervisor, candidate authority, Phase A/B executors, commit/recovery code, runtime, substrate, or unrelated docs/tests.
- Do not weaken adapter validation, permit arbitrary config paths, or create a hidden environment/model override. The durable bus command created by existing launch authority is the sole per-lane command truth.
- Preserve the terminal P0IM lane and old pre-P0IX P0IM lane unchanged. All roles and pager use Codex; commit stays providerless. Nonblockers cannot delay P0IMF.

## Stop conditions

- Halt before launch unless exact P0IMQ PR #1229 merge 08060fb8c09aaef32f82b24ad76431db1fe657fd equals origin/dev, HEAD, and comparison_commit, the fresh lane/bus are unique, roles/pager are Codex, and commit is providerless.
- Halt as NEEDS_RESCOPING if closure requires a production file outside bridge_adapters.py, a test outside test_agent_bridge_supervisor.py, receipt changes, launch-wave changes, model-default changes, or Phase B/commit/recovery changes.
- Halt as DEFECT if staged or unstaged target executor_config.json can still change a loaded bus adapter command, or if new-lane launch seeding can no longer use current committed defaults.
- Do not release P0IMRP until deterministic P0IMF PR, merge SHA, origin/dev equality, and cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- For a namespaced launch bus, load_bridge_config() and get_adapter() return the exact persisted model/effort command before and after target-worktree executor_config.json is changed or staged.
- A fresh launch/seed path still materializes the currently committed defaults into its new bus config; P0IMF removes mutable post-launch overlay, not launch-time configuration authority.
- No model/default, receipt, Phase B, commit, runtime, substrate, or unrelated file changes enter the candidate.
- Focused tests, exact candidate receipt verification, staged L4 enforcement, independent review, providerless commit, CI, merge, exact dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMF-LAUNCH-BOUND-MODEL-AUTHORITY-FREEZE]; wave id `pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous narrow prerequisite packets when a wave stops converging. P0IM round 1 reproduced pre-merge self-activation as an active blocker; P0IMF isolates only that adapter authority defect.

FOUNDER_OVERRIDE:pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md`
  - `reports/deferred/non_blocking/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md`, `reports/deferred/non_blocking/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4ebb21bdcd8c01c49d7eb62796f4ce204db7d546ad6f0b62eb7b69f0fefae128`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md`, `reports/deferred/non_blocking/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_2026-08-22.md`
  - `reports/deferred/non_blocking/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
