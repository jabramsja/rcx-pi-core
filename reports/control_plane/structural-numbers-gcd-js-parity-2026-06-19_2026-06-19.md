# NEXT-CODEX-POST-REDTEAM - StructuralNumbers Stage 3 GCD JS parity gate

Date: 2026-06-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-gcd-js-parity-2026-06-19
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage 3: prove the landed structural GCD projections run content-addressed-equal across Python run_mu and the JS bootstrap_core path over the same bounded corpus, without adding runtime, substrate, seed, registry, or host semantic authority.

## Scope

Additive gate-only JS parity proof for the already-landed structural GCD projections. This wave may add one test file, update the growth-cap registry, create its control packet/config, and collect the indicator artifact only.

Files and surfaces in scope:

- mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py (NEW) -- cross-substrate parity gate for the landed GCD projections.
- mu/tests/docs/test_growth_caps.py (MODIFY) -- bump CAP_TEST_FILES plus one with FOUNDER_OVERRIDE:structural-numbers-gcd-js-parity-2026-06-19.
- reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-19 tracker sync note for wave `structural-numbers-gcd-js-parity-2026-06-19` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Create mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py.
2. Import the landed GCD_PROJECTIONS and CORPUS from test_structural_numbers_gcd.py and reuse encode/decode/hash helpers from the landed StructuralNumbers gates where appropriate.
3. Run the same GCD projections through Python run_mu and JS bootstrap_core via node over the bounded GCD corpus; assert content-addressed equality and decoded math.gcd agreement as oracle-only supporting evidence.
4. Use the existing mu/host/js/core/container_factory.js API as a use-only surface for trusted JS Mu construction; do not edit JS runtime or core files.
5. Mark run_mu/node parity tests with pytest.mark.l4_expensive and pytest.mark.slow so the gate is excluded from the fast lane.
6. Bump CAP_TEST_FILES plus one in mu/tests/docs/test_growth_caps.py with the wave-specific founder override comment.
7. Run the evidence command and collect the L4 indicator artifact.

## Constraints

- Use the launcher and dispatcher path; do not hand-implement or hand-commit this wave.
- No runtime, substrate, seed, registry, projection seed, JS production, or host semantic file may change.
- No host-only canonicalization may be added to force parity; any content-addressed divergence is a real finding.
- Do not reimplement GCD, compare, or subtract projection logic; import and reuse the already-landed GCD table.
- Keep the corpus bounded to the landed GCD corpus.
- Do not touch rationals, Stage 4 design, or Stage 4 cutover in this wave.

## Stop conditions

- Stop done when the evidence command passes, host-semantics ratchet stays flat if run, and the indicator artifact is collected.
- Halt as PARITY_DIVERGENCE if Python run_mu and JS bootstrap_core are not content-addressed-equal over the bounded corpus.
- Halt as POLICY_BOUND if the gate requires touching runtime, substrate, seed, registry, JS core, or production semantic files.
- Halt as GROWTH_CAP_STALE if the current test-file cap cannot be bumped exactly once for this new gate file.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`
- Slow-kernel guard-tests (`run_mu`, `node`) carry an in-function `# SPEED_OK: <reason>` annotation so they stay out of the green-gate speed lane.

## Acceptance criteria

- mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py exists and passes.
- The gate proves Python run_mu and JS bootstrap_core GCD results are content-addressed-equal for every landed GCD corpus pair.
- Decoded supporting evidence equals math.gcd(a, b) for every corpus pair, with math.gcd used only as a test oracle.
- The run_mu/node parity test carries l4_expensive and slow markers.
- mu/tests/docs/test_growth_caps.py is bumped plus one with FOUNDER_OVERRIDE:structural-numbers-gcd-js-parity-2026-06-19.
- No diff appears under runtime, substrate, seed, registry, JS core, or production Mu semantic paths.
- reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `structural-numbers-gcd-js-parity-2026-06-19`.
- Governing packet: this file, `reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_2026-06-19.md`.
- TASKS.md authority: the 2026-06-19 tracker sync note for wave `structural-numbers-gcd-js-parity-2026-06-19` is canonical for this packet's L4 fields.
- Authorization: Founder-directed ordered queue from TASKS.md: after structural-numbers-gcd-2026-06-19 lands, run structural-numbers-gcd-js-parity-2026-06-19 before rationals.

FOUNDER_OVERRIDE:structural-numbers-gcd-js-parity-2026-06-19

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-gcd-js-parity-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_2026-06-19.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`
  - `reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_2026-06-19.md`
  - `reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_wave_config.json`
  - `reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-gcd-js-parity-2026-06-19 --output reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-gcd-js-parity-2026-06-19.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-gcd-js-parity-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_2026-06-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `74fba0ba5f10c91ff4fd003b29294373f61a82917827cb9616570fbf0e3f6313`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`
  - `reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_2026-06-19.md`
  - `reports/control_plane/structural-numbers-gcd-js-parity-2026-06-19_wave_config.json`
  - `reports/l4_wave_indicators/structural-numbers-gcd-js-parity-2026-06-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
