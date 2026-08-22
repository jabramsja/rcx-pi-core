# PR 1219 P0IMRPAT Provenance Requirement Anchor 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMRPAT-PROVENANCE-REQUIREMENT-ANCHOR]
Wave ID: pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22
Phase-A-Lock: LOCKED
Purpose: Carry the reviewed P0IMRPA bootstrap commit and P0IMRPAS numbering repair forward from exact ff2e0304432b1405cf1584f44e26535e1291fc29, then close only the reproduced P1 downgrade in standalone candidate-authority receipt verification: deleting reviewer_agent, reviewer_launch_provenance, and its hash from a receipt while clearing reviewer_agent in the bus-local spec and omitting launch routing identity must never reconstruct a legacy-shaped payload and return current. Anchor the provenance requirement in immutable code/schema or explicit caller-owned trusted authority rather than the mutable artifacts being verified, without activating P0IMRP producer/consumer behavior or widening into unrelated receipt robustness.

## Scope

Fresh nested repair branch at exact clean P0IMRPAS head ff2e0304. Modify only candidate_authority.py, its existing focused test module, TASKS canonical tracker note, and standard same-wave governance. Reproduce the exact P1 before changing code, enforce an immutable provenance-required trust boundary, and preserve the exhausted P0IMRPA/P0IMRPAS lanes, PR #1232, all PROGRAM QUEUE rows, and every later packet unchanged.

Files and surfaces in scope:

- mu/tools/executors/candidate_authority.py (MODIFY) -- make provenance-required receipt verification fail closed when mutable receipt/spec provenance fields are simultaneously stripped and no trusted routing/spec identity exists; the requirement must come from immutable schema/code semantics or explicit caller-owned trusted authority, never only the artifacts being verified.
- mu/tests/tools/test_candidate_authority.py (MODIFY) -- reproduce the exact PR #1232 P1 by stripping all three receipt provenance fields, clearing reviewer_agent in the bus-local authority spec, and ensuring launch routing identity is absent; prove rejection plus valid launch-bound/trusted-spec behavior and relevant tamper/drift regressions.
- TASKS.md (MODIFY THROUGH PIPELINE) -- add only the canonical launcher-generated P0IMRPAT tracker note; preserve every PROGRAM QUEUE row, label, number, state, order, prose, dependency, North Star invariant, and other TODO byte.
- reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md (GENERATED) -- sole governing same-wave repair packet.
- reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json (GENERATED BEFORE REVIEW) -- exact same-wave current-candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave deferrals; unrelated edge cases cannot widen or delay this active P1 repair.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from a fresh clean canonical branch whose HEAD and comparison commit are exact P0IMRPAS commit ff2e0304432b1405cf1584f44e26535e1291fc29; prove ff2e0304 has exact P0IMRPA commit 7e95e66d as its parent and preserve both commits unchanged.
2. Add a focused regression that mints a valid reviewer-provenance receipt, removes reviewer_agent, reviewer_launch_provenance, and reviewer_launch_provenance_hash, clears reviewer_agent in the bus-local authority spec, leaves no launch routing identity, and proves the current implementation wrongly accepts the downgraded payload before repair.
3. Implement the smallest fail-closed trust anchor so provenance-required status cannot be downgraded by editing the receipt and spec together. Prefer immutable accepted-schema/code semantics or an explicit caller-owned trusted spec/identity; do not treat another untrusted bus-local snapshot as sufficient authority.
4. Preserve valid governed Phase B verification with trusted_spec, exact model/effort/config/command drift detection, provider polymorphism, and all existing candidate inventory/allowlist/index authority. Make any legacy-receipt compatibility choice explicit and fail closed rather than guessing.
5. Run the full focused candidate-authority module, compile check, staged L4 gate, and diff check, then leave commit, broad pre-push, push, new PR creation, bot review, CI, merge, exact dev verification, and cleanup to the pipeline.

## Constraints

- Exact clean P0IMRPAS commit ff2e0304432b1405cf1584f44e26535e1291fc29 is the comparison base and direct parent authority. Use a fresh canonical P0IMRPAT worktree, branch, and namespaced bus; preserve the P0IMRPA and P0IMRPAS worktrees, buses, branches, receipts, recovery records, commits, and PR #1232 unchanged.
- Use the trusted detached predecessor launcher source at exact P0IMQR merge 14f3bc4acc828e49ba3d8c6c251bc8e899f97837 so neither unmerged candidate implementation can authorize its own repair delta. The new receipt governs only the comparison-relative P0IMRPAT candidate.
- Candidate production/test scope is only candidate_authority.py and test_candidate_authority.py plus exact same-wave governance. Do not modify executor_common.py, launch_wave.py, Phase A/B, commit_executor.py, recovery_gate.py, bridge adapters/config, role/model defaults, runtime, substrate, seeds, registries, hooks, or unrelated tests/docs.
- Do not activate meta/pre-commit production, commit consumption, or bot-remediation routing in this wave. Do not absorb fresh P0IMRP, P0IM, P0IB, P0T, P0R2, legacy-delta materialization, or any P2/nonblocking robustness issue.
- P0IMRPAT is a nested landing repair, not a new numbered PROGRAM QUEUE row. All model-bearing roles and pager routing use Codex; commit remains providerless. No manual candidate edit, index mutation, commit, push, review-thread mutation, PR closure, merge, or gate bypass is authorized.

## Stop conditions

- Halt before implementation unless exact ff2e0304432b1405cf1584f44e26535e1291fc29 is clean HEAD and comparison_commit, its direct parent is exact 7e95e66d8e26a6b01977b08459be06955ef28807, origin/dev remains exact 14f3bc4acc828e49ba3d8c6c251bc8e899f97837, and the new branch/worktree/bus identities are fresh and canonical.
- Halt as NEEDS_RESCOPING if the exact downgrade does not reproduce, if a correct fix requires any production file beyond candidate_authority.py, if governed trusted-spec verification would be weakened, or if backward compatibility would accept provenance stripping rather than fail closed.
- Halt on any comparison-relative path outside the literal allowlist, any rewrite or omission of 7e95e66d/ff2e0304, any PROGRAM QUEUE or North Star change, or any proposal to resolve the P1 by comment suppression, manual merge, mutable self-attestation, or disabling bot/P1/critical-path policy.
- Do not release fresh P0IMRP until deterministic combined P0IMRPA/P0IMRPAS/P0IMRPAT merge, exact merge SHA, origin/dev equality, and cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py`

## Acceptance criteria

- The exact simultaneous downgrade attack is a focused regression: stripped receipt provenance fields plus cleared bus-spec reviewer_agent plus absent routing identity deterministically raises CandidateAuthorityError and can never return status=current.
- The provenance-required decision is anchored outside the mutually mutable receipt/spec artifacts, either in immutable accepted-schema/code semantics or explicit trusted caller authority; removing, downgrading, or contradicting that authority fails closed.
- Valid Codex and provider-polymorphic provenance receipts still prepare and verify; governed Phase B trusted_spec verification, exact model/effort/command/config drift checks, receipt tampering checks, and candidate inventory authority remain green.
- The comparison-relative staged set is exactly candidate_authority.py, test_candidate_authority.py, TASKS.md, the same-wave packet, the same-wave indicator, and only if generated the exact same-wave deferred nonblocker report. No PROGRAM QUEUE or North Star content changes.
- The repair commit has exact parent ff2e0304, which has exact parent 7e95e66d. The pipeline-created PR against dev contains all three commits; focused tests, compile, staged L4, broad pre-push, independent review, bot review, required CI, merge, exact origin/dev proof, and cleanup pass.

## Grounding / Authorization

- Task: [PR1219-P0IMRPAT-PROVENANCE-REQUIREMENT-ANCHOR]; wave id `pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous narrower packets whenever a wave stops converging and prioritized landing valuable work over unrelated edge cases. The standalone downgrade was previously a nonblocking proof limit, but GitHub classified it P1 on a critical executor path and commit policy now actively blocks the otherwise-green combined PR. P0IMRPAT is therefore the minimum active-blocker repair; all other edge cases remain deferred.

FOUNDER_OVERRIDE:pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_candidate_authority.py`
  - `mu/tools/executors/candidate_authority.py`
  - `reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tools/executors/candidate_authority.py`, `reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a9f00a7cf2a5c8286ace92760d0d8667f7d93e473ac36280dd77ace0f9b17580`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tools/executors/candidate_authority.py`, `reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_candidate_authority.py`
  - `mu/tools/executors/candidate_authority.py`
  - `reports/control_plane/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrpat-provenance-requirement-anchor-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
