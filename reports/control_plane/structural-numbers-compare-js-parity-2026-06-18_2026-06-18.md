# Structural-Numbers-Compare-Js-Parity-2026-06-18 2026-06-18

Date: 2026-06-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-compare-js-parity-2026-06-18
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers JS-parity-for-compare: L4_ENABLER gate proving the landed COMPARE projections run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu compare verdict -- the L3 parity for the ordering op. JS Mu via container_factory; run_mu/node classes l4_expensive; growth cap pre-bumped. Gate-only, no runtime change.

## Scope

Gate-only, additive L4_ENABLER: it adds a cross-substrate parity gate and does NOT modify runtime/substrate semantics.

In scope -- the complete, exact list of files this wave creates or modifies:

- `mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py` -- NEW. The cross-substrate L3-parity gate for binary COMPARE (the wave's `structural_artifact_ref`). Mirrors the just-landed ADD parity gate `mu/tests/l4_gates/test_structural_numbers_add_js_parity.py` (PR #1111): it IMPORTS the landed COMPARE objects as the single source of truth (Work item 1) and EMBEDS its JS runner as an inline `node` snippet (Work item 2). The "JS Mu container-factory registration" is this in-test wiring -- NOT a separate or new module -- so no part of it is deferred to Phase B.
- `mu/tests/docs/test_growth_caps.py` -- MODIFIED. Bump the test-file-count ratchet (the `CAP_TEST_FILES` assignment in `mu/tests/docs/test_growth_caps.py`) 137 -> 138 to admit exactly the one new gate file, with the standard `+1 for test_structural_numbers_compare_js_parity.py (... FOUNDER_OVERRIDE:structural-numbers-compare-js-parity-2026-06-18)` provenance comment. No other cap or baseline change.
- `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json` -- NEW (generated, not hand-authored). The wave indicator artifact, produced by the `indicator_collection_command`.
- `reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md` -- this governing packet (already exists; Phase A design content only).

Exercised read-only / invoked, NOT modified (USE-ONLY -- imported / `require`d and called, never edited):

- JS substrate modules `require`d by the new gate's inline `node` runner snippet (this in-test wiring IS the "JS Mu container-factory registration" -- there is no separate or new JS module):
  - `mu/host/js/core/bootstrap_core.js` -- the JS `run` engine that drives the projection table over each input state.
  - `mu/host/js/core/container_factory.js` -- `list` / `record` rebuild the JSON-serialized projection table and input states as TRUSTED Mu containers; the factory adds each constructed value to its private trusted-Mu set at call time, which is exactly the "registration" JS `isValidMu` requires. The ADD precedent locks this file as USE-ONLY (imported + called, never modified).
  - `mu/host/js/core/types.js` -- `muHash` / `muHashCached`, the content address compared across substrates.
- The landed Python COMPARE projection table, codec, corpus, and `run_mu` driver in `mu/tests/l4_gates/test_structural_numbers_compare.py` (Stage 2b) -- imported and run, semantics unchanged.
- `mu/tools/checks/check_host_semantics_ratchet.py` -- invoked by the `evidence_command`; expected to show no delta.

## Work items

Concrete, bounded tasks for this wave (from the `evidence_delta` of the TASKS.md tracker sync note for 2026-06-18, `structural-numbers-compare-js-parity-2026-06-18`):

1. Author `mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py`. Import the landed COMPARE objects from `tests.l4_gates.test_structural_numbers_compare` as the SINGLE SOURCE OF TRUTH (not re-derived) -- `COMPARE_PROJECTIONS` (the landed 13-projection table), `CORPUS`, the numeral codec `encode`/`decode`, the ordering-tag codec `encode_ord`/`decode_ord`, and the `run_mu` driver `run_compare` -- mirroring the ADD gate's import of its landed objects. For every pair in the imported `CORPUS`, run the SAME projection table through (a) Python `run_mu` (`run_compare`) and (b) JS `bootstrap_core` (node), and assert the two verdicts are content-addressed-equal (`muHashCached` byte-identical), structurally identical, and both decode (`decode_ord`) to the host comparison tag (`eq`/`lt`/`gt`), equal to the `encode_ord(sign)` oracle.
   - Parity corpus (BOUNDED, imported -- not re-derived): the landed `CORPUS` is exactly 20 operand pairs, operands <= 12 (<= 4-bit, well within the run_mu <= 8-bit budget). It covers all three ordering verdicts: 2 EQ (the mandatory `0 == 0` plus a nonzero equality `5 == 5`), 9 GT, and the 9 LT swaps of those GT pairs. Category coverage: zero-vs-positive dispatch on both arms (`5 vs 0` = GT and its `0 vs 5` = LT swap); length-decisive differences (`2 vs 1`, `4 vs 3`, and `8 vs 7` where length is the most-significant difference); and the first differing bit at LSB / interior / MSB depths on equal-length operands (`9 vs 8`, `10 vs 8`, `12 vs 8`). A `TestParityScaffolding` drift guard asserts `len(CORPUS) == 20`, the 2 EQ / 9 LT / 9 GT verdict split, and `len(COMPARE_PROJECTIONS) == 13` -- mirroring the ADD gate's `test_uses_landed_corpus`.
2. Embed the JS runner as an inline `node -e` source snippet INSIDE the new test file (mirroring the ADD gate's `_JS_ADD_PARITY_SRC`): it `require`s the USE-ONLY modules `mu/host/js/core/bootstrap_core.js`, `mu/host/js/core/container_factory.js`, and `mu/host/js/core/types.js`; JSON-serializes the imported projection table and per-pair input states from Python; and rebuilds them as TRUSTED Mu containers via the factory's `list`/`record` (a `trustMu` helper). The factory's call-time trusting IS the "registration" `isValidMu` requires -- there is NO separate or new JS registration module, and `container_factory.js` is imported and called, never modified.
3. Mark the `run_mu`/node test classes `l4_expensive` + `slow` so the gate is excluded from the green/fast tier and runs in the nightly tier at the 900s timeout.
4. Pre-bump `CAP_TEST_FILES` 137 -> 138 (admits the single new gate file; no other ratchet/cap change).
5. Produce the wave indicator artifact via the `indicator_collection_command` (writes `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json`).

## Constraints (NOT in scope)

- NO runtime/substrate change. Do NOT modify the Python `run_mu` COMPARE projections, the compare engine, or JS `eval_step.js`/`bootstrap_core` semantics. Gate-only and additive (L4_ENABLER -- MUST NOT touch runtime dirs, per `.claude/rules/l4-contract.md`).
- NO new comparison semantics and NO host comparison primitive. The verdict equality MUST remain pure content-addressed equality (`muHashCached`), parity-safe and consistent with `NorthStarSemantics.v0.md`. Do NOT canonicalize or special-case to force a match.
- NO seed change, NO ratchet/authority increase, NO host-semantics delta (`check_host_semantics_ratchet.py` must report no delta).
- Do NOT add the gate to the green/fast tier -- it is nightly-only (`l4_expensive` + `slow`).
- Do NOT re-author the COMPARE projections -- they already landed (Stage 2b); this wave only validates their JS-substrate parity.
- Scope is binary COMPARE only -- NOT ADD (already landed, PR #1111), NOT codec, NOT Stage-4. Do NOT widen `CAP_TEST_FILES` beyond the single +1.

## Stop conditions

- STOP once items 1-5 land and the `evidence_command` passes: the gate is green in the nightly tier and `check_host_semantics_ratchet.py` shows no delta. Do NOT extend to codec or Stage-4 JS parity in this wave.
- ESCALATE (POLICY_BOUND, founder decision -- do NOT self-resolve) if achieving content-addressed-equal verdicts appears to require changing COMPARE projection semantics, substrate eval semantics, or adding a host comparison primitive. That would violate the gate-only / parity-safe constraint.
- HALT and report a DEFECT if the Python `run_mu` and JS `bootstrap_core` COMPARE verdicts are NOT content-addressed-equal (a real L3-parity divergence). Do NOT paper over it by canonicalizing or adding host semantics.
- Phase A stops at an agent-reviewed + bridge-converged plan; implementation is Phase B.

## Acceptance criteria

- `mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py` exists and, run via the `evidence_command`, proves for the BOUNDED imported `CORPUS` -- exactly 20 operand pairs (operands <= 4-bit), covering all three verdicts: 2 EQ (incl. the mandatory `0 == 0`), 9 GT, and 9 LT swaps (see Work item 1) -- that the Python `run_mu` (`run_compare`) and JS `bootstrap_core` COMPARE verdicts are content-addressed-equal (`muHashCached` byte-identical) and both decode (`decode_ord`) to the host comparison tag (`eq`/`lt`/`gt`), equal to the `encode_ord(sign)` oracle for every pair.
- A `TestParityScaffolding` drift guard asserts the imported single source of truth: `len(CORPUS) == 20` with the 2 EQ / 9 LT / 9 GT verdict split, `len(COMPARE_PROJECTIONS) == 13`, and that the JS runner `require`s the real `bootstrap_core` / `container_factory` / `types` modules.
- The new test classes carry `l4_expensive` + `slow` markers (excluded from green gate; run nightly at 900s); the `evidence_command` passes end-to-end.
- `check_host_semantics_ratchet.py` shows no host-semantics delta (no authority/ratchet increase).
- `CAP_TEST_FILES` in `mu/tests/docs/test_growth_caps.py` is 138 (was 137), with the matching `+1 for test_structural_numbers_compare_js_parity.py` provenance comment; no other cap or ratchet is changed.
- The indicator artifact `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json` is produced by the `indicator_collection_command`.
- The diff is additive and gate-only: no change to Python `run_mu` COMPARE projections, the compare engine, or JS `eval_step.js` semantics; `git diff --check` is clean.

## Grounding / Authorization

- Authorized by the TASKS.md Tracker sync note (2026-06-18, `structural-numbers-compare-js-parity-2026-06-18`), task `[NEXT-CODEX-POST-REDTEAM]`, Class `L4_ENABLER`, `target_gate_id: G8`, `primary_blocker_class: INTEGRATION`, `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`.
- Governing packet: this file (`reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md`).
- Predecessor / precedent: the ADD cross-substrate L3-parity gate (PR #1111); this wave is the binary-COMPARE sibling -- the second arithmetic op validated in both substrates, after ADD.
- `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`; `boot0_track_id: V1`; `boot0_progress_state: HOLD`.

FOUNDER_OVERRIDE:structural-numbers-compare-js-parity-2026-06-18

Authorization: the wave-bound founder override above (identical to the `FOUNDER_OVERRIDE` token in that same TASKS.md tracker sync note) authorizes this control-plane L4_ENABLER packet; commit automation derives the same-wave override mechanically from this literal token.

## Request from Post-Merge Supervisor

StructuralNumbers JS-parity-for-compare: L4_ENABLER gate proving the landed COMPARE projections run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu compare verdict -- the L3 parity for the ordering op. JS Mu via container_factory; run_mu/node classes l4_expensive; growth cap pre-bumped. Gate-only, no runtime change.

Routed next-candidate:
structural-numbers-compare-js-parity-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-compare-js-parity-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-compare-js-parity-2026-06-18.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-compare-js-parity-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py`
  - `reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md`
  - `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-compare-js-parity-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `40f84a4858fd49d18b8c371cc2601f8dbdccc1932f34036c6b206b928bf53150`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py`
  - `reports/control_plane/structural-numbers-compare-js-parity-2026-06-18_2026-06-18.md`
  - `reports/l4_wave_indicators/structural-numbers-compare-js-parity-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
