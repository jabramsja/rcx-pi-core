# N3 Max Steps Structural Fuel Production Lock 2026-05-14

Date: 2026-05-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-max-steps-structural-fuel-production-lock-2026-05-14
Class: L4_STRUCTURAL
Category: /mu structural host-debt reduction
Target gate: G8
Phase-A-Lock: LOCKED
Governing packet: reports/control_plane/n3-max-steps-structural-fuel-production-lock-2026-05-14_2026-05-17.md

FOUNDER_OVERRIDE:n3-max-steps-structural-fuel-production-lock-2026-05-14

## Purpose

Route the next N3 /mu structural wave through the pipeline. The target is the
remaining `max_steps` / fuel normalization surface at the engine boundary. This
wave must narrow host semantics toward explicit structural fuel data or return
NO-GO with direct evidence if the current behavior is an intentional bootstrap
resource primitive that cannot be narrowed in this slice.

The implementation must not make Python or JavaScript smarter. It must remove,
narrow, or justify host fallback behavior; any retained host cap must be framed
as a resource guard, not Mu semantic authority.

## Current Code Truth

- Python `run_trace` currently normalizes host values before execution:
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:705-720` documents
  "max_steps parity policy: normalize-fallback", falls back non-numeric,
  bool, NaN, Inf, and negative values to `100`, floors finite numbers via
  `int(max_steps)`, and clamps values above `10000`.
- JavaScript mirrors that fallback policy:
  `mu/host/js/engine/pipeline.js:243-250` documents "max_steps parity policy:
  normalize-fallback", uses `reqInput.max_steps ?? 100`, rejects non-number,
  NaN, and Inf by replacing them with `100`, floors via `Math.floor`, falls
  negative values back to `100`, and clamps above `MAX_BOUNDARY_TRACE_STEPS`.
- Mu already carries a default structural budget for the standard engine entry:
  `mu/programs/rcx_engine.v1.json:31-57` emits a `run_trace` boundary request
  with `input.max_steps: 100` and `_config.max_steps: 100`.
- Mu also carries custom budget data through the configured entry:
  `mu/programs/rcx_engine.v1.json:60-89` copies `_run_engine.max_steps` into
  both `_boundary_request.input.max_steps` and `_config.max_steps`.
- Current L4 tests lock the fallback behavior, not just parity:
  `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py:521-538`
  expects Python string `max_steps` to normalize instead of erroring;
  `:540-557` expects Python float `1.5` to floor; `:609-664` expects the same
  behavior in JavaScript; `:666-758` expects Python/JS NaN and Inf to
  normalize to `100`.
- The public JSON API already has stricter boundary tests:
  `mu/tests/parity/test_js_parity_automated.py:1856-1895` expects over-cap,
  non-integer, and negative `maxSteps` values to fail closed with
  `api.bad_request`. Phase B must account for this split before changing
  internal boundary behavior.

## Doctrine Grounding

- `mu/docs/core/BootstrapPrimitives.v0.md:71-76` classifies `max_steps` as an
  iteration / clock primitive and says it provides the termination clock.
- `mu/docs/core/BootstrapPrimitives.v0.md:231-242` prohibits semantic branching,
  arithmetic on data, type-specific logic, and control-flow choices in host code;
  those must be projections.
- `mu/docs/core/L4MicroAbi.v0.md:55-70` defines `rcx_step` input as structural
  state with `fuel: int`, fail-closed invalid input, and explicit fuel
  decrement/exhaustion.
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:193-196`
  names this wave and its goal: move remaining `max_steps` / fuel control toward
  structural budget data without changing program meaning, proved by Python/JS
  parity, exhaustion/fuel tests, and no host oracle.

## Scope

Governing packet:
- `reports/control_plane/n3-max-steps-structural-fuel-production-lock-2026-05-14_2026-05-17.md`

Candidate Phase B implementation scope:
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
- `mu/host/js/engine/pipeline.js`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
- focused Python/JS parity or engine tests that already cover boundary fuel
  behavior, only if Phase B names the exact tests before edits
- `TASKS.md`, only for the same-wave L4_STRUCTURAL tracker note
- `reports/l4_wave_indicators/n3-max-steps-structural-fuel-production-lock-2026-05-14.json`
- this packet
- generated same-wave deferred non-blocker only if the pipeline produces one

No seed JSON, projection loader, scheduler, Stage0, registry, D010/binary image,
Claude, or unrelated pipeline-control files are in scope unless a reproduced
same-wave pipeline failure names an exact mechanical root fix.

## Work Items

1. Re-ground before edits by reading the founder bootstrap, `TASKS.md`,
   `STATUS.md`, this packet, the N3 autonomous host-debt plan, the cited core
   docs, and the current Python/JavaScript `run_trace` boundary code.

2. Decide whether the current normalize-fallback behavior is reducible host
   semantics. The decision must cite the exact code and test lines above. Do not
   treat current tests as doctrine; tests that enforce dirty host fallback must
   be revised if the correct structural contract is fail-closed explicit fuel.

3. If GO, narrow the `run_trace` boundary in both substrates so explicit
   `max_steps` / fuel values are structural integer budget data. The default
   `100` may remain only when the key is absent and Mu has not supplied a budget;
   non-integer, non-numeric, bool, NaN, Inf, and negative explicit values must
   fail closed with a typed boundary error instead of silently becoming `100`,
   unless Phase B proves a smaller correct contract with file:line evidence.

4. Preserve a hard upper resource cap as a bootstrap safety guard only if it is
   identical across substrates and tested as a host resource limit. A cap must
   not become Mu semantic branching or a hidden host oracle.

5. Update focused tests so they prove the chosen structural fuel contract:
   missing budget default behavior, explicit integer acceptance, explicit bad
   value fail-closed behavior, over-cap behavior, fuel exhaustion behavior, and
   Python/JS parity. Remove or rewrite fallback-locking tests that no longer
   match the contract.

6. Add a same-wave `TASKS.md` tracker note and collect the same-wave indicator
   artifact before commit handoff. The tracker must bind this as
   `Class: L4_STRUCTURAL`, include host-semantics and authority ratchet evidence,
   name the touched runtime/test files, and include the same-wave
   `FOUNDER_OVERRIDE`.

7. If the pipeline fails, diagnose with command output or file:line evidence.
   Include a same-wave mechanical root fix if it is within scope; otherwise
   route a precise follow-up automation packet and stop.

## Constraints

- Do not add host-only semantics, lambdas, JS arrow adapter theater, dynamic
  callable hiding, optional overload/sentinel tricks, detector evasion, or new
  bootstrap primitives.
- Do not make Python or JavaScript infer program meaning from `max_steps`.
- Do not widen `max_steps` work into scheduler behavior, seed-image loading,
  projection registries, Stage0, D010/binary images, or docs-only closure.
- Do not weaken first-match-wins, projection order, structural fuel exhaustion,
  or fail-closed boundary behavior to make tests pass.
- Do not update ratchet baselines as proof. Any host-authority split must be
  exact, same-wave, and detector-visible.
- Do not claim this wave eliminates the `max_steps` primitive, closes N3,
  completes L4, or proves meta-circular completion. This is one bounded
  reduction step toward a narrower bootstrap.

## Stop Conditions

- Stop as NO-GO if current code truth proves the fallback behavior is required
  by documented Mu semantics rather than host convenience.
- Stop as NO-GO if Python and JavaScript cannot enforce the same explicit fuel
  contract without new host interpretation.
- Stop if the only possible implementation would move Mu semantic authority into
  host code or add a new host oracle.
- Stop if preserving compatibility requires keeping explicit bad values as
  silent fallback without a separately documented bootstrap-boundary decision.
- Stop if host-semantics or host-authority ratchets increase without an exact,
  reviewed structural split.
- Stop before closeout if `TASKS.md`, the L4 indicator artifact, focused tests,
  and contract enforcement are not detector-visible for this same wave.

## Required Validation

Phase B must select focused validation from current code truth, and the final
closeout must include exact commands and results. Minimum required checks:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py --tb=short
```

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short
```

```bash
node mu/host/js/eval_step.js
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-max-steps-structural-fuel-production-lock-2026-05-14 --output reports/l4_wave_indicators/n3-max-steps-structural-fuel-production-lock-2026-05-14.json
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-max-steps-structural-fuel-production-lock-2026-05-14
```

## Acceptance Criteria

- Phase B either implements a real narrowing of explicit `max_steps` handling or
  returns NO-GO with the smallest next prerequisite and direct file:line
  evidence.
- Explicit bad `max_steps` / fuel inputs no longer silently become `100` unless
  Phase B proves that retaining one specific fallback is a documented resource
  boundary rather than host semantic policy.
- Mu-provided integer budgets and the default engine budget in
  `mu/programs/rcx_engine.v1.json` continue to work.
- Python and JavaScript behavior remains parity-preserving and fail-closed.
- Exhaustion/fuel tests prove structural budget behavior rather than host
  fallback behavior.
- Host-semantics and host-authority ratchets do not regress.
- Same-wave `TASKS.md`, indicator, validation evidence, and proof limits are
  present before commit handoff.

## Grounding / Authorization

`[NEXT-CODEX-POST-REDTEAM]` remains the active structural reduction lane. The
N3 autonomous host-debt reduction plan names this exact wave at
`reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:193-196`.

Required same-wave authorization:

FOUNDER_OVERRIDE:n3-max-steps-structural-fuel-production-lock-2026-05-14

## Required Human-Facing Footer

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-max-steps-structural-fuel-production-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-max-steps-structural-fuel-production-lock-2026-05-14_2026-05-17.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-max-steps-structural-fuel-production-lock-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/engine/pipeline.js`
  - `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `reports/control_plane/n3-max-steps-structural-fuel-production-lock-2026-05-14_2026-05-17.md`
  - `reports/l4_wave_indicators/n3-max-steps-structural-fuel-production-lock-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
