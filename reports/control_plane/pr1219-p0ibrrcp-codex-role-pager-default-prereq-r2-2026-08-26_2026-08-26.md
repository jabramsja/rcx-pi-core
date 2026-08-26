# PR 1219 P0IBRRCP Codex Role And Pager Default Prerequisite R2 2026-08-26

Date: 2026-08-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-CODEX-ROLE-PAGER-DEFAULT-PREREQ-R2]
Wave ID: pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26
Phase-A-Lock: LOCKED
Purpose: Replace the preserved nonconvergent R1 attempt with a complete, bounded candidate that lands the committed Codex/Codex role selection and Codex pager fallback together with every directly coupled committed-default synchronization assertion required by pre-push-fast, while preserving providerless commit execution and all provider-menu choices.

## Scope

From exact PR 1245 merge authority, use set_roles.py to select Codex/Codex, explicitly select the Codex pager route, atomically update both raw committed-default assertion sites including the full backend/reviewer/pager tuple, and record the preserved R1 stop plus R2 tracker truth without changing the pre-existing CURRENT/NEXT queue.

Files and surfaces in scope:

- mu/tools/executors/executor_config.json (MODIFY) -- use set_roles.py for Codex/Codex and set pipeline_agent_pager.route to codex; preserve commit_executor null and all provider-menu entries.
- mu/tests/tools/test_pipeline_agent_pager.py (MODIFY) -- replace the existing Claude committed-default assertion with one atomic Codex assertion covering role agents, all model-bearing backends, bridge reviewers, providerless commit, and pager route.
- mu/tests/tools/test_bridge_config_model_sync.py (MODIFY) -- update the entire committed selection block atomically: role_agents Codex/Codex; post_merge_supervisor, dialectic_executor, phase_a_executor, phase_b_executor, and bot_remediation Codex; commit_executor null; bridge reviewers Codex; pager enabled with Codex route. Preserve bridge_agent_defaults assertions and all other sync behavior.
- TASKS.md (MODIFY) -- add only the R2 same-wave tracker record and a preservation record for the stopped R1 target/source/commits/stash; preserve the existing CURRENT/NEXT/P0R2 queue, every task, every stopped attempt, all five TODO-bearing lines, and PR/fleet cleanup order.
- reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md (GENERATED) -- sole canonical replacement packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator collected and staged before review.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-08-26 tracker sync note for wave `pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct only from exact merge 8b08902052e94bbf9b000def5f9c7bbde1be8f34. Do not copy root WIP or any file/commit/stash from stopped R1; preserve every stopped lane and artifact unchanged.
2. Run python3 mu/tools/executors/set_roles.py --implementer codex --reviewer codex --repo-root "$PWD" inside the clean candidate, then explicitly set pipeline_agent_pager.route to codex while preserving enabled=true and commit_executor=null.
3. Update the complete raw selection expectations in both scoped test files in the same implementation turn. Do not stop after the first assertion: the full role_agents/backends/bridge_reviewers/pager tuple must match the new committed config before Phase B.
4. Run the exact three-selector evidence command before review, and include both modified test files in Phase B final testing so pre-push-fast cannot discover a stale committed-default assertion after commit.
5. Add the narrow R2 tracker and stopped-R1 preservation truth to TASKS without reordering or deleting any existing queue/task/TODO/cleanup authority.
6. Complete launch_wave.py dispatcher, Phase A, Phase B, providerless terminal executor, PR checks, Codex review clearance, and merge through the normal immutable-source pipeline.

## Constraints

- Functional/test scope is exactly executor_config.json plus the two directly coupled committed-default assertion files, TASKS.md, and same-wave generated governance. Add no adapter, template, runtime, recovery, commit, hook, or Mu semantic file.
- Do not modify set_roles.py, executor_common.py, bridge_supervisor.py, run_review.py, bridge templates, phase_a_executor.py, phase_b_executor.py, commit_executor.py, dispatcher, launcher, hooks, Claude-owned files, runtime/substrate code, or Mu semantics.
- Do not remove Claude or Fable from bridge_agent_defaults. They remain available provider-menu choices but must not be selected by committed role, backend, bridge-reviewer, or pager defaults.
- Do not run set_orchestrator_mode.py --apply inside the candidate.
- Do not widen into absent-config fallbacks, standalone bridge submit defaults, claude_agent_sdk review mode, synthetic claude-session labels, request_for_claude aliases, provider-local memory, or the R1 recovery/stash mechanism. Those are inactive or separately serialized packets.
- Do not rewrite CURRENT/NEXT/P0R2 queue authority in this replacement. TASKS ownership is limited to the R2 tracker and stopped-R1 preservation note.
- Use launch_wave.py and the immutable-source pipeline only. No manual candidate patch, staging, commit, push, PR, merge, source substitution, or stopped-R1 folding.
- Every model-bearing implementation, review, meta-review, pager, bot-remediation, and recovery role is Codex. Commit execution remains providerless.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from 8b08902052e94bbf9b000def5f9c7bbde1be8f34; if target is dirty; if identity collides; or if Codex/Codex/Codex pins or providerless commit are unavailable.
- Stop as NEEDS_RESCOPING if any clean pre-push failure proves another tracked committed-default assertion outside the two scoped test files; preserve the candidate and create another bounded replacement rather than tier-3 assertion-by-assertion recovery.
- Stop and preserve if review demands adapter, fallback, template, runtime, bridge, recovery, convergence, commit, or Claude-owned-file work in this packet.
- Do not stop or widen for provider-menu entries, legacy request_for_claude names, synthetic Claude prose, absent-config fallbacks, standalone unused review paths, spelling, or any nonblocking edge case.
- Do not resume, edit, delete, or source from R1. Its target, bus, source, local commits, and stash are immutable preservation evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_pipeline_agent_pager.py`

## Acceptance criteria

- Only the seven allowlisted candidate paths change and no packet alias is created.
- Raw tracked role_agents equals {implementer: codex, reviewer: codex}; all five model-bearing backends equal codex; commit_executor remains null; bridge_reviewers equals {phase_a: codex, phase_b: codex}; pager remains enabled with route codex.
- test_pipeline_agent_pager.py and test_bridge_config_model_sync.py both assert the complete new committed selection and contain no stale assertion selecting Claude for a role, backend, bridge reviewer, or pager fallback.
- Claude and Fable remain provider-menu choices but are not selected defaults.
- The exact three-selector evidence command passes before review; both modified test files, relevant set_roles/config-alignment/dispatcher/launcher tests, staged L4 enforcement, pre-push-fast, and required CI pass.
- TASKS records R2 and the stopped R1 preservation facts without changing existing CURRENT/NEXT/P0R2 authority or losing any task, stopped attempt, TODO line, or cleanup ordering.
- Launch evidence proves Codex/Codex/Codex pins, providerless terminal execution, required CI, fresh Codex review clearance, and normal merge completion.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-CODEX-ROLE-PAGER-DEFAULT-PREREQ-R2]; wave id `pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md`.
- TASKS.md authority: the 2026-08-26 tracker sync note for wave `pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26` is canonical for this packet's L4 fields.
- Authorization: The founder requires Codex for everything, launch_wave.py builders, preservation of all WIP, and narrow replacement packets when a wave does not converge. R1 demonstrated a deterministic clean-pre-push recursion because its directly coupled sync test was omitted. This R2 is the smallest complete replacement that can pass the real landing gate.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_pipeline_agent_pager.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/executors/executor_config.json`, `reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `89df8bb9d27cd6009c0100dd63fc4fe4700a3a96a4796a2d6f036cc27f490d90`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/executors/executor_config.json`, `reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_2026-08-26.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-codex-role-pager-default-prereq-r2-2026-08-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
