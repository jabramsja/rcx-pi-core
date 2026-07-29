# PIPELINE ROLE SWITCH - exact all-Codex 5.6-sol ultra

Date: 2026-07-29
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: roles-all-codex-current-dev-2026-07-29
Phase-A-Lock: LOCKED
Purpose: Make every model-bearing pipeline implementer and reviewer resolve durably to Codex gpt-5.6-sol at ultra effort on current dev and on freshly seeded namespaced buses, while keeping commit_executor deterministic and providerless.

## Scope

Bounded current-dev pipeline-role configuration switch and stale Phase B provenance removal. Phase A owns the packet; Phase B owns implementation; commit_executor owns commit, PR, CI, and merge.

Files and surfaces in scope:

- TASKS.md (MODIFY) -- launcher-owned same-wave tracker authority.
- mu/tools/executors/executor_config.json (MODIFY) -- set authoritative live implementer/reviewer roles, derived backends/reviewers, and Codex provider metadata.
- mu/tools/executors/executor_common.py (MODIFY, NARROW) -- synchronize only the fallback Codex provider-menu metadata; do not flip static fallback role maps.
- mu/tools/executors/phase_b_executor.py (MODIFY, NARROW) -- replace both stale version-specific Phase B attributions with one version-neutral helper.
- mu/tests/tools/test_bridge_config_model_sync.py (MODIFY) -- prove exact model/effort synchronization.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- prove version-neutral Phase B attribution at both call sites.
- reports/control_plane/roles-all-codex-current-dev-2026-07-29_2026-07-29.md (GENERATED) -- pipeline-owned packet.
- reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json (GENERATED) -- pipeline-owned indicator.
- TASKS.md -- tracker-sync authority. The 2026-07-29 tracker sync note for wave `roles-all-codex-current-dev-2026-07-29` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/roles-all-codex-current-dev-2026-07-29_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Use the existing role derivation contract so live role_agents implementer=codex and reviewer=codex mechanically materialize all five model-bearing backends and both bridge reviewers as codex.
2. Set the live Codex provider menu to display_name Codex 5.6-sol ultra, model gpt-5.6-sol, and reasoning_effort ultra.
3. Synchronize only the static fallback Codex provider-menu entry in DEFAULT_EXECUTOR_CONFIG; preserve the established live-config authority and its fallback role-import behavior.
4. Replace the two hard-coded Codex GPT-5.5 xhigh Phase B commit-message attributions with one version-neutral helper and cover both production call sites.
5. Prove a freshly seeded namespaced bus and adapter reload both derive the exact committed Codex model and effort.
6. Run the focused evidence command, L4 validation, and the ordinary pipeline commit/CI/merge path.

## Constraints

- Use launch_wave, Phase A, Phase B, and deterministic commit_executor. Do not hand-implement, hand-commit, hand-push, or hand-merge candidate changes.
- Every model-bearing process in this wave must be Codex gpt-5.6-sol with ultra reasoning; commit_executor remains providerless.
- Do not modify set_roles.py or build a model/effort builder in this wave.
- Do not flip the static DEFAULT role_agents, backends, or bridge_reviewers: the committed live config remains role authority and existing fallback import/rematerialization remains intact.
- Do not modify launch_wave.py, dispatcher, bridge, recovery, commit executor, orchestrator watcher, runtime, Stage0, Mu semantics, host, substrate, seeds, registries, or docs-truth surfaces.
- Do not revive or copy the stale roles-convergence, model-builder, or PR 1212 packages; implement against current origin/dev through this fresh packet.
- Do not add speculative hardening or address unrelated reviewer findings.

## Stop conditions

- Stop done only when the focused proof is green and the pipeline has committed, pushed, opened a PR, passed CI/review, and merged to dev.
- Halt as SCOPE_UNCERTAIN if direct evidence requires any production file outside the three authorized production paths; return the exact dependency to Phase A rather than broadening.
- Halt as REGRESSION if any effective implementer/reviewer command resolves to Claude, another Codex model, or effort other than ultra.
- Halt as POLICY_BOUND if version-specific authorship is required instead of version-neutral implementation provenance.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_launch_wave.py::test_setup_bridge_config_auto_seeds_fresh_namespaced_bus mu/tests/tools/test_phase_b_executor.py::TestPrepareCommitHandoff::test_phase_b_commit_message_has_version_neutral_provenance --tb=short`

## Acceptance criteria

- Authoritative live role_agents are implementer=codex and reviewer=codex, with all five derived model-bearing backends and both bridge reviewers equal to codex.
- Live and static fallback Codex provider-menu metadata both resolve exactly to gpt-5.6-sol and ultra.
- Fresh namespaced bus setup and adapter reload resolve exact Codex model/effort from committed provider metadata.
- Both Phase B commit-message paths use one version-neutral implementation provenance helper and contain no stale gpt-5.5/xhigh claim.
- Static fallback role maps retain their established authority semantics and set_roles remains unchanged.
- The focused evidence command, L4 contract, CI, and bot review pass before deterministic merge to dev.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `roles-all-codex-current-dev-2026-07-29`.
- Governing packet: this file, `reports/control_plane/roles-all-codex-current-dev-2026-07-29_2026-07-29.md`.
- TASKS.md authority: the 2026-07-29 tracker sync note for wave `roles-all-codex-current-dev-2026-07-29` is canonical for this packet's L4 fields.
- Authorization: Founder explicitly requires the orchestrated pipeline's implementers and reviewers to use only Codex gpt-5.6-sol ultra, with the same setting holding for main and parallel namespaced pipeline lanes.

FOUNDER_OVERRIDE:roles-all-codex-current-dev-2026-07-29

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `roles-all-codex-current-dev-2026-07-29`
- Active packet: `reports/control_plane/roles-all-codex-current-dev-2026-07-29_2026-07-29.md`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/roles-all-codex-current-dev-2026-07-29_2026-07-29.md`
  - `reports/deferred/non_blocking/roles-all-codex-current-dev-2026-07-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `roles-all-codex-current-dev-2026-07-29`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/roles-all-codex-current-dev-2026-07-29_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_TYPED_FAIL_CLOSED_OUTCOMES.
- `indicator_artifact_ref`: reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-current-dev-2026-07-29 --output reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_launch_wave.py::test_setup_bridge_config_auto_seeds_fresh_namespaced_bus mu/tests/tools/test_phase_b_executor.py::TestPrepareCommitHandoff::test_phase_b_commit_message_has_version_neutral_provenance --tb=short`.
- `evidence_delta`: Before: current origin/dev resolves implementer and reviewer roles, all five model-bearing backends, and both bridge reviewers to Claude; its Codex menu is gpt-5.5/xhigh and Phase B hard-codes that stale version into two commit messages. After: the authoritative live roles and their derived backends/reviewers are Codex, the live and fallback Codex provider-menu metadata are gpt-5.6-sol/ultra, fresh and existing bus adapter configs resolve those exact settings, and Phase B attribution is version-neutral..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: ADVANCE.
- `founder_override`: roles-all-codex-current-dev-2026-07-29.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `roles-all-codex-current-dev-2026-07-29`
- Active packet: `reports/control_plane/roles-all-codex-current-dev-2026-07-29_2026-07-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `13fdb590ce90755160fca262dd368b8e3d88c4a5fd80fb85de2377d2b616945c`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_launch_wave.py::test_setup_bridge_config_auto_seeds_fresh_namespaced_bus mu/tests/tools/test_phase_b_executor.py::TestPrepareCommitHandoff::test_phase_b_commit_message_has_version_neutral_provenance --tb=short`.
- Evidence delta: Before: current origin/dev resolves implementer and reviewer roles, all five model-bearing backends, and both bridge reviewers to Claude; its Codex menu is gpt-5.5/xhigh and Phase B hard-codes that stale version into two commit messages. After: the authoritative live roles and their derived backends/reviewers are Codex, the live and fallback Codex provider-menu metadata are gpt-5.6-sol/ultra, fresh and existing bus adapter configs resolve those exact settings, and Phase B attribution is version-neutral..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/roles-all-codex-current-dev-2026-07-29_2026-07-29.md`
  - `reports/deferred/non_blocking/roles-all-codex-current-dev-2026-07-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/roles-all-codex-current-dev-2026-07-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
