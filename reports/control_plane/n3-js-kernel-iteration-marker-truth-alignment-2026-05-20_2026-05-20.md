# N3-Js-Kernel-Iteration-Marker-Truth-Alignment-2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-js-kernel-iteration-marker-truth-alignment-2026-05-20
Class: L4_STRUCTURAL
Category: /mu structural host-semantics marker truth alignment
Phase-A-Lock: LOCKED
Purpose: Build a bounded Phase A plan for correcting JavaScript host-iteration marker truth before any further host-semantics reduction. This wave is a drift-correction prerequisite: it must preserve ratchet count while ensuring the tracked JS `@host_iteration` marker names the active kernel driver loop, not a legacy or boundary wrapper.
FOUNDER_OVERRIDE:n3-js-kernel-iteration-marker-truth-alignment-2026-05-20

## Scope

In scope for the planned implementation:

- `mu/host/js/engine/kernel.js`: candidate active JS engine kernel loop, specifically `_stepKernelCore` and its `for (let i = 0; i < maxSteps; i++)` driver loop cited by the routing evidence.
- `mu/host/js/core/bootstrap_core.js`: current JS `@host_iteration` marker location at `bootstrap_core.step`, to be treated as the candidate stale marker surface unless Phase A proves it is still the true tracked production kernel primitive.
- `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`: focused L4 marker-truth structural-test surface for proving marker placement truth and preventing marker laundering.
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`: existing pre-push L4 gate that must enforce the same active-loop marker truth instead of the stale `bootstrap_core.step` location.
- `mu/tests/tools/test_check_host_semantics_ratchet.py`: focused ratchet-tool test surface if the marker move requires scanner expectation coverage.
- `mu/tools/checks/check_host_semantics_ratchet.py`: canonical host-semantics scanner/ratchet command surface for validation; read only except for running validation.
- `tools/checks/check_host_semantics_ratchet.py`: repo-root host-semantics ratchet wrapper/compatibility surface for validation; read only except for running validation.
- Python paired-kernel marker context is read-only grounding only: the routing evidence identifies the paired Python marker at `rcx_pi/selfhost/step_mu.py:1163` on `step_kernel_mu`; this wave must not edit Python runtime behavior.

Out of scope for this packet rewrite itself: implementation edits, downstream runtime inspection, test execution, ratchet execution, and TASKS.md edits. This packet only locks the first real Phase A plan.

## Work Items

1. Confirm same-wave authorization before implementation.
   - Use the `[NEXT-CODEX-POST-REDTEAM]` queue in `TASKS.md:569-586` as the current task authority.
   - Treat `TASKS.md:577` as binding governance: every wave requires both a control-plane packet and a `TASKS.md` tracker entry.
   - Hard stop until the exact wave id `n3-js-kernel-iteration-marker-truth-alignment-2026-05-20` is present in `TASKS.md` or an equivalent same-wave tracker sync is mechanically supplied by the pipeline.

2. Reproduce the marker-location evidence before touching implementation.
   - Confirm `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` still reports the current expected marker inventory and does not already show this wave's intended correction.
   - Confirm the root wrapper surface at `tools/checks/check_host_semantics_ratchet.py` remains validation-only for this wave.
   - Confirm JS `@host_iteration` is still only on `mu/host/js/core/bootstrap_core.js:293`.
   - Confirm `_stepKernelCore` in `mu/host/js/engine/kernel.js` still owns the active `maxSteps` iteration loop cited by the request.
   - Do not inspect broader implementation surfaces unless this focused reproduction contradicts the routing evidence.

3. Select GO branch A only if current code confirms `_stepKernelCore` is the tracked active production kernel loop.
   - Move the JS `@host_iteration` marker from `bootstrap_core.step` to the `_stepKernelCore` active loop.
   - Preserve the same marker category and ratchet count; this is a truth-alignment move, not a reduction.
   - Add focused structural tests in `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py` proving the active `_stepKernelCore` loop is tracked and `bootstrap_core.step` is not the only marker-bearing JS kernel surface.
   - Add or adjust ratchet-tool coverage only in `mu/tests/tools/test_check_host_semantics_ratchet.py`, and only if needed to prove the scanner preserves marker-count truth for the move.
   - Ensure tests fail if the marker is deleted, left only on `bootstrap_core.step`, or moved to a non-active wrapper while the active loop remains untracked.

4. Select NO-GO branch B if current code proves `bootstrap_core.step` is still the true tracked production kernel primitive.
   - Do not move the marker.
   - Record the reproduction evidence and stop with a precise follow-up packet recommendation if another authority boundary must be resolved first.

5. Validate no semantic or authority expansion occurred.
   - Prove no production behavior change in Python or JS.
   - Prove no new host authority, no ratchet baseline edit, and no host-semantics count reduction using `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` plus the existing host-authority inventory validation.
   - Keep any test additions structural and marker-truth focused.

## Constraints

- No host-semantics baseline reduction in this wave.
- No marker deletion without a same-category active-loop marker replacing it.
- No production semantic changes.
- No Python behavior changes.
- No JS behavior changes beyond marker-comment placement and focused structural test updates in `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py` plus the pre-existing pre-push guard `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`, with `mu/tests/tools/test_check_host_semantics_ratchet.py` touched only if scanner expectation coverage is required.
- No new host authority.
- No seed, registry, Stage0, scheduler, loader, binary/TLV, checksum, integrity, dispatcher, commit, push, PR, or closeout edits.
- No broad refactor.
- No Claude-file edits.
- No re-listing already landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.
- No implementation until Phase A converges and same-wave TASKS tracker authority exists.

## Stop Conditions

- Stop with NO-GO if the exact wave id remains absent from `TASKS.md` at implementation time, because `TASKS.md:577` requires every wave to have a tracker entry.
- Stop with NO-GO if focused reproduction shows `bootstrap_core.step` is still the true tracked production kernel primitive.
- Stop with NO-GO if moving the marker would reduce or increase host-semantics ratchet counts.
- Stop with NO-GO if preserving the ratchet count requires adding a second JS `@host_iteration` marker instead of moving the existing same-category marker.
- Stop with NO-GO if the only available proof path requires production runtime changes, Python/JS parity behavior changes, new host authority, or ratchet baseline edits.
- Stop with NO-GO if `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py` cannot distinguish active-loop tracking from marker laundering on a wrapper or legacy boundary.

## Acceptance Criteria

- The Phase A packet contains the required sections: Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization.
- The packet carries a wave-bound `FOUNDER_OVERRIDE:n3-js-kernel-iteration-marker-truth-alignment-2026-05-20` line for same-wave control-plane automation.
- Before implementation, same-wave TASKS tracker authority exists for `n3-js-kernel-iteration-marker-truth-alignment-2026-05-20`; otherwise the wave remains NO-GO.
- GO branch acceptance requires the JS `@host_iteration` marker to be placed on the active `_stepKernelCore` kernel driver loop and removed from the stale `bootstrap_core.step` marker site without changing total host-semantics marker count.
- `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py` proves the active JS loop is the tracked host-iteration site and fails on stale-only `bootstrap_core.step` tracking.
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py` agrees with that same truth: `_stepKernelCore` carries the tracked JS marker and `bootstrap_core.step` remains boundary evidence only.
- If scanner expectation coverage is touched, `mu/tests/tools/test_check_host_semantics_ratchet.py` preserves host-semantics ratchet truth for the same marker-count move.
- Host-semantics ratchet validation passes through `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` with no baseline edit and no marker count reduction; `tools/checks/check_host_semantics_ratchet.py` remains a validation wrapper/compatibility surface, not a separate rebaseline path.
- Host-authority inventory validation passes with no unaccepted authority-site or total-inventory increase.
- Python and JS runtime behavior remain unchanged.
- If branch B is selected, the wave closes as NO-GO with reproduction evidence and no implementation edits.

## Grounding / Authorization

- Governing packet: `reports/control_plane/n3-js-kernel-iteration-marker-truth-alignment-2026-05-20_2026-05-20.md`.
- Current task authority: `TASKS.md:569-586`, where `[NEXT-CODEX-POST-REDTEAM]` is UNPARKED, the current phase remains OPEN for separate bounded structural-reduction packets, and the founder-ordered directive requires each wave to have a control-plane packet plus a `TASKS.md` tracker entry.
- Authorization truth for this rewrite: exact lookup for `n3-js-kernel-iteration-marker-truth-alignment-2026-05-20` in `TASKS.md` returned no matches during this packet rewrite. Therefore this packet supplies the missing Phase A design surface but does not claim that same-wave TASKS tracker sync is already present.
- Same-wave control-plane override for packet automation: `FOUNDER_OVERRIDE:n3-js-kernel-iteration-marker-truth-alignment-2026-05-20`.
- Prior adjacent N3 tracker entry: `TASKS.md:586` authorizes `n3-engine-pipeline-run-algorithm-authority-source-prereq-2026-05-19`; it does not authorize this wave id and must not be reused as this wave's tracker proof.
- Scope-path reproduction for this rewrite: `rg --files mu/tests tools mu/tools | rg 'host|semantics|ratchet|l4'` identifies the concrete marker/ratchet surfaces this packet relies on, including `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`, `mu/tests/tools/test_check_host_semantics_ratchet.py`, `mu/tools/checks/check_host_semantics_ratchet.py`, and `tools/checks/check_host_semantics_ratchet.py`.
- Routing evidence accepted for this Phase A plan: the host-semantics scanner currently scans `rcx_pi/selfhost` and `mu/host/js` and reports 5 markers; JS `@host_iteration` is cited only at `mu/host/js/core/bootstrap_core.js:293`; active JS engine kernel execution is cited at `mu/host/js/engine/kernel.js::_stepKernelCore` lines 72-132 with `for (let i = 0; i < maxSteps; i++)`; the paired Python kernel marker is cited at `rcx_pi/selfhost/step_mu.py:1163` on `step_kernel_mu`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-js-kernel-iteration-marker-truth-alignment-2026-05-20`
- Active packet: `reports/control_plane/n3-js-kernel-iteration-marker-truth-alignment-2026-05-20_2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-js-kernel-iteration-marker-truth-alignment-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/bootstrap_core.js`
  - `mu/host/js/engine/kernel.js`
  - `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tools/checks/check_js_debt.sh`
  - `reports/control_plane/n3-js-kernel-iteration-marker-truth-alignment-2026-05-20_2026-05-20.md`
  - `reports/deferred/non_blocking/n3-js-kernel-iteration-marker-truth-alignment-2026-05-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-js-kernel-iteration-marker-truth-alignment-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
