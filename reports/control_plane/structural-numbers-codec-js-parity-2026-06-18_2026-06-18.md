# Structural-Numbers-Codec-Js-Parity-2026-06-18 2026-06-18

Date: 2026-06-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-codec-js-parity-2026-06-18
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers JS-parity-for-codec: L4_ENABLER gate proving the landed nested<->flat CODEC projections run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu codec (both round-trip directions) -- the L3 parity for the codec, completing the Stage-2 cross-substrate trio. JS Mu via container_factory; run_mu/node classes l4_expensive; growth cap pre-bumped. Gate-only, no runtime change.

## Scope

Files/directories this wave is authorized to touch (gate-only, additive):

- `mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py` -- **NEW**. The primary deliverable (the tracker `structural_artifact_ref`): a cross-substrate L3-parity gate that imports the already-landed nested<->flat numeral CODEC projections and runs them through both substrates (Python `run_mu` and JS `bootstrap_core` via node), asserting content-addressed equality.
- `mu/tests/docs/test_growth_caps.py` -- the single repo-local module that declares the `CAP_TEST_FILES` constant. Pre-bump `CAP_TEST_FILES` `138 -> 139` (and append the wave's cap-comment entry) so the new gate file does not trip the test-file growth cap. The bump `138 -> 139` is the value authorized by the TASKS.md tracker note (`evidence_delta` (2)); `138` already accounts for the sibling compare-js-parity gate, and this wave's `test_structural_numbers_codec_js_parity.py` is the next `+1`.
- `reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json` -- generated/refreshed indicator artifact (the output of `indicator_collection_command`; not hand-authored).
- `reports/control_plane/structural-numbers-codec-js-parity-2026-06-18_2026-06-18.md` -- this Phase A packet.

No other files are in scope. In particular, the landed CODEC projections and all runtime/substrate sources are read-only here (see Constraints).

- `reports/deferred/non_blocking/structural-numbers-codec-js-parity-2026-06-18_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

Concrete, bounded tasks derived from the TASKS.md tracker note (`evidence_delta` points 1-3) plus indicator collection:

1. **Author the cross-substrate CODEC gate** `mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py`. Following the established add/compare js-parity pattern, **import the landed objects as the single source of truth** -- `CODEC_PROJECTIONS`, `CORPUS`, the boundary codecs (`encode_nested`/`encode_flat`/`decode_nested`/`decode_flat`), and the Python drivers (`run_forward`/`run_reverse`) -- from `tests.l4_gates.test_structural_numbers_codec` (do NOT re-derive a copy). Drive the SAME landed nested<->flat numeral CODEC projections through:
   - Python: `run_forward`/`run_reverse` (the `run_mu` codec).
   - JS: `bootstrap_core` (`mu/host/js/core/bootstrap_core.js`) via node, with the projection table + input states serialized to JSON and rebuilt as TRUSTED Mu containers through the existing `container_factory` (`trustMu`; use-only, never modified).
   Assert content-addressed equality (`muHashCached` byte-identical) between the JS and Python results for **both** conversion directions (forward nested->flat encode and reverse flat->nested decode).

   **Parity corpus (concrete and bounded):** the imported landed `CORPUS` -- exactly the 8 non-negative, <=8-bit values `{0, 1, 2, 6, 8, 21, 170, 255}` -- each exercised in BOTH directions, i.e. `8 x 2 = 16` cross-substrate parity comparisons (no fewer). The corpus is the landed set imported wholesale (NOT a Phase-B-chosen subset), and it already pins the mandatory structural shapes (asserted in `test_structural_numbers_codec.py`, guarding against silent drift): `0` (both zero-dispatch arms), `1` (single bit / MSB-only), `8` (power of two -- long `b0`/`xO` zero run), `255` (8-bit all-ones -- all `b1`/`xI`), and `6`/`21`/`170` (mixed / alternating interior bits). Each case additionally anchors the host value: `decode_flat`/`decode_nested` of the JS-and-Python results both equal the original `n`.
2. **Class the heavy test paths** `l4_expensive` + `slow` so the run_mu/node-invoking classes are excluded from the fast green gate and run nightly (900s timeout).
3. **Pre-bump the test-file growth cap** in `mu/tests/docs/test_growth_caps.py`: raise the `CAP_TEST_FILES` constant `138 -> 139` and append the wave's cap-comment entry, so the new gate file does not trip the cap check.
4. **Collect the wave indicator** by running `indicator_collection_command` to produce `reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json`.

## Constraints (NOT in Scope)

- **L4_ENABLER discipline:** MUST NOT touch runtime/substrate directories (`rcx_pi/selfhost/`, `mu/host/`, seeds). No runtime/substrate/seed change. This wave is tooling/gate-only.
- **Do not modify the CODEC projections.** The gate only *exercises* the already-landed nested<->flat codec; it does not change codec behavior, shape, or semantics.
- **No host capability, no host primitive.** Do not add host-only codec/comparison/equality semantics to reach parity (North Star; `check_bootstrap_purity_ratchet.py`). Parity must hold via content-addressed structure, not a host shortcut.
- **No ratchet/authority increase, no host-semantics delta.** `check_host_semantics_ratchet.py` must stay clean.
- **Out of scope:** the already-landed ADD (PR #1111) and COMPARE (PR #1112) parity gates; Stage 3; the matcher cutover. Those follow the trio; they are not part of this wave.

## Stop Conditions

- **Success stop:** the new gate passes in both substrates (content-addressed-identical, both round-trip directions) AND `check_host_semantics_ratchet.py` is clean -- i.e., the full `evidence_command` passes.
- **Policy stop (escalate as POLICY_BOUND):** if parity cannot be reached without a runtime/substrate change or a host primitive, STOP and surface to the founder. Do not force parity by adding host semantics -- that violates L4_ENABLER and the North Star.
- **Defect stop:** if the codec projections are found NOT content-addressed-equal across substrates, that is a real L3 divergence -- report it as a DEFECT; do not mask or canonicalize it away.
- **Phase A stop (this turn):** end after the packet is rewritten with the required sections. Do NOT implement the gate, edit downstream files, or run the evidence command in this turn.

## Acceptance Criteria

- `mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py` exists and proves cross-substrate CODEC L3 parity: Python `run_mu` <-> JS `bootstrap_core`, `muHashCached` byte-identical, for BOTH conversion directions over the full imported landed `CORPUS` (all 8 values `{0, 1, 2, 6, 8, 21, 170, 255}` = 16 cross-substrate parity comparisons), with the host value preserved (`decode_*` == `n`) in each case. The corpus and projection table are imported from `tests.l4_gates.test_structural_numbers_codec` (single source of truth), so the gate validates the landed objects, not a re-derived copy.
- `evidence_command` passes:
  `PYTHONHASHSEED=0 python3 -m pytest -q -m l4_expensive mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py --timeout=900 --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- The run_mu/node test classes carry `l4_expensive` + `slow`; the fast green gate remains fast (heavy paths excluded).
- `CAP_TEST_FILES` in `mu/tests/docs/test_growth_caps.py` reflects `139` (with the wave's cap-comment entry appended); the growth-cap check is green.
- `reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json` is present (output of `indicator_collection_command`).
- No diff under runtime/substrate directories; host-semantics ratchet unchanged (gate-only, additive).
- Net effect: the Stage-2 cross-substrate trio (add + compare + codec JS-parity) is complete, ahead of Stage 3 and the matcher cutover.

## Grounding / Authorization

- **TASKS.md authorization:** the dated tracker sync note (`2026-06-18`, `structural-numbers-codec-js-parity-2026-06-18`) authorizes `[NEXT-CODEX-POST-REDTEAM]` -- "StructuralNumbers JS-parity-for-codec cross-substrate gate." Class: **L4_ENABLER**. `target_gate_id`: **G8**.
- **Governing packet:** this file, named as `Packet:` in that tracker note.
- **structural_artifact_ref:** `mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py`.
- Wave-bound override token (plain, whitespace-delimited for mechanical derivation): FOUNDER_OVERRIDE:structural-numbers-codec-js-parity-2026-06-18 -- from the TASKS.md tracker note, mirrored in the auto-derived L4 fields `founder_override` below. Provided literally so commit automation can derive the same-wave override mechanically.
- **progress_proof_before:** ADD and COMPARE have cross-substrate L3 parity (PRs #1111, #1112); the CODEC is proven only as Python `run_mu` projections -- its mandatory JS-substrate parity is not yet validated.
- **progress_proof_after:** a cross-substrate gate locks the nested<->flat CODEC's L3 parity (Python `run_mu` vs JS `bootstrap_core`, content-addressed-identical, both directions) -- completing the Stage-2 arithmetic+codec cross-substrate trio before Stage 3 and the matcher cutover.
- **primary_blocker_class:** INTEGRATION. **primary_invariant_id:** INV_STRUCTURAL_FORWARD_MOTION.

## Request from Post-Merge Supervisor

StructuralNumbers JS-parity-for-codec: L4_ENABLER gate proving the landed nested<->flat CODEC projections run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu codec (both round-trip directions) -- the L3 parity for the codec, completing the Stage-2 cross-substrate trio. JS Mu via container_factory; run_mu/node classes l4_expensive; growth cap pre-bumped. Gate-only, no runtime change.

Routed next-candidate:
structural-numbers-codec-js-parity-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-codec-js-parity-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-codec-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-codec-js-parity-2026-06-18 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `structural-numbers-codec-js-parity-2026-06-18`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/structural-numbers-codec-js-parity-2026-06-18_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-codec-js-parity-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-codec-js-parity-2026-06-18_2026-06-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a184e1efcd1630ae52e86faa687c8756150f691433d2e6e7c4f8790c3b1dffc8`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-codec-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_codec_js_parity.py`
  - `reports/control_plane/structural-numbers-codec-js-parity-2026-06-18_2026-06-18.md`
  - `reports/deferred/non_blocking/structural-numbers-codec-js-parity-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-codec-js-parity-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
