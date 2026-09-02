# Launch Wave Post-Commit Continuation Consumer R4

Date: 2026-09-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [LAUNCH-WAVE-POST-COMMIT-CONTINUATION-CONSUMER-R4]
Wave ID: launch-wave-post-commit-continuation-consumer-r4-2026-09-02
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: f105ad2c201d380f80924a9152454f285bbffc7f24057ae3dc6ea4968a44aae9
Purpose: Admit one same-wave post-commit launch_wave.py re-entry using only independently checkable config, packet, candidate, continuation, handoff, branch, and Git authority, without treating diagnostic route fields as authentication proofs.

## Scope

Land only the cross-bound post-commit continuation consumer in launch_wave.py, preserve the R2 and R3 non-convergence evidence in TASKS, and make PR1219 root-exit R4C the parser-visible immediate successor without weakening the urgent PR/fleet cleanup chain before Mu production.

Files and surfaces in scope:

- Exact permitted path 1: TASKS.md for tracker and PROGRAM QUEUE synchronization.
- Exact permitted path 2: mu/tools/executors/launch_wave.py for the read-only continuation admission fast path.
- Exact permitted path 3: mu/tests/tools/test_launch_wave.py for focused positive, refusal, no-mutation, and non-authoritative-diagnostic regressions.
- Exact permitted path 4: reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md for the Phase-A-authored canonical packet.
- Exact permitted path 5: reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json for the required L4 indicator.
- Exact permitted path 6, conditional only when real findings exist: reports/deferred/non_blocking/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_bridge_nonblockers.md.
- TASKS.md -- tracker-sync authority. The 2026-09-02 tracker sync note for wave `launch-wave-post-commit-continuation-consumer-r4-2026-09-02` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub; carry forward only useful reviewed implementation evidence from /private/tmp/WorkingRCX-source-continuation-consumer-r2-Codex0902.
2. Before any setup producer runs, validate the native packet contract and version-1 launch overrides exactly against this WaveConfig; bind route head_sha and merge_sha to comparison_commit and require launch-time blocker_report_paths to be exactly empty.
3. Require exact candidate spec identity, an explicit typed continuation receipt, an exact Phase B handoff digest with an explicit target_branch, equality of continuation/handoff/current branch, current committed HEAD and ancestry, and the dispatcher's normal commit-only readiness proof.
4. Treat timestamp_utc as diagnostic only. Treat state_sha only as the dispatcher's stale/fresh signal: a fresh or indeterminate route refuses the fast path, while a stale value alone grants nothing without every continuation authority above.
5. On complete proof, invoke the unchanged normal dispatcher command without rewriting packet, TASKS, route, candidate authority, bridge config, indicator, handoff, or continuation. On any required-authority mismatch, fall through to the existing corrected-config relaunch refusal before mutation.
6. Synchronize TASKS: mark R2 and R3 preserved/non-convergent with their exact reasons, R4 CURRENT, and use the already supported form **Unnumbered prerequisite baton — [ROLES-ALL-CODEX-PR1219-ROOT-EXIT-R4C] NEXT** as the immediate successor; preserve all numbered PR/fleet/Mu rows.

## Constraints

- Authority boundary: the local repo and agent bus are pipeline single-writer artifacts protected by the host/worktree boundary; this wave detects mismatches among independently produced artifacts but does not claim cryptographic resistance to an actor that can rewrite every local proof coherently.
- Authorization inputs are limited to WaveConfig-derived native/launch identity, candidate spec identity, typed continuation receipt, exact handoff digest and target branch, current branch, current committed HEAD/ancestry, and dispatcher commit-only readiness.
- Route timestamp_utc is non-authoritative diagnostic metadata. Route state_sha is only a freshness signal and may never substitute for continuation authority. Neither field must be copied into a new authority envelope or treated as a privilege grant.
- A launch-time target_branch_authority may be absent for a detached clean source and must not be synthesized. If present it must validate exactly; post-commit admission always requires the independently emitted handoff and continuation target branches.
- Do not add a producer digest, signer, MAC, migration, retrofit, compatibility route, continuation repair, or inference path.
- Phase-state rule: the pre-existing PROGRAM QUEUE remains canonical during Phase A; the same-wave tracker note authorizes this design pass, and Phase B must stage the explicit CURRENT/LANDED/NEXT reconciliation before review and commit. Do not describe the unimplemented R4 consumer as already current or landed.
- The six candidate paths above are a maximum allowlist; path 6 is conditional and must not be generated merely to reach a file count.
- Do not absorb producer R3, R4C, envelope validation, recovery policy, generic queue parser code, open-PR disposition, never-behind application, fleet cleanup, or Mu production.
- Every model-bearing role is Codex gpt-5.6-sol ultra; commit execution remains providerless; do not edit Claude-owned files or hand-author the canonical packet.

## Stop conditions

- Stop only for a reproduced authorization-path blocker requiring a file outside the six exact permitted paths or evidence that one of the enumerated authority artifacts cannot be checked without mutation.
- Defer non-occurring edge cases, coordinated all-artifact tamper outside the stated trust boundary, and diagnostics that cannot independently alter commit-only authorization.
- Do not revise this config or the Phase-A-authored canonical packet in place after launch; preserve any nonconvergent attempt and split a fresh narrower wave only for a reproduced active blocker.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`

## Acceptance criteria

- One valid same-config post_commit_pending fixture proves dispatcher commit-only resume occurs before every setup producer and leaves tracked files plus all pre-existing bus artifacts byte-identical before dispatch.
- Required-authority negative controls independently cover: native/config mismatch; version-1 launch override mismatch; route head_sha or merge_sha unequal to comparison_commit; non-empty blocker_report_paths; candidate spec mismatch; non-string or non-GO receipt_decision; missing/mismatched handoff digest; missing or mismatched explicit handoff target_branch; continuation wave/commit/branch mismatch; current branch mismatch; current HEAD mismatch; non-ancestor commit; fresh or indeterminate route; and dispatcher-not-ready state.
- Focused tests prove timestamp_utc cannot grant authorization and that an arbitrary stale-shaped state_sha still cannot resume without all required continuation proofs; these route-only values are not advertised as independently authenticated.
- Missing detached-launch target_branch_authority is accepted only when exact handoff, continuation, and current-branch equality supplies later authority; a present launch target authority must match exactly and is never inferred or repaired.
- Initial launch and every pre-commit partial-run behavior remain unchanged, the full launcher test file passes, and TASKS has exactly one parser-visible immediate root-exit R4C baton while retaining PR census, never-behind, PR disposition, fleet cleanup, and Mu production before production work.

## Grounding / Authorization

- Task: [LAUNCH-WAVE-POST-COMMIT-CONTINUATION-CONSUMER-R4]; wave id `launch-wave-post-commit-continuation-consumer-r4-2026-09-02`.
- Governing packet: this file, `reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md`.
- TASKS.md authority: the 2026-09-02 tracker sync note for wave `launch-wave-post-commit-continuation-consumer-r4-2026-09-02` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:launch-wave-post-commit-continuation-consumer-r4-2026-09-02

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `launch-wave-post-commit-continuation-consumer-r4-2026-09-02`
- Active packet: `reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md`
  - `reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id launch-wave-post-commit-continuation-consumer-r4-2026-09-02 --output reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md`, `reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: launch-wave-post-commit-continuation-consumer-r4-2026-09-02.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `launch-wave-post-commit-continuation-consumer-r4-2026-09-02`
- Active packet: `reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a0e190af2fd69c547e2842e32d7eabb3f92468d633073e5c83d698a685b189f8`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md`, `reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/launch-wave-post-commit-continuation-consumer-r4-2026-09-02_2026-09-02.md`
  - `reports/l4_wave_indicators/launch-wave-post-commit-continuation-consumer-r4-2026-09-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
