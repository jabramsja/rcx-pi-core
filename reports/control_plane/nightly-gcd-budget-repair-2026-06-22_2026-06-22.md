# NEXT-CODEX-POST-REDTEAM - repair nightly StructuralNumbers GCD timeout budget

Date: 2026-06-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: nightly-gcd-budget-repair-2026-06-22
Phase-A-Lock: LOCKED
Purpose: Repair the scheduled Slow Tests (Nightly) l4_expensive lane after repeated StructuralNumbers GCD timeout failures. Keep the structural GCD proof honest, but bring the gate back inside the 900 second nightly budget authorized by the original GCD packet.

## Scope

Test/CI repair for the landed StructuralNumbers GCD gates. The wave may edit only the mirrored GCD test files, the nightly workflow if selector structure must change, the growth-cap/tracker/docs surfaces required by the pipeline, and generated control/indicator artifacts.

Files and surfaces in scope:

- tests/l4_gates/test_structural_numbers_gcd.py and mu/tests/l4_gates/test_structural_numbers_gcd.py (MODIFY) -- keep the structural GCD proof but reduce or partition over-budget corpus evidence inside the original packet authorization.
- tests/l4_gates/test_structural_numbers_gcd_js_parity.py and mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py (MODIFY IF NEEDED) -- keep Python-vs-JS parity proof aligned with the repaired GCD corpus or cache shape.
- .github/workflows/slow_tests.yml (MODIFY IF NEEDED) -- only if the nightly selector itself needs a narrow scheduling/grouping repair; do not mask failures or skip GCD evidence.
- reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-22 tracker sync note for wave `nightly-gcd-budget-repair-2026-06-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Ground the failure with the GitHub Actions run evidence from Slow Tests (Nightly) run 27975618821 and the prior same-pattern failures on June 20 and June 21.
2. Reproduce the timeout shape locally with a bounded GCD probe before editing: zero-operand cases must be fast, while positive-positive GCD pairs are the budget pressure.
3. Repair the landed GCD gate so the evidence still proves structural Euclidean GCD through run_mu without host gcd/mod/divide/comparison/subtraction in the engine path.
4. Prefer reducing or partitioning redundant over-budget corpus evidence under the original GCD packet's budget stop condition over changing runtime code. Preserve at least zero/left-zero/right-zero and one positive-positive structural compute case.
5. Keep tests/ and mu/tests/ mirrors byte-identical for the touched GCD files unless a repo rule explicitly requires otherwise.
6. If the nightly workflow changes, keep l4_expensive evidence in nightly; do not deselect, xfail, skip, or move the GCD proof out of all scheduled coverage.
7. Run the configured evidence command, collect the L4 indicator artifact, and ensure host semantics and authority ratchets do not gain sites.

## Constraints

- Use the launcher and dispatcher path; do not hand-implement or hand-commit this wave.
- No runtime, substrate, seed, registry, projection seed, JS production, host semantic, or Stage 4 files may change.
- No new host primitives, no host-only GCD shortcut, no host mod/divide/comparison/subtraction inside the engine path, and no new host authority sites.
- Do not mask the failing tests with skip, xfail, marker removal, or broad deselection. Any corpus reduction must be justified by the original GCD packet's nightly-budget stop condition.
- Do not touch the active Stage 4 structuralization worktree or packet.
- If the repair needs a broader structural performance/runtime fix, stop and route a new L4_STRUCTURAL packet instead of sneaking runtime optimization into this test/CI wave.

## Stop conditions

- Stop done when the configured GCD nightly selector passes under --timeout=900, the host semantics ratchet has no increases, the host authority inventory has no unaccepted new sites, and the indicator artifact is collected.
- Halt as POLICY_BOUND if the only apparent fix is a host semantic shortcut or runtime semantic expansion.
- Halt as DEFECT if Python and JS GCD results diverge structurally or by content hash after the budget repair.
- Halt as CI_MASKING if the fix removes scheduled GCD evidence rather than making it budget-valid.
- Do not commit without a pipeline-produced handoff/receipt and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_structural_numbers_gcd.py mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`
- Slow-kernel guard-tests (`run_mu`, `node`) carry an in-function `# SPEED_OK: <reason>` annotation so they stay out of the green-gate speed lane.

## Acceptance criteria

- The GCD and GCD JS parity tests pass through the same xdist/worksteal selector shape used by nightly, with --timeout=900.
- The repaired corpus or grouping still proves structural GCD over zero operands and at least one positive-positive Euclidean compute case.
- Python run_mu and JS bootstrap_core remain content-addressed-equal for every parity corpus pair retained by the gate.
- tests/ and mu/tests/ copies of touched GCD files remain byte-identical.
- No runtime, substrate, seed, registry, JS core, production Mu semantic, or Stage 4 file appears in the diff.
- Host-semantics and host-authority ratchets report no unaccepted new sites.
- reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `nightly-gcd-budget-repair-2026-06-22`.
- Governing packet: this file, `reports/control_plane/nightly-gcd-budget-repair-2026-06-22_2026-06-22.md`.
- TASKS.md authority: the 2026-06-22 tracker sync note for wave `nightly-gcd-budget-repair-2026-06-22` is canonical for this packet's L4 fields.
- Authorization: Founder reported the nightly failure on 2026-06-22 during the active Stage 4 session. The repair is separate from Stage 4 and must run in a dedicated pipeline lane.

FOUNDER_OVERRIDE:nightly-gcd-budget-repair-2026-06-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `nightly-gcd-budget-repair-2026-06-22`
- Active packet: `reports/control_plane/nightly-gcd-budget-repair-2026-06-22_2026-06-22.md`
- Indicator artifact: `reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_structural_numbers_gcd.py`
  - `mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`
  - `reports/control_plane/nightly-gcd-budget-repair-2026-06-22_2026-06-22.md`
  - `reports/control_plane/nightly-gcd-budget-repair-2026-06-22_wave_config.json`
  - `reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id nightly-gcd-budget-repair-2026-06-22 --output reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_structural_numbers_gcd.py mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/nightly-gcd-budget-repair-2026-06-22_2026-06-22.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: nightly-gcd-budget-repair-2026-06-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `nightly-gcd-budget-repair-2026-06-22`
- Active packet: `reports/control_plane/nightly-gcd-budget-repair-2026-06-22_2026-06-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2e85b0e49a38f469ae731e4855d1d2f0cdfcde751c34e55aa18b2e6c7dd34fd9`
- Indicator artifact: `reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_structural_numbers_gcd.py mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/nightly-gcd-budget-repair-2026-06-22_2026-06-22.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_structural_numbers_gcd.py`
  - `mu/tests/l4_gates/test_structural_numbers_gcd_js_parity.py`
  - `reports/control_plane/nightly-gcd-budget-repair-2026-06-22_2026-06-22.md`
  - `reports/control_plane/nightly-gcd-budget-repair-2026-06-22_wave_config.json`
  - `reports/l4_wave_indicators/nightly-gcd-budget-repair-2026-06-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
