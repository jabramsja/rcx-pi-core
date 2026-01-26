# DeepStep Specification v0

Status: VECTOR (design-only)

## Purpose

Define `deep_step` - a mechanism to find and reduce nested sub-expressions without host recursion. This is the key blocker for Phase 3 (EVAL_SEED as Mu).

## Problem Statement

Current `step()` only matches at the ROOT level:

```
Input:  {"op": "append", "xs": [1,2], "ys": [3]}
Step 1: {"head": 1, "tail": {"op": "append", "xs": [2], "ys": [3]}}
Step 2: ??? - step() doesn't find nested {"op": "append"}
```

After step 1, the reducible expression `{"op": "append", ...}` is NESTED inside `tail`. The current `step()` function only checks the root, so it returns unchanged (stall) even though work remains.

## Semantic Question

**"How do we express tree traversal as Mu projections, using the kernel loop for iteration instead of Python recursion?"**

## Design Constraints

1. **No host recursion** - Must work with flat projections + kernel loop
2. **Finite projections** - Cannot have one projection per tree depth
3. **Pure Mu** - All state must be JSON-compatible (no Python objects)
4. **Correct** - Must produce same results as recursive `deep_step`

## Solution: Work-Stack Machine

Instead of Python's call stack tracking "where we are" in the tree, we use an EXPLICIT work stack as Mu structure.

### State Schema

```json
{
  "mode": "deep_eval",
  "focus": <current node being examined>,
  "context": [<stack of frames - where we came from>],
  "projections": [<the domain projections to apply>],
  "changed": false
}
```

### Context Frame Schema

A context frame records "the hole we descended into":

```json
{
  "type": "dict_value",
  "key": "tail",
  "parent_keys": ["head", "tail"],
  "done": {"head": 1},
  "remaining": []
}
```

Meaning: We're examining the value at key "tail" in a dict. We've already processed key "head" (result in `done`). No keys remaining after "tail".

For lists:
```json
{
  "type": "list_elem",
  "index": 2,
  "done": [1, 2],
  "remaining": [4, 5]
}
```

### Projection Categories

The work-stack machine needs these projection categories:

#### 1. Wrap (entry point)
Transform plain value into eval state:
```json
{
  "id": "deep.wrap",
  "pattern": {"var": "v"},
  "guard": "not already wrapped",
  "body": {
    "mode": "deep_eval",
    "focus": {"var": "v"},
    "context": [],
    "projections": <injected>,
    "changed": false
  }
}
```

#### 2. Try Reduce at Focus
If focus matches any domain projection, apply it:
```json
{
  "id": "deep.reduce",
  "pattern": {
    "mode": "deep_eval",
    "focus": {"var": "f"},
    "context": {"var": "ctx"},
    ...
  },
  "guard": "f matches some domain projection",
  "body": {
    "mode": "deep_eval",
    "focus": <result of applying projection to f>,
    "context": {"var": "ctx"},
    "changed": true
  }
}
```

#### 3. Descend into Dict
If focus is a dict and not reducible, descend into first value:
```json
{
  "id": "deep.descend_dict",
  "pattern": {
    "mode": "deep_eval",
    "focus": {"var": "d"},  // where d is a dict
    "context": {"var": "ctx"},
    ...
  },
  "guard": "d is dict, d not reducible, d has keys",
  "body": {
    "mode": "deep_eval",
    "focus": <d[first_key]>,
    "context": [
      {"type": "dict_value", "key": <first_key>, "done": {}, "remaining": <rest_keys>},
      ...ctx
    ],
    ...
  }
}
```

#### 4. Descend into List
If focus is a list and not reducible, descend into first element:
```json
{
  "id": "deep.descend_list",
  "pattern": {
    "mode": "deep_eval",
    "focus": [{"var": "first"}, {"var": "rest"}],  // non-empty list
    "context": {"var": "ctx"},
    ...
  },
  "body": {
    "mode": "deep_eval",
    "focus": {"var": "first"},
    "context": [
      {"type": "list_elem", "index": 0, "done": [], "remaining": {"var": "rest"}},
      ...ctx
    ],
    ...
  }
}
```

#### 5. Sibling (move to next key/element)
After processing one child, move to next:
```json
{
  "id": "deep.sibling_dict",
  "pattern": {
    "mode": "deep_eval",
    "focus": {"var": "v"},  // just finished this
    "context": [
      {"type": "dict_value", "key": {"var": "k"}, "done": {"var": "done"}, "remaining": [{"var": "next"}, {"var": "rest"}]},
      {"var": "outer_ctx"}
    ],
    ...
  },
  "guard": "remaining is non-empty",
  "body": {
    "mode": "deep_eval",
    "focus": <parent[next]>,
    "context": [
      {"type": "dict_value", "key": {"var": "next"}, "done": <done + {k: v}>, "remaining": {"var": "rest"}},
      {"var": "outer_ctx"}
    ],
    ...
  }
}
```

#### 6. Ascend (pop frame, plug result)
When all children done, reconstruct parent:
```json
{
  "id": "deep.ascend_dict",
  "pattern": {
    "mode": "deep_eval",
    "focus": {"var": "v"},
    "context": [
      {"type": "dict_value", "key": {"var": "k"}, "done": {"var": "done"}, "remaining": []},
      {"var": "outer_ctx"}
    ],
    ...
  },
  "guard": "remaining is empty",
  "body": {
    "mode": "deep_eval",
    "focus": <done + {k: v}>,  // reconstructed dict
    "context": {"var": "outer_ctx"},
    ...
  }
}
```

#### 7. Unwrap (exit point)
When context empty and nothing changed, return result:
```json
{
  "id": "deep.unwrap",
  "pattern": {
    "mode": "deep_eval",
    "focus": {"var": "result"},
    "context": [],
    "changed": false
  },
  "body": {"var": "result"}
}
```

#### 8. Restart (another pass)
When context empty but something changed, start over:
```json
{
  "id": "deep.restart",
  "pattern": {
    "mode": "deep_eval",
    "focus": {"var": "result"},
    "context": [],
    "changed": true
  },
  "body": {
    "mode": "deep_eval",
    "focus": {"var": "result"},
    "context": [],
    "changed": false
  }
}
```

## Example: Append [1,2] ++ [3]

Initial:
```json
{"op": "append", "xs": {"head": 1, "tail": {"head": 2, "tail": null}}, "ys": {"head": 3, "tail": null}}
```

### Trace (simplified)

1. **Wrap**: Create eval state with focus = input
2. **Try reduce**: Focus matches `append.recursive`, reduce it
3. **Result**: `{"head": 1, "tail": {"op": "append", "xs": {...}, "ys": {...}}}`
4. **Restart**: changed=true, so start over with new focus
5. **Try reduce**: Focus is dict but not `{op: append}`, no match
6. **Descend dict**: Push frame for "head", focus on 1
7. **Try reduce**: 1 is primitive, no match
8. **Sibling**: Move to "tail"
9. **Descend dict**: Focus on `{"op": "append", ...}`
10. **Try reduce**: Matches! Reduce to `{"head": 2, "tail": {...}}`
11. **Restart**: changed=true
12. ... continue until no more `{op: append}` anywhere ...
13. **Unwrap**: context empty, changed=false, return result

Final:
```json
{"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": null}}}
```

## Complexity Analysis

| Aspect | Complexity |
|--------|------------|
| Projections needed | ~12-15 (fixed, not per depth) |
| Steps per reduction | O(tree_size) to find reducible node |
| Total steps | O(reductions × tree_size) |
| Space (context stack) | O(tree_depth) |

This is more steps than recursive `deep_step`, but each step is O(1) work by the kernel.

## Challenges

### 1. Guard Conditions
Some projections need "guards" (conditions beyond pattern matching):
- "d is a dict" - could encode as `{"_type": "dict", "value": {...}}`
- "d not reducible" - need to check no domain projection matches
- "remaining is non-empty" - pattern matching can handle this

**Option A**: Encode type info in Mu (verbose but pure)
**Option B**: Extend match to support type predicates (more power)

### 2. Dict Key Ordering
Projections need to iterate dict keys in consistent order. Use sorted keys.

### 3. Domain Projection Injection
The `deep_eval` state needs access to domain projections. Options:
- Inline them in the state (verbose)
- Reference by ID + global lookup (requires kernel support)
- Fixed at wrap time (simplest)

## Alternative: One-Level-At-A-Time

A simpler (but slower) approach:

```
Pass 1: Try to reduce at depth 0 (root)
Pass 2: Try to reduce at depth 1 (immediate children)
Pass 3: Try to reduce at depth 2
...
```

Each pass uses the current `step()` on progressively nested sub-structures. Requires tracking "current depth" and "did anything change this pass".

**Pros**: Simpler projections
**Cons**: O(depth × tree_size) per reduction, very slow for deep trees

## Non-Goals (v0)

- Parallel reduction (reduce multiple sites at once)
- Lazy evaluation (reduce only when needed)
- Memoization (cache reduced sub-expressions)
- Optimal ordering (e.g., innermost-first)

These can be added in later versions.

## Test Plan

### Unit tests
- `test_wrap_unwrap` - Wrap value, no reductions, unwrap unchanged
- `test_single_reduction` - One reducible node at root
- `test_nested_reduction` - Reducible node at depth 2
- `test_multiple_reductions` - Several reducible nodes at different depths
- `test_empty_structures` - Empty dict, empty list
- `test_deep_nesting` - Tree depth 10+

### Integration tests
- `test_append_empty` - append([], ys) = ys
- `test_append_single` - append([1], [2]) = [1,2]
- `test_append_multi` - append([1,2,3], [4,5]) = [1,2,3,4,5]
- `test_countdown_peano` - Peano numeral countdown

### Property tests
- For any tree T and projections P: `deep_step(P, T)` produces same result as Python recursive version

## Promotion Checklist (VECTOR → NEXT)

- [ ] State schema finalized
- [ ] All projection categories defined (with concrete Mu)
- [ ] Guard condition strategy decided
- [ ] Example worked through completely (all 12+ steps)
- [ ] Complexity acceptable for Phase 3 goals
- [ ] Alternative approaches considered and rejected/deferred

## Next Steps

1. ~~Write this design doc~~ ✓
2. Work through append example BY HAND (all steps, all frames)
3. Decide on guard condition approach
4. Write concrete projections (actual Mu JSON)
5. Implement and test

## References

- `prototypes/linked_list_append.json` - Discovery of deep_step need
- `docs/EVAL_SEED.v0.md` - Current EVAL_SEED spec
- Zipper data structure - functional tree navigation
- Abstract machines (SECD, CEK) - stack-based evaluation
