# Independent Encounter Semantics v0

Status: IMPLEMENTED

**Implementation status:**
- ✅ Stall memory tracking (`_stall_memory: Dict[str, str]`)
- ✅ Closure signal detection (`_check_second_independent_encounter()`)
- ✅ Memory clearing on `execution.fixed` (`_clear_stall_memory_for_value()`)
- ✅ Public API: `closure_evidence`, `has_closure` properties
- ✅ All 8 pathological scenarios tested (`tests/test_second_independent_encounter.py`)

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
- Detected inevitability, not policy: the VM observes that closure has become unavoidable based on the event stream; it does not decide to close. What happens after closure is detected is policy that lives elsewhere.

## Non-goals (v0)

- Defining global normal form across all patterns.
- Deciding what the VM should do after closure is detected.
- Optimizing memory (pattern-local vs global reset).
- Cross-trace or cross-run independence.
- Closure detection may only emit trace evidence. Any termination decision must be external and explicit. This document defines when closure becomes unavoidable as an observable condition, not as an engine "stop" directive.

## Pathological trace scenarios (normative examples)

These scenarios clarify edge cases. The rule: closure evidence triggers only when the SAME (value_hash, pattern_id) stalls twice with NO intervening execution.fixed that changes away from that value_hash.

Memory is per-pattern: stall_memory[pattern_id] = value_hash.

Reset rule (v0): an execution.fixed clears remembered values whose value_hash equals fixed.before_hash (value-based reset).

### Scenario 1: A-then-B-then-A

- Setup: stall(v, pA), stall(v, pB), stall(v, pA)
- Question: Does the third event produce closure evidence for pA?
- Answer: Yes. The stall memory for pA held v after the first stall. The stall at pB does not clear it (different pattern). The third stall at pA with value v matches, producing closure evidence for (v, pA).

### Scenario 2: Idempotent fix (after_hash == before_hash)

- Setup: stall(v, pA), execution.fixed(before=v, after=v), stall(v, pA)
- Question: Does the second stall produce closure evidence?
- Answer: No. The execution.fixed event has before_hash == v, so it triggers stall memory clearing under the conservative reset rule. Even though after_hash == v, the memory was cleared. The second stall is a first encounter again (no closure evidence), because the intervening execution.fixed cleared memory.

### Scenario 3: Single stall at end

- Setup: stall(v, pA), trace.end
- Question: Is there closure evidence?
- Answer: No. Closure evidence requires TWO stalls at the same (value_hash, pattern_id). A single stall provides no evidence of normal form.

### Scenario 4: Move away and back

- Setup: stall(v, pA), execution.fixed(before=v, after=w), stall(v, pA)
- Question: Does the second stall at (v, pA) produce closure evidence?
- Answer: No. The execution.fixed(v→w) cleared stall memory (before_hash == v triggers reset). The second stall at (v, pA) is a fresh first encounter, even though the value returned to v by some other means.

### Scenario 5: Two different values at same pattern

- Setup: stall(v, pA), stall(w, pA), stall(v, pA)
- Question: Does the third stall produce closure evidence for (v, pA)?
- Answer: No. The second stall at (w, pA) overwrote stall_memory[pA] = w. The third stall at (v, pA) finds stall_memory[pA] == w ≠ v, so it is a fresh encounter. No closure evidence.

### Scenario 6: Intervening reduction on different value

- Setup: stall(v, pA), execution.fixed(before=w, after=x), stall(v, pA)
- Question: Does the second stall produce closure evidence?
- Answer: Yes. The execution.fixed event has before_hash == w ≠ v, so stall memory for pA (which holds v) is NOT cleared under the rule "clear if before_hash matches any stall_memory entry." Since v ≠ w, the memory persists, and the second stall matches.

### Scenario 7: execution.fix does not reset memory

- Setup: stall(v, pA), execution.fix(target_hash=v), stall(v, pA)
- Question: Does the second stall produce closure evidence?
- Answer: Yes. The execution.fix event is intent/validation only and does NOT reset stall memory. Only execution.fixed resets memory. The second stall matches stall_memory[pA] == v.

### Scenario 8: Multiple patterns, partial closure

- Setup: stall(v, pA), stall(v, pB), stall(v, pA), stall(v, pB)
- Question: Which patterns have closure evidence?
- Answer: Both. After stall(v, pA), stall_memory[pA] = v. After stall(v, pB), stall_memory[pB] = v. The third event stall(v, pA) matches stall_memory[pA] → closure evidence for (v, pA). The fourth event stall(v, pB) matches stall_memory[pB] → closure evidence for (v, pB).

## Appendix: Compact definition

Second independent encounter occurs at time t2 for (v, p) if:

- execution.stall(v, p) occurred before at t1
- between t1 and t2 there was no execution.fixed that changed v

---

## Implementation

Document version: v0
Last updated: 2026-01-25
Status: IMPLEMENTED

Implementation:
- `rcx_pi/trace_canon.py` (ExecutionEngine with stall memory tracking)
- `tests/test_second_independent_encounter.py` (15 tests covering all 8 scenarios)

Key methods:
- `_stall_memory`: Dict mapping pattern_id → value_hash
- `_closure_evidence`: List of closure evidence entries
- `_check_second_independent_encounter()`: Detects second stall at same (v, p)
- `_clear_stall_memory_for_value()`: Clears entries on execution.fixed
- `closure_evidence` property: Returns list of detected closures
- `has_closure` property: True if any closure detected
- `stall()` / `consume_stall()`: Now return bool indicating closure detection
