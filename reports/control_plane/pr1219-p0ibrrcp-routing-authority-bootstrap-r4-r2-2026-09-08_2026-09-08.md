# PR 1219 P0IBRRCP Routing Authority Bootstrap R4 R2 2026-09-08

Date: 2026-09-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-ROUTING-AUTHORITY-BOOTSTRAP-R4]
Wave ID: pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 4438c72919500716f62e71e3e77584548ec6011b441a16456ceb849713f5c45d
Purpose: Land only the dispatcher candidate-authority carry-forward repair in one fresh bounded bootstrap after evidence-handoff R4. Preserve the exact launch-owned candidate authority across canonical routing refresh and the normal Phase A to Phase B rebuild, fail closed before persistence or Phase B launch when required authority is missing, and leave R3C5, R3C6, exact P0IBRRCP closure, urgent PR and fleet reconciliation, builder-input hardening, and Mu production serialized behind this merge.

## Scope

One fresh dispatcher-only bootstrap from the exact evidence-handoff R4 merge. Modify executor_dispatch.py, its existing focused test module, TASKS current/next and preservation truth, and exact builder-generated same-wave governance only. The predecessor dispatcher cannot carry its own candidate-introduced authority fields into Phase B, so this wave alone uses the existing optional bootstrap route without claiming strict launch-bound review authority.

Files and surfaces in scope:

- mu/tools/executors/executor_dispatch.py (MODIFY) -- add one fail-closed carry-forward seam for the exact launch-owned candidate_authority_required and candidate_authority pair and use it in canonical refresh and normal Phase A to Phase B reconstruction.
- mu/tests/tools/test_executor_dispatch.py (MODIFY) -- add positive deep-equality regressions for both rebuild seams and negative regressions proving required true plus missing paired authority neither persists a downgraded canonical record nor launches Phase B.
- TASKS.md (MODIFY) -- mark evidence-handoff R4 landed with exact PR and merge truth, preserve the stopped August routing R4 lane, make this fresh successor sole CURRENT, make R3C5 the immediate NEXT and R3C6 follow it, and retain exact P0IBRRCP closure, PR census, never-behind, PR disposition, fleet cleanup, builder-input hardening, Mu production, and all later obligations.
- reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md (GENERATED) -- canonical complete Phase A packet derived by launch_wave.py from this WaveConfig.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json (GENERATED BEFORE PHASE B REVIEW) -- same-wave L4 indicator.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave nonblockers only.
- TASKS.md -- tracker-sync authority. The 2026-09-08 tracker sync note for wave `pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Add one dispatcher helper that copies candidate_authority_required and candidate_authority without normalization or reconstruction and returns a deterministic failure when required authority lacks its paired object.
2. In _refresh_canonical_routing_record_state, validate and capture launch-owned authority before any canonical write, attach the exact fields to refreshed state, and persist no intermediate downgraded record.
3. In _continue_successful_executor_chain, attach the exact captured fields to phase_b_routing before Phase B argv construction; required true with missing paired authority must return before _run_executor_in_group.
4. Preserve the complete candidate_authority object by deep equality, including required, precommit_inventory, spec_path, spec_identity, target_branch_authority, and nested values; do not regenerate it from mutable bus state.
5. Add one positive and one required-missing negative regression for each of the two rebuild seams, then run the entire existing dispatcher test module as the canonical evidence command.
6. Update TASKS without deleting or reordering later work, and keep stopped lanes immutable noncomplete evidence rather than source authority.
7. After merge, launch R3C5 fresh from this exact merge with pre_review_authority true; never resume the preserved August routing R4 or R3C4 lanes.

## Constraints

- The external JSON WaveConfig is the operator input; launch_wave.py generates the complete canonical Markdown Phase A packet. Do not rewrite or replace that generated packet after launch.
- Production and test scope is exactly mu/tools/executors/executor_dispatch.py and mu/tests/tools/test_executor_dispatch.py, plus TASKS and exact same-wave generated governance.
- Every Phase A author, Phase A reviewer, Phase B implementer, Phase B reviewer, and remediation role must remain foreground-only and single-agent: do not spawn, delegate, or wait on subagents. Emit the bounded result in the same turn.
- Do not modify launch_wave.py, executor_common.py, phase_a_executor.py, phase_b_executor.py, candidate_authority.py, commit_executor.py, recovery_gate.py, bridge code/config, receipt schemas, runtime, substrate, hosts, seeds, projections, Mu, or Claude-owned files.
- Do not copy, resume, mutate, cherry-pick, or patch-transfer implementation bytes from the preserved August routing R4, R3C4, evidence-handoff, or other stopped lanes; reconstruct from the exact fresh predecessor and locked packet.
- Do not weaken candidate allowlist, comparison authority, independent review, staged L4, supervisor, receipt, providerless commit, push, CI, or merge gates. All model-bearing roles and pager remain Codex gpt-5.6-sol ultra.
- Do not absorb R3C4 findings, parser variants, malformed legacy record variants beyond the required missing-authority negative, receipt formatting, provider behavior, timeout tuning, PR/fleet cleanup implementation, docs polish, or unrelated/non-occurring edge cases. Record real nonblockers and continue.

## Stop conditions

- Stop before launch unless source, target initial HEAD, comparison commit, local origin/dev, and remote dev all equal the exact PR #1273 merge SHA; the source is detached and clean; target, branch, bus, and remote branch identities are fresh; Codex role pins resolve; and commit remains providerless.
- Stop as NEEDS_RESCOPING only if closure requires a production or test path outside executor_dispatch.py and test_executor_dispatch.py or requires changing a separately serialized authority surface.
- Stop as DEFECT if canonical refresh can persist a record after required authority becomes absent or unequal, or if the Phase A chain can launch Phase B after the same loss.
- Stop as DEFECT if either positive route changes any candidate_authority value or if existing optional records regress.
- Do not stop, widen, or delay for preserved-lane findings, optional wording, later cleanup work, or non-occurring edge cases outside the exact dispatcher carry-forward invariant.
- If a builder-input failure occurs, preserve the lane and diagnose the exact builder defect; do not revise the generated packet in place.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py`

## Acceptance criteria

- The candidate changes only TASKS.md, executor_dispatch.py, test_executor_dispatch.py, and exact same-wave builder-generated packet, indicator, and optional nonblocker artifacts.
- Canonical stale-state refresh returns and persists candidate_authority_required and candidate_authority deeply equal to launch input without any intermediate downgraded write.
- Normal Phase A to Phase B chaining passes the same exact fields in Phase B routing JSON before process launch.
- Required true plus missing paired authority fails before persistence or Phase B launch; the canonical sentinel remains byte-unchanged and the Phase B runner remains uncalled.
- The whole test_executor_dispatch.py module passes, Python compilation passes, staged L4 enforcement is compliant, and providerless commit, push, PR, CI, review, and merge complete through the normal pipeline.
- TASKS records exact predecessor merge truth, this successor as sole CURRENT, R3C5 as immediate NEXT, R3C6 after it, and every urgent PR/worktree, never-behind, cleanup, builder-hardening, P0IBRRCP, Mu, post-Mu, and optimization obligation without deletion.
- The review record explicitly states pre_review_authority false for this one bootstrap and makes no strict launch-bound identity claim; the fresh post-merge R3C5 is launched with strict authority.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-ROUTING-AUTHORITY-BOOTSTRAP-R4]; wave id `pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md`.
- TASKS.md authority: the 2026-09-08 tracker sync note for wave `pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tools/executors/executor_dispatch.py`, `reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `e4dc1c2de73337ad6f834d9acdea482070158c2f745996f37ed1c0222f3294e6`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tools/executors/executor_dispatch.py`, `reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08_2026-09-08.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-routing-authority-bootstrap-r4-r2-2026-09-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
