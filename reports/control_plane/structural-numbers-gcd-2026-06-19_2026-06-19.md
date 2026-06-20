# NEXT-CODEX-POST-REDTEAM - StructuralNumbers Stage 3 structural GCD as run_mu projections

Date: 2026-06-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-gcd-2026-06-19
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage 3: express integer GCD as pure RCX projections through run_mu by lifting the landed COMPARE and SUBTRACT projection tables. The engine must use Euclidean subtraction over non-negative N operands with no host gcd, mod, divide, comparison, or subtraction primitive.

## Scope

Add a Python-only L4 gate for structural GCD and the required growth-cap tracker update. This wave is gate-only and uses TASKS.md as tracker-sync authority.

Files and surfaces in scope:

- mu/tests/l4_gates/test_structural_numbers_gcd.py (NEW) -- L4 gate expressing GCD as run_mu projections that lift the landed COMPARE and SUBTRACT tables.
- mu/tests/docs/test_growth_caps.py (MODIFY) -- bump CAP_TEST_FILES plus one with FOUNDER_OVERRIDE:structural-numbers-gcd-2026-06-19.
- reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-19 tracker sync note for wave `structural-numbers-gcd-2026-06-19` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Create mu/tests/l4_gates/test_structural_numbers_gcd.py implementing the _gcd state machine with zero dispatch, lifted compare dispatch, lifted subtract work slots, and _gcd re-seeding after each strict positive difference.
2. Import and lift COMPARE_PROJECTIONS plus _v from the landed compare gate and SUB_PROJECTIONS from the landed subtract gate; do not copy or reimplement their projection logic.
3. Use the lean corpus only: gcd pairs (0,0), (5,0), (0,4), (4,2), (6,4), and (6,3), with operands no larger than 6 and at most two Euclidean steps for compute cases.
4. Assert canonical structural equality, content-hash equality, valid canonical N numeral shape, stall fixpoint, and decode-to-host as supporting evidence only.
5. Mark run_mu engine assertions with pytest.mark.l4_expensive and pytest.mark.slow; any fast guard that transitively references run_mu must carry an in-function # SPEED_OK comment.
6. Bump CAP_TEST_FILES plus one in mu/tests/docs/test_growth_caps.py with the wave-specific founder override comment.
7. Run the evidence command and collect the L4 indicator artifact.

## Constraints

- Use the pipeline launcher and dispatcher path before any direct manual implementation or commit path.
- No runtime, substrate, seed, registry, projection seed, JS parity, or production Mu semantic file may change in this wave.
- No new host primitive and no host gcd, mod, divide, comparison, or subtraction in the engine; math.gcd is oracle-only in mu/tests.
- Do not reimplement compare or subtract; lift the already landed projection tables.
- Keep the corpus bounded to operands no larger than 6 and at most two Euclidean steps per compute case.
- JS parity is deferred to a separate follow-up wave.

## Stop conditions

- Stop done when the evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if integer GCD cannot be expressed without host gcd or host mod.
- If the lean corpus exceeds the nightly 900 second budget, reduce corpus only within the packet bounds before escalating.
- If the gate requires touching runtime, substrate, seed, or JS production files, re-scope rather than relaxing the boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_gcd.py`
- Slow-kernel guard-tests (`run_mu`) carry an in-function `# SPEED_OK: <reason>` annotation so they stay out of the green-gate speed lane.

## Acceptance criteria

- mu/tests/l4_gates/test_structural_numbers_gcd.py exists and passes for every corpus pair.
- run_mu reduces each _gcd input to encode(math.gcd(a,b)) with canonical structural equality and content-hash equality.
- The result is a valid canonical N numeral and no _gcd, _gcd_cmp, _gcd_sub, _cmp, _cc, or _sub state remains.
- COMPARE and SUBTRACT are mechanically lifted from the landed gate tables, not reimplemented.
- mu/tests/docs/test_growth_caps.py is bumped plus one with FOUNDER_OVERRIDE:structural-numbers-gcd-2026-06-19.
- check_host_semantics_ratchet.py reports no host semantics delta.
- reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `structural-numbers-gcd-2026-06-19`.
- Governing packet: this file, `reports/control_plane/structural-numbers-gcd-2026-06-19_2026-06-19.md`.
- TASKS.md authority: the 2026-06-19 tracker sync note for wave `structural-numbers-gcd-2026-06-19` is canonical for this packet's L4 fields.
- Authorization: StructuralNumbers program continuation: Stage 3 first, numbers as Mu rather than host semantics. This is the queued GCD prerequisite for exact rationals.

FOUNDER_OVERRIDE:structural-numbers-gcd-2026-06-19

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-gcd-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-gcd-2026-06-19_2026-06-19.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_gcd.py`
  - `reports/control_plane/structural-numbers-gcd-2026-06-19_2026-06-19.md`
  - `reports/control_plane/structural-numbers-gcd-2026-06-19_wave_config.json`
  - `reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-gcd-2026-06-19 --output reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_gcd.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-gcd-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-gcd-2026-06-19.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-gcd-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-gcd-2026-06-19_2026-06-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `bb352660a5ebf99bbc2caecbee7b558c48a7cf06a774282a62e49343f76f64b7`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_structural_numbers_gcd.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-gcd-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_structural_numbers_gcd.py`
  - `reports/control_plane/structural-numbers-gcd-2026-06-19_2026-06-19.md`
  - `reports/control_plane/structural-numbers-gcd-2026-06-19_wave_config.json`
  - `reports/l4_wave_indicators/structural-numbers-gcd-2026-06-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
