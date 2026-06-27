<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-06-27
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/l4_gates/test_fixpoint_meta_circular_foundation_gate.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest mu/tests/l4_gates/test_fixpoint_meta_circular_foundation_gate.py -v
-->

# Fixpoint Meta-Circular Evaluator For RCX (FixpointMetaCircularEvaluator.v0)

**Status:** REFERENCE - first bounded foundation contract for representing
evaluator fixed points and evaluator-as-data shapes as structural Mu data. This
v0 is not a host evaluator API, not a host recursion API, not a host scheduler
API, not a host coroutine API, not a host iterator API, not a host parser API,
and not an optimizer pass. It does not authorize production evaluator
semantics.

**Authority:** `TASKS.md` carries the 2026-06-27 tracker sync note for
`fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-payoff`.
The governing packet is
`reports/control_plane/fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-payoff_2026-06-27.md`.
The bridge-review `-pa` packet is a normalization surface only.

## Purpose

FixpointMetaCircularEvaluator records the first representation boundary for
the meta-circularity payoff: evaluators represented as Mu data, finite
self-application trace prefixes, fixed-point witness candidates, explicit
closure/stall boundaries, and explicit proof limits. This first step is
deliberately small. It defines the data shapes and falsifiable foundation
criteria that later waves must satisfy before any production evaluator,
fixed-point executor, self-application executor, scheduler, parser, optimizer,
or self-hosting closure can be claimed.

This document is a structural-data proposal, not an implementation plan for
host recursion, host callables, host closures, host coroutine frames, host
iterators, host scheduler queues, host parser dispatch, or optimization
passes. A meta-circular evaluator is represented here by open structural
obligations and finite trace prefixes, not by asking the host to call an
evaluator on itself.

## Representation Boundary

The v0 representation uses explicit Mu nodes and linked lists:

```text
evaluator_envelope ::= {"_fix_eval_envelope": {"evaluator": evaluator_ref,
                                               "program": Mu,
                                               "input": Mu,
                                               "environment": environment_ref,
                                               "budget": budget_window,
                                               "trace": self_application_trace,
                                               "proof_limits": proof_limit_list}}

evaluator_ref      ::= {"_fix_evaluator_ref": {"id": string,
                                               "body": Mu,
                                               "interface": evaluator_interface}}

evaluator_interface ::= {"_fix_eval_interface": {"input_shape": Mu,
                                                 "output_shape": Mu,
                                                 "step_relation": relation_ref}}

fixed_point_witness ::= {"_fix_witness": {"candidate": evaluator_ref,
                                          "unfolding": evaluator_envelope,
                                          "observed_state": Mu,
                                          "next_state": Mu,
                                          "relation": relation_ref,
                                          "status": witness_status,
                                          "obligations": obligation_list}}

witness_status      ::= {"_fix_status": "open"}
                     |  {"_fix_status": "stalled"}
                     |  {"_fix_status": "closure-candidate"}

self_application_trace ::= {"_fix_trace": null}
                         | {"_fix_trace": {"event": self_application_event,
                                           "rest": self_application_trace}}

self_application_event ::= {"_fix_event": {"phase": string,
                                           "evaluator_as_data": evaluator_ref,
                                           "input_envelope": evaluator_envelope_ref,
                                           "output_obligation": obligation_ref}}

closure_boundary   ::= {"_fix_boundary": {"state": Mu,
                                          "budget": budget_window,
                                          "stall": stall_boundary,
                                          "result": boundary_result,
                                          "proof_limits": proof_limit_list}}

stall_boundary     ::= {"_fix_stall_boundary": {"before_hash": string,
                                                "after_hash": string,
                                                "same_hash": boolean,
                                                "reason": string}}

boundary_result    ::= {"_fix_result": "open"}
                    |  {"_fix_result": "stalled"}
                    |  {"_fix_result": "budget-exhausted"}
                    |  {"_fix_result": "closure-candidate"}

budget_window      ::= {"_fix_budget": {"prefix": prefix_budget,
                                        "source": string,
                                        "finite": true}}

prefix_budget      ::= {"_fix_prefix_budget": null}
                    |  {"_fix_prefix_budget": {"event": string,
                                               "rest": prefix_budget}}

proof_limit_list   ::= {"_fix_limits": null}
                    |  {"_fix_limits": {"limit": proof_limit,
                                        "rest": proof_limit_list}}

proof_limit        ::= {"_fix_proof_limit": {"claim": string,
                                             "withheld": true,
                                             "reason": string}}
```

The linked shapes are intentional. They use ordinary Mu dictionaries, strings,
booleans, and `null`. They do not require host callables, host recursion
frames, host closures, host coroutine frames, host iterator objects, host
scheduler queues, host parser dispatch, host object identity, host arrays as
semantic authority, or optimization passes.

The `_fix_eval_envelope`, `_fix_evaluator_ref`, `_fix_witness`, `_fix_trace`,
`_fix_boundary`, `_fix_stall_boundary`, `_fix_budget`, and
`_fix_proof_limit` tags name the representation family only. They do not make
an evaluator run, do not execute a fixed point, do not execute
self-application, do not prove evaluator closure, and do not close
self-hosting by host authority. A v0 foundation record does not execute a
fixed point.

## Structural Discipline

A FixpointMetaCircularEvaluator datum is a candidate foundation record only
when these obligations are met:

1. An evaluator-as-data envelope carries an evaluator reference, program,
   input, environment reference, finite budget window, finite trace prefix, and
   proof-limit list as Mu data.
2. An evaluator reference carries the evaluator body as Mu data. It cannot
   carry a Python callable, JavaScript function, host closure, host class,
   host generator, host coroutine, host iterator, host parser callback, or
   optimizer callback.
3. A fixed-point witness names a candidate evaluator, one unfolded envelope,
   the observed state, the next state, the relation to be checked, a status,
   and later obligations. The witness is not itself a proof.
4. A self-application trace prefix is finite. Each event records the evaluator
   as data, the input envelope reference, and an output obligation. It does not
   run recursive self-application.
5. Closure and stall boundaries remain explicit. A stall boundary records
   before/after hashes and a structural reason; a closure candidate remains a
   candidate until later proof obligations are discharged.
6. Budget exhaustion is distinct from closure. A finite prefix budget can be
   exhausted without proving either evaluator closure or fixed-point closure.
7. Proof limits are first-class records. A withheld claim must name the claim
   and the reason it is outside this first slice.

These rules define representation obligations. They are not Python callable
semantics, JavaScript function semantics, not host recursion semantics, host
scheduler semantics, host parser semantics, or optimizer semantics.

## Later Proof Obligations

Evaluator fixed points and meta-circular closure are later implementation
obligations. A future Phase A must narrow a falsifiable slice before any
production evaluator, fixed-point executor, self-application executor,
closure verifier, scheduler, parser, projection, seed, substrate, parity, or
optimizer work is implemented.

Later waves must prove at least these obligations before claiming production
semantics:

1. **Evaluator step relation:** the evaluator body as Mu data defines a
   structural step relation without host callables, host recursion, host parser
   dispatch, or optimizer callbacks.
2. **Self-application relation:** passing an evaluator-as-data envelope through
   the evaluator is represented as structural trace events, not host recursive
   calls.
3. **Fixed-point witness validation:** a witness must show how the candidate
   and its unfolding relate by structural equality or a declared structural
   relation. The v0 witness shape only names this obligation.
4. **Closure/stall verification:** closure candidates, stalls, and exhausted
   budgets must be distinguishable as Mu boundary records.
5. **Budget/exhaustion discipline:** finite trace windows must fail closed when
   exhausted without converting exhaustion into a closure claim.
6. **Fail-closed malformed envelopes:** missing evaluator bodies, non-Mu
   bodies, unbounded trace tails, malformed budgets, missing proof limits, and
   host-only evaluator claims fail closed.
7. **Proof-limit preservation:** later work must not delete proof limits by
   replacing them with host execution shortcuts.

This v0 records those obligations only. It does not claim evaluator execution,
fixed-point execution, self-application execution, fixed-point witness
validation, meta-circular closure, optimization closure, or self-hosting
closure.

## Small Foundation Examples

The examples below use aliases so the shapes stay readable:

```text
EmptyTrace := {"_fix_trace": null}
EmptyLimits := {"_fix_limits": null}
OneEventBudget := {"_fix_budget": {"prefix": {"_fix_prefix_budget": {
                    "event": "one-self-application-observation",
                    "rest": {"_fix_prefix_budget": null}}},
                    "source": "foundation-example",
                    "finite": true}}
Limit(claim, reason) := {"_fix_proof_limit": {"claim": claim,
                                              "withheld": true,
                                              "reason": reason}}
```

### Evaluator-As-Data Envelope

```text
IdentityEvaluatorData := {"_fix_evaluator_ref": {
  "id": "identity-evaluator-data.v0",
  "body": {"projection": {"pattern": {"var": "x"}, "body": {"var": "x"}}},
  "interface": {"_fix_eval_interface": {
    "input_shape": {"var": "any-mu"},
    "output_shape": {"var": "any-mu"},
    "step_relation": "identity-step-obligation"}}}}

EnvelopeIdentityA := {"_fix_eval_envelope": {
  "evaluator": IdentityEvaluatorData,
  "program": {"program": "identity-example"},
  "input": {"value": "A"},
  "environment": "empty-structural-env",
  "budget": OneEventBudget,
  "trace": EmptyTrace,
  "proof_limits": {"_fix_limits": {
    "limit": Limit("production evaluator execution", "representation only"),
    "rest": EmptyLimits}}}}
```

Required proof facts: the evaluator is carried as Mu data; the body is not a
host callable; the envelope contains a finite budget and explicit proof limit.
This does not prove production evaluator execution.

### Self-Application Trace Prefix

```text
SelfApplyEvent0 := {"_fix_event": {
  "phase": "evaluator-as-data-observed",
  "evaluator_as_data": IdentityEvaluatorData,
  "input_envelope": "EnvelopeIdentityA",
  "output_obligation": "identity-output-not-executed"}}

TracePrefix1 := {"_fix_trace": {"event": SelfApplyEvent0,
                                "rest": EmptyTrace}}
```

Required proof facts: the prefix records one finite observation that an
evaluator-as-data envelope is the subject of self-application. The event is a
trace obligation, not a host recursive call and not self-application
execution.

### Fixed-Point Witness Candidate

```text
WitnessIdentityOpen := {"_fix_witness": {
  "candidate": IdentityEvaluatorData,
  "unfolding": EnvelopeIdentityA,
  "observed_state": {"state": "identity-before"},
  "next_state": {"state": "identity-after"},
  "relation": "same-shape-under-one-unfolding",
  "status": {"_fix_status": "open"},
  "obligations": {"_fix_obligations": {
    "head": "prove structural relation without host recursion",
    "tail": null}}}}
```

Required proof facts: the witness shape names a candidate, an unfolding, and a
relation. It remains open and does not prove a working fixed point.

### Closure And Stall Boundary

```text
StallBoundaryIdentity := {"_fix_boundary": {
  "state": {"state": "identity-after"},
  "budget": OneEventBudget,
  "stall": {"_fix_stall_boundary": {
    "before_hash": "h.identity.after",
    "after_hash": "h.identity.after",
    "same_hash": true,
    "reason": "same structural state observed"}},
  "result": {"_fix_result": "stalled"},
  "proof_limits": {"_fix_limits": {
    "limit": Limit("meta-circular closure", "stall is not closure"),
    "rest": EmptyLimits}}}}

BudgetBoundaryOpen := {"_fix_boundary": {
  "state": {"state": "identity-after"},
  "budget": OneEventBudget,
  "stall": {"_fix_stall_boundary": {
    "before_hash": "h.identity.before",
    "after_hash": "h.identity.after",
    "same_hash": false,
    "reason": "budget ended before closure evidence"}},
  "result": {"_fix_result": "budget-exhausted"},
  "proof_limits": {"_fix_limits": {
    "limit": Limit("fixed-point closure", "budget exhaustion is not closure"),
    "rest": EmptyLimits}}}}
```

Required proof facts: stall and budget exhaustion are separate boundary
records. Neither record proves evaluator closure, fixed-point closure, or
self-hosting closure.

## Explicit Proof Limits

This v0 does not prove or authorize:

- production evaluator semantics;
- a production evaluator, fixed-point executor, self-application executor,
  closure verifier, scheduler, parser, projection, seed, substrate, parity
  change, or optimizer;
- fixed-point execution, self-application execution, meta-circular closure,
  fixed-point closure, evaluator closure, optimization closure, or
  self-hosting closure;
- production proof that evaluator-as-data can run itself;
- changes to runtime, substrate, seed, registry, projection, JavaScript parity,
  pager/autoping, tmux, evaluator, parser, scheduler, or execution semantics
  files;
- host evaluator behavior, host recursion authority, host callable authority,
  host closure authority, host coroutine behavior, host iterator authority,
  host scheduler authority, host parser authority, host object identity, or
  host-only fixed-point semantics.

The only closure claimed by this wave is a docs-backed foundation boundary:
FixpointMetaCircularEvaluator can be described as structural Mu envelopes,
finite self-application trace prefixes, fixed-point witness candidates,
closure/stall boundary records, budget/exhaustion distinctions, and explicit
proof-limit records.

## Deferred Queue Boundaries

Coinduction remains separate completed structural foundation work. This wave
does not advance coinduction.

Optimization remains LAST. This wave does not authorize optimization work,
performance-first rewrites, cached evaluator normal forms, scheduler
optimization, parser optimization, projection optimization, or production
evaluator optimization.

## First Foundation Gate Criteria

The focused foundation gate for this v0 must prove:

1. This document exists in `mu/docs/core/` with a DOC_STATUS header and names
   `mu/tests/l4_gates/test_fixpoint_meta_circular_foundation_gate.py` as its
   grounding test.
2. The `TASKS.md` tracker note and governing payoff packet reference this
   document, the L4 gate, the docs wrapper, and the indicator artifact, making
   the v0 discoverable without relying on an untracked side channel.
3. The bridge-review `-pa` packet is only a normalization surface and does not
   supersede the governing payoff packet.
4. The text states the representation boundary as structural data, not a host
   evaluator API, host recursion API, host scheduler API, host coroutine API,
   host iterator API, host parser API, or optimizer pass.
5. The text defines evaluator-as-data envelopes, evaluator references,
   fixed-point witness candidates, self-application trace prefixes,
   closure/stall boundaries, budget windows, and proof limits as Mu shapes.
6. The text records evaluator step, self-application, fixed-point witness,
   closure/stall, budget/exhaustion, fail-closed malformed-envelope, and
   proof-limit obligations as later implementation obligations.
7. The text records finite examples for evaluator-as-data envelopes,
   self-application trace prefixes, fixed-point witness candidates, and
   closure/stall boundaries.
8. The text withholds runtime, substrate, seed, registry, projection, parity,
   pager/autoping, tmux, evaluator, parser, scheduler, execution semantics,
   and optimization edits.
9. The L4 indicator artifact is bound to
   `fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-payoff`.

Passing that gate is evidence that the first Fixpoint/meta-circular evaluator
step is bounded and falsifiable. It is not evidence of production evaluator
semantics, fixed-point execution, self-application execution,
meta-circular closure, optimization closure, or self-hosting closure.

## Relationship To Existing Structural Work

`MuType.v0.md` remains the base value contract: every representation above is
ordinary JSON-compatible Mu.

`SelfHosting.v0.md` and `MetaCircularKernel.v0.md` remain the current
self-hosting and kernel-loop references. This v0 adds representation
obligations only; it does not change match, substitution, kernel selection,
Stage0 execution, or the accepted kernel-driver watchdog boundary.

`StructuralPurity.v0.md` remains the guardrail: computation should be expressed
as Mu transformations, not host object-model behavior.

`NorthStarSemantics.v0.md` remains the semantic policy lock: bounded
non-closure must be explicit, and structural facts must not be smuggled through
host evaluator, host recursion, host scheduler, host parser, or host iterator
behavior.

`OntologyPromotionContract.v0.md` remains the promotion discipline: no host
code can mint ontology tokens, and later fixed-point or evaluator tokens
require structural provenance.

`L3SubstrateArchitecture.v0.md` remains the L3/L4 boundary reference: Python
and JavaScript parity is bridge evidence, while L4 bounded reductions must
avoid adding host authority.
