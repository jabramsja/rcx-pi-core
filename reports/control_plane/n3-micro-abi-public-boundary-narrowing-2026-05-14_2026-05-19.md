# N3-Micro-Abi-Public-Boundary-Narrowing-2026-05-14

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-micro-abi-public-boundary-narrowing-2026-05-14
Packet Class: L4_ENABLER control-plane planning packet
Target Implementation Class: L4_STRUCTURAL, only if Phase A returns GO
Phase-A-Lock: LOCKED
Governing Packet: `reports/control_plane/n3-micro-abi-public-boundary-narrowing-2026-05-14_2026-05-19.md`
FOUNDER_OVERRIDE:n3-micro-abi-public-boundary-narrowing-2026-05-14
Purpose: Run Phase A only for the next ordered N3 host-semantics reduction surface: public Micro-ABI boundary narrowing. The packet may authorize bounded investigation and plan lock only. It does not authorize implementation until Phase A proves an exact write set, parity proof, ratchet expectations, rollback/proof limits, and stop conditions.

Phase B repair note: Bridge Round 1 hard-stopped before any Micro-ABI runtime implementation because same-wave TASKS tracker authority was absent. The current Phase B change is a control-plane tracker-authority repair only; it does not claim L4_STRUCTURAL implementation authority for `rcx_load`, `rcx_step`, or `rcx_run`.

## Scope

Phase A is limited to the public Micro-ABI boundary around the current `rcx_load`, `rcx_step`, and `rcx_run` ingress/egress surfaces.

The in-scope file set for Phase A investigation and any downstream GO is locked to the exact paths below. A downstream implementation write set must be a subset of this list. If current code truth proves a required implementation, test, tracker, or evidence path outside this list is necessary, Phase A returns NO-GO and a separate packet must be routed instead of widening this packet.

Governance and evidence paths:

- `reports/control_plane/n3-micro-abi-public-boundary-narrowing-2026-05-14_2026-05-19.md` - governing packet and the only Phase A rewrite target.
- `TASKS.md` - read-only authorization and tracker-current-truth grounding for `[NEXT-CODEX-POST-REDTEAM]`; downstream tracker edits are allowed only if implementation automation hard-stops before code changes and a same-wave tracker sync is mechanically required.
- `reports/l4_wave_indicators/n3-micro-abi-public-boundary-narrowing-2026-05-14.json` - downstream indicator artifact if a later L4_STRUCTURAL implementation proceeds; do not create it during Phase A.

Python public-boundary implementation candidates:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py` - current seed-load boundary for `rcx_load` equivalents through `load_verified_seed_image()` and `load_verified_seed()`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py` - current `rcx_step` / `rcx_run` equivalents through `step_mu()` and `run_mu()`.

JavaScript public-boundary implementation candidates:

- `mu/host/js/core/seed_loader.js` - current seed-load boundary for `rcx_load` equivalents through `loadVerifiedSeedImage()` and `loadVerifiedSeed()`.
- `mu/host/js/cli/main.js` - CLI ingress load boundary through its local `loadVerifiedSeed()` wrapper.
- `mu/host/js/engine/kernel.js` - current step/run parity boundary through `stepKernel()`, `runStructural()`, and `stepKernelStructural()`.
- `mu/host/js/engine/pipeline.js` - current engine-run public ingress/egress only if Phase A selects engine result-envelope narrowing for `rcx_run`.

Existing focused proof candidates:

- `mu/tests/engine/test_seed_integrity.py` - Python `rcx_load` checksum/projection-id and malformed/tampered input boundary proof.
- `mu/tests/parity/test_seed_loading_parity.py` - Python/JS seed-load parity and projection-loader exclusion proof.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py` - L4 boundary-dispatch authority gate for load-side boundary changes.
- `mu/tests/structural/test_gate4_runtime_hardening.py` - Python `run_mu()` and structural runtime boundary hardening proof.
- `mu/tests/engine/test_phase8b_mechanical_kernel.py` - Python `step_mu()` mechanical kernel behavior proof.
- `mu/tests/parity/test_js_parity_automated.py` - Python/JS Mu host-object parity and rejection proof.
- `mu/tests/l4_gates/test_d009_production_depth_gate.py` - JS Mu host-artifact rejection gate.
- `mu/tests/docs/test_l4_current_state_truth.py` - current-state documentation guard for `rcx_run` fuel-threading truth only if the selected slice changes public Micro-ABI doctrine wording.

Already-closed work must stay closed. TASKS.md already records the engine-state/scheduler slice as landed and says not to relist those seed, fixture, structural-test, or scheduler-parity items as unresolved. TASKS.md also records the N3 projection-loader JS binary decoder parity wave as implemented with local evidence; projection-loader work is therefore not pending in this packet.

- `reports/deferred/non_blocking/n3-micro-abi-public-boundary-narrowing-2026-05-14_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Re-open current code truth for the public `rcx_load`, `rcx_step`, and `rcx_run` boundary only. Record the exact public inputs, public outputs, error surface, and any host-owned values currently crossing the boundary.
2. Build a before/after Micro-ABI table for those three public calls. The after state must shrink or normalize host object-model exposure rather than teaching Python or JavaScript new semantic behavior.
3. Choose exactly one bounded boundary-narrowing slice. Valid examples are public result-envelope narrowing, public error-envelope narrowing, or public input-shape rejection for host-owned objects. The selected slice must be small enough to implement symmetrically in Python and JavaScript with focused tests.
4. Lock the exact downstream write set as a subset of the in-scope paths listed above. The lock must name every implementation file, every parity or L4 test file, and every control-plane/tracker/evidence file required for the downstream implementation. If this cannot be named exactly within the listed paths, Phase A returns NO-GO.
5. Define the parity proof before implementation starts. The proof must include accepted Mu-shaped cases and rejected host-object cases for Python and JavaScript, and must show that `rcx_load`, `rcx_step`, and `rcx_run` remain behaviorally aligned at the narrowed public boundary.
6. Define ratchet expectations before implementation starts. The expected result is no host-semantics ratchet increase and no unaccepted host-authority inventory increase. Any proposed baseline update is out of scope for this packet.
7. Define rollback/proof limits. The rollback path is to preserve the current production/default boundary behavior until the narrowed adapter is proven; proof may claim boundary narrowing and parity only, not full L4 completion, bootstrap elimination, production readiness, or seed/registry migration.
8. Prepare the bounded implementation sequence for a later Phase B only: add or adjust the public-boundary adapter, apply the same shape in Python and JavaScript, add focused parity and rejection tests, run ratchets, collect indicators, and run the L4 execution contract with this wave id and the final wave class.

## Constraints

- Do not implement code in Phase A.
- Do not edit outside the final locked write set in any downstream phase.
- Do not add files, directories, tests, generated artifacts, tracker lines, or evidence files outside the exact in-scope path list above under this packet.
- Do not move VM semantics, scheduler behavior, seed behavior, projection-loader behavior, registry authority, numeric policy, binary/TLV policy, checksum policy, or production readiness into Python or JavaScript.
- Do not relist landed engine-state/scheduler, projection-loader, max-steps, or stack-guard work as unresolved.
- Do not change ratchet baselines to make the wave pass.
- Do not treat docs wording or stale packet text as proof that code work is unlanded.
- Do not use baseline-only cleanup as a substitute for structural boundary reduction.
- Do not edit Claude files.
- Do not make dispatcher, commit, push, recovery, or unrelated control-plane repairs under this packet unless Phase A returns NO-GO with a separate precise automation packet.

## Stop Conditions

Return NO-GO and stop before implementation if any condition is true:

- Current code truth already closed the public Micro-ABI boundary surface selected by this packet.
- The exact implementation and test write set cannot be locked to named files that are already listed in Scope.
- The selected slice requires new Python-only or JavaScript-only semantics instead of a parity-preserving boundary contraction.
- The selected slice touches seeds, registries, scheduler internals, projection-loader migration, binary/TLV production policy, checksum policy, or production default flips.
- Python and JavaScript cannot share the same public boundary rule and rejection behavior.
- Focused tests would only prove behavior in one substrate.
- Host-semantics ratchet output would increase, or host-authority inventory would report an unaccepted increase.
- Downstream automation requires a same-wave TASKS tracker entry and none is present or mechanically derivable before implementation.

## Acceptance Criteria

Phase A may return GO only when all of the following are true:

- The selected public Micro-ABI slice is exactly one bounded boundary-narrowing change for `rcx_load`, `rcx_step`, and/or `rcx_run`.
- The packet records a concrete before/after boundary table for public inputs, public outputs, errors, and host-object rejection behavior.
- The final write set names exact implementation files, exact test files, and exact evidence/control-plane files, and every named path is already present in the Scope list above.
- The parity proof names the focused Python/JS test cases for accepted Mu-shaped data and rejected host-owned data.
- The rollback/proof limit states that existing production/default behavior remains the fallback until the narrowed public boundary is proven.
- Ratchet expectations are explicit: host-semantics ratchet must not increase, and host-authority inventory must not gain unaccepted authority sites or total inventory.
- The validation plan includes focused parity tests, relevant L4 gates, `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`, `python3 tools/checks/check_host_authority_inventory_ratchet.py`, indicator collection for this wave id, and `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-micro-abi-public-boundary-narrowing-2026-05-14 --wave-class L4_STRUCTURAL` if implementation proceeds as structural work.
- Already-landed surfaces from TASKS.md are excluded from pending work and acceptance criteria.

Phase A must return NO-GO if any acceptance item cannot be proven from current code truth.

## Grounding / Authorization

TASKS.md lines 552-560 authorize `[NEXT-CODEX-POST-REDTEAM]` as founder-authorized and still OPEN for future bounded work not already proven by landed slices. TASKS.md line 560 also requires every wave to carry a control-plane packet plus a TASKS.md tracker entry, and allows manual pipeline repair only as a bounded unblocker paired with same-wave automation or a precise follow-up automation packet.

TASKS.md line 556 is binding current-truth grounding: the landed engine-state/scheduler slice must not be relisted as unresolved. TASKS.md line 568 is binding current-truth grounding for the prior N3 projection-loader JS binary decoder parity wave: it is implemented with local evidence and same-wave founder override, so projection-loader parity is not a pending work item here.

Bridge Round 1 targeted reviewer evidence found no exact TASKS.md match for `n3-micro-abi-public-boundary-narrowing-2026-05-14`, so the first strict wave-id binding failed before class/scope validation. The Phase B tracker-authority repair adds a same-wave `TASKS.md` tracker sync note for `n3-micro-abi-public-boundary-narrowing-2026-05-14` and preserves the packet-local `FOUNDER_OVERRIDE:n3-micro-abi-public-boundary-narrowing-2026-05-14` as the mechanical override token. This repair is control-plane authority sync only and must not be treated as structural Micro-ABI implementation authority.

Authorization: Phase A control-plane planning plus this Phase B tracker-authority repair under `[NEXT-CODEX-POST-REDTEAM]` and `FOUNDER_OVERRIDE:n3-micro-abi-public-boundary-narrowing-2026-05-14`. Runtime implementation still requires a separate GO result from this packet, exact write-set lock, parity proof, ratchet expectations, and L4 execution-contract compliance.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-micro-abi-public-boundary-narrowing-2026-05-14`
- Active packet: `reports/control_plane/n3-micro-abi-public-boundary-narrowing-2026-05-14_2026-05-19.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-micro-abi-public-boundary-narrowing-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-micro-abi-public-boundary-narrowing-2026-05-14_2026-05-19.md`
  - `reports/deferred/non_blocking/n3-micro-abi-public-boundary-narrowing-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-micro-abi-public-boundary-narrowing-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-micro-abi-public-boundary-narrowing-2026-05-14`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-micro-abi-public-boundary-narrowing-2026-05-14_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-micro-abi-public-boundary-narrowing-2026-05-14`
- Active packet: `reports/control_plane/n3-micro-abi-public-boundary-narrowing-2026-05-14_2026-05-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6a1ad9836ddbfa00eb8472c5439f73b74d4e990422d6ab390959b76fc1f7ea7b`
- Indicator artifact: `reports/l4_wave_indicators/n3-micro-abi-public-boundary-narrowing-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-micro-abi-public-boundary-narrowing-2026-05-14 --output reports/l4_wave_indicators/n3-micro-abi-public-boundary-narrowing-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-micro-abi-public-boundary-narrowing-2026-05-14_2026-05-19.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-micro-abi-public-boundary-narrowing-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-micro-abi-public-boundary-narrowing-2026-05-14_2026-05-19.md`
  - `reports/deferred/non_blocking/n3-micro-abi-public-boundary-narrowing-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-micro-abi-public-boundary-narrowing-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
