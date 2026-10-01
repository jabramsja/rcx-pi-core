# Complete native metadata authority across dispatcher and Phase B handoffs

Date: 2026-09-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [MU-COINDUCTION-PRODUCTION-PROOF]
Wave ID: native-structural-metadata-roundtrip-r2-2026-09-28
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: cb0b9bed294baf5a6b92ae98d228bdf3e00765c8962758e463c223fac4587f12
Purpose: Finish the existing Mu enabler using the preserved R1 candidate, adding the demonstrated missing dispatcher scope. R1 fixed metadata preservation, immutable-envelope binding and early structural authorization but could not land because the canonical recovery route dropped its envelope. Repair both actual dispatcher route rebuilds and land once; then continue the preserved Mu runtime. No new queue item or runtime change.

## Scope

Reuse the preserved metadata/authorization candidate and add only the demonstrated missing dispatcher envelope transport plus its tests. Cover normal Phase A-to-B chaining and canonical recovery rebind, retaining exact authority and compatibility. No runtime, fleet, commit/recovery redesign or hypothetical hardening.

Files and surfaces in scope:

- TASKS.md -- Carry complete current PRIMARY TASKS including the new real NOW anchor for the existing Mu task; preserve all268IDs/ownership and update only this blocker and truthful next Mu handoff.
- CHANGELOG.md -- Record the executed builder repair and regression proof, without claiming the stopped Mu runtime has merged.
- mu/tools/executors/launch_wave.py -- Bind the existing validated structural metadata into native packet authority/rendering and run the existing structural task-authorization predicate before launch writes/model dispatch; no new metadata naming scheme or gate bypass.
- mu/tools/executors/phase_a_executor.py -- Narrow matching native contract shape/render/validation support for the builder-owned structural metadata; retain exact integrity checks and explicit compatible behavior for existing envelopes.
- mu/tools/executors/phase_b_executor.py -- Preserve explicit declared workload_target and both host_semantics_delta fields when building pre-supervisor and final-handoff trackers; use existing legacy inference only where no explicit authoritative metadata exists.
- mu/tools/executors/executor_dispatch.py -- Preserve the exact validated native_stub_packet_contract in the real Phase A-to-B route and atomic canonical rebind; retain existing candidate/terminal/founder/pager authority. Do not regenerate native authority from mutable packet headers.
- mu/tests/tools/test_launch_wave.py -- Portable regression for actual structural metadata roundtrip, missing NOW/NEXT fail-before-write admission and valid existing task authorization; keep all prior launcher coverage.
- mu/tests/tools/test_phase_a_executor.py -- Exact native contract/render validation and metadata tamper rejection using the actual supported structural envelope; preserve legacy/non-structural behavior.
- mu/tests/tools/test_phase_b_executor.py -- Reproduce stage0_vm scope overriding explicit execution_layer_truth, then prove all three fields survive pre-supervisor and handoff generation and existing downstream commit-field extraction; no live-repo fixtures.
- mu/tests/tools/test_executor_dispatch.py -- Portable real-route rebuild regressions for both demonstrated envelope losses, exact digest/identity retention, existing malformed-authority rejection and unmarked legacy compatibility; assert persistence and actual chained argument delivery, not just a helper return.
- reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md -- Native Phase A owns the full packet; implementer must not hand-edit the locked contract or add ad hoc H2s.
- reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_implementation_evidence.json -- Record actual failing reproduction, corrected builder results, cheap gate outcomes, unchanged preserved source identities, tests and proof limits.
- reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json -- Native collector and commit path own measured L4_ENABLER indicators.
- reports/deferred/non_blocking/native-structural-metadata-roundtrip-r2-2026-09-28_bridge_nonblockers.md -- Optional native nonblocking findings only; no speculative prerequisite queue.
- TASKS.md -- tracker-sync authority. The 2026-09-28 tracker sync note for wave `native-structural-metadata-roundtrip-r2-2026-09-28` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. First read the preserved R1 terminal manifest /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/metadata_roundtrip_r1_stopped_candidate_20260928.json and root-cause record /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/metadata_roundtrip_r1_reentry_evidence_routing_root_cause_20260928.json. Read the twelve-file candidate in /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-structural-metadata-roundtrip-r1-20260928 without mutation. Reuse its three executor edits and three corresponding test edits after verifying hashes. It already repairs all three metadata fields, envelope/packet binding, both real tracker builders, early structural NOW/NEXT admission and the test-only reader-clock waits. Do not reimplement from an earlier weaker revision. R1 TASKS/CHANGELOG/evidence/packet/indicator must not replace this wave's fresh identities.
2. Carry complete current PRIMARY TASKS including the existing Mu NOW anchor, all268task IDs and cleanup ownership. Update this same task and one native canonical Ra note truthfully. Native Phase A owns the full R2 packet. Do not copy or edit old native packets, source raw indices, configs, routes, stashes, spent cleanup receipts or preservation manifests.
3. Reproduce the actual producer defects using the candidate's real builders and portable disposable repository fixtures: executor_dispatch._continue_successful_executor_chain constructs a Phase B route without native_stub_packet_contract; executor_dispatch._refresh_canonical_routing_record_state refreshes canonical routing via a generic builder and restores candidate/terminal authority but not the native envelope. The active R1 canonical route lost the envelope at10:45:59Z; both supervisor evidence attempts then failed. Fix both actual route projections, not the validator's absence semantics.
4. Carry the exact validated launch-owned native envelope through those two observed projections, preserving nested identity/contract/digest and the existing atomic no-downgrade write behavior. Reuse the existing strict native validator; present malformed or mismatched authority must not become an unmarked legacy route. Do not reconstruct or re-sign authority from mutable packet text; do not broadly copy unrecognized route fields. Preserve all existing candidate/terminal/founder/pager behavior and legacy absence semantics.
5. Retain R1's structural payload and strict packet/envelope binding across every real Phase B tracker call. Portable integration must exercise WaveConfig -> native envelope/packet -> actual dispatcher canonical rebind and A-to-B argument -> both pre-supervisor and durable handoff tracker regeneration -> existing commit marker extraction, with workload_target=execution_layer_truth, a conflicting stage0_vm path and distinct before/after host-semantic descriptions. Test the reproduced changed-header/unchanged-envelope attack still fails before trusted tracker emission.
6. Retain early structural NOW/NEXT admission before launch writes/model work through the existing check_tasks_authorization predicate. Current PRIMARY existing Mu authorization passes; Ra-only/PROGRAM QUEUE prose and founder override do not authorize a missing structural task. No new approval layer or unrelated behavior change.
7. Retain the recovered test-only clock virtualization that removed repeated real two-second sleeps from mocked bridge-review tests; maintain its real artifact IO, missing/partial/ready/delayed findings regressions and unchanged production timeout behavior. No timeout cap increase, reduced test scope or broad monkeypatch of production execution.
8. Run the six full declared modules after final edits. The immutable R2 evidence command invokes candidate-code regressions, not a live bootstrap routing file that an already-running old dispatcher may have produced. Independently report actual native packet/tracker/authorization status honestly; do not assert a missing native envelope validates True or claim an old running process hot-loaded the patch. Include a cheap isolated candidate-code whole-chain RED/PASS regression before expensive validation.
9. Preserve the stopped23-file Mu R4 source at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-mu-coinduction-prefix-r4-20260928 and its manifest /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/mu_coinduction_r4_stopped_candidate_20260928.json. The next existing Mu continuation must keep all24expected vector outcomes and passing runtime fixes, replace only the new document's hardcoded projection-count wording with a registry/count-test reference, carry current NOW authority and prove explicit metadata with these landed builders before expensive suites. This enabler does not alter or claim landing of that runtime.
10. Native Phase B/commit own implementation, staging, indicator collection, independent review, pre-push, CI, merge and protected dev synchronization. Record source hashes and actual tests in this wave's evidence. After this demonstrated blocker lands, go directly back to preserved Mu work; no new numbered prerequisite or speculative queue expansion.

## Constraints

- Root writes an external STUB only; use launch_wave.py and dispatcher. Native Phase A owns the full immutable packet. Phase B must not rewrite its locked packet or add custom H2 sections.
- One native mutation lane. All selected model roles Codex gpt-6-astra/max, commit providerless, pager Codex; no quota watchdog/latch recreation. Root performs one-shot quota milestones and immediate stop at or below10%.
- Only declared files may change. No runtime/substrate/seed/parity implementation edits, no host authority/debt baseline changes, no Claude-owned edits, no recovery/commit/fleet redesign or speculative hardening.
- Preserve all stopped source files, raw indices, configs, native routes, held stashes and spent cleanup/lifecycle records; no unchanged retries, authority reset, force deletion or fake closure.
- Keep explicit structural metadata values and immutable authority intact. No target downgrade, empty-proof relabel, skipped tests, timeout increase, broad gate relaxation or forged NOW authority.
- Evidence must run real candidate-code handoff/rebind paths. This is a self-hosted control-plane repair: do not make proof depend on a pre-merge bootstrap process magically hot-reloading newly implemented code. Do not weaken native authority or hide an actual failing candidate-code regression.
- Scope is the already-reproduced metadata/authorization defects plus their proven missing dispatcher producer. All unrelated non-blockers remain deferred; no new numbered task.

## Stop conditions

- If an undeclared write is actually required, report the exact observed producer/consumer or test failure before expanding scope; do not infer speculative dependencies.
- If native packet or canonical Ra authority fails, preserve evidence and use the actual supported builder path; no manual locked-packet or consumed-authority edits.
- Do not claim the Mu runtime, all fleet cleanup, infinite productivity or production-complete proof from this L4_ENABLER. Existing Mu continuation remains required after this blocker lands.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_tracker_sync_note_generation.py mu/tests/tools/test_commit_executor_receipt.py --tb=short`

## Acceptance criteria

- Recovered R1 source/test behavior is preserved, including exact structural fields, launch-envelope binding, both real Phase B tracker paths, early structural authorization and test-only timing fix.
- Portable before/after tests of the actual dispatcher Phase A-to-B call and canonical rebind reproduce the omitted envelope, then preserve its complete validated digest/identity/contract exactly. Persisted route and delivered Phase B arguments are checked; existing atomic authority guards and legacy behavior still pass.
- Whole-chain portable real-builder integration preserves execution_layer_truth despite stage0_vm scope, retains both exact host-semantics strings through both tracker stages, and existing commit extraction reads all three fields. The demonstrated metadata tamper remains rejected.
- All six full declared modules, native validation, docs, L4_ENABLER gates, independent review, commit/pre-push/CI, merge and protected dev sync pass without new runtime/host authority or weakened gates.
- All stopped candidates, indices, stashes, receipts and268task IDs remain preserved. TASKS and durable to-do agree on this existing enabler and the next preserved Mu documentation/runtime continuation, with no false Mu or fleet completion.

## Grounding / Authorization

- Task: [MU-COINDUCTION-PRODUCTION-PROOF]; wave id `native-structural-metadata-roundtrip-r2-2026-09-28`.
- Governing packet: this file, `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md`.
- TASKS.md authority: the 2026-09-28 tracker sync note for wave `native-structural-metadata-roundtrip-r2-2026-09-28` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:native-structural-metadata-roundtrip-r2-2026-09-28

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `native-structural-metadata-roundtrip-r2-2026-09-28`
- Active packet: `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md`
- Indicator artifact: `reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md`
  - `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_implementation_evidence.json`
  - `reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id native-structural-metadata-roundtrip-r2-2026-09-28 --output reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_tracker_sync_note_generation.py mu/tests/tools/test_commit_executor_receipt.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_a_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md`, `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_implementation_evidence.json`, `reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: native-structural-metadata-roundtrip-r2-2026-09-28.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `native-structural-metadata-roundtrip-r2-2026-09-28`
- Active packet: `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9e6b5e727703af0a8feef9a1cdfab95d0be9dc79e5dc4c04e4541ad8c738857d`
- Indicator artifact: `reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_tracker_sync_note_generation.py mu/tests/tools/test_commit_executor_receipt.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_a_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md`, `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_implementation_evidence.json`, `reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_2026-09-28.md`
  - `reports/control_plane/native-structural-metadata-roundtrip-r2-2026-09-28_implementation_evidence.json`
  - `reports/l4_wave_indicators/native-structural-metadata-roundtrip-r2-2026-09-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
