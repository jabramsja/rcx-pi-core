# Self-Hosting Specification v0

Status: DESIGN (Phase 4 planning) - **REVISED based on agent feedback**

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

### Phase 4a: Match as Mu (~1-2 weeks)
- Implement 6-8 match projections
- Test parity: `match_mu(p, v) == match_python(p, v)`
- ~30 parity tests
- Deliverable: `seeds/match.v1.json`

### Phase 4b: Substitute as Mu (~1 week)
- Implement 5-6 substitute projections
- Test parity: `subst_mu(body, bindings) == subst_python(body, bindings)`
- ~20 parity tests
- Deliverable: `seeds/subst.v1.json`

### Phase 4c: Binding Lookup as Mu (~0.5 weeks)
- Implement 2-3 lookup projections
- Chain lookup into subst
- ~10 tests

### Phase 4d: Self-Hosting Test (~0.5 weeks)
- EVAL_SEED evaluates EVAL_SEED
- Trace comparison
- Success = identical traces

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

## Success Criteria

Phase 4 is complete when:

1. [ ] `match()` expressed as Mu projections (13-17 projections)
2. [ ] `substitute()` expressed as Mu projections (included above)
3. [ ] Parity tests pass: Mu-match == Python-match (30+ tests)
4. [ ] Parity tests pass: Mu-subst == Python-subst (20+ tests)
5. [ ] EVAL_SEED can evaluate EVAL_SEED (self-hosting test)
6. [ ] Traces from Python→EVAL and EVAL→EVAL are identical
7. [ ] No `@host_recursion` markers remain in evaluation path

## References

- `docs/EVAL_SEED.v0.md` - Current EVAL_SEED spec
- `docs/DeepStep.v0.md` - Deep traversal design
- `rcx_pi/eval_seed.py` - Python implementation (to be replaced)
- `rcx_pi/deep_eval.py` - Deep evaluation machinery
- `seeds/eval.v1.json` - Phase 3 traversal projections (template)

## Next Steps

1. [x] Review this doc with agents (verifier, adversary, expert) - **DONE**
2. [x] Decide on type dispatch approach - **Structure IS type**
3. [x] Decide on dict iteration approach - **Fixed key patterns**
4. [ ] Implement Phase 4a: match projections
5. [ ] Create `seeds/match.v1.json`
6. [ ] Write parity tests
