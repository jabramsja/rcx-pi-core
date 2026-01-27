# Self-Hosting Specification v0

Status: **PHASE 6d COMPLETE** - Iterative validation, code cleanup, debt reduced to 11

**Important distinction**:
- ✓ **Algorithmic self-hosting**: match/subst ALGORITHMS are expressed as Mu projections
- ✓ **Behavioral parity**: `step_mu == step` for all inputs (33+ tests prove this)
- ✗ **Operational self-hosting**: The projections are still EXECUTED by Python's `step()`

See structural-proof agent report for detailed analysis.

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
will ONLY match things with that structure. This is how `seeds/eval.v1.json` works.

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

The existing `seeds/eval.v1.json` shows how to express traversal as Mu projections.
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
| Conflicts | **Linear patterns only** (Phase 4a) | Simplify first, add non-linear later |
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

### Total Projection Count

| Component | Projections |
|-----------|-------------|
| Match     | 6-8         |
| Substitute| 5-6         |
| Lookup    | 2-3         |
| **Total** | **13-17**   |

This aligns with the Expert agent's estimate of 10-15 projections.

## Phased Implementation

### Phase 4a: Match as Mu ✅ COMPLETE
- 12 match projections in `seeds/match.v1.json`
- Implementation: `rcx_pi/match_mu.py`
- 23 parity tests in `tests/test_match_parity.py`

### Phase 4b: Substitute as Mu ✅ COMPLETE
- 9 substitute projections in `seeds/subst.v1.json`
- Implementation: `rcx_pi/subst_mu.py`
- 17 parity tests in `tests/test_subst_parity.py`

### Phase 4c: Binding Lookup ✅ COMPLETE
- Integrated into substitute projections (no separate seed needed)
- Lookup done via linked list traversal in subst projections

### Phase 4d: Integration Testing ✅ COMPLETE
- 67 total tests verifying match_mu + subst_mu work together:
  - `tests/test_apply_mu_integration.py` - 28 parity tests
  - `tests/structural/test_apply_mu_grounding.py` - 27 structural tests
  - `tests/test_apply_mu_fuzzer.py` - 12 property-based tests (Hypothesis)
- Shared utility: `apply_mu()` in `tests/conftest.py`
- Agent review: verifier=APPROVE, adversary=HARDENED, expert=ACCEPTABLE

### Phase 5: Self-Hosting ✅ COMPLETE
- `rcx_pi/step_mu.py`: `apply_mu()`, `step_mu()`, `run_mu()`
- Implementation: step_mu uses match_mu + subst_mu (Mu projections, not Python recursion)
- `tests/test_step_mu_parity.py`: 22 parity tests verifying step_mu == step
- `tests/test_self_hosting_v0.py`: 11 self-hosting tests including trace comparison
- Critical test: `test_self_hosting_complete` - Python trace == Mu trace
- Note: Operations (match/subst) are self-hosted; kernel loop is still Python for-loop (Phase 6+ goal)

### Phase 6a: Lookup as Mu Projections ✅ COMPLETE
- Added `subst.lookup.found` and `subst.lookup.next` projections to `seeds/subst.v1.json`
- Lookup is now structural: pattern matching with non-linear vars (same name binds same value)
- Removed 2 `@host_builtin` decorators from `subst_mu.py`
- 37 subst parity tests pass with structural lookup

### Phase 6b: Classification as Mu Projections ✅ COMPLETE
- Created `seeds/classify.v1.json` with 6 projections for linked list classification
- Created `rcx_pi/selfhost/classify_mu.py` for projection-based classification
- `denormalize_from_match()` uses `classify_linked_list()` instead of `is_dict_linked_list()`
- Classification distinguishes dict-encoding (all kv-pairs with string keys) from list-encoding
- Removed 2 `@host_builtin` decorators from `match_mu.py`
- 26 tests in `tests/test_classify_mu.py`

### Phase 6c: Type Tags and Iterative Normalization ✅ COMPLETE
- **Iterative normalization**: `normalize_for_match()` and `denormalize_from_match()` converted from recursive to iterative with explicit stack
- Removed 2 `@host_recursion` decorators from `match_mu.py`
- **Type tags** resolve list/dict ambiguity (previously `[["a", 1]]` and `{"a": 1}` normalized identically):
  - Lists get `_type: "list"`, dicts get `_type: "dict"` at root node
  - `VALID_TYPE_TAGS` whitelist + `validate_type_tag()` for security
  - New projections: `match.typed.descend`, `subst.typed.{descend,sibling,ascend}`
- `classify_linked_list()` fast-path for type-tagged structures
- 24 new property-based fuzzer tests (`tests/test_type_tags_fuzzer.py`)
- All 1022 self-hosting tests pass

## Resolved Questions

| Question | Resolution |
|----------|------------|
| Kernel type primitives? | **No** - structure IS type |
| Dict key ordering? | **sorted() in JSON serialization** |
| Non-linear patterns? | **Linear only for Phase 4** |
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
| Deep nesting DoS | MAX_MU_DEPTH=200 limit |
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

1. [x] `match()` expressed as Mu projections (`seeds/match.v1.json`, 12 projections)
2. [x] `substitute()` expressed as Mu projections (`seeds/subst.v1.json`, 9 projections)
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
  - `kernel.py` - 4 kernel primitives
  - `eval_seed.py` - EVAL_SEED evaluator (match, substitute, step)
  - `match_mu.py` - Pattern matching as Mu projections + normalization
  - `subst_mu.py` - Substitution as Mu projections
  - `step_mu.py` - Self-hosting step (uses match_mu + subst_mu)
  - `classify_mu.py` - Linked list classification as Mu projections
- `rcx_pi/deep_eval.py` - Deep evaluation machinery
- `seeds/` - Mu projection definitions:
  - `eval.v1.json` - EVAL_SEED traversal projections
  - `match.v1.json` - Match projections (13 rules, includes typed.descend)
  - `subst.v1.json` - Substitute projections (13 rules, includes lookup + typed)
  - `classify.v1.json` - Classification projections (6 rules)

## Next Steps

**Completed (Phase 4a-4d):**
1. [x] Review this doc with agents (verifier, adversary, expert)
2. [x] Decide on type dispatch approach - **Structure IS type**
3. [x] Decide on dict iteration approach - **Fixed key patterns**
4. [x] Phase 4a: match projections (`seeds/match.v1.json`, `rcx_pi/selfhost/match_mu.py`)
5. [x] Phase 4b: substitute projections (`seeds/subst.v1.json`, `rcx_pi/selfhost/subst_mu.py`)
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
14. [x] **Debt reduced!** 15 total (11 tracked + 3 AST_OK + 1 review), down from 23

**Phase 7+ (Future):**
- Self-host the kernel loop (projection selection as Mu projections)
- Self-host iteration itself (recursion as structural transformation)
- These are "scaffolding debt", not required for operational self-hosting
