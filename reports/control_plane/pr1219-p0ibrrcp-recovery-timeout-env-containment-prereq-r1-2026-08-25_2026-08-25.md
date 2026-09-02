# PR 1219 P0IBRRCP Recovery Timeout Environment Containment Prerequisite R1

Date: 2026-08-25
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IBRRCP-RECOVERY-TIMEOUT-ENV-CONTAINMENT-PREREQ-R1]
Wave ID: pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 8ab5779bda52985afdcb1a62b9bc170331745da135fe15942f8b3b92b8a248a0
Purpose: Contain the two observed bridge-turn recovery-timeout variables at the shared commit-validation child boundary so live retry state cannot alter repository-owned validation tests.

## Scope

Land only the observed two-variable commit-validation environment leak from exact PR 1258 merge authority; do not widen recovery behavior or pursue theoretical environment cases.

Files and surfaces in scope:

- Contain the exact bridge-turn recovery-timeout override/key pair in the shared commit-validation environment helper and add focused proof in its existing test class.
- Update TASKS through builder-owned same-wave governance while preserving all queued PR/fleet and Mu-production obligations.
- TASKS.md -- tracker-sync authority. The 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub, then implement and validate only the reproduced shared-boundary fix.
2. Land through normal Phase B, providerless commit, PR, CI, review, merge, and cleanup; then advance to provider-terminal R4B.

## Constraints

- Do not change timeout values, retry classification, recovery routing, bridge behavior, provider/model configuration, or unrelated environment handling.
- Every model-bearing role is Codex gpt-5.6-sol ultra; commit execution remains providerless; do not edit Claude-owned files or hand-author the canonical packet.

## Stop conditions

- Stop only for a reproduced in-scope blocker requiring a file outside the allowlist or for failed exact candidate authority; do not widen for non-occurring edge cases.
- Do not revise this same wave config or packet after native-stub admission; any genuinely nonconverging blocker requires a fresh narrower builder wave.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`

## Acceptance criteria

- The exact two bridge-turn recovery-timeout variables cannot reach any commit-owned validation child, including when supplied through caller overrides, and parent os.environ remains unchanged.
- Unrelated recovery variables and all existing commit, hook, live-lane, and dispatcher recovery semantics remain unchanged; focused and pipeline gates pass and the PR merges.

## Grounding / Authorization

- Task: [PR1219-P0IBRRCP-RECOVERY-TIMEOUT-ENV-CONTAINMENT-PREREQ-R1]; wave id `pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md`.
- TASKS.md authority: the 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25

## Non-normative review clarification

The immutable native launcher contract above remains unchanged. For the two blocking review findings only, its Scope resolves to this explicit and exhaustive file allowlist:

1. `mu/tools/executors/commit_executor.py` -- implementation surface for the shared commit-validation child-environment containment helper.
2. `mu/tests/tools/test_commit_executor_receipt.py` -- focused proof surface in `TestCommitValidationChildBusIsolation`.
3. `TASKS.md` -- builder-owned same-wave tracker-sync authority already named in Scope.

The immutable Work items above map to these concrete bounded design tasks:

1. In `mu/tools/executors/commit_executor.py`, add `RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE` and `RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY` to post-override child-environment containment, after caller overrides are applied and before any commit-owned validation child is launched.
2. In `mu/tests/tools/test_commit_executor_receipt.py::TestCommitValidationChildBusIsolation`, add a focused proof that inherited values for both variables are absent from the validation child environment.
3. In the same test class, add a focused proof that caller-override values for both variables are absent from the validation child environment.
4. In the same test class, prove that containment does not mutate parent `os.environ`.
5. In the same test class, prove that unrelated environment variables are preserved in the validation child environment.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `b3221e93899455a0169ef0ff5c9a5bb54ac8913e913411810424b01e389d630f`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25_2026-08-25.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-recovery-timeout-env-containment-prereq-r1-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
