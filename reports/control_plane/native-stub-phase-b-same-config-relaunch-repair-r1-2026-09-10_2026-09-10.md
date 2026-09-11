# Native Stub Phase B Same Config Relaunch Repair R1 2026-09-10

Date: 2026-09-10
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR]
Wave ID: native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 323be3fa11af3c1682e54596e6ac9ca8847e74fbf786edf39e3bbfabc0be3f69
Purpose: Repair the observed native-stub same-config relaunch path so an exactly authorized locked Phase B candidate resumes through the existing recoverable Phase B surface instead of being sent back through Phase A.

## Scope

Add only the missing launcher-level Phase B continuation selection and its exact observed-state regression coverage.

Files and surfaces in scope:

- TASKS.md queue synchronization from the exact R3 merge.
- CHANGELOG.md landing record.
- mu/tools/executors/launch_wave.py.
- mu/tests/tools/test_launch_wave.py.
- Builder-generated packet, same-wave indicator, and optional bridge nonblocker.
- TASKS.md -- tracker-sync authority. The 2026-09-10 tracker sync note for wave `native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Add a pre-producer same-config Phase B continuation check parallel to the existing post-commit continuation check.
2. Authorize continuation only when the unchanged native WaveConfig, routing envelope, launch authority, candidate authority, and discovered packet sources pass existing exact validation and the selected packet has one locked Phase B lifecycle with only balanced allowlisted post-lock machine blocks.
3. For that exact state, invoke the existing recoverable dispatcher Phase B surface with the tracked packet, canonical routing record, namespaced bus, and existing role and pager environment overrides.
4. Do not rerun packet, TASKS, routing, candidate-authority, bridge, or indicator producers before Phase B continuation dispatch.
5. Model the observed R2 state in the existing launcher test file: locked Phase B packet, exact indicator block, staged candidate, same config, and no completed handoff. Prove one Phase B dispatch, no Phase A dispatch, and byte-identical packet, index, TASKS, routing, authority, and staged scope at the dispatch boundary.
6. Retain the existing initial unlocked Phase A path and existing corrected-config fresh-wave rejection for changed or tampered packet/config authority.
7. Synchronize the serial queue as landed retry-idempotency R3 -> this launcher repair -> fresh fleet census R3 -> classification -> bounded apply -> retained queue -> Mu production -> optimization last.

## Constraints

- Do not relax Phase A native packet validation or make Phase A accept post-lock machine sections.
- Do not modify executor_dispatch.py, phase_a_executor.py, phase_b_executor.py, bridge code, recovery_gate.py, commit_executor.py, role configuration, runtime, substrate, PR disposition, or fleet mutation code.
- Do not repair or broaden reviewer-envelope parsing in this wave.
- Do not rewrite ROUTE_PHASE_A into mutable same-attempt route authority; use the existing explicit recoverable Phase B surface.
- Do not authorize an unlocked packet, a changed WaveConfig, a mismatched route, malformed machine blocks, or candidate-authority drift.
- Use preserved retry-idempotency R2 only as read-only failure evidence; do not resume, adopt, mutate, or delete it.
- Do not absorb nonblocking findings or hypothetical launcher edge cases.

## Stop conditions

- Do not launch until comparison_commit is replaced with the exact landed retry-idempotency R3 merge SHA.
- If the existing recoverable Phase B surface cannot carry the exact routing and candidate authority without modifying executor_dispatch.py, stop rather than widening the wave.
- If implementation requires weakening Phase A or native-contract validation, stop.
- If continuation selection can match an unlocked, changed, tampered, or non-Phase-B packet, stop fail-closed.
- If any implementation file outside the exact allowlist is required, stop for narrower routing.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_launch_wave.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py -k 'phase_b_surface_reads_routing_record_path or phase_b_surface_forwards_dispatcher_owned_routing_record or phase_b_surface_success_chains_to_commit' --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10 --wave-class L4_ENABLER`

## Acceptance criteria

- The exact staged R2-shaped regression relaunches directly through the recoverable Phase B surface exactly once and never invokes Phase A.
- Packet, index, TASKS, routing, candidate authority, indicator, and staged candidate bytes remain unchanged before continuation dispatch.
- An initial unlocked same-config launch still routes through Phase A.
- Changed config, routing envelope, launch authority, candidate authority, packet identity, status, lock, or post-lock machine blocks remain rejected before dispatch.
- Existing dispatcher Phase B surface tests continue proving routing-record intake, dispatcher-owned authority forwarding, recovery, and commit chaining.
- The complete launcher test file and staged L4 contract pass through the pipeline.
- TASKS.md records this repair landed and keeps fresh fleet census R3 immediately next.

## Grounding / Authorization

- Task: [NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR]; wave id `native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10`.
- Governing packet: this file, `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md`.
- TASKS.md authority: the 2026-09-10 tracker sync note for wave `native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10`
- Active packet: `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md`
- Indicator artifact: `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md`
  - `reports/deferred/non_blocking/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10 --output reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_launch_wave.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py -k 'phase_b_surface_reads_routing_record_path or phase_b_surface_forwards_dispatcher_owned_routing_record or phase_b_surface_success_chains_to_commit' --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md`, `reports/deferred/non_blocking/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_bridge_nonblockers.md`, `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10`
- Active packet: `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4e5953d5399f6ce8ee50c38bd130386685f62187eb5181d1f2adabd656d16343`
- Indicator artifact: `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_launch_wave.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_executor_dispatch.py -k 'phase_b_surface_reads_routing_record_path or phase_b_surface_forwards_dispatcher_owned_routing_record or phase_b_surface_success_chains_to_commit' --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md`, `reports/deferred/non_blocking/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_bridge_nonblockers.md`, `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_2026-09-10.md`
  - `reports/deferred/non_blocking/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/native-stub-phase-b-same-config-relaunch-repair-r1-2026-09-10.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
