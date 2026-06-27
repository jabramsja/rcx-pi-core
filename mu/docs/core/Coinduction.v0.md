<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-06-27
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/l4_gates/test_coinduction_foundation_gate.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest mu/tests/l4_gates/test_coinduction_foundation_gate.py -v
-->

# Coinduction for RCX (Coinduction.v0)

**Status:** REFERENCE - first bounded foundation contract for representing
coinduction and productive non-termination as structural Mu data. This v0 is
not a host coroutine API, not a host iterator API, not a host async API, not a
host async loop model, not a host process model, not a host scheduler authority,
and not a host liveness oracle. It does not authorize production coinductive
runtime semantics.

**Authority:** `TASKS.md` carries the 2026-06-27 tracker sync note for
`coinduction-non-termination-as-structure-2026-06-27`. That same-wave tracker
note is the authority for this bounded Coinduction first step. `STATUS.md`
keeps Phase 8c, the L4 bounded-reduction posture, and the current debt ledgers
unchanged unless separately revalidated.

## Purpose

Coinduction records the first representation boundary for non-termination as
structure: observations, guarded steps, finite productive trace prefixes, and
codata-like process traces as Mu values. The first step is deliberately small:
define the data shapes and falsifiable foundation criteria that later waves
must satisfy before any production coinductive evaluator, productivity checker,
bisimulation engine, scheduler, stream runtime, or self-hosting claim can be
made.

This document is a structural-data proposal, not an implementation plan for a
host coroutine, host iterator, host event loop, host process monitor, host
thread, host scheduler, or optimization path. Non-termination is represented by
open structural trace obligations and finite observations, not by asking the
host to run forever.

## Representation Boundary

The v0 representation uses explicit Mu nodes and linked lists:

```text
co_trace        ::= {"_co_trace": {"head": observation_node,
                                   "tail": trace_tail}}

trace_tail      ::= {"_co_tail": {"next": trace_ref,
                                  "guard": guarded_step_ref}}
                  | {"_co_tail": {"open": true,
                                  "obligation": obligation_ref}}

observation_node ::= {"_co_observation": {"label": string,
                                          "payload": Mu,
                                          "position": observation_position}}

guarded_step    ::= {"_co_guarded_step": {"source": trace_ref,
                                          "observation": observation_ref,
                                          "next": trace_ref,
                                          "guard": guard_witness}}

trace_prefix    ::= {"_co_prefix": null}
                  | {"_co_prefix": {"observation": observation_node,
                                    "step": guarded_step_ref,
                                    "rest": trace_prefix}}

observation_window ::= {"_co_window": {"from": observation_position,
                                       "through": observation_position,
                                       "prefix": trace_prefix,
                                       "finite": true}}

observation_position ::= {"_co_position": {"path": position_path}}
position_path         ::= {"_co_position_path": null}
                       | {"_co_position_path": {"step": string,
                                                "rest": position_path}}
```

The linked shapes are intentional. They use ordinary Mu dictionaries, strings,
booleans, and `null`. They do not require host generators, host coroutine
frames, host iterator objects, host promises, host async tasks, host process
handles, host timers, host thread identity, host scheduler queues, host liveness
polling, or host arrays as semantic authority.

The `_co_trace`, `_co_observation`, `_co_guarded_step`, `_co_prefix`,
`_co_window`, and `_co_position` tags name the representation family only. They
do not make a stream productive, prove bisimulation, execute a corecursive
step, schedule a process, certify liveness, or close self-hosting by host
authority.

## Observation Discipline

A Coinduction datum is a candidate structural trace only when these obligations
are met:

1. An observation node carries a structural label, a Mu payload, and an
   explicit structural position.
2. A guarded step exposes at least one observation before naming the next
   trace reference. The step cannot hide progress behind host coroutine
   suspension, host iterator `next`, host async/event-loop wakeup, host process
   state, or host scheduler fairness.
3. A productive trace prefix is a finite linked list of observations and
   guarded step witnesses.
4. A finite observation window states the structural positions covered by a
   finite prefix and carries the prefix as Mu data.
5. An open tail is permitted only as an obligation marker. It is not evidence
   that the trace has been executed forever.
6. Observation equivalence is a later proof obligation. Representation identity
   of two finite prefixes is not yet coinductive equality.

These rules define representation obligations. They are not Python generator
semantics, JavaScript iterator semantics, host async semantics, host process
liveness semantics, host timer semantics, or host scheduler semantics.

## Guarded Corecursion Obligations

Guarded corecursion is a later implementation obligation. A future Phase A must
narrow a falsifiable slice before any production guarded corecursor,
productivity checker, bisimulation checker, stream runtime, scheduler, or
coinductive evaluator is implemented.

Later waves must prove at least these obligations before claiming production
semantics:

1. **Guarded exposure:** every corecursive transition emits an observation node
   before referring to the next trace.
2. **Productive prefix extraction:** for any requested finite observation
   window, the system can produce a finite linked prefix or fail closed with a
   structural reason.
3. **Finite observation windows:** windows are represented as Mu data and do
   not rely on host array slicing, host iterator positions, host timestamps, or
   host scheduler ticks.
4. **Observation-equivalence obligations:** later proofs must define when two
   trace prefixes are equivalent by structural observation, not by host object
   identity or host process state.
5. **Bisimulation obligations:** any future bisimulation proof must be a
   structural proof object over observations and guarded steps.
6. **Fail-closed malformed traces:** missing observations, unguarded tails,
   malformed windows, unknown trace references, and host-only liveness claims
   fail closed.

This v0 records those obligations only. It does not claim guarded corecursion
execution, productivity checker closure, bisimulation closure, scheduler
closure, stream runtime closure, production coinductive evaluator closure,
fixpoint closure, optimization closure, or self-hosting closure.

## Small Foundation Examples

The examples below use aliases so the shapes stay readable:

```text
P0 := {"_co_prefix": null}
Pos(name) := {"_co_position": {"path": {"_co_position_path": {"step": name,
               "rest": {"_co_position_path": null}}}}}
Open(reason) := {"_co_tail": {"open": true, "obligation": reason}}
```

### Constant Stream Prefix

```text
ObsZero0 := {"_co_observation": {"label": "zero",
                                 "payload": {"_num": null},
                                 "position": Pos("zero-0")}}

ObsZero1 := {"_co_observation": {"label": "zero",
                                 "payload": {"_num": null},
                                 "position": Pos("zero-1")}}

StepZero0 := {"_co_guarded_step": {"source": "ZeroStream@0",
                                   "observation": ObsZero0,
                                   "next": "ZeroStream@1",
                                   "guard": "observed-before-tail"}}

ZeroPrefix2 := {"_co_prefix": {"observation": ObsZero0,
                               "step": StepZero0,
                               "rest": {"_co_prefix": {
                                 "observation": ObsZero1,
                                 "step": "StepZero1",
                                 "rest": P0}}}}
```

Required proof facts: the prefix exposes two finite observations of the same
structural zero payload; the open tail remains an obligation, not an infinite
host iterator or coroutine.

### Repeating Structural Transition

```text
ObsA := {"_co_observation": {"label": "state",
                             "payload": {"state": "A"},
                             "position": Pos("toggle-0")}}

ObsB := {"_co_observation": {"label": "state",
                             "payload": {"state": "B"},
                             "position": Pos("toggle-1")}}

TogglePrefix2 := {"_co_prefix": {"observation": ObsA,
                                 "step": "A-to-B-observed",
                                 "rest": {"_co_prefix": {
                                   "observation": ObsB,
                                   "step": "B-to-A-observed",
                                   "rest": P0}}}}
```

Required proof facts: the prefix records two observed transitions in a finite
window. It does not prove fair scheduling, process liveness, bisimulation, or
infinite execution.

### Finite Observation Window

```text
ToggleWindow2 := {"_co_window": {"from": Pos("toggle-0"),
                                 "through": Pos("toggle-1"),
                                 "prefix": TogglePrefix2,
                                 "finite": true}}
```

Required proof facts: the window is a bounded observation request and result.
It is not a host time slice, host event-loop tick range, host process sample, or
host scheduler trace.

## Canonical Boundary

Coinduction v0 has two identities that must not be conflated:

- **Representation identity:** the exact Mu shape and content hash of an
  observation node, guarded step, finite prefix, or observation window.
- **Observation equivalence:** the later proof that two traces expose the same
  observations under a declared finite window or bisimulation relation.

Representation identity is enough for the hand-authored finite fixtures in
this document only because the examples fix one local spelling. It is not a
global trace equality proof, not a bisimulation proof, not a productivity
proof, and not a liveness proof.

## Deferred Queue Boundaries

Fixpoint remains the next structural queue item after Coinduction for
evaluator-as-structure and the meta-circular payoff. This wave does not advance
fixpoint.

Optimization remains LAST. This wave does not authorize optimization work,
performance-first rewrites, cached trace normal forms, scheduler optimization,
stream runtime optimization, or production projection optimization.

## Explicit Proof Limits

This v0 does not prove or authorize:

- production coinductive runtime semantics;
- a production guarded corecursor, productivity checker, bisimulation checker,
  scheduler, stream runtime, corecursive evaluator, liveness oracle, or trace
  normalizer;
- guarded corecursion execution, observation-equivalence closure,
  productivity checker closure, bisimulation closure, scheduler closure,
  stream runtime closure, coinductive evaluator closure, fixpoint closure,
  optimization closure, or self-hosting closure;
- non-termination proof by running forever;
- changes to runtime, substrate, seed, registry, projection, JavaScript parity,
  pager/autoping, tmux, evaluator, parser, or execution semantics files;
- host coroutine behavior, host iterator authority, host async/event-loop
  authority, host process liveness authority, host scheduler authority, host
  timers, host threads, host object identity, or host-only non-termination
  semantics.

The only closure claimed by this wave is a docs-backed foundation boundary:
Coinduction can be described as structural Mu observations, guarded steps,
finite productive trace prefixes, finite observation windows, and explicit
later proof obligations.

## First Foundation Gate Criteria

The focused foundation gate for this v0 must prove:

1. This document exists in `mu/docs/core/` with a DOC_STATUS header and names
   `mu/tests/l4_gates/test_coinduction_foundation_gate.py` as its grounding
   test.
2. The wave config, governing packet, and tracker note reference this document
   and the foundation gate, making the v0 discoverable without relying on an
   untracked side channel.
3. The text states the representation boundary as structural data, not a host
   coroutine API, host iterator API, host async API, host process model, host
   scheduler authority, or host liveness oracle.
4. The text defines observation node, guarded step, productive trace prefix,
   finite observation windows, open-tail obligations, and codata-like process
   traces as Mu shapes.
5. The text records guarded corecursion and observation-equivalence obligations
   as later implementation obligations without authorizing a production
   corecursor, productivity checker, bisimulation checker, scheduler, stream
   runtime, coinductive evaluator, or self-hosting closure.
6. The text records finite examples for stream prefixes, repeating structural
   transitions, and finite observation windows.
7. The text explicitly defers fixpoint and optimization, and keeps
   Optimization LAST.
8. The text withholds runtime, substrate, seed, registry, projection, parity,
   pager/autoping, tmux, evaluator, parser, execution semantics, scheduler, and
   optimization edits.

Passing that gate is evidence that the first Coinduction step is bounded and
falsifiable. It is not evidence of coinductive semantic closure, productivity
checker closure, bisimulation closure, scheduler closure, stream runtime
closure, fixpoint closure, optimization closure, or self-hosting closure.

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
host process, host scheduler, host async, or host iterator behavior.

`OntologyPromotionContract.v0.md` remains the promotion discipline: no host
code can mint ontology tokens, and later coinductive trace tokens require
structural provenance.

`L3SubstrateArchitecture.v0.md` remains the L3/L4 boundary reference: Python
and JavaScript parity is bridge evidence, while L4 bounded reductions must
avoid adding host authority.
