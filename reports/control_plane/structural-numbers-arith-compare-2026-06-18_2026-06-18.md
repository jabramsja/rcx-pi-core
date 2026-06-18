# Structural-Numbers-Arith-Compare-2026-06-18 2026-06-18

Date: 2026-06-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-arith-compare-2026-06-18
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage 2b (Python-only compare): L4_ENABLER gate proving binary COMPARE (EQ/LT/GT) as RCX projections via run_mu, decoding to the host comparison; run_mu classes marked l4_expensive, growth cap pre-bumped. JS parity deferred (mirrors the ADD wave).

## Scope

Explicit files/directories in scope (gate-only, Python-only, additive):

- `mu/tests/l4_gates/test_structural_numbers_compare.py` — NEW gate test (the tracker's `structural_artifact_ref`). The sole runtime-behavior deliverable.
- `mu/tests/docs/test_growth_caps.py` — holds the `CAP_TEST_FILES` test-file cap (currently `134`), pre-bumped by one (134->135) to admit the new gate file. This is the same cap and file the predecessor ADD wave bumped (133->134) for `test_structural_numbers_add.py` in commit `343e1d0b`.
- `reports/control_plane/structural-numbers-arith-compare-2026-06-18_2026-06-18.md` — this governing packet.
- `reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json` — wave indicator artifact, regenerated via the `indicator_collection_command`.
- `TASKS.md` — the authorizing tracker note (already present); `STATUS.md` only if phase/debt changes.

Out-of-scope paths are enumerated under **Constraints**.

- `reports/deferred/non_blocking/structural-numbers-arith-compare-2026-06-18_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks, derived from the line-542 tracker note `evidence_delta`:

1. **Add the compare gate test** `mu/tests/l4_gates/test_structural_numbers_compare.py`: a Python `run_mu` gate that drives binary COMPARE (EQ/LT/GT) on the StructuralNumbers numeral as RCX projections (linear patterns, most-significant-difference-decides). Mirroring the Stage 2a ADD gate (`test_structural_numbers_add.py`, `TestStructuralAddEquivalence`), decode-to-host is **SUPPORTING ONLY**; the **governing** assertions are structural:
   - **Structural ordering-tag equality (GOVERNING):** each `run_mu(compare(a,b))` result equals the canonical expected ordering tag derived structurally — the EQ/LT/GT analog of the ADD gate's `result == encode(a+b)`, not merely the host decode.
   - **Canonical result shape:** the result is well-formed Mu (`is_mu`) and exactly one of the three canonical ordering tags (EQ/LT/GT) — a single-key wrapper with no residual operands — and is a fixpoint of `decode∘encode` of its ordering tag (no non-canonical tag could survive).
   - **Content-hash equality:** `mu_hash(result) == mu_hash(expected_tag)` (free content-addressed equality, mirroring `test_content_hash_equality`).
   - **Convergence / no residual compare input:** `run_mu` reached a stall fixpoint (`stalled is True`, not `max_steps`) and the result is NOT the unprocessed input state — the compare marker is gone — proving the engine actually reduced the comparison (mirrors `test_engine_reaches_stall_fixpoint`).
   - **Projection linearity:** every compare projection pattern is linear (no variable repeated in a pattern), asserted up front as the ADD gate does.
   - **Decode-to-host (SUPPORTING ONLY, not sufficient):** the result decodes to the host three-way sign `(a > b) - (a < b)` for each corpus pair (mirrors `test_decode_to_host_supporting`).
   The corpus is bounded by the **mandatory minimum matrix** defined under Acceptance criteria, kept lean for the nightly budget.
2. **Classify the run_mu cost**: mark the run_mu gate classes `@pytest.mark.l4_expensive` and `@pytest.mark.slow` so the green gate excludes them and they run nightly under `--timeout=900`. (Mirrors the ADD gate, which commit `3908f551` marked `l4_expensive` to clear the green-gate 300s slow-lane timeout.)
3. **Pre-bump `CAP_TEST_FILES`** (134->135) in `mu/tests/docs/test_growth_caps.py` by one so the new gate file does not trip the test-file-count cap check.
4. **Regenerate the wave indicator artifact** via `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-arith-compare-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json`.
5. **Keep packet and tracker in sync**: this packet and the TASKS.md tracker note stay consistent; update `STATUS.md` only if phase/debt changes.

## Constraints

What is explicitly NOT in scope this wave:

- **No JS / cross-substrate parity for compare.** Deferred to a follow-up wave (mirrors the ADD wave). `mu/host/js/eval_step.js` is untouched.
- **No host comparison primitive.** The projection must structurally decide EQ/LT/GT; only the final decode/assert in the test may use a host comparison to check correctness. No new host capability is added to the bootstrap (bootstrap purity ratchet must not move).
- **No seed / runtime / substrate change.** No edits to `rcx_pi/selfhost/` runtime or seeds — consistent with the L4_ENABLER class (must not touch runtime dirs).
- **No ratchet or authority increase.** `check_host_semantics_ratchet.py` must not regress.
- **No new operations** beyond COMPARE (EQ/LT/GT). The ADD gate and existing StructuralNumbers projections are not modified.
- **Not a green-gate (fast-lane) test.** It is nightly-only by design; it must not run in the per-commit green gate.

## Stop conditions

- **Done** once the gate test, marker classification, and cap bump land and the `evidence_command` passes green on the nightly slow lane. Do NOT continue into JS parity or further operations in this wave.
- **Escalate (POLICY_BOUND), do not proceed**, if COMPARE cannot be expressed as a pure projection without introducing a host comparison primitive — adding a host primitive would violate the North Star / bootstrap purity and is outside this wave's authority.
- **Narrow then stop** if the meta-circular `run_mu` cost makes the corpus impractical within the 900s nightly budget. The ADD engine facts show ~0.6s/domain-step meta-circular cost and ~3x depth blowup through `normalize_for_match`; keep the corpus lean. If still infeasible, STOP and report rather than weakening the gate.
- **COMMIT_GO_HOLD_PUSH discipline:** if a hold is signaled, do not push.

## Acceptance criteria

- `evidence_command` passes: `PYTHONHASHSEED=0 python3 -m pytest -q -m l4_expensive mu/tests/l4_gates/test_structural_numbers_compare.py --timeout=900 --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- **Governing structural proof (not host-decode):** for every corpus pair the `run_mu` COMPARE result is asserted structurally — (a) it equals the canonical expected ordering tag (structural equality), (b) it is content-hash equal to that tag via `mu_hash`, (c) it is a well-formed Mu canonical ordering tag (exactly one of EQ/LT/GT, single-key, no residual operands), and (d) `run_mu` converged to a stall fixpoint with the compare marker fully reduced out of the result. All COMPARE projection patterns are linear, and the ordering is decided structurally with no host comparison primitive inside the projection.
- **Decode-to-host is SUPPORTING ONLY:** `decode(result) == (a > b) - (a < b)` is asserted but explicitly not sufficient on its own (mirrors the ADD gate's `test_decode_to_host_supporting`); it is never the sole acceptance for any case.
- **Mandatory minimum corpus matrix** — the gate must cover at least the following rows (kept lean for the 900s budget); a host-decoded smoke test that omits any row is insufficient:
  - **Equality:** `a == b`, including `0 == 0`, decides EQ.
  - **LT/GT symmetry:** for each unequal pair `(a, b)`, the swapped pair `(b, a)` yields the opposite tag (LT becomes GT and vice versa) and never EQ.
  - **Prefix / length differences:** operands of differing canonical bit-length — a case where the longer operand is the greater, and a case proving length is the most-significant difference (decided without an equal-length tie-break).
  - **First differing bit at multiple depths:** on equal-length operands, the most-significant differing bit falls at several distinct positions — MSB, an interior bit, and the LSB — the COMPARE analog of the ADD gate's explicit carry-cascade spotlights.
- run_mu classes carry `l4_expensive` + `slow`; the green gate excludes them; the test-file-count cap check passes after the `CAP_TEST_FILES` bump.
- `check_host_semantics_ratchet.py` shows no regression (no new host authority/primitive).
- Change is additive and gate-only: no diff to the JS substrate, runtime, seeds, or other operations.
- Wave indicator artifact regenerated at `reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json`.

## Grounding / Authorization

- **TASKS.md tracker authorization:** tracker sync note `(2026-06-18, structural-numbers-arith-compare-2026-06-18)` — *"StructuralNumbers Stage 2b Python-only compare projections gate."* Class `L4_ENABLER`; `target_gate_id: G8`; `primary_blocker_class: INTEGRATION`; `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`.
- **Governing packet:** this file, referenced as `Packet:` in that tracker note.
- **Wave-bound founder override** (present in the tracker note so commit automation can derive the same-wave override mechanically): `FOUNDER_OVERRIDE:structural-numbers-arith-compare-2026-06-18 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)`.
- **L4_ENABLER contract satisfied:** `target_gate_id` + `evidence_command` + `evidence_delta` all present; the wave does not touch runtime dirs.
- **Predecessor / lineage:** Stage 2a ADD-as-projections gate landed in PR #1106 (`test_structural_numbers_add.py`). This Stage 2b adds the meta-circular arithmetic core's second operation (COMPARE) before JS parity / further ops, per `progress_proof_after`.

## Request from Post-Merge Supervisor

StructuralNumbers Stage 2b (Python-only compare): L4_ENABLER gate proving binary COMPARE (EQ/LT/GT) as RCX projections via run_mu, decoding to the host comparison; run_mu classes marked l4_expensive, growth cap pre-bumped. JS parity deferred (mirrors the ADD wave).

Routed next-candidate:
structural-numbers-arith-compare-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-arith-compare-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_compare.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-arith-compare-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-arith-compare-2026-06-18 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `structural-numbers-arith-compare-2026-06-18`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/structural-numbers-arith-compare-2026-06-18_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-arith-compare-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-arith-compare-2026-06-18_2026-06-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2ec19a7e31d49507fcab483c10173a167f3193f95685e58ffe21806b6e189a39`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_compare.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-arith-compare-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_compare.py`
  - `reports/control_plane/structural-numbers-arith-compare-2026-06-18_2026-06-18.md`
  - `reports/deferred/non_blocking/structural-numbers-arith-compare-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-arith-compare-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
