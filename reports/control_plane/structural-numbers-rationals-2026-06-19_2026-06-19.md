# NEXT-CODEX-POST-REDTEAM - StructuralNumbers Stage 3 exact rational reduction gate

Date: 2026-06-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-rationals-2026-06-19
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage 3: prove exact rational representation as `{num: Z, den: positive}` reduced to lowest terms by composing the landed structural GCD projections and bounded exact quotient projections, with no host floats and no runtime, substrate, seed, registry, or production semantic edits.

## Scope

Additive gate-only exact-rationals proof over the landed StructuralNumbers projection stack. This wave may add one L4 gate file, update the growth-cap registry, create its control packet/config, update TASKS.md through the launcher tracker-note builder, and collect the indicator artifact only.

Files and surfaces in scope:

- mu/tests/l4_gates/test_structural_numbers_rationals.py (NEW) -- bounded exact-rational normalization gate over `{num: Z, den: positive}`.
- mu/tests/docs/test_growth_caps.py (MODIFY) -- bump CAP_TEST_FILES plus one with FOUNDER_OVERRIDE:structural-numbers-rationals-2026-06-19.
- reports/control_plane/structural-numbers-rationals-2026-06-19_wave_config.json (GENERATED) -- same-wave launcher/control config for this L4 gate.
- reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-19 tracker sync note for wave `structural-numbers-rationals-2026-06-19` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/structural-numbers-rationals-2026-06-19_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Create mu/tests/l4_gates/test_structural_numbers_rationals.py.
2. Define the test-local rational envelope shape exactly as StructuralNumbers.v0.md specifies: `{num: Z, den: positive}`, with zero encoded as numerator zero and denominator one.
3. Import and compose the landed StructuralNumbers codec helpers and `GCD_PROJECTIONS`. Repo-local evidence does not show a landed quotient/divide projection builder, and the landed multiply gate defers division/rationals, so this wave must define a test-local bounded exact quotient builder rather than pretending one already exists.
4. Define `build_exact_quotient_projections()` inside the new gate as a structural state machine over non-negative `N` numerator `n` and positive `N` divisor `d`:
   - Initial state: `{"_quot": {"n": n, "d": d}}` seeds `{"_quot_loop": {"rem": n, "d": d, "q": zero}}`.
   - Compare state: lift landed `COMPARE_PROJECTIONS` into `_quot_cmp` and compare `rem` to `d`.
   - Exact zero/equality exits: `rem == 0` emits `q`; `rem == d` runs one lifted landed ADD-by-one step and emits `q + 1`.
   - Strict greater loop: `rem > d` runs lifted landed SUBTRACT for `rem - d`, then lifted landed ADD-by-one for `q + 1`, then resumes `_quot_loop` with the positive difference.
   - Strict less failure: `rem < d` before a zero/equality exit is a visible non-exact stall/failure state and must not be consumed as a valid quotient.
   `MUL_PROJECTIONS` may be lifted only for an optional structural verifier that `q * d == n`; it must not substitute for exact division or become a production division surface.
5. Lock the exact-divisibility invariant: the quotient builder returns a canonical structural `N` only when the loop has consumed the remainder exactly. It must never return floor division. The rational reducer may call it only for `abs(num) / gcd(abs(num), den)` and `den / gcd(abs(num), den)`, where exactness is expected because the divisor is the structural GCD.
6. Bound termination explicitly: set a named corpus bound such as `MAX_STRUCTURAL_QUOTIENT = 6`, assert every rational corpus item and every quotient subcase stays within that bound, and size `run_mu` `max_steps` for at most that many quotient loop iterations per exact division. The structural measure is the non-negative remainder, which decreases by positive `d` on each strict-greater iteration.
7. Use a lean bounded rational corpus that covers zero numerator, already-reduced positive fractions, reducible positive fractions, reducible negative numerators, denominator-to-one results, and improper fractions. Include quotient-specific subcases for zero quotient, unit divisor, multi-step exact quotient, equality exit, and one non-exact negative control that visibly stalls/fails.
8. Assert canonical reduced form by structural equality and content-hash equality against oracle-built envelopes, with host arithmetic used only to build expected test oracles outside the engine.
9. Prove denominator positivity and canonical numerator shape; reject or visibly stall zero denominators rather than minting an invalid rational.
10. Mark run_mu engine assertions with pytest.mark.l4_expensive and pytest.mark.slow; any fast guard that transitively references run_mu must carry an in-function # SPEED_OK comment.
11. Bump CAP_TEST_FILES plus one in mu/tests/docs/test_growth_caps.py with the wave-specific founder override comment.
12. Run the evidence command and collect the L4 indicator artifact.

## Constraints

- Use the launcher and dispatcher path; do not hand-implement or hand-commit this wave.
- No runtime, substrate, seed, registry, projection seed, JS production, or host semantic file may change.
- No host floats anywhere in the wave. Host integer arithmetic, math.gcd, or division may appear only as test oracle scaffolding outside the engine path.
- Do not add a production rational seed or boundary codec in this wave; this is a bounded L4 gate over the existing structural-number projection stack.
- Do not reimplement landed GCD, compare, subtract, add, multiply, or codec projection logic when importing and lifting them is sufficient. The only new arithmetic scaffolding allowed is the test-local bounded exact quotient state machine described above.
- Keep the corpus bounded to small operands already compatible with the landed Stage 3 performance envelope.
- Do not touch Stage 4 design, Stage 4 int-first cutover, Stage 5 ordinal bridge, or pipeline-fix waves.

## Stop conditions

- Stop done when the evidence command passes, host-semantics ratchet stays flat, and the indicator artifact is collected.
- Halt as POLICY_BOUND if rational reduction cannot be expressed without host floats, runtime edits, production seed edits, or host-only semantic authority.
- Halt as STRUCTURAL_GAP if the bounded reducer requires a full structural division surface larger than the bounded exact quotient machine above can honestly prove; record the exact missing primitive rather than forcing host division into the engine.
- Halt as STRUCTURAL_GAP if a non-exact quotient path can return a floor quotient, a malformed numeral, or any value that the rational reducer could consume as valid.
- Halt as GROWTH_CAP_STALE if the current test-file cap cannot be bumped exactly once for this new gate file.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_rationals.py`
- Slow-kernel guard-tests (`run_mu`) carry an in-function `# SPEED_OK: <reason>` annotation so they stay out of the green-gate speed lane.

## Acceptance criteria

- mu/tests/l4_gates/test_structural_numbers_rationals.py exists and passes.
- The gate proves every normalized result has shape `{num: Z, den: positive}` with denominator one for zero numerator.
- The reducer composes landed structural GCD rather than using host gcd in the engine path.
- The gate includes a test-local bounded exact quotient projection builder with explicit compare, subtract, add-by-one, exact exit, non-exact failure, and termination-bound tests.
- Every quotient used by rational reduction is exact by structural state-machine construction; a non-exact quotient control visibly stalls/fails and is not accepted as a rational result.
- The corpus asserts small operand and quotient bounds, including a named maximum quotient loop bound, before any `run_mu` engine assertion.
- Every corpus item reduces to lowest terms and is structurally/content-hash equal to the oracle envelope.
- Zero denominator is rejected or stalls visibly; it must not produce a valid rational envelope.
- The run_mu tests carry l4_expensive and slow markers plus # SPEED_OK annotations where required.
- mu/tests/docs/test_growth_caps.py is bumped plus one with FOUNDER_OVERRIDE:structural-numbers-rationals-2026-06-19.
- reports/control_plane/structural-numbers-rationals-2026-06-19_wave_config.json is the only wave config artifact in scope.
- No diff appears under runtime, substrate, seed, registry, JS core, or production Mu semantic paths.
- reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `structural-numbers-rationals-2026-06-19`.
- Governing packet: this file, `reports/control_plane/structural-numbers-rationals-2026-06-19_2026-06-19.md`.
- TASKS.md authority: the 2026-06-19 tracker sync note for wave `structural-numbers-rationals-2026-06-19` records this packet path, structural artifact `mu/tests/l4_gates/test_structural_numbers_rationals.py`, evidence command, indicator artifact, and same-wave `FOUNDER_OVERRIDE`.
- Authorization: Founder-directed ordered queue from TASKS.md: after structural-numbers-gcd-js-parity-2026-06-19 lands, run structural-numbers-rationals-2026-06-19 before Stage 4 design.
- Reviewer correction grounding: repo-local search over `mu/tests/l4_gates/test_structural_numbers_*.py` found no landed quotient/divide projection builder; the Stage 3 multiply gate documents division/rationals as deferred. This packet therefore treats bounded exact quotient as an explicit new test-local design obligation.

FOUNDER_OVERRIDE:structural-numbers-rationals-2026-06-19

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-rationals-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-rationals-2026-06-19_2026-06-19.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_rationals.py`
  - `reports/control_plane/structural-numbers-rationals-2026-06-19_2026-06-19.md`
  - `reports/control_plane/structural-numbers-rationals-2026-06-19_wave_config.json`
  - `reports/deferred/non_blocking/structural-numbers-rationals-2026-06-19_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `structural-numbers-rationals-2026-06-19`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/structural-numbers-rationals-2026-06-19_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-rationals-2026-06-19 --output reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_rationals.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-rationals-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-rationals-2026-06-19.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-rationals-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-rationals-2026-06-19_2026-06-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c6a24821a41661a93211a61d8baf38e9afcca7a167af4a11bd93825fc87210a0`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_rationals.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-rationals-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_rationals.py`
  - `reports/control_plane/structural-numbers-rationals-2026-06-19_2026-06-19.md`
  - `reports/control_plane/structural-numbers-rationals-2026-06-19_wave_config.json`
  - `reports/deferred/non_blocking/structural-numbers-rationals-2026-06-19_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/structural-numbers-rationals-2026-06-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
