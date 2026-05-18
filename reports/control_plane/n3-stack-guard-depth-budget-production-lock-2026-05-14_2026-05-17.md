# N3-Stack-Guard-Depth-Budget-Production-Lock-2026-05-14 2026-05-17

Date: 2026-05-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-stack-guard-depth-budget-production-lock-2026-05-14
Class: L4_ENABLER
Category: /mu structural host-debt reduction plan
Phase-A-Lock: LOCKED
Decision: NO-GO
FOUNDER_OVERRIDE:n3-stack-guard-depth-budget-production-lock-2026-05-14

Purpose: produce the bounded Phase A GO/NO-GO packet for one production
boundary: whether stack_guard validation can narrow from integer host
`_depth` / `MAX_MU_DEPTH` bookkeeping to structural Mu depth-budget data in
both Python and JavaScript while preserving crash protection as a host safety
boundary.

## Decision Summary

Phase A is **NO-GO** for production implementation in this wave.

Smallest blocker: the allowed governing evidence does not prove structural
depth-budget production validation in both substrates. It proves the opposite:
D009 is research-only Python analog evidence, production stack_guard remains
unchanged, and productionization still requires cross-substrate JavaScript
implementation, memoization parity, cycle-detection parity, sibling budget
semantics reconciliation, and performance profiling.

The stop condition therefore fires before source/test implementation. This
packet does not authorize edits to Python Mu type code, JavaScript Mu type code,
or D009/P7 tests. A later bounded packet may reopen the boundary only after it
can cite current file:line evidence proving the missing productionization
prerequisites can be satisfied within a smaller scoped write set.

Exact runtime/test implementation write set for this NO-GO: none. The Phase A
packet edit and later same-wave control-plane package-refresh files are named in
Scope.

## Scope

The Phase A NO-GO packet edit was limited to this governing packet:

- `reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md`

The later same-wave commit/package refresh scope is limited to these
control-plane files:

- `TASKS.md`
- `reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md`
- `reports/deferred/non_blocking/n3-stack-guard-depth-budget-production-lock-2026-05-14_bridge_nonblockers.md`
- `reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`

Allowed Phase A evidence sources:

- `TASKS.md:542-550`
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- `STATUS.md`
- `reports/README.md`
- `mu/docs/core/L4ExitChecklist.v0.md`
- `mu/docs/core/BootstrapPrimitives.v0.md`
- `mu/docs/core/L4MicroAbi.v0.md`

Explicitly out of scope for this packet:

- Runtime implementation changes.
- Test implementation changes.
- Source files, tests, archive packets, ratchet baselines, dispatcher records,
  Claude-related files, and closeout surfaces.
- Any `TASKS.md`, indicator, or deferred packet edit outside the same-wave
  control-plane package-refresh files listed above.
- Any claim that stack_guard is eliminated, L4 is complete, or production depth
  validation is already structural.

- `reports/deferred/non_blocking/n3-stack-guard-depth-budget-production-lock-2026-05-14_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Grounding / Authorization

`TASKS.md:542-550` is the live queue authority for this packet:

- `TASKS.md:542` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked and
  founder-authorized.
- `TASKS.md:545` keeps the current phase open for remaining structural
  reduction through separate bounded packets.
- `TASKS.md:546` records landed engine-state/scheduler work and forbids
  relisting those seed, fixture, structural-test, scheduler-parity, or
  seed-registration items as unresolved.
- `TASKS.md:550` carries the founder-ordered wave queue directive, requires
  every wave to have a control-plane packet plus a `TASKS.md` tracker entry, and
  provides source authorization through
  `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.

`reports/README.md:7` defines `reports/control_plane/` as tracked
founder-facing control-plane packets referenced by `TASKS.md`.
`reports/README.md:23-25` says routed bounded work is tracked from the routed
packet and `TASKS.md`.

The N3 queue controller authorizes this candidate as one bounded successor:
`reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:198-201`
names `n3-stack-guard-depth-budget-production-lock-2026-05-14`, with the goal
to evaluate production depth budget as structural input while preserving crash
protection as a host safety boundary and the proof requirement of
hostile-depth negative controls in both substrates.

Same-wave authority is carried directly in this packet because direct
reproduction of
`rg -n "n3-stack-guard-depth-budget-production-lock-2026-05-14" TASKS.md`
returned exit code `1` with no matches. This is detector-visible authority for
the current `L4_ENABLER` packet only:

FOUNDER_OVERRIDE:n3-stack-guard-depth-budget-production-lock-2026-05-14

## Evidence Findings

1. Current L4 state does not permit broad completion claims.
   `STATUS.md:52` says full L4 completion remains in SINK while bounded
   reduction work is active. `STATUS.md:56` still lists `stack_guard` as one of
   four bootstrap primitives.

2. Current stack_guard is a host safety primitive, not semantic Mu authority.
   `mu/docs/core/BootstrapPrimitives.v0.md:73-78` classifies `stack_guard` as a
   host resource limit and says it must remain because removing it would allow
   crash-by-depth attacks. `mu/docs/core/BootstrapPrimitives.v0.md:157-181`
   describes `MAX_MU_DEPTH` validation in `is_mu()` and says the guard rejects
   structures before they can overflow traversal while making no semantic
   nesting decision.

3. The current production boundary is explicitly depth-only.
   `mu/docs/core/L4ExitChecklist.v0.md:96-111` defines G4 as `stack_guard` being
   a single integer threshold checked during `is_mu()` validation, with the
   reduction path to express depth as a Mu counter still marked UNPROVEN.
   `mu/docs/core/L4MicroAbi.v0.md:62-74` requires fail-closed valid Mu
   input/output and maps `MAX_MU_DEPTH` to G4.

4. D009 is insufficient for production GO.
   `mu/docs/core/L4ExitChecklist.v0.md:187` classifies `stack_guard` as
   REDUCIBLE_WITH a depth parameter, but says D009 is research-only Python
   analog evidence, production stack_guard is unchanged, and memoization /
   cycle-detection parity was deferred. `mu/docs/core/L4ExitChecklist.v0.md:205`
   says research analog evidence is sufficient for classification gates only,
   while production reduction claims require separate productionization gates.

5. The missing production prerequisites are exact and blocking.
   `mu/docs/core/L4ExitChecklist.v0.md:209-216` says any production primitive
   reduction claim is blocked unless primitive-specific prerequisites are met.
   For `stack_guard`, line 215 requires memoization parity, cycle-detection
   parity, cross-substrate JavaScript implementation, node-count vs per-level
   budget semantics reconciliation, and performance profiling.

6. Python/JavaScript parity is mandatory, not optional.
   `STATUS.md:62-67` says any Python projection-behavior change must be
   mirrored in JavaScript and parity violations break L3.
   `mu/docs/core/BootstrapPrimitives.v0.md:352-364` maps the bootstrap
   primitives across Python and JavaScript, including current `stack_guard`
   constants, but does not prove structural depth-budget data in both
   production substrates.

7. Hash/cache and validation paths remain part of the proof surface.
   `mu/docs/core/BootstrapPrimitives.v0.md:116-120` records `mu_equal`
   demotion through `mu_hash_cached`, with production code using cached hashes
   directly. `mu/docs/core/L4MicroAbi.v0.md:87-92` defines fixed-point stopping
   through hash-equal consecutive states. Any future depth-budget production
   change must prove hash/cache paths cannot bypass Mu validation.

8. Behavior-only tests are not architectural proof.
   `mu/docs/core/L4ExitChecklist.v0.md:199-205` says G8 does not imply full L4
   completion or production primitive reduction, and line 205 separates
   research analog evidence from production claims.
   `mu/docs/core/L4MicroAbi.v0.md:157-165` repeats that reduction statuses are
   classification statuses, not production-completion claims.

## Work Items

1. Lock this packet as the bounded Phase A record for the stack_guard
   depth-budget production boundary.
2. Preserve the `[NEXT-CODEX-POST-REDTEAM]` current-phase rule: remaining
   structural reduction requires separate bounded packets, every wave needs a
   control-plane packet plus `TASKS.md` tracker entry, and already-landed
   engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and
   seed-registration work must not be relisted.
3. Attach same-wave detector-visible authority with
   `FOUNDER_OVERRIDE:n3-stack-guard-depth-budget-production-lock-2026-05-14`.
4. Decide only this boundary: whether production stack_guard validation can use
   structural Mu depth-budget data in Python and JavaScript without weakening
   crash protection.
5. Record NO-GO because the governing evidence does not satisfy the two-substrate
   production readiness prerequisite.
6. Preserve the future Phase B obligations below without authorizing source or
   test edits in this wave.

## Future Phase B Contract If Reopened

A later packet may authorize implementation only if it first produces current
file:line evidence satisfying the blocker above. If that later packet reaches
GO, the default candidate write set is limited to:

- `mu/host/python/rcx_pi/mu_type.py`
- `mu/host/python/rcx_pi/selfhost/mu_type.py`
- `mu/host/js/core/types.js`
- `mu/tests/l4_gates/test_d009_production_depth_gate.py`
- `mu/tests/l4_gates/test_p7_mutation_elimination_gate.py`
- `mu/tests/l4_gates/test_p7w2_builtin_reduction_gate.py`
- `mu/tests/l4_gates/test_p7w3_boundary_reclassification_gate.py`
- `mu/tests/l4_gates/test_p7w4_structural_reduction_gate.py`
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`

The later packet must shrink that set if file:line evidence proves a smaller
set is sufficient, and it must stop and split if required edits exceed these Mu
type/depth-budget and focused D009/P7 surfaces.

Required parity obligations for any reopened GO:

- Python and JavaScript accept the same valid Mu values.
- Python and JavaScript reject the same invalid Mu / host-artifact classes.
- Both substrates fail closed on hostile depth before host recursion, process
  crash, or validator bypass.
- Hash/cache/fixed-point paths cannot bypass production Mu validation.
- Crash protection remains a host safety boundary; Mu depth-budget data may
  narrow validation only if it does not become new host semantics.

Required hostile-depth negative controls for any reopened GO:

- Deeply nested valid Mu accepted up to the structural budget.
- Over-budget nested Mu rejected before host recursion.
- Hostile or trapping objects/arrays rejected at depth boundaries.
- Budget exhaustion occurs before recursion overflow or process crash.
- Sibling-boundary behavior reconciles node-count research semantics with
  current per-level production depth semantics.

Required ratchet and test expectations for any reopened GO:

- L4 execution contract.
- Host-semantics ratchet.
- Host-authority inventory ratchet.
- Focused D009/P7 gate coverage.
- Python/JavaScript parity coverage.
- Anti-theater coverage that invokes production JS paths rather than inline
  helper simulations, consistent with
  `mu/docs/core/L4ExitChecklist.v0.md:236-238`.

## Constraints

- This is a packet-only Phase A repair.
- Do not implement the stack_guard/depth-budget production change in this wave.
- Do not edit runtime files, tests, archive packets, source files, ratchet
  baselines, dispatcher records, Claude-related files, or closeout surfaces.
- Same-wave `TASKS.md`, indicator, and generated deferred-packet edits are
  allowed only for the four-file control-plane package-refresh scope listed in
  this packet.
- Do not add host-only semantics, make Python or JavaScript "smarter" as a
  substrate workaround, or broaden the Mu object model.
- Do not claim stack_guard elimination, full L4 completion, bootstrap
  elimination, or semantic proof beyond the file:line evidence above.
- Do not widen into Stage0, lowering, scheduler, registry, seed, engine-state,
  docs cleanup, Claude-related files, or baseline-only cleanup.
- Do not treat behavior-only tests as proof of architectural direction.

## Stop Conditions

- Stop with NO-GO if file:line evidence cannot prove structural depth-budget
  production validation in both Python and JavaScript.
- Stop with NO-GO if the candidate change relies on new host semantics rather
  than narrowing an existing host safety boundary.
- Stop with NO-GO if Python and JavaScript cannot be parity-aligned for valid
  Mu, invalid Mu, hostile-depth, and hash/cache validation paths.
- Stop with NO-GO if hostile-depth negative controls cannot prove fail-closed
  budget exhaustion before host recursion, process crash, or validator bypass.
- Stop before implementation if commit/pipeline automation still needs a
  `TASKS.md` tracker sync entry beyond this packet's same-wave override.
- Stop and split the wave if required edits exceed the scoped Mu type /
  depth-budget and focused D009/P7 surfaces.
- Stop and remove any pending item or acceptance criterion if file:line evidence
  proves that item is already implemented in current code.

## Acceptance Criteria

- This packet contains explicit Scope, Work Items, Constraints, Stop Conditions,
  Acceptance Criteria, and Grounding / Authorization sections.
- This packet contains same-wave authority via
  `FOUNDER_OVERRIDE:n3-stack-guard-depth-budget-production-lock-2026-05-14`.
- Phase A records a bounded NO-GO with file:line evidence, smallest missing
  prerequisite, future candidate write set, parity obligations, hostile-depth
  negative controls, ratchet expectations, proof limits, and stop conditions.
- No underlying source/test implementation starts from this packet.
- No already-landed engine-state/scheduler seed, fixture, structural-test,
  scheduler-parity, or seed-registration work is listed as unresolved.

## Phase B Packet-Only Implementation Record

Current package file scope:

- `TASKS.md`
- `reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md`
- `reports/deferred/non_blocking/n3-stack-guard-depth-budget-production-lock-2026-05-14_bridge_nonblockers.md`
- `reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`

Validation command policy:

- No Phase B-local validation command is listed as required by the locked plan
  for this packet-only repair.
- Startup, preflight, attestation, dispatcher, commit, push, PR, merge, and
  closeout commands are executor-owned context and were not run from this
  implementer.
- Runtime tests are intentionally not run because this wave does not authorize
  runtime or test changes.

Invariant tuple:

- Debt before/after: unchanged by packet-only NO-GO.
- Host semantics before/after: unchanged; no Python or JavaScript source edits.
- Runtime/substrate delta: none.

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-stack-guard-depth-budget-production-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md`
  - `reports/deferred/non_blocking/n3-stack-guard-depth-budget-production-lock-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-stack-guard-depth-budget-production-lock-2026-05-14`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-stack-guard-depth-budget-production-lock-2026-05-14_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-stack-guard-depth-budget-production-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `81b8cbda57b2da80563c5eb523608752f6700002062034be8ec508459480a8d9`
- Indicator artifact: `reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-stack-guard-depth-budget-production-lock-2026-05-14 --output reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-stack-guard-depth-budget-production-lock-2026-05-14_2026-05-17.md`
  - `reports/deferred/non_blocking/n3-stack-guard-depth-budget-production-lock-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-stack-guard-depth-budget-production-lock-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
