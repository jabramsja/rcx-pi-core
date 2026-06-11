# N3-Kernel-Driver-Watchdog-Accepted-Boundary-Marker-Truth-2026-06-11 2026-06-11

Date: 2026-06-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11
Phase-A-Lock: LOCKED
Purpose: GOAL: An L4_ENABLER, NON-RUNTIME wave that records the two residual no-fuel kernel-driver host_iteration watchdog markers -- Python step_kernel_mu and JavaScript _stepKernelCore -- as an ACCEPTED-IRREDUCIBLE boundary at the max_steps/maxSteps watchdog, per the LOCKED decision (B) in the merged decision packet (PR #1099). The purpose is to durably CLOSE this reduction frontier so it stops being re-attempted as an open reduction TODO (it was re-attempted across 4 prior NO-GO waves before the decision was locked). This wave implements the WI-4 next-bounded-packet spec recorded in that decision packet. It changes documentation marker-truth wording and adds one read-only text-truth gate; it does NOT touch runtime, ratchet baselines, or any host_iteration marker.

## Scope

L4_ENABLER marker-truth recording wave (PR #1099 WI-4): record the two residual no-fuel kernel-driver host_iteration markers (step_kernel_mu, _stepKernelCore) as an ACCEPTED-IRREDUCIBLE boundary at the max_steps watchdog in mu/docs marker-truth wording + a new tests/l4_gates text-truth gate, durably closing the frontier per the locked (B) decision. No runtime/baseline/marker edit; zero-delta ratchets.

Files in scope (EDIT):
- `mu/docs/core/L3SubstrateArchitecture.v0.md` -- accepted-boundary record (WI-1).
- `mu/docs/core/BootstrapPrimitives.v0.md` -- max_steps primitive entry status update (WI-2).
- `tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py` -- NEW read-only text-truth gate (WI-3).
- `mu/tests/docs/test_growth_caps.py` -- CONDITIONAL, only if the new gate file trips a test-file/tool-script growth cap (WI-4).
- `reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md` -- this Phase A packet.

Files in scope (READ-ONLY, for the gate's assertions; editing them is FORBIDDEN in this wave):
- `mu/host/python/rcx_pi/selfhost/step_mu.py` -- the Python selfhost step_mu module (verbatim `step_kernel_mu` host_iteration marker string).
- `mu/host/js/engine/kernel.js` -- the JS engine kernel module (verbatim `_stepKernelCore` host_iteration marker string).
- `mu/tools/checks/host_semantics_baseline.json` -- the host-semantics ratchet baseline (asserted to track exactly one host_iteration marker per substrate; the ratchet checker's default baseline path `tools/checks/host_semantics_baseline.json` resolves here via the repo `tools -> mu/tools` symlink).
- `mu/tests/docs/test_l4_current_state_truth.py` (technique mirror for the new gate).
- `reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md` (binding decision packet, read-only authority).

- `reports/deferred/non_blocking/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

All work items derive from THE THREE EDITS in the supervisor request (below) and the TASKS.md tracker sync note for this wave; none re-derives or re-litigates the locked (B) decision.

- **WI-1 -- L3 substrate-architecture accepted-boundary record.** In `mu/docs/core/L3SubstrateArchitecture.v0.md`, add an "Accepted kernel-driver watchdog boundary" record adjacent to the canonical L3 truth statement ("execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics"). The record states: (i) the two residual host_iteration markers -- Python `step_kernel_mu` (selfhost step_mu module) and JS `_stepKernelCore` (JS engine kernel module) -- are ACCEPTED-IRREDUCIBLE at the max_steps/maxSteps watchdog per the locked decision (B), citing this wave id and the decision packet path; (ii) every no-fuel caller budget is a host numeric bound by design (33/33 census rows HOST-COUNT-DETERMINED, census recorded in the decision packet); (iii) this frontier is CLOSED as an open reduction absent a founder-authorized reversal.
- **WI-2 -- Bootstrap-primitives marker-truth update.** In `mu/docs/core/BootstrapPrimitives.v0.md`, in the max_steps primitive entry (the "cannot be structural fuel" termination-clock row) and, if present, the bootstrap-primitive inventory row referring to `step_kernel_mu`, replace any open-reduction framing with the locked ACCEPTED-boundary status, citing the decision packet; keep wording consistent with the existing "cannot be structural fuel" row.
- **WI-3 -- New read-only text-truth gate.** Create `tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py`, mirroring the technique of `mu/tests/docs/test_l4_current_state_truth.py` (read_text + content assertions; core tier; NO kernel execution; NO `run_mu` / `run_algorithm_meta_circular`). Three assertion groups: (a) both WI-1/WI-2 docs contain the ACCEPTED-boundary record citing this wave id; (b) the two host_iteration marker strings still exist VERBATIM in their two runtime files (Python step_mu module + JS engine kernel module), so a future silent marker removal/demotion fails the gate; (c) the host-semantics ratchet baseline still tracks exactly one host_iteration marker per substrate (Python and JavaScript), so any future marker movement on this frontier fails the gate unless it cites a founder reversal.
- **WI-4 -- CONDITIONAL growth-cap bump.** Only if adding the WI-3 gate file trips a test-file or tool-script growth cap in `mu/tests/docs/test_growth_caps.py`: bump the matching cap by exactly +1 with an inline comment citing this wave id and the FOUNDER_OVERRIDE token, and include `test_growth_caps.py` in the wave scope. No other cap or gate change is authorized.

## Constraints (NOT in scope)

- Class L4_ENABLER: NO runtime edit. No file under `mu/host/python/rcx_pi/selfhost/` or `mu/host/js/` may be modified; reading them for the gate's verbatim-marker assertions is in scope, editing them is not.
- NO ratchet baseline edit: host-semantics and host-authority-inventory baselines stay untouched.
- NO marker movement: no host_iteration marker may be added, removed, or reclassified in code.
- NO seed/registry/Stage0/scheduler/loader/binary edit.
- Do NOT reverse or re-litigate the locked (B) decision -- it is a binding input; this wave only RECORDS it.
- No edits beyond the WI-1..WI-4 file list; no opportunistic doc rewrites, marker work, or reduction attempts on other frontiers.

## Stop Conditions

Implementers MUST STOP (halt the wave and report, rather than adapt or widen scope) when any of the following occurs:

1. **Runtime-edit requirement.** Any work item turns out to require modifying a file under `mu/host/python/rcx_pi/selfhost/` or `mu/host/js/` -- that contradicts the L4_ENABLER class boundary. Stop and report; do not make the edit.
2. **Baseline/marker-delta requirement.** Completing WI-3 (or any other item) would require editing a ratchet baseline or adding/removing/reclassifying any host_iteration marker. Zero marker/authority delta is a hard wave invariant; stop and report.
3. **Stale census / missing verbatim marker.** Either marker string (Python `step_kernel_mu` host_iteration marker; JS `_stepKernelCore` host_iteration marker) cannot be found verbatim in its runtime module while writing the gate's group (b) assertions. The decision-packet census would be stale; stop and report the discrepancy -- do NOT adapt the gate to the drifted state.
4. **Baseline precondition fails.** The host-semantics ratchet baseline does not already track exactly one host_iteration marker per substrate (gate group (c) precondition fails before any edit). Stop and report; do not edit the baseline to make the gate pass.
5. **Nonzero evidence delta.** The evidence_command shows ANY nonzero marker/authority count delta after the edits (expected: Python host_iteration 1 / host_builtin 1; JS host_iteration 1 / host_builtin 2; tracked-marker total 5). Stop; the wave may not land with a delta.
6. **Decision re-litigation pressure.** Anything in scope would require reversing or re-litigating the locked (B) decision (e.g., a doc statement that cannot be updated without contradicting it). Founder decision required; stop and surface it.
7. **Unexpected gate/cap blockage.** A cap or gate other than the single matching growth cap in `mu/tests/docs/test_growth_caps.py` blocks the new gate file. Only the bounded +1 bump (WI-4) is authorized; any other gate bypass is ask-first. Stop and report.
8. **Completion.** WI-1..WI-3 (plus WI-4 if triggered) are landed and the evidence_command passes with zero delta. Stop -- do not extend into other reduction TODOs, marker work, or doc rewrites.

## Acceptance Criteria

1. `mu/docs/core/L3SubstrateArchitecture.v0.md` and `mu/docs/core/BootstrapPrimitives.v0.md` both carry the ACCEPTED-boundary marker-truth record, citing the decision packet (and, for the L3 doc record, this wave id), per WI-1/WI-2.
2. `tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py` exists and passes, with all three assertion groups holding: (a) doc records present; (b) both marker strings verbatim in their runtime files; (c) host-semantics baseline tracks exactly one host_iteration marker per substrate.
3. The gate is core-tier compliant: read_text + content assertions only; no kernel execution; no `run_mu` / `run_algorithm_meta_circular`.
4. The evidence_command passes end-to-end with ZERO marker/authority count delta -- both ratchets unchanged: Python host_iteration 1 / host_builtin 1; JS host_iteration 1 / host_builtin 2; tracked-marker total 5 unchanged.
5. No runtime, baseline, or marker edit anywhere in the wave-owned diff.
6. If WI-4 triggered: the growth-cap bump is exactly +1, with an inline comment citing this wave id and the FOUNDER_OVERRIDE token; no other cap changed.

## Grounding / Authorization

- **TASKS.md authorization:** Tracker sync note (2026-06-11, n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11) under `[NEXT-CODEX-POST-REDTEAM]` authorizes this wave: Class L4_ENABLER, target_gate_id G8, Packet = this file, evidence_command/evidence_delta as mirrored in the L4 fields block below. The tracker note carries the wave-bound override token verbatim.
- **Governing packet:** this file, `reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md` (Phase A governing packet for the wave).
- **Binding decision packet (read-only authority):** `reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md` -- LOCKED decision (B) ACCEPTED-IRREDUCIBLE, merged via PR #1099; this wave implements its WI-4 next-bounded-packet spec and does not reopen the decision.
- **Same-wave override (mechanically derivable by commit automation):**

FOUNDER_OVERRIDE:n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11

Scope of the override token: it backs the same-wave override derivation for commit automation and the bounded WI-4 growth-cap bump (+1, inline-commented) ONLY. It does NOT authorize runtime edits, ratchet baseline edits, marker movement, or any mechanical-gate bypass beyond WI-4.

## Request from Post-Merge Supervisor

GOAL: An L4_ENABLER, NON-RUNTIME wave that records the two residual no-fuel kernel-driver host_iteration watchdog markers -- Python step_kernel_mu and JavaScript _stepKernelCore -- as an ACCEPTED-IRREDUCIBLE boundary at the max_steps/maxSteps watchdog, per the LOCKED decision (B) in the merged decision packet (PR #1099). The purpose is to durably CLOSE this reduction frontier so it stops being re-attempted as an open reduction TODO (it was re-attempted across 4 prior NO-GO waves before the decision was locked). This wave implements the WI-4 next-bounded-packet spec recorded in that decision packet. It changes documentation marker-truth wording and adds one read-only text-truth gate; it does NOT touch runtime, ratchet baselines, or any host_iteration marker.

GROUNDING (binding inputs; do NOT re-derive): the decision packet (read-only authority for this wave) at reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md LOCKED decision (B) ACCEPTED-IRREDUCIBLE with a budget-source census of EVERY no-fuel caller into both drivers: 33 of 33 rows (13 Python + 20 JS) are HOST-COUNT-DETERMINED, 0 DATA-DETERMINED -- every no-fuel path's termination budget is a host numeric bound (driver max_steps/maxSteps defaults, host literals, API integers, or the host-count-realized stepBudget = max(20, 4*entry_count + 10) in run_metabolization_cycle / runMetabolizationCycle), so demoting the residual watchdog loop would either break the public no-fuel caller contract or construct fuel from a host count (which only MOVES host authority). The L3 Canonical Truth clause "execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics" governs the (B) classification. The tracked-marker floor of 5 (Python 1 host_iteration + 1 host_builtin; JS 1 host_iteration + 2 host_builtin) is ACCEPTED at this frontier.

THE THREE EDITS (all OUTSIDE runtime dirs; reading runtime files is in scope, editing them is NOT):
1. mu/docs/core/L3SubstrateArchitecture.v0.md -- add an "Accepted kernel-driver watchdog boundary" record adjacent to the canonical L3 truth statement: state that the two residual host_iteration markers (Python step_kernel_mu in the selfhost step_mu module; JS _stepKernelCore in the JS engine kernel module) are ACCEPTED-IRREDUCIBLE at the max_steps watchdog per the decision packet (cite this wave id and the decision packet path); every no-fuel caller budget is a host numeric bound by design (census recorded in the decision packet); this frontier is CLOSED as an open reduction absent a founder-authorized reversal.
2. mu/docs/core/BootstrapPrimitives.v0.md -- in the max_steps primitive entry (the "cannot be structural fuel" termination-clock row) and, if present, the bootstrap-primitive inventory row referring to step_kernel_mu, replace any open-reduction framing with the locked ACCEPTED-boundary status, citing the decision packet; keep wording consistent with the existing "cannot be structural fuel" row.
3. NEW read-only text-truth gate at tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py -- mirror the technique of the existing marker-truth gate mu/tests/docs/test_l4_current_state_truth.py (read_text + content assertions; core tier; NO kernel execution, NO run_mu / run_algorithm_meta_circular). The gate asserts: (a) both docs above contain the ACCEPTED-boundary record citing this wave id; (b) the two host_iteration marker strings still exist VERBATIM in their two runtime files (Python step_mu module + JS engine kernel module) -- so a future silent marker removal/demotion fails the gate; (c) the host-semantics ratchet baseline still tracks exactly one host_iteration marker per substrate (Python and JavaScript), so any future marker movement on this frontier fails the gate unless it cites a founder reversal.

CONSTRAINTS / OUT OF SCOPE: Class L4_ENABLER. NO runtime edit (no file under mu/host/python/rcx_pi/selfhost/ or mu/host/js/ may be modified; reading them for the gate's verbatim-marker assertions is in scope). NO ratchet baseline edit (host-semantics and host-authority-inventory baselines untouched). NO marker movement: no host_iteration marker may be added, removed, or reclassified in code. NO seed/registry/Stage0/scheduler/loader/binary edit. Do NOT reverse or re-litigate the locked (B) decision -- it is a binding input; this wave only RECORDS it. If adding the new gate file trips a test-file or tool-script growth cap (mu/tests/docs/test_growth_caps.py), bump the matching cap by exactly +1 with an inline comment citing this wave id and the FOUNDER_OVERRIDE token, and include test_growth_caps.py in the wave scope.

ACCEPTANCE: the two doc marker-truth records land citing the decision packet; the new tests/l4_gates gate exists and passes (its three assertion groups hold); the evidence_command shows ZERO marker/authority count delta (both ratchets unchanged: Python host_iteration 1 / host_builtin 1; JS host_iteration 1 / host_builtin 2; tracked-marker total 5 unchanged); no runtime/baseline/marker edit anywhere in the wave-owned diff.

Routed next-candidate:
n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11 --output reports/l4_wave_indicators/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11`
- Active packet: `reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/docs/core/BootstrapPrimitives.v0.md`
  - `mu/docs/core/L3SubstrateArchitecture.v0.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py`
  - `reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md`
  - `reports/deferred/non_blocking/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11`
- Active packet: `reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `25951707c594bc88ba528bdd8f0a2d6e86c7f7849674383de2c9e75bada3c726`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.json`
- Current staged files:
  - `TASKS.md`
  - `mu/docs/core/BootstrapPrimitives.v0.md`
  - `mu/docs/core/L3SubstrateArchitecture.v0.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py`
  - `reports/control_plane/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_2026-06-11.md`
  - `reports/deferred/non_blocking/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-watchdog-accepted-boundary-marker-truth-2026-06-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
