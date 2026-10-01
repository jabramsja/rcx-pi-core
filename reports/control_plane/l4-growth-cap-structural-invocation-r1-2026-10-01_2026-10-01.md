# Restore structural growth-cap settlement without supervisor override

Date: 2026-10-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [L4-GROWTH-CAP-PREBUMP-BUILDER]
Wave ID: l4-growth-cap-structural-invocation-r1-2026-10-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: f530ec6e0d595f84e52e236be378484672729ec40dd1b9765d75d636c827b03f
Purpose: Unblock the observed Mu R6 commit failure by separating explicit same-wave growth-cap invocation authority from class-restricted supervisor override. Reuse the existing parked task; no general hardening or new queue item. Root supplies only this external STUB; native Phase A authors the full packet.

## Scope

One commit consumer correction, existing receipt/launch/dispatch regression modules, TASKS/CHANGELOG and native-owned wave artifacts only. No launcher/PhaseB/runtime/fleet implementation changes.

Files and surfaces in scope:

- TASKS.md -- Carry complete PRIMARY tracker; existing growth-cap owner active and Mu blocked pending this narrow fix; preserve all cleanup and useful-work owners.
- CHANGELOG.md -- Record the actual bounded correction and proof, no Mu or fleet completion claim.
- mu/tools/executors/commit_executor.py -- Separate growth-cap invocation authority from supervisor/proof override at the actual commit call boundary; retain exact retry authority.
- mu/tests/tools/test_commit_executor_receipt.py -- Existing module only; focused observed-path regression and compatible integration coverage, no weakened assertions.
- mu/tests/tools/test_launch_wave.py -- Existing module only; focused observed-path regression and compatible integration coverage, no weakened assertions.
- mu/tests/tools/test_executor_dispatch.py -- Existing module only; focused observed-path regression and compatible integration coverage, no weakened assertions.
- reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md -- Native Phase A owns the full immutable packet.
- reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json -- Native generated/optional wave artifact only.
- reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_implementation_evidence.json -- Record executed regressions, exact changes, preservation checks and proof limits.
- reports/deferred/non_blocking/l4-growth-cap-structural-invocation-r1-2026-10-01_bridge_nonblockers.md -- Native generated/optional wave artifact only.
- TASKS.md -- tracker-sync authority. The 2026-10-01 tracker sync note for wave `l4-growth-cap-structural-invocation-r1-2026-10-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/l4-growth-cap-structural-invocation-r1-2026-10-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read exact diagnosis /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/mu_r6_growth_cap_invocation_root_cause_20261001.json and frozen Mu R6 preservation manifest /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/mu_coinduction_r6_stopped_candidate_20261001.json. Do not mutate /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-mu-coinduction-prefix-r6-20261001, its index, packet/config, receipts, lifecycle attempts or prior candidates. Mu R6 is terminal; no restart/retry of spent authority. Retain all useful sources and seven verified prior physical retirements.
2. Reproduce the actual caller-chain defect before editing: launch_wave.py3205-3209 persists correct founder token; commit_executor.py519-521/1124-1134 intentionally suppress supervisor overrides for L4_STRUCTURAL; run_commit_pipeline19484-19495 feeds that class-filtered token into growth-cap Step5e20157-20162, which rejects the canonical postimage at18963-18976. Existing test_run_commit_pipeline_omits_founder_override_for_structural_handoff must remain true. The raw token in actual R6 tracker/packet is present; this is not another builder omission or cap-byte repair.
3. Implement the smallest separation of authority domains: resolve explicit same-wave cap authorization for the growth-cap invocation without granting structural supervisor/proof override or fabricating missing authority. Preserve class restriction, all structural gates, staged-byte/HEAD/index/postimage checks, same-wave validation and existing enabler/maintenance behavior. Do not relabel Mu, expand allowed supervisor classes, weaken the exact-cap check, rely only on routing presence, or change cap values/generator/runtime.
4. Add regression in existing receipt module through actual run_commit_pipeline orchestration (not only a raw-token helper): structural explicit same-wave authority works for first canonical bump and exact postimage settlement; captured supervisor remains L4_STRUCTURAL with empty override; missing/wrong-wave authority and noncanonical candidate remain rejected with no unauthorized mutation. Reuse existing growth-cap fixtures and existing fail-closed cases. Run focused red/green tests first, then complete declared receipt/launcher/dispatcher modules and docs. Existing production assertions and structural omission regression remain unchanged or strengthened.
5. Preserve full current PRIMARY TASKS and every current task ID; use native tracker builder/canonical Ra note. Keep existing cleanup rows38/40, all retained-source/useful-work owners, and Mu-next ordering. Record proof in declared evidence JSON, never append custom sections to locked packet. Native pipeline owns staging/review/recovery/commit/CI/merge and preservation-safe primary/base sync. After landing, root resumes preserved Mu with this exact consumer fix verified, not a repeated unchanged packet.

## Constraints

- External STUB only; native Phase A authors complete packet. One native mutation lane. All selected LLM roles Codex gpt-6-astra/max, providerless commit and Codex pager. No manual root implementation/stage/commit/push/merge; no new watchdog.
- Only allowlisted paths. No runtime/seed/kernel, PhaseB, launch builder production, fleet, hooks/models, growth-cap file/count, old packet/config/receipt, assertion weakening, skip/xfail or timeout change. No speculative cases or new prerequisite waves.
- Keep stopped R6 and all other sources/indices/history/stashes/receipts immutable and recoverable; do not replay spent native/fleet authority. Seven physical retirements remain verified, residual fleet is not clean. Stop immediately on user stop or freshly observed quota<=10%; no finishing afterward.

## Stop conditions

- If exact regression needs a path outside the declared scope, report concrete failing command and required path; no post-lock scope widening, hypothetical expansion or bypass.
- Do not infer Mu production or useful-work completion from this enabler. Preserve evidence if any authorization/byte/identity bound cannot be verified.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- Actual commit-orchestration regression fails on landed base and passes with bounded fix, including authorized structural preimage/postimage cases and unchanged empty supervisor override.
- Missing/wrong-wave authorization and wrong bytes remain fail-closed. Existing enabler/maintenance/structural authority and complete declared modules/docs pass without weakened gates.
- Native independent review,CI,merge and protected PRIMARY/dev synchronization finish; TASKS/to-do accurately record enabler result, preserved Mu next, and unresolved folder/useful-work obligations.

## Grounding / Authorization

- Task: [L4-GROWTH-CAP-PREBUMP-BUILDER]; wave id `l4-growth-cap-structural-invocation-r1-2026-10-01`.
- Governing packet: this file, `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md`.
- TASKS.md authority: the 2026-10-01 tracker sync note for wave `l4-growth-cap-structural-invocation-r1-2026-10-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:l4-growth-cap-structural-invocation-r1-2026-10-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `l4-growth-cap-structural-invocation-r1-2026-10-01`
- Active packet: `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md`
- Indicator artifact: `reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md`
  - `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_implementation_evidence.json`
  - `reports/deferred/non_blocking/l4-growth-cap-structural-invocation-r1-2026-10-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `l4-growth-cap-structural-invocation-r1-2026-10-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/l4-growth-cap-structural-invocation-r1-2026-10-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id l4-growth-cap-structural-invocation-r1-2026-10-01 --output reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md`, `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_implementation_evidence.json`, `reports/deferred/non_blocking/l4-growth-cap-structural-invocation-r1-2026-10-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: l4-growth-cap-structural-invocation-r1-2026-10-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `l4-growth-cap-structural-invocation-r1-2026-10-01`
- Active packet: `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ab71667e81ded9eacc9c7afe32895611404ed27b884c020f79aeb5278867859a`
- Indicator artifact: `reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md`, `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_implementation_evidence.json`, `reports/deferred/non_blocking/l4-growth-cap-structural-invocation-r1-2026-10-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_2026-10-01.md`
  - `reports/control_plane/l4-growth-cap-structural-invocation-r1-2026-10-01_implementation_evidence.json`
  - `reports/deferred/non_blocking/l4-growth-cap-structural-invocation-r1-2026-10-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/l4-growth-cap-structural-invocation-r1-2026-10-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
