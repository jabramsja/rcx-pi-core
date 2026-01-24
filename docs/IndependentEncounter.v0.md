# Independent Encounter Semantics v0

Status: VECTOR (design-first, no code changes)

This document defines the "second independent encounter" rule and how it is tracked using existing RCX-π v2 execution/trace concepts.

## Problem statement

We need a principled way to decide when closure becomes unavoidable, in a purely structural / observable manner, without relying on private engine internals or test-only shortcuts.

We model "encounters" as attempts by the execution system to apply reduction rules to a value at a particular pattern site. A stall indicates no reduction is available at that site for that value state.

The key rule we want to formalize:

A value that stalls twice on the same pattern with no intervening reduction is in normal form (closure becomes unavoidable).

This is the "second independent encounter."

## Terms

### Value identity

- value_hash: canonical identifier for the current value state (as already used in v2 events).

### Pattern identity

- pattern_id: stable identifier for the pattern site being matched (may be a string or structured tag; must be stable in trace output).

### Encounter

An encounter is the pair:

(value_hash, pattern_id)

representing: "we attempted to reduce value_hash at pattern_id."

### Independent encounter

A second encounter is independent of the first if:

1. It is the same (value_hash, pattern_id) pair, AND
2. There has been no intervening reduction event that changes the value_hash between the two encounters.

In other words, independence here means "not causally downstream of a successful reduction."
It is not about wall-clock time, metadata, or observer noise.

This definition is intentionally strict and deterministic.

## Trace model v2

We assume v2 traces already include:

- execution.stall
  - mu.value_hash (or equivalent canonical field)
  - mu.pattern_id (or equivalent canonical field)

- execution.fix (optional)
  - mu.target_hash

- execution.fixed
  - mu.before_hash
  - mu.after_hash

We do not introduce new trace events in v0. This is a detection semantics document only.

## The rule: Second independent encounter implies closure

Let E be the stream of execution events.

We define the predicate:

STALL_AT(v, p, t): at time t, an execution.stall occurs with value_hash=v and pattern_id=p.

We define REDUCED(v_old, v_new, t): at time t, an execution.fixed occurs with before_hash=v_old and after_hash=v_new.

Closure becomes unavoidable for (v, p) if there exist times t1 < t2 such that:

- STALL_AT(v, p, t1)
- STALL_AT(v, p, t2)
- For all execution.fixed events between (t1, t2), the value did not change away from v.
  Concretely, there is no execution.fixed whose before_hash == v and after_hash != v between t1 and t2.

Operationally: the value_hash at the second stall must be the same as at the first stall, and no successful reduction changed that value_hash in between.

### Rationale

- If the value is unchanged and the same pattern stalls again, nothing new has been learned by computation.
- Therefore, continuing to search for reductions at that same site is theater.
- We declare the site closed (normal form with respect to that pattern), and the system may emit a terminal "closure" status at the higher level.

## Tracking and minimal state

To detect the second independent encounter, we only need:

- last_stall[(pattern_id)] = value_hash at most recent stall at that pattern_id, for the current trace segment

Then, on each execution.stall(v, p):

- If last_stall[p] == v, this is a second independent encounter at (v, p).
  Closure is unavoidable.
- Else, set last_stall[p] = v.

On execution.fixed(before=v_old, after=v_new):

- If any last_stall entries equal v_old, they must be updated or invalidated.
  Conservative and simplest: clear all last_stall entries when value changes.
  This keeps semantics strict and avoids subtle partial invalidation errors.

v0 recommendation: clear all stall memory on any value transition.

## What counts as "intervening reduction"

Only a successful reduction that changes the value_hash resets independence.
Events like execution.fix do not count as reduction. They are intent/validation signals only.

Therefore:

- execution.fix does NOT reset the stall memory
- execution.fixed DOES reset the stall memory if it changes the value_hash

## Event that signals closure becomes unavoidable

v0 does not mandate a new event type. Closure can be inferred deterministically from the existing v2 stream.

If/when we add an explicit event later, it should be purely derived:

- execution.closure_detected
  - mu.value_hash
  - mu.pattern_id
  - mu.reason = "second_independent_stall"

But v0 stays detection-only to preserve minimal surface area.

## Invariants and safety properties

- Determinism: the closure decision is fully determined by the event stream.
- Anti-theater: prevents repeated identical work from looking like progress.
- No private engine access: only uses fields already emitted in trace.
- Conservative reset: clearing stall memory on any value change prevents false closures.

## Non-goals (v0)

- Defining global normal form across all patterns.
- Deciding what the VM should do after closure is detected.
- Optimizing memory (pattern-local vs global reset).
- Cross-trace or cross-run independence.

## Appendix: Compact definition

Second independent encounter occurs at time t2 for (v, p) if:

- execution.stall(v, p) occurred before at t1
- between t1 and t2 there was no execution.fixed that changed v
