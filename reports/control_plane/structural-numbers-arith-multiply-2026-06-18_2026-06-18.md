# Structural-Numbers-Arith-Multiply-2026-06-18 2026-06-18

Date: 2026-06-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-arith-multiply-2026-06-18
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage 3 prereq (Python-only multiply): L4_ENABLER gate proving integer MULTIPLY as RCX shift-and-add projections via run_mu (composing the landed add), structurally equal to encode(a*b) + decoding to the host product over a small corpus; run_mu classes l4_expensive, growth cap pre-bumped. First wave of the Stage-3 numeric tower. JS parity deferred.

## Scope

Files/directories in scope for this wave (additive, gate-only):

- `mu/tests/l4_gates/test_structural_numbers_multiply.py` -- NEW. Primary structural artifact: the Python run_mu gate proving integer MULTIPLY as projections (structural_artifact_ref).
- `mu/tests/docs/test_growth_caps.py` -- the `CAP_TEST_FILES` constant ONLY (value bump 139 -> 140), so the new gate file does not trip the test-file-count ratchet (`TestGrowthCaps.test_test_file_count_within_cap`). This is the same `CAP_TEST_FILES` surface the landed `test_structural_numbers_add.py` / `_compare.py` / `_codec.py` Stage-2 waves each bumped by +1 (recorded in that constant's provenance comment). The bump is FOUNDER_OVERRIDE-gated; `commit_executor.py` Step 5e may auto-apply the same single +1 under the wave's FOUNDER_OVERRIDE.
- `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json` -- generated L4 indicator artifact (produced by the indicator_collection_command; not hand-authored).
- `reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md` -- this governing packet.

Out of the edit surface: `TASKS.md` (its `structural-numbers-arith-multiply-2026-06-18` tracker sync note is the authorization, and tracker updates are pipeline-managed via `tracker_sync_note.py`, not a manual work item).

## Work Items

Concrete, bounded tasks (derived from the TASKS.md tracker-note evidence_delta):

1. Add `mu/tests/l4_gates/test_structural_numbers_multiply.py`: a Python run_mu gate that
   (a) builds integer MULTIPLY as RCX shift-and-add projections (linear patterns) **composing the already-landed add-with-carry** projection -- the **engine** (run_mu) does the actual multiply structurally, with **no host `*`** in the projection;
   (b) runs it via `run_mu` (Python) over a small fixed corpus of `(a, b)` operand pairs;
   (c) **GOVERNING assertion** -- asserts the engine's projected product is **structurally identical** (`==` and byte-identical `mu_hash`) to the **host test oracle** `encode(a*b)`, where `a*b` is computed host-side **inside the test only**. This is the same host-oracle convention the landed `test_structural_numbers_add.py` uses for `encode(a + b)`; divergence from this structural oracle is the gate failure.
   (d) **SUPPORTING assertion only (not sufficient)** -- asserts `decode(product) == a*b` for every corpus pair, mirroring the landed add gate's supporting `decode(result) == a + b` check. (d) on its own never proves the gate.
2. Mark the run_mu classes `@pytest.mark.l4_expensive` + `@pytest.mark.slow` (green-gate-excluded; nightly run under `--timeout=900`).
3. Bump `CAP_TEST_FILES` 139 -> 140 in `mu/tests/docs/test_growth_caps.py` to admit the new gate file (or rely on the FOUNDER_OVERRIDE-gated `commit_executor.py` Step 5e auto-bump, which applies the same single +1 to that constant before the growth-cap gate).
4. Produce the L4 indicator artifact via the indicator_collection_command (writes `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json`).

## Constraints (NOT in scope)

- **No host `*` (or any host arithmetic) in the engine / projection / runtime.** MULTIPLY MUST be structural shift-and-add composing the landed add; a host multiply in the projection or in any runtime dir is a hard defect that would raise the host-authority count. **The test oracle is explicitly exempt:** computing the expected product host-side as `encode(a*b)` (and the supporting `decode(product) == a*b`) lives only inside `mu/tests/l4_gates/test_structural_numbers_multiply.py`, exactly as the landed add gate computes `encode(a + b)` host-side. `check_host_semantics_ratchet.py` scans only the runtime dirs (`rcx_pi/selfhost`, `mu/host/js`), never `mu/tests/`, so the host-side test oracle cannot raise the host-authority count. The "no host `*`" invariant therefore binds the engine under test, not the corpus oracle.
- **No JS / cross-substrate parity.** Python-only this wave; JS parity is deferred to a follow-up.
- **No seed, runtime, or substrate changes; no ratchet or host-authority increase.** Per the L4_ENABLER class, this wave MUST NOT touch runtime dirs (`rcx_pi/selfhost/`, `mu/host/` runtime, seed dirs).
- **No modification of the already-landed ADD / COMPARE / CODEC projections.** Compose them; do not change them.
- **Not the full Stage-3 rational tower.** This is only the integer-multiply prerequisite; division / rationals are later waves.
- **No green-gate inclusion.** The gate is nightly-only (`l4_expensive` + `slow`), kept out of the per-commit green gate by design.

## Stop Conditions

The implementer halts and escalates (does not work around) when:

- Integer multiply cannot be expressed as composed structural shift-and-add projections without a host arithmetic primitive -> STOP, escalate to founder; do NOT add host `*`.
- run_mu meta-circular cost makes the corpus infeasible even at `l4_expensive` / nightly `--timeout=900` -> STOP, re-scope to a smaller corpus; do NOT relax the structural-equality assertion to make it pass.
- The new gate forces a change to the landed add/compare/codec projections or to any runtime/substrate file -> STOP (outside L4_ENABLER scope), escalate.
- (This Phase-A turn only) Stop after rewriting this packet with the required sections; do NOT implement the gate in this turn.

## Acceptance Criteria

1. `mu/tests/l4_gates/test_structural_numbers_multiply.py` exists and proves integer MULTIPLY as RCX shift-and-add projections executed via `run_mu` (Python), composing the landed add-with-carry. GOVERNING: the engine's projected product is structurally identical (`==` and `mu_hash`) to the host-side test oracle `encode(a*b)` over the small fixed corpus. SUPPORTING only (not sufficient): `decode(product) == a*b`. The engine carries no host `*`; `a*b` is computed host-side inside the test only.
2. The multiply classes carry `@pytest.mark.l4_expensive` and `@pytest.mark.slow` (excluded from the green gate; run nightly under `--timeout=900`).
3. `CAP_TEST_FILES` in `mu/tests/docs/test_growth_caps.py` is bumped 139 -> 140 so the new file does not trip the test-file-count ratchet.
4. The `evidence_command` passes verbatim: `PYTHONHASHSEED=0 python3 -m pytest -q -m l4_expensive mu/tests/l4_gates/test_structural_numbers_multiply.py --timeout=900 --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
5. No host `*` (or other host arithmetic) is introduced into any runtime dir; `check_host_semantics_ratchet.py` (which scans only `rcx_pi/selfhost` and `mu/host/js`) shows no increase in host-authority sites. The test-only `encode(a*b)` oracle is outside the ratchet's scan surface and is not counted as a host-authority site.
6. No seed/runtime/substrate/ratchet/authority changes (L4_ENABLER does not touch runtime dirs).
7. The L4 indicator artifact is produced at `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json` via the indicator_collection_command.

## Grounding / Authorization

- **TASKS.md** (tracker sync note 2026-06-18, structural-numbers-arith-multiply-2026-06-18) -- authorizes `[NEXT-CODEX-POST-REDTEAM]`; Class `L4_ENABLER`; `target_gate_id: G8`; structural_artifact_ref `mu/tests/l4_gates/test_structural_numbers_multiply.py`.
- **FOUNDER_OVERRIDE:structural-numbers-arith-multiply-2026-06-18.
- **Governing packet:** this file (`reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md`).
- **progress_proof_before (TASKS.md tracker note):** ADD + COMPARE + CODEC are proven as Stage-2 projections, but MULTIPLY -- needed for the Stage-3 rational tower -- is not yet proven expressible as a Mu projection. This wave therefore composes the landed add-with-carry; it does not reimplement add/compare/codec.
- **progress_proof_after (TASKS.md tracker note):** A Python run_mu gate locks integer MULTIPLY as shift-and-add projections (structurally equal to the host oracle `encode(a*b)`); the meta-circular arithmetic core gains multiply, the first prerequisite of the Stage-3 rational tower.
- **L4 fields:** see the auto-derived block below (single source of truth; do not hand-edit).

## Request from Post-Merge Supervisor

StructuralNumbers Stage 3 prereq (Python-only multiply): L4_ENABLER gate proving integer MULTIPLY as RCX shift-and-add projections via run_mu (composing the landed add), structurally equal to encode(a*b) + decoding to the host product over a small corpus; run_mu classes l4_expensive, growth cap pre-bumped. First wave of the Stage-3 numeric tower. JS parity deferred.

Routed next-candidate:
structural-numbers-arith-multiply-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-arith-multiply-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_multiply.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-arith-multiply-2026-06-18.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-arith-multiply-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_multiply.py`
  - `reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md`
  - `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-arith-multiply-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5cbe42d35d23bcd742b861c578685866df7f8e8731281e6611a2d19316da4ed4`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_multiply.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_multiply.py`
  - `reports/control_plane/structural-numbers-arith-multiply-2026-06-18_2026-06-18.md`
  - `reports/l4_wave_indicators/structural-numbers-arith-multiply-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
