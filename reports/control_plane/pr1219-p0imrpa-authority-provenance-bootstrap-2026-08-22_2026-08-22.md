# PR 1219 P0IMRPA Authority Provenance Bootstrap 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMRPA-AUTHORITY-PROVENANCE-BOOTSTRAP]
Wave ID: pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22
Phase-A-Lock: LOCKED
Purpose: After exact P0IMQR PR #1231 merge 14f3bc4acc828e49ba3d8c6c251bc8e899f97837, perform the migration-safe first half of P0IMRP: land the provider-polymorphic launch-bound provenance parser/validator and the candidate-authority receipt writer/verifier under the existing trusted predecessor receipt schema. This bootstrap must not load candidate authority code into the predecessor Phase B process or claim that the new receipt field self-authorized the wave. It makes the landed source capable of minting and verifying the new field for the immediately following fresh P0IMRP producer/consumer activation wave.

## Scope

Founder-authorized queue-transition and schema-bootstrap predecessor to P0IMRP. Start and compare at exact P0IMQR PR #1231 merge 14f3bc4acc828e49ba3d8c6c251bc8e899f97837 in a fresh unique lane/bus. Candidate production scope is only the shared provenance parser/validator and candidate-authority writer/verifier. Preserve the stopped P0IMRP lane and reconstruct only these authorized semantics through the pipeline; do not load candidate authority into Phase B, activate meta/pre-commit production, or enforce commit consumption in this wave.

Files and surfaces in scope:

- mu/tools/executors/executor_common.py (MODIFY) -- add one provider-polymorphic, fail-closed parser/validator for launch-bound bridge adapter provenance from a namespaced bus command: selected agent, exact model, exact reasoning effort/effort, deterministic command hash, and bridge-config hash/path identity. Do not mutate configuration or serialize secrets/environment values.
- mu/tools/executors/candidate_authority.py (MODIFY) -- add selected reviewer launch-bound provenance to the current-candidate receipt and include it in deterministic recomputation, bus/config drift detection, and tamper verification for future waves.
- mu/tests/tools/test_candidate_authority.py (MODIFY) -- prove exact Codex gpt-5.5/xhigh extraction, provider-polymorphic command shapes, receipt recomputation, and missing/malformed/ambiguous/tampered provenance rejection without weakening candidate authority.
- TASKS.md (MODIFY THROUGH PIPELINE) -- record the stopped P0IMRP attempt as preserved/rescoped, insert P0IMRPA as CURRENT, fresh P0IMRP producer/consumer activation as immediate NEXT, and P0IM after exact P0IMRP merge; preserve and renumber every other queue/TODO row without loss.
- reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json (GENERATED BEFORE REVIEW) -- same-wave indicator.
- reports/deferred/non_blocking/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblockers only.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the bootstrap boundary on exact 14f3bc4a: trusted Phase B imports candidate_authority once from detached source, so another review entry overwrites any manually candidate-minted new-schema receipt.
2. Reconstruct only the parser/validator and candidate-authority writer/verifier semantics from the preserved stopped P0IMRP evidence. Independently verify every hunk; do not cherry-pick, copy unrelated changes, or absorb meta/pre-commit or commit-executor behavior.
3. Parse only the immutable launch-bound namespaced-bus adapter command. Support provider-polymorphic --model/-m and --effort or model_reasoning_effort forms; reject missing, duplicate, conflicting, empty, or non-string selectors; hash exact command/config bytes without exposing secrets.
4. Bind reviewer provenance into candidate-authority receipt construction and verify-current recomputation so later command/config drift or receipt tampering fails closed in waves launched from this merge.
5. Keep this wave's live pre-review receipt governed by predecessor schema. Prove the new code with focused tests and do not present a candidate-minted receipt as authority for its own merge.
6. Update TASKS without deleting or reordering unrelated successors. Route implementation, independent review, providerless commit, CI, merge, exact dev proof, and cleanup only through the pipeline.

## Constraints

- Exact P0IMQR PR #1231 merge 14f3bc4acc828e49ba3d8c6c251bc8e899f97837 is the hard dependency; HEAD, origin/dev, comparison_commit, source, and target must all equal it before launch.
- Candidate production allowlist is only executor_common.py and candidate_authority.py, with one focused existing test module and exact same-wave governance artifacts. This external WaveConfig is excluded.
- Do not modify meta_bridge_supervisor.py, meta_bridge_client.py, bridge adapters, Phase A/B executors, commit_executor.py, executor_config.json, launch_wave.py, role/model defaults, runtime, substrate, or unrelated tests/docs.
- Do not load or refresh candidate candidate_authority.py inside the predecessor Phase B process. Trusted review authority remains detached-source code; candidate code cannot mint authority for its own merge.
- This wave's predecessor-schema live receipt is expected bootstrap evidence. Do not require or claim that it contains the new provenance field; the immediate successor supplies first live activation proof from landed source.
- Preserve all stopped/current P0IM and P0IMRP lanes and buses unchanged. All roles and pager use Codex; commit remains providerless. Nonblockers and edge cases cannot delay the serial bootstrap.

## Stop conditions

- Halt before launch unless exact P0IMQR PR #1231 merge 14f3bc4acc828e49ba3d8c6c251bc8e899f97837 equals origin/dev, HEAD, and comparison_commit; source/target are fresh and clean; bus/branch are unique; roles/pager are Codex; and commit is providerless.
- Halt as NEEDS_RESCOPING if a production change outside executor_common.py or candidate_authority.py is required, or if implementation requires candidate-code authority loading, meta/pre-commit production, commit enforcement, adapter execution, Phase A/B control flow, model defaults, or role topology changes.
- Halt as DEFECT if provenance can disagree with the exact launch-bound command, derives from mutable defaults after launch, omits model or effort, serializes secrets/environment values, or is not covered by drift/tamper tests.
- Do not release fresh P0IMRP or P0IM until deterministic P0IMRPA PR, merge SHA, origin/dev equality, and cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py`

## Acceptance criteria

- Focused tests prove the landed parser extracts exact agent/model/reasoning effort and deterministic command/config identity across supported provider-polymorphic command forms and rejects missing, duplicate, conflicting, malformed, or ambiguous selectors.
- Focused tests prove future candidate-authority receipts write the provenance, recompute it from immutable launch-bound authority, and reject receipt or bus/config drift/tampering.
- The independent reviewer explicitly confirms the bootstrap trust boundary: this wave is authorized by the predecessor receipt schema, does not claim a new-schema self-attestation, and does not load candidate authority into Phase B.
- No meta/pre-commit producer, client refresh, commit enforcement, adapter behavior, role/model default, runtime, substrate, or unrelated change enters the candidate.
- TASKS records the exact preservation/rescope state and serial queue P0IMRPA -> fresh P0IMRP -> P0IM without losing any other TODO row.
- Focused tests, compile proof, staged L4 enforcement, diff check, independent review, providerless commit, CI, merge, exact origin/dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMRPA-AUTHORITY-PROVENANCE-BOOTSTRAP]; wave id `pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous narrow prerequisite packets when a wave stops converging and explicitly prioritized landing over nonblocking edge cases. The live P0IMRP attempt exposed a deterministic self-schema bootstrap boundary plus an out-of-scope commit-consumer defect. P0IMRPA is the smallest trust-preserving queue-transition packet and leaves all valuable stopped candidate evidence intact.

FOUNDER_OVERRIDE:pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_candidate_authority.py`
  - `mu/tools/executors/candidate_authority.py`
  - `mu/tools/executors/executor_common.py`
  - `reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tools/executors/candidate_authority.py`, `mu/tools/executors/executor_common.py`, `reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `dfe8b2ae578edfdd2e2187e58513f4568792ddbb6291fe926745f0405845891d`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tools/executors/candidate_authority.py`, `mu/tools/executors/executor_common.py`, `reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_candidate_authority.py`
  - `mu/tools/executors/candidate_authority.py`
  - `mu/tools/executors/executor_common.py`
  - `reports/control_plane/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrpa-authority-provenance-bootstrap-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
