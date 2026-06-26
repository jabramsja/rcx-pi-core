# NEXT-CODEX-POST-REDTEAM - StructuralNumbers rationals cross-substrate JS-parity gate (Python run_projections over the landed RATIONAL_PROJECTIONS vs JS bootstrap_core, byte-identical), the one missing _js_parity proof

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-rationals-js-parity-2026-06-21b
Phase-A-Lock: LOCKED
Purpose: Add the missing StructuralNumbers RATIONALS cross-substrate JS-parity gate. Every other operation (add, compare, codec, multiply, subtract, gcd) has a `test_structural_numbers_<op>_js_parity.py` proving the landed Mu projections produce BYTE-IDENTICAL results in Python and JS (bootstrap_core via node); rationals is the only one without it (test_structural_numbers_rationals.py exists but no _js_parity). This wave adds `mu/tests/l4_gates/test_structural_numbers_rationals_js_parity.py` mirroring the proven template `test_structural_numbers_gcd_js_parity.py`: import the landed rationals projections, drive them through the bounded Python stepper AND JS bootstrap_core, assert muHashCached is byte-identical across substrates, the decoded rational equals the expected value, AND both substrates reach a genuine stall/fixpoint with no leftover internal-state keys (the explicit cross-substrate convergence proof the GCD template's `test_both_engines_reach_stall_fixpoint` provides; round-3). Test-only (the rationals projections already landed); no runtime/substrate modification -> L4_ENABLER. Growth-cap handling: this wave HAND-PRE-BUMPS `CAP_TEST_FILES` 151 -> 152 in `mu/tests/docs/test_growth_caps.py` (under the wave FOUNDER_OVERRIDE) because the Phase-B bridge reviews the PRE-COMMIT staged state, where the #1141 commit_executor Step-5e auto-bump has not yet fired; a gate-authoring wave that relies ONLY on the auto-bump trips the growth-cap guard at bridge time (the sequencing lesson behind this `-21b` restart). The Step-5e auto-bump is the idempotent commit-time SAFETY NET that byte-matches the hand-bump and no-ops -- this wave does NOT prove a no-manual-step auto-bump.

## Cross-substrate driver (resolves bridge REQUEST_CHANGES round-1)

REQUEST_CHANGES finding (DEFECT): the prior draft required Python `run_mu` for the rationals parity proof, but the landed rationals gate deliberately does NOT use `run_mu`. Resolution, grounded in current code truth:

- The gcd parity template drives its Python side with `run_mu` (the `run_mu` calls in `test_structural_numbers_gcd_js_parity.py`) because GCD does not blow up under the meta-kernel.
- The landed rationals functional gate drives `RATIONAL_PROJECTIONS` through `run_projections`, NOT `run_mu` (`run_rational_reduce` in `test_structural_numbers_rationals.py`), with the inline rationale: the quotient/exact-division subcases exercise `run_mu` separately, "while this wrapper uses the repo's test stepper to avoid meta-kernel blowup on already-landed GCD rows." Rationals COMPOSE those already-landed GCD rows, so `run_mu` over `RATIONAL_PROJECTIONS` is the documented blowup path.
- Therefore the rationals parity gate's Python driver is `run_projections(RATIONAL_PROJECTIONS, state, max_steps=RATIONAL_MAX_STEPS, terminal_value=None)` -- the EXACT bounded stepper the landed `run_rational_reduce` uses -- not `run_mu`. This is the single deliberate deviation from the gcd template; every other piece of the template (l4_expensive+slow marks, `# SPEED_OK` pattern, JSON->trustMu node bridge, JS `MAX_RUN_STEPS` clamp) is mirrored unchanged.
- Bounded-by-construction: `run_projections` is the repo test stepper capped at `RATIONAL_MAX_STEPS`, run over a lean corpus, so the Python side cannot blow up. The JS side stays `bootstrap_core.run` clamped to the live `MAX_RUN_STEPS` (10000). The parity claim is unchanged: the SAME landed `RATIONAL_PROJECTIONS` evaluated to fixpoint on each substrate yield byte-identical muHashCached result terms, and `decode == expected`.
- The TASKS.md tracker note's "Python run_mu" wording (the wave's TASKS.md tracker sync note) is the general cross-substrate-parity intent; the operational Python driver for the rational reduction is `run_projections`, per the landed code above. `run_mu` is intentionally NOT used for the rational reduction in this gate. (The packet derives its L4 fields -- target_gate_id, evidence_command, FOUNDER_OVERRIDE, indicator -- from the tracker note unchanged; only the Python stepper choice is made precise here.)

## Bridge REQUEST_CHANGES round-2 resolution

Two blocking findings from bridge round 2, resolved here with packet-only edits (TASKS.md and code are unchanged by this rewrite; the fix is to make the packet internally consistent and the proof limitation mechanically explicit).

### Finding 1 (DEFECT) -- growth-cap proof was internally inconsistent and ungated

- Source of the inconsistency: the prior Purpose claimed this wave "proves the #1141 normal-commit-path growth-cap auto-bump end-to-end ... with no manual step," which directly contradicted the Scope/Constraints requirement to PRE-BUMP `CAP_TEST_FILES` in-wave. A wave cannot both require a manual pre-bump and prove a no-manual-step auto-bump. The no-manual-step framing is withdrawn.
- Consistent policy (now stated identically in Purpose, Scope, Constraints, and Acceptance): the Phase-B bridge reviews the PRE-COMMIT staged state, where the commit_executor Step-5e auto-bump has NOT yet fired. A gate-authoring wave that relies ONLY on the auto-bump trips `mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap` at bridge time (the sequencing lesson behind this `-21b` restart). Therefore this wave HAND-PRE-BUMPS `CAP_TEST_FILES` 151 -> 152 under the wave FOUNDER_OVERRIDE, byte-matching what Step-5e would write so the commit-time auto-bump idempotently no-ops. The auto-bump is a redundant SAFETY NET, not the proof.
- Validation gate added (the "lacks a validation gate" half of the finding): the scoped cap change is now guarded by `mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap` (which asserts `count <= BASELINE_TEST_FILES(190) + CAP_TEST_FILES`). It must be GREEN in the same staged state the bridge reviews. See Validation gates. The tracker-bound L4 `evidence_command` (the rationals parity test) is unchanged; the cap guard is an ADDITIONAL local gate, not a mutation of the tracker-derived evidence_command.

### Finding 2 (DOC_ACCURACY) -- the TASKS.md tracker note says "run_mu", this packet uses "run_projections"

- The TASKS.md tracker note phrases the proof as "Python run_mu vs JS bootstrap_core" in its PROSE fields only: the note title, `evidence_delta`, `progress_proof_after`, and the "# SPEED_OK on the node/run_mu calls" aside.
- Code truth overrides the prose (CLAUDE.md rule_5): the landed `run_rational_reduce` (in `mu/tests/l4_gates/test_structural_numbers_rationals.py`, re-verified this round) drives `RATIONAL_PROJECTIONS` with `run_projections`, NOT `run_mu`, with the inline rationale "to avoid meta-kernel blowup on already-landed GCD rows." `run_mu` over the composed rationals table is the documented blowup path, so it is INFEASIBLE here -- not merely heavier.
- Mechanically explicit limitation (what this gate does and does NOT prove): it proves `RATIONAL_PROJECTIONS` *fixpoint* parity across substrates -- the SAME landed table evaluated to fixpoint by Python `run_projections` and JS `bootstrap_core.run` yields byte-identical muHashCached + `decode == expected`. It does NOT additionally assert `run_mu` meta-kernel evaluation of the rational reduction; the already-landed quotient/exact-division subcases exercise `run_mu` separately. The JS side never used `run_mu` (it uses `bootstrap_core.run`), so confining the Python driver to `run_projections` does not weaken the cross-substrate claim.
- No L4 field drifts: every machine-derived field is driver-agnostic and identical between the note and this packet -- `evidence_command` (`pytest ... test_structural_numbers_rationals_js_parity.py -m l4_expensive`, which contains NO `run_mu` reference), `target_gate_id` (G8), class (L4_ENABLER), `FOUNDER_OVERRIDE`, `indicator_artifact_ref`, `primary_invariant_id` (INV_CROSS_SUBSTRATE_PARITY). The divergence is confined to human-readable prose; this packet supersedes that prose per code truth. A follow-up tracker-sync MAY re-word the note from "run_mu" to "run_projections", but is NOT required for L4 binding because every machine field already matches.

## Bridge REQUEST_CHANGES round-3 resolution

One blocking finding from bridge round 3, resolved here with packet-only edits (TASKS.md and code are unchanged; the fix tightens the test's acceptance so the gate proves the cross-substrate *convergence* it claims -- not merely a byte-identical snapshot of two states that might both be unconverged).

### Finding 3 (DEFECT) -- acceptance omitted the explicit cross-substrate stall/fixpoint proof

- Gap: work item 2 and the acceptance criteria required only byte-identical `muHashCached` + `decode == expected`. They did NOT require both substrates to report a genuine stall/fixpoint, nor that the result reject leftover rationals internal-state keys. Two substrates can byte-match on an *intermediate* (unconverged) state, so byte-identity alone does not prove the projections ran to fixpoint.
- The proven GCD template already supplies this proof: `test_both_engines_reach_stall_fixpoint` (in `test_structural_numbers_gcd_js_parity.py`) asserts `stalled is True` for BOTH engines, that the result is the clean `{"_num": ...}` numeral wrapper (`len == 1`), and that NO in-progress state keys (`_gcd`, `_gcd_cmp`, `_cmp`, `_cc`, `_sub`, `_sub_cmp`, `_borrow`, `_subfold`) survive. The rationals gate MUST mirror this method.
- Critical substrate asymmetry -- why a literal copy of the GCD `assert stalled is True` is INSUFFICIENT for this gate, and the precise adaptation:
  - JS `bootstrap_core.run` returns `stalled: true` ONLY on a genuine fixpoint (`nextHash === currentHash` in `bootstrap_core.run`) and `stalled: false` on `maxSteps` exhaustion (the `maxSteps`-exhaustion branch of `bootstrap_core.run`). So `entry["stalled"] is True` on the JS side IS a genuine-convergence assertion -- mirror it unchanged.
  - Python `run_projections` (the round-1 rationals driver, NOT `run_mu`) returns `is_stall=True` for a genuine stall (`steps < max_steps`) AND for budget exhaustion (`steps == max_steps`) -- see the `run_projections` docstring and its post-loop `return state, max_steps, True` in `projection_stepper.py`. Asserting Python `is_stall is True` ALONE therefore does NOT exclude budget exhaustion; the gate must ALSO assert `steps < RATIONAL_MAX_STEPS` to prove a genuine fixpoint.
- Resolution (now required in Work items 2-3 + Acceptance; it runs under the SAME `-m l4_expensive` evidence_command -- no new gate command): the gate adds a `test_both_engines_reach_stall_fixpoint`-equivalent over the rationals corpus asserting, for every case --
  1. JS: `entry["stalled"] is True` (genuine fixpoint).
  2. Python: `is_stall is True` AND `steps < RATIONAL_MAX_STEPS` (genuine stall, NOT exhaustion).
  3. Both results: key-set EXACTLY `{"num", "den"}` -- the clean reduced-rational wrapper (`_oracle_rational(0, 2) == {"num": ZERO_N, "den": ONE_POS}`, the `_oracle_rational` helper in `test_structural_numbers_rationals.py`) -- with NONE of the rationals in-progress work-slot keys (`_rat`, `_rat_gcd`, `_rat_quot`, `_quot`, `_quot_add`, `_quot_cmp`, `_quot_loop`, `_quot_non_exact`, `_quot_sub`, `_gcd`, `_gcd_cmp`, `_gcd_sub`, `_cmp`, `_sub`) surviving. This is the rationals analog of the GCD forbidden set; the implementer enumerates the exact set from `RATIONAL_PROJECTIONS`.
- Corpus consequence: the lean corpus MUST use EXACT-reducible num/den pairs (the converging `RATIONAL_CORPUS` family that reaches `{"num","den"}`), NOT the deliberately-stalling raw `_quot` / `_quot_non_exact` control cases (in `test_structural_numbers_rationals.py`), which stall `True` at a work-slot state and would (correctly) fail the clean-wrapper check.
- No L4 field drifts: evidence_command, target_gate_id (G8), class (L4_ENABLER), FOUNDER_OVERRIDE, indicator, and primary_invariant_id (INV_CROSS_SUBSTRATE_PARITY) are all unchanged; this finding only strengthens the test body the evidence_command already executes.

## Scope

Add the rationals cross-substrate JS-parity gate (Python `run_projections` over the landed `RATIONAL_PROJECTIONS` vs JS `bootstrap_core`, byte-identical), mirroring the existing _js_parity gates' harness scaffolding. L4_ENABLER: a new l4_gates test file + the in-wave PRE-BUMPED growth cap (the commit-time Step-5e auto-bump is the idempotent safety net); no runtime dirs. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/tests/l4_gates/test_structural_numbers_rationals_js_parity.py (CREATE) -- mirror test_structural_numbers_gcd_js_parity.py for rationals: import the landed rationals projections (as test_structural_numbers_rationals.py does), run a lean corpus through the bounded Python stepper `run_projections` over `RATIONAL_PROJECTIONS` (capped at `RATIONAL_MAX_STEPS`, terminal_value=None -- mirroring the landed `run_rational_reduce`, NOT `run_mu`) AND JS bootstrap_core (node, JSON->trustMu), assert byte-identical muHashCached across substrates + decode==expected, AND mirror `test_both_engines_reach_stall_fixpoint` (assert both substrates genuinely converge -- JS `stalled is True`; Python `is_stall is True` AND `steps < RATIONAL_MAX_STEPS` -- and each result is the clean `{"num","den"}` reduced-rational wrapper with no leftover in-progress work-slot keys). Use an EXACT-reducible corpus so each case reaches that fixpoint. Mark @pytest.mark.l4_expensive (+ slow); add in-function `# SPEED_OK: <bounded proof>` on the rational-reduce + node-subprocess calls (the landed `run_rational_reduce` `# SPEED_OK` pattern; check_test_speed.sh transitive-flag pattern). Clamp the JS driver to the live MAX_RUN_STEPS cap (do not assert a literal step count above it).
- mu/tests/docs/test_growth_caps.py (MODIFY) -- HAND-PRE-BUMP `CAP_TEST_FILES` 151 -> 152 IN THIS WAVE with an inline FOUNDER_OVERRIDE annotation appended in the SAME style as the existing `+1 for ...` entries, e.g. `; +1 for test_structural_numbers_rationals_js_parity.py (structural-numbers-rationals-js-parity-2026-06-21b wave, FOUNDER_OVERRIDE:structural-numbers-rationals-js-parity-2026-06-21b)`. REQUIRED: the Phase-B bridge reviews the PRE-COMMIT staged state where the commit_executor Step-5e auto-bump has NOT yet fired, so the new gate file trips `test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap` unless the wave bumps the cap. The hand-bump must BYTE-MATCH what Step-5e would write so the commit-time auto-bump idempotently no-ops; the auto-bump remains the redundant safety net.
- reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-21 tracker sync note for wave `structural-numbers-rationals-js-parity-2026-06-21b` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/structural-numbers-rationals-js-parity-2026-06-21b_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read test_structural_numbers_gcd_js_parity.py (the harness template, incl. `test_both_engines_reach_stall_fixpoint`) + test_structural_numbers_rationals.py (the landed rationals projections, corpus, the `run_rational_reduce` Python driver, the `{"num","den"}` reduced-result shape, and `RATIONAL_MAX_STEPS`) + the JS-parity harness pattern (JSON->trustMu in node, bootstrap_core.run, the muHashCached comparison). Confirm the Python driver to mirror is `run_projections` over `RATIONAL_PROJECTIONS` (NOT `run_mu`).
2. Create test_structural_numbers_rationals_js_parity.py mirroring the template's harness for rationals: a lean EXACT-reducible corpus (each num/den pair reduces to the clean `{"num","den"}` fixpoint -- NOT the deliberately-stalling raw `_quot`/`_quot_non_exact` control cases), Python side via `run_projections(RATIONAL_PROJECTIONS, state, max_steps=RATIONAL_MAX_STEPS, terminal_value=None)` (the landed `run_rational_reduce` driver, capturing the returned steps + stall flag), JS bootstrap_core side (node subprocess, trustMu container construction), byte-identical muHashCached assertion + decode==expected.
3. Mirror `test_both_engines_reach_stall_fixpoint` -- the explicit cross-substrate convergence proof (Finding 3). For every corpus case assert: (a) JS `entry["stalled"] is True` (genuine fixpoint -- JS reports `stalled:false` on maxSteps exhaustion); (b) Python `is_stall is True` AND `steps < RATIONAL_MAX_STEPS` (genuine stall, NOT budget exhaustion -- `run_projections` returns `is_stall=True` on exhaustion too); (c) both substrates' result has key-set EXACTLY `{"num","den"}` (the clean reduced-rational wrapper) with NONE of the rationals in-progress work-slot keys (`_rat`, `_rat_gcd`, `_rat_quot`, `_quot`, `_quot_add`, `_quot_cmp`, `_quot_loop`, `_quot_non_exact`, `_quot_sub`, `_gcd`, `_gcd_cmp`, `_gcd_sub`, `_cmp`, `_sub`) -- the rationals analog of the GCD forbidden set, enumerated from `RATIONAL_PROJECTIONS`.
4. Mark l4_expensive+slow; add in-function `# SPEED_OK` on the rational-reduce + node-subprocess calls (mirroring the landed `run_rational_reduce` SPEED_OK); clamp the JS maxSteps to the live MAX_RUN_STEPS (do not exceed/assert-above the cap). Do NOT introduce a `run_mu` call over `RATIONAL_PROJECTIONS`.
5. Run the evidence_command (l4_expensive) and confirm byte-identical parity AND genuine cross-substrate stall/fixpoint; emit the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- L4_ENABLER: do NOT touch runtime dirs (mu/host/**, rcx_pi/selfhost/**) -- the rationals projections already landed; this wave adds ONLY the parity test.
- Mirror the template's HARNESS scaffolding (l4_expensive+slow marks, `# SPEED_OK` pattern, JSON->trustMu node bridge, JS-side MAX_RUN_STEPS clamp) -- do not invent a new harness -- with ONE deliberate, code-grounded deviation: the Python-side driver is `run_projections` over `RATIONAL_PROJECTIONS` (the landed `run_rational_reduce` stepper), NOT `run_mu`. The gcd template uses `run_mu` because gcd does not blow up; rationals composes the already-landed GCD rows where `run_mu` does (the documented meta-kernel blowup). Do NOT "restore" `run_mu` over `RATIONAL_PROJECTIONS` to match the template literally -- that reintroduces the blowup the landed gate already avoids.
- Lean corpus: keep the corpus small enough to converge under `RATIONAL_MAX_STEPS` (Python) and the JS `MAX_RUN_STEPS` cap, like the other _js_parity gates.

- PRE-BUMP `CAP_TEST_FILES` 151 -> 152 in mu/tests/docs/test_growth_caps.py IN THIS WAVE with an inline FOUNDER_OVERRIDE annotation (same style as the existing `+1 for ...` entries), byte-matching what commit_executor Step-5e would write. The Phase-B bridge reviews the pre-commit staged state, so the new gate file trips `test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap` unless the wave bumps the cap -- this is the actual guard for the scoped cap change. The Step-5e auto-bump is the redundant idempotent safety net (no-ops on the byte-matched hand-bump), NOT the primary mechanism for a gate-authoring wave.

## Stop conditions

- Stop done when the evidence_command passes (byte-identical Python<->JS muHashCached for the rationals corpus + decode==expected) and the indicator is collected.
- Halt as POLICY_BOUND if a rationals projection is NOT byte-identical across substrates (a real parity defect to surface, like the prior signed-zero finding) rather than weakening the assertion.
- Bounded-infeasibility stop (DEFECT-resolution): the Python side is the bounded `run_projections` stepper, so it cannot blow up by construction. If, contrary to the landed `run_rational_reduce` evidence, even a lean `run_projections` corpus cannot converge under `RATIONAL_MAX_STEPS` (the genuine-stall assertion `steps < RATIONAL_MAX_STEPS` fails -- i.e. budget exhaustion rather than fixpoint), HALT and surface POLICY_BOUND -- do NOT widen the step cap unboundedly, do NOT fall back to `run_mu` over `RATIONAL_PROJECTIONS` (the documented blowup), and do NOT add any host shortcut. Report the non-convergence as the blocker.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command (tracker-bound per the TASKS.md tracker sync note; driver-agnostic, contains no `run_mu` reference): `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_structural_numbers_rationals_js_parity.py -m l4_expensive --tb=short`
- growth-cap guard (Finding-1 fix; gates the in-wave `CAP_TEST_FILES` 151 -> 152 pre-bump): `PYTHONHASHSEED=0 python3 -m pytest -q "mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap" --tb=short` -- asserts the post-bump test-file count stays <= BASELINE_TEST_FILES (190) + CAP_TEST_FILES (152). This is the actual guard for the scoped cap change and must be GREEN in the same staged state the Phase-B bridge reviews. It is an ADDITIONAL local gate; it does NOT mutate the tracker-bound L4 evidence_command above.

## Acceptance criteria

- test_structural_numbers_rationals_js_parity.py asserts byte-identical muHashCached across the Python `run_projections` driver (over the landed `RATIONAL_PROJECTIONS`, mirroring `run_rational_reduce`) and JS bootstrap_core for the rationals corpus, decode==expected; l4_expensive+slow marked. No `run_mu` call over `RATIONAL_PROJECTIONS` is introduced.
- The gate proves cross-substrate *convergence*, not just a byte-identical snapshot (Finding 3): for every corpus case it asserts JS `entry["stalled"] is True` (genuine fixpoint -- JS reports `stalled:false` on maxSteps exhaustion) AND Python `is_stall is True` with `steps < RATIONAL_MAX_STEPS` (genuine stall, not budget exhaustion -- `run_projections` returns `is_stall=True` on exhaustion too), AND both substrates' result has key-set exactly `{"num","den"}` (the clean reduced-rational wrapper) with no leftover rationals in-progress work-slot keys (`_rat`/`_rat_gcd`/`_rat_quot`/`_quot*`/`_gcd*`/`_cmp`/`_sub`) -- mirroring the GCD `test_both_engines_reach_stall_fixpoint`. This runs under the same `-m l4_expensive` evidence_command.
- No runtime dirs touched. The growth cap is HAND-PRE-BUMPED in-wave (`CAP_TEST_FILES` 151 -> 152) under the wave FOUNDER_OVERRIDE, and `test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap` is GREEN in the pre-commit staged state the Phase-B bridge reviews; the commit-time Step-5e auto-bump is the idempotent safety net (byte-matches the hand-bump, no-ops). This wave does NOT claim a no-manual-step auto-bump proof.
- evidence_command clean; growth-cap guard green; indicator emitted.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `structural-numbers-rationals-js-parity-2026-06-21b`.
- Governing packet: this file, `reports/control_plane/structural-numbers-rationals-js-parity-2026-06-21b_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `structural-numbers-rationals-js-parity-2026-06-21b` is canonical for this packet's L4 fields. Its "Python run_mu" phrasing is the general cross-substrate-parity intent; the operational Python driver for the rational reduction is `run_projections`, per the landed `run_rational_reduce` (code truth over packet wording).
- Authorization: Founder-approved 2026-06-21 (queue the missing rationals JS-parity + advance the StructuralNumbers cross-substrate program). This wave also exercises the #1141 Step-5e growth-cap auto-bump as the idempotent commit-time safety net behind the REQUIRED in-wave pre-bump -- it is NOT a no-manual-step auto-bump proof (the Phase-B bridge reviews the pre-commit staged state, so the pre-bump is mandatory). Auto-authorized (feedback_manual_then_structural_autonomy / feedback_pipeline_first_parallel_builders).

FOUNDER_OVERRIDE:structural-numbers-rationals-js-parity-2026-06-21b

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-rationals-js-parity-2026-06-21b`
- Active packet: `reports/control_plane/structural-numbers-rationals-js-parity-2026-06-21b_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_rationals_js_parity.py`
  - `reports/control_plane/structural-numbers-rationals-js-parity-2026-06-21b_2026-06-21.md`
  - `reports/deferred/non_blocking/structural-numbers-rationals-js-parity-2026-06-21b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `structural-numbers-rationals-js-parity-2026-06-21b`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/structural-numbers-rationals-js-parity-2026-06-21b_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-rationals-js-parity-2026-06-21b --output reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_rationals_js_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-rationals-js-parity-2026-06-21b_2026-06-21.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-rationals-js-parity-2026-06-21b.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-rationals-js-parity-2026-06-21b`
- Active packet: `reports/control_plane/structural-numbers-rationals-js-parity-2026-06-21b_2026-06-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `1785809c2f9ef9d1f92ff68d2bc68a8c973058222fc309dc6ee861cd1f82d360`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_rationals_js_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-rationals-js-parity-2026-06-21b_2026-06-21.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_rationals_js_parity.py`
  - `reports/control_plane/structural-numbers-rationals-js-parity-2026-06-21b_2026-06-21.md`
  - `reports/deferred/non_blocking/structural-numbers-rationals-js-parity-2026-06-21b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-rationals-js-parity-2026-06-21b.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
