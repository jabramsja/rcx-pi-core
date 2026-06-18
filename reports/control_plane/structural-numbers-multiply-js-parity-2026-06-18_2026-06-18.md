# Structural-Numbers-Multiply-Js-Parity-2026-06-18 2026-06-18

Date: 2026-06-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-multiply-js-parity-2026-06-18
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers JS-parity-for-multiply: L4_ENABLER gate proving the landed MULTIPLY projections (shift-and-add) run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu multiply over a small corpus, decoding to host a*b. JS Mu via container_factory; run_mu/node classes l4_expensive; growth cap pre-bumped. Stage 3 tower wave 2.

## Scope

Explicit files/directories in scope for this L4_ENABLER gate-only wave.

**Created / modified (in scope):**
- `mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py` — NEW cross-substrate parity gate test (the `structural_artifact_ref`). Follows the landed sibling harness pattern (`test_structural_numbers_add_js_parity.py`, `test_structural_numbers_compare_js_parity.py`, `test_structural_numbers_codec_js_parity.py`); the multiply sibling does not yet exist.
- `mu/tests/docs/test_growth_caps.py` — the test-file growth cap (`ln`; tracker labels it CAP_TEST_FILES) bumped +1 (140→141) for the one new test file. Performed mechanically by `commit_executor` Step 5e FOUNDER_OVERRIDE auto-bump, or pre-bumped.
- `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json` — generated L4 wave indicator artifact (output of `indicator_collection_command`).
- `reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md` — this governing packet.

**Exercised read-only / invoked (NOT modified):**
- `mu/host/js/` — JS substrate (`bootstrap_core` via node) driven for the JS side of parity; Mu values registered via `container_factory` (JSON → trustMu) inside the gate's node driver. No substrate/runtime change.
- Landed Python MULTIPLY projections (shift-and-add, PR #1114) — the Python `run_mu` side of parity, imported/read, not modified.
- `mu/tools/checks/check_host_semantics_ratchet.py` — invoked by `evidence_command` (verification only).
- `tools/metrics/collect_l4_wave_indicators.py` — invoked by `indicator_collection_command` (verification only).

- `reports/deferred/non_blocking/structural-numbers-multiply-js-parity-2026-06-18_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks derived from the TASKS.md line 554 tracker note (`evidence_delta` (1)(2)(3)) for this phase:

1. Author `mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py` proving CROSS-SUBSTRATE L3 PARITY for binary MULTIPLY: the SAME landed shift-and-add projections, run via JS `bootstrap_core` (node), yield results content-addressed-equal (`muHashCached` byte-identical) to the Python `run_mu` multiply over a small corpus, each decoding to host `a*b`. Reuse the existing add/compare/codec js-parity harness.
2. Register JS Mu via `container_factory` in the gate's node driver (JSON → trustMu); assert `muHashCached` byte-identical AND `decode == a*b` per corpus pair.
3. Mark the `run_mu`/node parity classes `l4_expensive` + `slow` so they are green-gate-excluded and run nightly under the 900s timeout (`--timeout=900`).
4. Bump the `ln` test-file growth cap in `mu/tests/docs/test_growth_caps.py` by +1 (140→141) for the one new file — or rely on the `commit_executor` Step 5e FOUNDER_OVERRIDE auto-bump.
5. Produce the indicator artifact via `indicator_collection_command` → `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json`.
6. Keep the change gate-only and additive: no runtime/substrate/seed change, no ratchet/authority increase (net host-semantics delta 0).

## Constraints

What is explicitly NOT in scope:

- No changes to the landed MULTIPLY projections or any Python `run_mu` / JS `bootstrap_core` runtime or substrate code. Gate-only, additive (`evidence_delta` (3): "no runtime/substrate/seed change").
- No host-semantics ratchet or authority increase; net host-semantics delta MUST be 0 (CLAUDE.md rule 6 / bootstrap purity).
- No new host capability and no host comparison/arithmetic primitive — parity is content-addressed via `muHashCached`, never host equality.
- No seed changes; no green-gate (core-tier) additions — new classes must be `l4_expensive` + `slow` (nightly only).
- Do NOT implement subtract or any later Stage-3 tower op ("Next: subtract" is a separate wave).
- Do NOT touch unrelated executor/test files, dirty working-tree files, or anything outside the Scope list.

## Stop conditions

- STOP once the gate test + growth-cap bump + indicator artifact exist and `evidence_command` passes. Do not widen the corpus beyond the small parity corpus or proceed to subtract.
- STOP and report POLICY_BOUND if parity would require any host-only semantics (host equality, `-0` canonicalization, a host multiply primitive) — do not add host capability to satisfy the gate.
- STOP and surface a DEFECT if Python `run_mu` and JS `bootstrap_core` diverge (`muHashCached` not byte-identical, or `decode != a*b`) — diagnose the real L3-parity gap; never mask it.
- STOP if the `ln`/growth-cap or any mechanical gate would require `--no-verify` or manual bypass — route through `commit_executor` (FOUNDER_OVERRIDE auto-bump), never bypass.
- Observe COMMIT_GO_HOLD_PUSH: do not push/merge beyond authorized pipeline steps.

## Acceptance criteria

- `evidence_command` passes: `PYTHONHASHSEED=0 python3 -m pytest -q -m l4_expensive mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py --timeout=900 --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- For every `(a,b)` in the small corpus: the JS `bootstrap_core` multiply result is `muHashCached` byte-identical to the Python `run_mu` multiply result, AND both decode to host `a*b`.
- New parity classes are marked `l4_expensive` + `slow` (excluded from the green gate; nightly).
- `ln` test-file growth cap reflects exactly the one new file (+1); no other cap/ratchet movement.
- Host-semantics ratchet check is clean (net delta 0); diff contains no runtime/substrate/seed change.
- Indicator artifact `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json` is produced by `indicator_collection_command`.
- target_gate_id **G8** obligations satisfied (gate present and evidence reproducible).

## Grounding / Authorization

- **TASKS.md authorization:** tracker sync note dated 2026-06-18, TASKS.md line 554, wave `structural-numbers-multiply-js-parity-2026-06-18`, task `[NEXT-CODEX-POST-REDTEAM]`. Class L4_ENABLER, target_gate_id G8, `structural_artifact_ref: mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py`.
- **Same-wave authorization (wave-bound; commit automation derives the override from this line):**

  `FOUNDER_OVERRIDE:structural-numbers-multiply-js-parity-2026-06-18`

- **Authorization:** standing Phase B → `commit_executor` pipeline path. The wave-bound `FOUNDER_OVERRIDE` above is present at TASKS.md line 554, enabling the Step 5e growth-cap (`ln`) auto-bump and the strict-staged L4 pre-lock guard for this wave; do not bypass any mechanical gate.
- **Governing packet:** this file (`reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md`).
- **Auto-derived L4 fields:** see the `L4_FIELDS_FROM_TRACKER` block below (single source of truth; do not hand-edit).
- **Lineage:** progress_proof_before — multiply proven as Python `run_mu` projections (PR #1114), JS-substrate parity not yet validated; progress_proof_after — cross-substrate gate locks binary MULTIPLY L3 parity in both substrates. Stage 3 tower wave 2; Next: subtract.

## Request from Post-Merge Supervisor

StructuralNumbers JS-parity-for-multiply: L4_ENABLER gate proving the landed MULTIPLY projections (shift-and-add) run in the JS substrate (bootstrap_core via node) content-addressed-equal to the Python run_mu multiply over a small corpus, decoding to host a*b. JS Mu via container_factory; run_mu/node classes l4_expensive; growth cap pre-bumped. Stage 3 tower wave 2.

Routed next-candidate:
structural-numbers-multiply-js-parity-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-multiply-js-parity-2026-06-18 --output reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-multiply-js-parity-2026-06-18.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-multiply-js-parity-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py`
  - `reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md`
  - `reports/deferred/non_blocking/structural-numbers-multiply-js-parity-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `structural-numbers-multiply-js-parity-2026-06-18`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/structural-numbers-multiply-js-parity-2026-06-18_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-multiply-js-parity-2026-06-18`
- Active packet: `reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `dc3ce6a26a94f19c93af8628543319991441a8060f15cffccc4e5eb29d2d4102`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_multiply_js_parity.py`
  - `reports/control_plane/structural-numbers-multiply-js-parity-2026-06-18_2026-06-18.md`
  - `reports/deferred/non_blocking/structural-numbers-multiply-js-parity-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-multiply-js-parity-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
