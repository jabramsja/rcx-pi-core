# N3-Ci-Runtime-Mu-Algorithm-Hotpath-2026-05-27

Date: 2026-05-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-ci-runtime-mu-algorithm-hotpath-2026-05-27
Phase-A-Lock: LOCKED
Purpose: Bounded Phase A plan for CI/green-gate runtime regression proof and first implementation target selection.

## Scope

This Phase A packet selects the first implementation wave as a production structural Mu runtime hot-path reduction, not a test evidence-reuse wave and not CI workflow deduplication.

Files and directories in implementation scope:

- `mu/host/python/rcx_pi/selfhost/mu_type.py` -- bounded investigation and possible reduction of duplicate validation in control-hash/public-hash paths cited by the supervisor evidence.
- `mu/host/python/rcx_pi/selfhost/step_mu.py` -- bounded investigation and possible reduction of repeated algorithm-runtime continuation hashing/validation cited by the supervisor evidence.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py` -- bounded investigation of `run_algorithm` boundary-effect dispatch/service hot paths cited by the supervisor evidence; edit only if needed to preserve structural runtime semantics.
- `mu/host/js/` -- parity mirror scope for any semantic or validation-boundary change made under the Python runtime files above; exact JS file set must be locked before Phase B implementation.
- `tests/l4_gates/test_engine_transition_gate.py` and `tests/l4_gates/engine_evidence_cache.py` -- evidence-only scope for focused before/after timing and unchanged observer-parity strength; do not weaken assertions, skip behavior, or fixture coverage.
- `mu/tests/parity/` and `mu/tests/l4_gates/` -- focused parity/L4 regression additions only when required by a production runtime edit.

Files and directories in packet/documentation scope:

- `reports/control_plane/n3-ci-runtime-mu-algorithm-hotpath-2026-05-27_2026-05-27.md` only for this Phase A rewrite.
- `TASKS.md` only for detector-visible same-wave tracker sync required by strict staged L4 validation for `n3-ci-runtime-mu-algorithm-hotpath-2026-05-27`.
- `scripts/green_gate.sh` and `mu/docs/agents/AgentRunbook.v0.md` are DOC_ACCURACY-adjacent only; do not touch them unless a later locked packet explicitly includes doc/control-plane cleanup.

## Work items

1. Re-open only the cited evidence needed for causality before Phase B: the current packet, the targeted `[NEXT-CODEX-POST-REDTEAM]` `TASKS.md` authorization block, and the supervisor-cited runtime/test/CI lines. Do not inspect unrelated dirty files, broad diffs, or unrelated executor/test changes.
2. Treat the first implementation target as L4_STRUCTURAL production runtime work: reduce redundant Mu validation/hash work in the algorithm-runtime hot path only if the change preserves the same Mu acceptance boundary and can be mirrored or proven non-semantic across Python and JavaScript.
3. Preserve test evidence strength. The existing Boot1/trampoline observer-parity path remains evidence, not a target for shortcutting; any test edit must make the proof more explicit or more fail-closed, not faster by weakening coverage.
4. Keep CI workflow duplication out of the first implementation wave. The duplicate `scripts/green_gate.sh python-only` invocation in CI/green-gate is a separate risk decision unless the implementation packet proves dedupe safety without reducing the seven-check GitHub surface.
5. Record same-session before/after performance evidence for the focused hot path. Treat timings as reproduction evidence, not semantic acceptance proof, and pair them with structural/parity tests.
6. If the runtime fix touches production semantics, classify the implementation as `L4_STRUCTURAL` and require Python/JS parity evidence, host-semantics ratchet, host-authority inventory ratchet, focused L4 evidence, and no ratchet baseline edit.

## Constraints

- Do not use `run_review.py`.
- Do not change `tools/executors/executor_config.json` or `agent_review_enabled=false`.
- Do not remove, rename, skip, xfail, deselect, timeout-mask, or weaken tests to improve runtime.
- Preserve the full seven-check GitHub surface: `test`, `green-gate`, `orbit-dot`, `orbit-provenance`, `engine-run-schema`, `orbit-svg`, and `orbit-index`.
- Do not change branch-protection behavior or check-surface definitions.
- Do not add host-only semantics, substrate-specific shortcuts, host exception tables, or smarter host interpretation that moves Mu authority into Python or JavaScript helpers.
- Do not edit ratchet baselines to claim progress.
- Do not implement CI workflow deduplication in this wave.
- Do not touch Claude files or unrelated docs/control-plane surfaces.
- Do not relist already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.

## Stop conditions

Stop before implementation or revert the candidate change if any of these conditions occurs:

- The proposed speedup requires weakening, skipping, xfail-ing, deselecting, or timeout-masking existing evidence.
- The proposed speedup adds host-only semantics or changes the accepted Mu value boundary without a mirrored Python/JS structural rule.
- The exact JS parity mirror cannot be identified for a semantic Python runtime change.
- Host-semantics ratchet or host-authority inventory would increase, or the fix requires a baseline edit to pass.
- The candidate fix relies on CI workflow dedupe, branch-protection/check-surface changes, or `scripts/green_gate.sh` invocation removal.
- The scoped hot-path measurement does not improve in a same-session comparison, or the improvement cannot be tied to a structural/runtime change without semantic risk.
- The required same-wave TASKS tracker entry or packet-local authorization cannot be made detector-visible before commit automation.

## Acceptance criteria

- The packet contains concrete bounded scope, work items, constraints, stop conditions, acceptance criteria, and grounding/authorization sections.
- Phase B, if dispatched, targets production structural Mu runtime hot paths first; test evidence reuse and CI workflow dedupe remain excluded unless a later packet authorizes them.
- Implementation acceptance requires focused before/after timing for the cited Boot1/algorithm-runtime path and must show a same-session reduction without weakening evidence.
- Focused L4 evidence remains green, including the Boot1/trampoline observer-parity path that currently exercises `cached_python_pipeline` and production `run_engine_pipeline`.
- Python/JS parity evidence is present for any production semantic or validation-boundary change, including `node mu/host/js/eval_step.js` or a narrower justified parity command plus focused pytest coverage.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` passes with no unapproved increases and no baseline edit.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` passes with no unapproved authority-site increase.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-ci-runtime-mu-algorithm-hotpath-2026-05-27 --wave-class L4_STRUCTURAL` passes before any production runtime commit.
- The final implementation packet or tracker note preserves the full seven-check GitHub surface and explicitly states that timings are reproduction evidence, not proof by themselves.

## Grounding / Authorization

Targeted `TASKS.md` grounding:

- `TASKS.md:636-640` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked/open and says remaining structural reduction requires separate bounded packets while already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and seed-registration work must not be relisted as unresolved.
- `TASKS.md:644` authorizes autonomous dispatcher/pipeline progression for the founder-ordered wave queue, requires every wave to have a control-plane packet plus `TASKS.md` tracker entry, and hard-stops `/mu` structural implementation until bounded routing exists.
- Targeted lookup for `n3-ci-runtime-mu-algorithm-hotpath-2026-05-27` in `TASKS.md` returned no same-wave hit before this tracker recovery, matching the bridge finding.
- This recovery adds detector-visible same-wave `TASKS.md` tracker authority for `n3-ci-runtime-mu-algorithm-hotpath-2026-05-27`, including Class, Packet, evidence command, evidence delta, progress proofs, `FOUNDER_OVERRIDE`, indicator artifact, and invariant metadata for strict staged L4 validation.

Packet-local same-wave authorization:

FOUNDER_OVERRIDE:n3-ci-runtime-mu-algorithm-hotpath-2026-05-27

Source authorization:

- `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`
- Governing packet: `reports/control_plane/n3-ci-runtime-mu-algorithm-hotpath-2026-05-27_2026-05-27.md`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-ci-runtime-mu-algorithm-hotpath-2026-05-27`
- Active packet: `reports/control_plane/n3-ci-runtime-mu-algorithm-hotpath-2026-05-27_2026-05-27.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-ci-runtime-mu-algorithm-hotpath-2026-05-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
  - `mu/host/python/rcx_pi/selfhost/mu_type.py`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tests/parity/test_cross_substrate_constants.py`
  - `mu/tests/structural/test_engine_pipeline_discipline.py`
  - `reports/control_plane/n3-ci-runtime-mu-algorithm-hotpath-2026-05-27_2026-05-27.md`
  - `reports/deferred/non_blocking/n3-ci-runtime-mu-algorithm-hotpath-2026-05-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-ci-runtime-mu-algorithm-hotpath-2026-05-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
