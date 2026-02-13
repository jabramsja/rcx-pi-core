<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-02-09
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Self-Hosting Specification v0

> **Current status:** See `STATUS.md` for current phase and L-level. This doc is the detailed design spec.

## Purpose

Define how EVAL_SEED achieves self-hosting: the evaluator (expressed as Mu projections) runs itself. This is the key milestone proving RCX emergence is structural, not host-dependent.

## Agent Feedback Integration

This revision addresses feedback from verifier, adversary, and expert agents:

- **Verifier**: Add concrete projection JSON, not just names
- **Adversary**: Fix dict determinism, handle binding conflicts properly
- **Expert**: Simplify! Structure IS the type. Target 10-15 projections, not 37

## Key Insight

> "Type dispatch analysis is a red herring. In Mu, structure IS the type."
> — Expert Agent

We don't need isinstance(). A projection that matches `{"head": ..., "tail": ...}`
will ONLY match things with that structure. This is how `mu/utilities/eval.v1.json` works.

## Problem Statement

Phase 3 achieved:
- Traversal machinery as Mu projections (wrap, descend, ascend, etc.)
- Domain projections (append) run identically in Python and Mu

But the core operations are still Python:
```python
@host_recursion("Tree traversal for pattern matching")
def match(pattern, value): ...

@host_recursion("Tree traversal for substitution")
def substitute(body, bindings): ...
```

For self-hosting, these must become Mu projections that the evaluator can run.

## The Self-Hosting Goal

```
┌─────────────────────────────────────────────────────┐
│  EVAL_SEED (as Mu data)                             │
│  ┌─────────────────────────────────────────────┐    │
│  │ projections: [                              │    │
│  │   {pattern: ..., body: ...},  // match      │    │
│  │   {pattern: ..., body: ...},  // substitute │    │
│  │   {pattern: ..., body: ...},  // step       │    │
│  │   ...                                       │    │
│  │ ]                                           │    │
│  └─────────────────────────────────────────────┘    │
│                        │                            │
│                        ▼                            │
│  ┌─────────────────────────────────────────────┐    │
│  │ EVAL_SEED (running)                         │    │
│  │   Input: EVAL_SEED (as data) + test value   │    │
│  │   Output: evaluated result                  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

If EVAL runs EVAL and produces the same trace as Python running EVAL, self-hosting is achieved.

## Design Approach: Leverage deep_eval

The existing `mu/utilities/eval.v1.json` shows how to express traversal as Mu projections.
We follow the same pattern for match and substitute.

### Core Representations

**Bindings as linked list** (immutable, uses existing append):
```json
{"name": "x", "value": 42, "rest": {"name": "y", "value": 10, "rest": null}}
```

**Match state** (parallel traversal of pattern + value):
```json
{
  "mode": "match",
  "pattern_focus": {"head": {"var": "a"}, "tail": {"var": "b"}},
  "value_focus": {"head": 1, "tail": 2},
  "bindings": {"name": "x", "value": 42, "rest": null},
  "stack": []
}
```

**Substitute state** (traversal of body, looking up bindings):
```json
{
  "mode": "subst",
  "focus": {"var": "x"},
  "bindings": {"name": "x", "value": 42, "rest": null},
  "context": [],
  "result": null
}
```

### Design Decisions (Based on Agent Feedback)

| Challenge | Decision | Rationale |
|-----------|----------|-----------|
| Type dispatch | **Structure IS type** | Projections match structures, not types |
| Variable site | **Pattern `{"var": x}`** | Well-formed input assumption (adversary-verified) |
| Dict iteration | **Fixed key patterns** | Already works! Current system uses this |
| Bindings | **Linked list** | Immutable, concatenate via append |
| Conflicts | **Non-linear via bridge** (B-structural) | match_mu uses match.v2 + bridge projections for conflict detection |
| Dict determinism | **Sorted keys in JSON serialization** | Fix existing code |

## Concrete Projections (Phase 4a: Match)

### Match Projections (~6-8 total)

**1. match.var** - Variable site binds to value
```json
{
  "id": "match.var",
  "pattern": {
    "mode": "match",
    "pattern_focus": {"var": {"var": "name"}},
    "value_focus": {"var": "value"},
    "bindings": {"var": "bindings"},
    "stack": {"var": "stack"}
  },
  "body": {
    "mode": "match",
    "pattern_focus": null,
    "value_focus": null,
    "bindings": {
      "name": {"var": "name"},
      "value": {"var": "value"},
      "rest": {"var": "bindings"}
    },
    "stack": {"var": "stack"}
  }
}
```

**2. match.null** - Null matches null
```json
{
  "id": "match.null",
  "pattern": {
    "mode": "match",
    "pattern_focus": null,
    "value_focus": null,
    "bindings": {"var": "bindings"},
    "stack": {"var": "stack"}
  },
  "body": {
    "mode": "match",
    "pattern_focus": null,
    "value_focus": null,
    "bindings": {"var": "bindings"},
    "stack": {"var": "stack"}
  }
}
```

**3. match.dict.descend** - Descend into head/tail structure
```json
{
  "id": "match.dict.descend",
  "pattern": {
    "mode": "match",
    "pattern_focus": {"head": {"var": "ph"}, "tail": {"var": "pt"}},
    "value_focus": {"head": {"var": "vh"}, "tail": {"var": "vt"}},
    "bindings": {"var": "b"},
    "stack": {"var": "s"}
  },
  "body": {
    "mode": "match",
    "pattern_focus": {"var": "ph"},
    "value_focus": {"var": "vh"},
    "bindings": {"var": "b"},
    "stack": {
      "head": {"pattern_rest": {"var": "pt"}, "value_rest": {"var": "vt"}},
      "tail": {"var": "s"}
    }
  }
}
```

**4. match.sibling** - Move to sibling after head match
```json
{
  "id": "match.sibling",
  "pattern": {
    "mode": "match",
    "pattern_focus": null,
    "value_focus": null,
    "bindings": {"var": "b"},
    "stack": {
      "head": {"pattern_rest": {"var": "pt"}, "value_rest": {"var": "vt"}},
      "tail": {"var": "rest"}
    }
  },
  "body": {
    "mode": "match",
    "pattern_focus": {"var": "pt"},
    "value_focus": {"var": "vt"},
    "bindings": {"var": "b"},
    "stack": {"var": "rest"}
  }
}
```

**5. match.done** - Empty stack, return bindings
```json
{
  "id": "match.done",
  "pattern": {
    "mode": "match",
    "pattern_focus": null,
    "value_focus": null,
    "bindings": {"var": "b"},
    "stack": null
  },
  "body": {
    "mode": "match_done",
    "bindings": {"var": "b"}
  }
}
```

**6. match.wrap** - Entry point (must be last)
```json
{
  "id": "match.wrap",
  "pattern": {"pattern": {"var": "p"}, "value": {"var": "v"}},
  "body": {
    "mode": "match",
    "pattern_focus": {"var": "p"},
    "value_focus": {"var": "v"},
    "bindings": null,
    "stack": null
  }
}
```

### Substitute Projections (~5-6 total)

**1. subst.var** - Replace variable with bound value
```json
{
  "id": "subst.var",
  "pattern": {
    "mode": "subst",
    "focus": {"var": {"var": "name"}},
    "bindings": {"var": "b"},
    "context": {"var": "ctx"}
  },
  "body": {
    "mode": "subst",
    "focus": {"op": "lookup", "name": {"var": "name"}, "in": {"var": "b"}},
    "bindings": {"var": "b"},
    "context": {"var": "ctx"}
  }
}
```

**2. subst.dict.descend** - Descend into dict structure
```json
{
  "id": "subst.dict.descend",
  "pattern": {
    "mode": "subst",
    "focus": {"head": {"var": "h"}, "tail": {"var": "t"}},
    "bindings": {"var": "b"},
    "context": {"var": "ctx"}
  },
  "body": {
    "mode": "subst",
    "focus": {"var": "h"},
    "bindings": {"var": "b"},
    "context": {
      "head": {"type": "dict_head", "tail": {"var": "t"}},
      "tail": {"var": "ctx"}
    }
  }
}
```

**3. subst.sibling** - Move to tail after head substitution
(Similar pattern to match.sibling)

**4. subst.ascend** - Reconstruct parent after both children done
(Similar pattern to deep_eval ascend)

**5. subst.done** - Return final result

**6. subst.wrap** - Entry point

### Seed Projection Counts

> **Verified by grounding tests in `tests/structural/test_seed_counts.py`**

| Seed | File | Projections |
|------|------|-------------|
| Match | `mu/substrate/match.v1.json` | (see grounding tests) |
| Substitute | `mu/substrate/subst.v1.json` | (see grounding tests) |
| Classify | `mu/utilities/classify.v1.json` | (see grounding tests) |

Grounding tests fail if seed files change. This prevents doc drift.

## Phased Implementation

> **Test counts are not hardcoded here.** Run `pytest --collect-only` to see current counts.
> Grounding tests verify structural claims; pytest verifies test existence.

### Phase 4a: Match as Mu ✅ COMPLETE
- Match projections in `mu/substrate/match.v1.json`
- Implementation: `rcx_pi/match_mu.py`
- Parity tests in `tests/test_match_parity.py`

### Phase 4b: Substitute as Mu ✅ COMPLETE
- Substitute projections in `mu/substrate/subst.v1.json`
- Implementation: `rcx_pi/subst_mu.py`
- Parity tests in `tests/test_subst_parity.py`

### Phase 4c: Binding Lookup ✅ COMPLETE
- Integrated into substitute projections (no separate seed needed)
- Lookup done via linked list traversal in subst projections

### Phase 4d: Integration Testing ✅ COMPLETE
- Integration tests in `tests/test_apply_mu_integration.py`
- Structural tests in `tests/structural/test_apply_mu_grounding.py`
- Fuzzer tests in `tests/test_apply_mu_fuzzer.py`

### Phase 5: Self-Hosting ✅ COMPLETE
- `rcx_pi/step_mu.py`: `apply_mu()`, `step_mu()`, `run_mu()`
- step_mu uses match_mu + subst_mu (Mu projections, not Python recursion)
- Parity tests in `tests/test_step_mu_parity.py`
- Self-hosting tests in `tests/test_self_hosting_v0.py`
- Note: Operations (match/subst) are self-hosted; kernel loop is still Python (see STATUS.md L1/L2)

### Phase 6a: Lookup as Mu Projections ✅ COMPLETE
- Added `subst.lookup.found` and `subst.lookup.next` projections
- Lookup is structural: pattern matching with non-linear vars
- Subst parity tests pass with structural lookup

### Phase 6b: Classification as Mu Projections ✅ COMPLETE
- Created `mu/utilities/classify.v1.json` for linked list classification
- Created `rcx_pi/selfhost/classify_mu.py`
- Classification distinguishes dict-encoding from list-encoding
- Tests in `tests/test_classify_mu.py`

### Phase 6c: Type Tags and Iterative Normalization ✅ COMPLETE
- `normalize_for_match()` and `denormalize_from_match()` are now iterative
- Type tags (`_type: "list"` / `_type: "dict"`) resolve list/dict ambiguity
- `VALID_TYPE_TAGS` whitelist for security
- Fuzzer tests in `tests/test_type_tags_fuzzer.py`

## Resolved Questions

| Question | Resolution |
|----------|------------|
| Kernel type primitives? | **No** - structure IS type |
| Dict key ordering? | **sorted() in JSON serialization** |
| Non-linear patterns? | **Supported via bridge projections** (match_mu uses match.v2 + bridge; step_mu/run_mu are fail-closed linear-only) |
| Conversion overhead? | **Minimal** - fixed-key patterns |
| Eager vs lazy? | **Eager** (matches current Python) |

## Adversary Attack Vectors (Addressed)

The adversary agent identified these attack vectors. Mitigations:

| Attack | Mitigation |
|--------|------------|
| Dict ordering non-determinism | Use `sorted()` in JSON serialization |
| Binding conflict (non-linear) | Linear patterns only in Phase 4 |
| Infinite loop in match | Bounded stack depth (same as deep_eval) |
| Variable site ambiguity | Well-formed input assumption + validation |
| Match/substitute interleaving | Explicit mode field in state |

## Security Hardening (PR #149)

Additional attack vectors addressed in security hardening pass:

| Attack | Mitigation |
|--------|------------|
| Resource exhaustion (cascading calls) | Global step budget: MAX_PROJECTION_STEPS=50,000 |
| Deep nesting DoS | MAX_MU_DEPTH=300 limit |
| Wide structure DoS | MAX_MU_WIDTH=1,000 limit |
| Circular reference infinite loop | Cycle detection in normalize/denormalize |
| Cross-thread budget contamination | Thread-local budget via `threading.local()` |
| Empty variable name edge case | Explicit rejection with ValueError |
| Hostile unicode edge cases | Tested with emoji, RTL, zero-width, homoglyphs |

**Test Coverage:**
- `tests/test_selfhost_fuzzer.py`: 53 tests, 10,000+ random examples
- `TestMatchMuParity`: match_mu == eval_seed.match (1,000 examples)
- `TestSubstMuParity`: subst_mu == eval_seed.substitute (1,200 examples)
- `TestNearLimitStress`: boundary testing at depth 190-200, width 900-1000
- All tests use `deadline=5000` to prevent infinite hangs

## Success Criteria

Phase 4a-4d complete:

1. [x] `match()` expressed as Mu projections (`mu/substrate/match.v1.json`, 7 projections)
2. [x] `substitute()` expressed as Mu projections (`mu/substrate/subst.v1.json`, 12 projections)
3. [x] Parity tests pass: Mu-match == Python-match (23 tests in `test_match_parity.py`)
4. [x] Parity tests pass: Mu-subst == Python-subst (17 tests in `test_subst_parity.py`)
5. [x] Integration tests: match_mu + subst_mu work together (67 tests total)
   - 28 parity tests (`test_apply_mu_integration.py`)
   - 27 structural grounding tests (`test_apply_mu_grounding.py`)
   - 12 property-based fuzzer tests (`test_apply_mu_fuzzer.py`)

Phase 5 complete:

6. [x] EVAL_SEED can evaluate EVAL_SEED (`test_self_hosting_complete` in `test_self_hosting_v0.py`)
7. [x] Traces from Python→EVAL and EVAL→EVAL are identical (verified in 11 self-hosting tests)
8. [x] No `@host_recursion` markers in step_mu evaluation path (operations use Mu projections)
   - Note: Kernel loop (for-loop) remains Python iteration; this is "scaffolding debt" not "semantic debt"

## References

- `docs/core/EVAL_SEED.v0.md` - Current EVAL_SEED spec
- `docs/execution/DeepStep.v0.md` - Deep traversal design
- `rcx_pi/selfhost/` - Core self-hosting modules:
  - `mu_type.py` - Mu type validation and guardrails
  - `kernel.py` - Step budget infrastructure only (legacy Kernel class DELETED 2026-01-29)
  - `eval_seed.py` - EVAL_SEED evaluator (apply_projection, step)
  - `match_mu.py` - Pattern matching as Mu projections + normalization
  - `subst_mu.py` - Substitution as Mu projections
  - `step_mu.py` - Self-hosting step (uses kernel.v1 + match.v2 + subst.v2)
  - `classify_mu.py` - Linked list classification as Mu projections
- `rcx_pi/deep_eval.py` - Deep evaluation machinery
- `mu/` - Mu projection definitions:
  - `substrate/match.v1.json` - Match projections v1 (7 rules, legacy)
  - `substrate/match.v2.json` - Match projections v2 (8 rules, used by match_mu + kernel)
  - `substrate/subst.v1.json` - Substitute projections (12 rules, includes lookup + typed)
  - `bridge/bootstrap_structural.v1.json` - Bridge projections (5 rules, non-linear pattern support)
  - `closures/recurrence.v1.json` - Closure detection v1 (9 projections, proof-of-concept)
  - `closures/recurrence.v2.json` - Closure detection v2 (9 projections, hash-accelerated)
  - `closures/exhaustion.v1.json` - Operator exhaustion (11 projections)
  - `programs/hemispheres.v1.json` - Hemisphere routing (12 projections)
  - `programs/paxos_demo.v1.json` - Paxos deadlock demo (6 projections)
  - `utilities/eval.v1.json` - EVAL_SEED traversal projections
  - `utilities/classify.v1.json` - Classification projections (6 rules)

**B-Structural Non-Linear Match (2026-02-09):**
- `match_mu()` now uses match.v2 + bridge projections directly (13 combined projections)
- Provides non-linear pattern conflict detection for `apply_mu()` without kernel overhead
- `step_mu()`/`run_mu()` are fail-closed: reject non-linear patterns with ValueError
- See `tests/structural/test_match_bridge_invariants.py` for ordering and contract tests

## Historical Phase Log and Deferred Follow-Ups

**Completed (Phase 4a-4d):**
1. [x] Review this doc with agents (verifier, adversary, expert)
2. [x] Decide on type dispatch approach - **Structure IS type**
3. [x] Decide on dict iteration approach - **Fixed key patterns**
4. [x] Phase 4a: match projections (`mu/substrate/match.v1.json`, `rcx_pi/selfhost/match_mu.py`)
5. [x] Phase 4b: substitute projections (`mu/substrate/subst.v1.json`, `rcx_pi/selfhost/subst_mu.py`)
6. [x] Phase 4d: Integration tests (67 tests across 3 test files)

**Phase 5 (Self-Hosting): ✅ COMPLETE**
7. [x] Create `apply_mu` as Mu projections (combines match + subst) - `rcx_pi/selfhost/step_mu.py`
8. [x] EVAL_SEED evaluates EVAL_SEED - `test_self_hosting_complete` passes
9. [x] Compare traces: Python→EVAL vs EVAL→EVAL - identical for all test cases
10. [x] **Self-hosting achieved!** 33 tests verify step_mu() == step()

**Phase 6 (Debt Reduction): ✅ COMPLETE**
11. [x] Phase 6a: Lookup as Mu projections (removed 2 @host_builtin)
12. [x] Phase 6b: Classification as Mu projections (removed 2 @host_builtin)
13. [x] Phase 6c: Iterative normalization + type tags (removed 2 @host_recursion)
14. [x] **Debt reduced!** See `STATUS.md` for current counts (down from 23)

**Phase 7 (L2 FULL achieved via explicit acceptance):**
- [x] 7a/7b/7c: Kernel projections, context passthrough, integration tests
- [x] 7d-1: Wire step_mu to structural kernel (selection is structural, execution is Python)
- [x] 7d-2/7d-3: CLOSED (not applicable - Phase 8 decided to accept for-loop as bootstrap primitive)
- L2 FULL = L2 PARTIAL + explicit acceptance. The for-loop is like Forth's NEXT: irreducible.
- See `STATUS.md` for current phase and `TASKS.md` for Phase 7 sub-phases

**Phase 8 (Bootstrap Primitives + Mechanical Kernel):**
- [x] 8a: Document 4 bootstrap primitives (eval_step, max_steps, stack_guard, projection_loader; mu_equal eliminated)
- [x] 8b: Simplify step_kernel_mu to mechanical operation (~15 lines)
- Deferred: 8c oscillation detection (future research)
- [x] 8d: EngineNews trace model (complete; see L3 notes below)

**L3 Substrate Portability (7-agent reviewed 2026-01-30):**
- [x] JS POC exists (`mu/host/js/eval_step.js`, ~1300 LOC core + ~900 LOC inline tests)
- [x] Same projections run on Python AND JavaScript
- [x] Step 1: Fix JS security gaps (KERNEL_RESERVED_FIELDS, type tag, dict kv-pair)
- [x] Step 2: Cross-substrate parity tests (`tests/test_parity_python.py`, 20 vectors)
- [x] Step 3: Phase 8d trace model in Python (`tests/test_structural_trace.py`, 14 tests)
- [x] Step 4: Port trace to JS POC (`runStructural()`, 5 tests)
- [x] Step 5: EngineNews demo on both substrates (structural, 2026-01-30)

**EngineNews Structural Closure Detection (IMPLEMENTED 2026-01-30)**

EngineNews rules are expressed as Mu projections in `mu/closures/recurrence.v1.json` (proof-of-concept, 9 projections) and `mu/closures/recurrence.v2.json` (hash-accelerated production version, 9 projections). See `docs/core/recurrence_v2_design.md` for the v2 design and `roadmap/ContentAddressedMu.md` for the broader Content-Addressed Mu direction.

1. **Why this matters:** If EngineNews runs via Python loops/logic, emergence might be a Python artifact. For structural honesty, closure detection must be pattern matching on traces.

2. **What's acceptable:** The bootstrap primitives (eval_step, max_steps, stack_guard, projection_loader, for-loop driver) are fine - they're like Forth's NEXT. The LOGIC must be projections. (mu_equal eliminated via Level 1 Content-Addressed Mu.)

3. **Success criteria (ALL MET):**
   - [x] `mu/closures/recurrence.v1.json` exists with 9 projections
   - [x] EngineNews projections run via `eval_seed.step()`, NOT Python loops
   - [x] Closure detection is structural: projection matches trace pattern
   - [x] Seen-set is Mu linked-list, NOT Python set
   - [x] No Python `if/for/while` in closure detection path (only in bootstrap)
   - [x] 7-agent review: All agents APPROVE

4. **Implemented projections (9 total):**
   - `recurrence.init` - Entry point
   - `recurrence.end_of_trace` - End of trace (null)
   - `recurrence.check_state_stall` - Extract state from stall entry
   - `recurrence.check_state_maxsteps` - Extract state from max_steps entry
   - `recurrence.check_state` - Extract state from normal entry
   - `recurrence.found_in_seen` - State in seen-set -> closure detected!
   - `recurrence.not_in_head` - State not in head -> check tail
   - `recurrence.not_found` - State not found -> add and advance
   - `recurrence.unwrap` - Extract final result

5. **Key design: Non-linear patterns for state equality**
   - `recurrence.found_in_seen` uses `{"var": "state"}` twice in pattern
   - eval_seed.match() binding conflict detection (lines 331-336, 351-355) enforces equality
   - This is bootstrap primitive (like Forth's NEXT), not semantic debt
   - Both Python and JS substrates handle binding conflicts identically

**Test files:**
- `tests/test_parity_python.py` - 20 parity + 3 security tests
- `tests/test_structural_trace.py` - 14 structural trace tests
- `tests/fixtures/parity_vectors.json` - 23 shared test vectors

**What L3 proves:** All meaning is in projections. The host (Python or JS) provides only mechanical execution via the 4 bootstrap primitives. Emergence is structural, not a Python artifact. This is the Hex0/Forth precedent.
