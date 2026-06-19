# Structural-Numbers-Subtract-Js-Parity-2026-06-18 2026-06-18

Date: 2026-06-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-subtract-js-parity-2026-06-18
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers JS-parity-for-subtract: L4_ENABLER gate proving the landed signed SUBTRACT projections (subtract-with-borrow + compare-based sign + leading-zero fold) run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu subtract over a corpus (neg form for a<b, canonical zero for a==b), decoding to host a-b. JS Mu via container_factory; run_mu/node classes l4_expensive; in-function # SPEED_OK on any transitive-run_mu fast guard-test; growth cap pre-bumped. Stage 3 tower (subtract cross-substrate).

## Scope

Gate-only, additive L4_ENABLER wave: prove the already-landed (PR #1116) Python signed-SUBTRACT projections run in the JS substrate content-addressed-equal to Python `run_mu`. Explicit in-scope surfaces:

**Modified / created (explicit paths):**
- `mu/tests/l4_gates/test_structural_numbers_subtract_js_parity.py` — NEW cross-substrate parity gate (primary deliverable; the `structural_artifact_ref`).
- `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json` — generated wave-indicator artifact (`indicator_artifact_ref`).
- `mu/tests/docs/test_growth_caps.py` — pre-bump the `CAP_TEST_FILES` constant 142 → 143 (the only edit to this file) so the new gate file is admitted.
- `reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md` — this governing packet.

**Read-only / driven, NOT modified (explicit paths):**
- The landed Python signed-SUBTRACT projections (subtract-with-borrow + compare-based sign + leading-zero fold) — imported by the gate from the PR #1116 surface, never redefined.
- `mu/host/js/core/bootstrap_core.js` — the JS substrate `run`, driven via node.
- `mu/host/js/core/container_factory.js` — **USE-ONLY**: imported and called (via the `trustMu` / `list` / `record` helpers) to rebuild the JSON-serialized projection table as trusted Mu containers for the node-side run; **never modified**. The "registration" is a runtime call (the factory adds each value to its private trusted set at call time), not a source edit.
- `mu/tools/checks/check_host_semantics_ratchet.py` — invoked as evidence.

- `reports/deferred/non_blocking/structural-numbers-subtract-js-parity-2026-06-18_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Request from Post-Merge Supervisor

StructuralNumbers JS-parity-for-subtract: L4_ENABLER gate proving the landed signed SUBTRACT projections (subtract-with-borrow + compare-based sign + leading-zero fold) run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu subtract over a corpus (neg form for a<b, canonical zero for a==b), decoding to host a-b. JS Mu via container_factory; run_mu/node classes l4_expensive; in-function # SPEED_OK on any transitive-run_mu fast guard-test; growth cap pre-bumped. Stage 3 tower (subtract cross-substrate).

Routed next-candidate:
structural-numbers-subtract-js-parity-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-subtract-js-parity-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_subtract_js_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-subtract-js-parity-2026-06-18.
<!-- L4_FIELDS_FROM_TRACKER:end -->


## Work items

Concrete, bounded tasks derived from the TASKS.md:558 `evidence_delta` (gate-only, additive):

1. **Add the cross-substrate parity gate** — new `mu/tests/l4_gates/test_structural_numbers_subtract_js_parity.py`:
   - Import the landed signed-SUBTRACT projections (subtract-with-borrow + compare-based sign + leading-zero fold) from the Python run_mu surface proven in PR #1116. Do NOT redefine them.
   - Run them via Python `run_mu` over a fixed corpus that covers a<b (neg form `{"_num":{"neg":p}}`), a==b (canonical zero), a>b (positive), plus borrow and leading-zero-fold edge cases.
   - Export the same projections to JSON, load them into the JS substrate as trustMu via `container_factory`, and drive them through `bootstrap_core` (node).
   - Assert cross-substrate **content-addressed equality**: `muHashCached` byte-identical between the Python and JS results for every corpus case.
   - Assert **decode == host a − b** for every corpus case.
2. **JS Mu container build (USE-ONLY, no substrate edit)** — rebuild the JSON-serialized projection table in JS as trusted Mu containers via the existing `mu/host/js/core/container_factory.js` (`list` / `record`) through the `trustMu` helper, exactly as the ADD/compare/multiply parity gates do. The factory registers each value in its private trusted set **at call time** — a runtime call, not a source edit. `container_factory.js` is USE-ONLY: imported and called, never modified. If parity appears to require a new factory entry — or any edit to `mu/host/js/core/container_factory.js` or any other substrate file — **HALT and escalate** (see Stop conditions); do NOT modify the substrate.
3. **Test classification** — mark the run_mu/node test(s) `l4_expensive` + `slow` (green-gate-excluded; nightly 900 s). Add an in-function `# SPEED_OK: <reason>` on any fast guard-test that transitively invokes `run_mu`.
4. **Pre-bump the growth cap** — bump the test-file growth cap `CAP_TEST_FILES` 142 → 143 so the new gate file is admitted.
5. **Emit the wave indicator** — run the `indicator_collection_command` to produce `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json`.


## Constraints (NOT in scope)

- **L4_ENABLER boundary:** MUST NOT touch runtime/substrate dirs. No edits to the Python `rcx_pi/selfhost/` subtract projections and no edits to the JS substrate `mu/host/js/core/` — specifically `bootstrap_core.js` and `container_factory.js` are USE-ONLY (imported and called, never modified). The gate imports/drives existing surfaces; it does not change them.
- **No semantics delta:** no runtime, substrate, or seed change; no ratchet or host-authority increase. `check_host_semantics_ratchet.py` must report net 0.
- **No re-derivation of subtract:** signed subtract already landed as Python run_mu projections (PR #1116). This wave proves JS parity only; it does not re-implement or "improve" the projections.
- **No host-only shortcut for the JS step budget:** do not raise any host step cap to force convergence. `bootstrap_core.run` hard-caps `maxSteps` (carry-forward gotcha from the multiply parity wave: last-known live cap `MAX_RUN_STEPS=10000`, larger values clamped). Drive JS at the live cap and assert the literal value ≤ the live cap — do NOT assume JS honors Python's larger budget. Verify the live cap value during implementation; if the corpus cannot converge under it, halt and report (see Stop conditions) rather than touching the substrate.
- **Out of scope:** structural gcd / rationals (the next wave per `progress_proof_after`); any non-subtract op; any change to the auto-derived `L4_FIELDS_FROM_TRACKER` block above (single source of truth is TASKS.md — do not hand-edit).


## Stop conditions

- **Done:** the parity gate passes — Python ↔ JS `muHashCached` byte-identical and `decode == a − b` across the full corpus — AND `check_host_semantics_ratchet.py` reports net 0.
- **Halt + escalate** if proving parity appears to require any runtime/substrate/seed change — including adding a new `container_factory` entry or any edit to `mu/host/js/core/container_factory.js`, `mu/host/js/core/bootstrap_core.js`, or other substrate code (that would break the L4_ENABLER boundary).
- **Halt + report** if the JS corpus cannot converge under the live `bootstrap_core` step cap — do not raise the cap.
- **Phase boundary:** this is Phase A. Stop when the plan is bridge-converged; do NOT implement the test or touch code in this turn.


## Acceptance criteria

- `evidence_command` green: `PYTHONHASHSEED=0 python3 -m pytest -q -m l4_expensive mu/tests/l4_gates/test_structural_numbers_subtract_js_parity.py --timeout=900 --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- Cross-substrate parity holds **byte-identical** (`muHashCached`) for every corpus case, including a<b (neg form), a==b (canonical zero), a>b, and the borrow / leading-zero-fold edges.
- `decode == host a − b` for every corpus case.
- New gate file classed `l4_expensive` + `slow` (excluded from the green gate; runs nightly at 900 s); any transitive-run_mu fast guard carries `# SPEED_OK`.
- `CAP_TEST_FILES` bumped 142 → 143; growth-cap check green.
- Net host-semantics delta **0** (no runtime/substrate/seed/ratchet/authority change).
- Wave-indicator artifact produced at `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json`.


## Grounding / Authorization

- **Authorizing task:** `[NEXT-CODEX-POST-REDTEAM]` — TASKS.md line 558 tracker note (2026-06-18, `structural-numbers-subtract-js-parity-2026-06-18`): "StructuralNumbers JS-parity-for-subtract cross-substrate gate." Class: **L4_ENABLER**. `target_gate_id: G8`. `primary_blocker_class: INTEGRATION`. `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`.
- **Governing packet:** this file (`reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md`); the L4 fields above are auto-derived from the same TASKS.md note.
- **progress_proof_before (TASKS.md:558):** "Signed integer subtract is proven as Python run_mu projections (PR #1116), but its mandatory JS-substrate parity is not yet validated." — confirms the subtract projections are landed and only JS parity is pending; no work item is already complete.
- **progress_proof_after (TASKS.md:558):** "A cross-substrate gate locks signed SUBTRACT's L3 parity (Python run_mu vs JS bootstrap_core, content-addressed-identical); the Stage-3 tower's subtract op is validated in both substrates. Next: structural gcd."
- **Prior art / harness:** the same Python-run_mu ↔ JS-bootstrap_core parity harness already landed for ADD, compare, codec, and multiply (multiply = PR #1115); this wave reuses that harness for signed subtract.
- **Wave-bound override** (detector-visible; matches TASKS.md:558 exactly so commit automation derives the same-wave override mechanically):

FOUNDER_OVERRIDE:structural-numbers-subtract-js-parity-2026-06-18

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-subtract-js-parity-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_subtract_js_parity.py`
  - `reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md`
  - `reports/deferred/non_blocking/structural-numbers-subtract-js-parity-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `structural-numbers-subtract-js-parity-2026-06-18`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/structural-numbers-subtract-js-parity-2026-06-18_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-subtract-js-parity-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5cb1a94332c4515e921743849708cdf9514a3f9e500830c1f0b73b60c2941ab9`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_subtract_js_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_subtract_js_parity.py`
  - `reports/control_plane/structural-numbers-subtract-js-parity-2026-06-18_2026-06-18.md`
  - `reports/deferred/non_blocking/structural-numbers-subtract-js-parity-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-subtract-js-parity-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
