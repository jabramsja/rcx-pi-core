# DeepStep Guard Conditions: Decision

## Problem

Some projections need "guard conditions" beyond pattern matching:
- "Is focus a dict?"
- "Is remaining list empty?"
- "Does focus match any domain projection?"

How do we express these in pure Mu without host logic?

## Solution: Projection Ordering

**Key insight**: The ORDER of projections provides guard logic.

When `step()` tries projections in order:
1. First matching projection wins
2. Later projections only match if earlier ones didn't
3. This IS the guard condition

### Example: TRY_REDUCE vs DESCEND

```json
[
  // Domain projections first (TRY_REDUCE)
  {"pattern": {"op": "append", "xs": null, ...}, "body": ...},
  {"pattern": {"op": "append", "xs": {"head": ..., "tail": ...}, ...}, "body": ...},

  // DESCEND_DICT only matches if above didn't
  {"pattern": {"mode": "deep_eval", "focus": {"var": "d"}, ...}, "body": ...}
]
```

If focus is `{"op": "append", ...}`, domain projections match first.
If focus is `{"head": 1, "tail": ...}`, domain projections don't match, DESCEND matches.

### Pattern Matching CAN Distinguish Types

| Type | Pattern that matches |
|------|---------------------|
| Dict | `{...}` with specific keys |
| List | `[...]` with specific structure |
| Empty list | `[]` |
| Non-empty list | `[{"var": "first"}, {"var": "rest"}]` (if we support rest patterns) |
| Null | `null` |
| Primitive | Catch-all `{"var": "x"}` after dict/list patterns fail |

### Remaining Empty vs Non-Empty

```json
// SIBLING - remaining is non-empty
{
  "pattern": {
    "mode": "deep_eval",
    "context": [
      {"remaining": [{"var": "next"}, {"var": "more"}], ...},
      {"var": "outer"}
    ],
    ...
  },
  "body": ...
}

// ASCEND - remaining is empty (matches after SIBLING fails)
{
  "pattern": {
    "mode": "deep_eval",
    "context": [
      {"remaining": [], ...},
      {"var": "outer"}
    ],
    ...
  },
  "body": ...
}
```

## The One Hard Case: "Does focus match domain projections?"

This is tricky because we'd need to try ALL domain projections.

### Solution: Separate phases

Instead of mixing domain projections with machine projections, we use TWO projection lists:

1. **Phase: TRY_REDUCE**
   - Try domain projections on focus
   - If any match: apply it, set changed=true
   - If none match: set a "tried" flag

2. **Phase: NAVIGATE**
   - DESCEND/SIBLING/ASCEND projections
   - Only run after TRY_REDUCE phase

### Implementation via mode sub-states

```json
{
  "mode": "deep_eval",
  "phase": "try_reduce",  // or "navigate"
  "focus": ...,
  "context": ...,
  "changed": false
}
```

Projections:
```json
[
  // TRY_REDUCE phase: try domain projections
  {"pattern": {"mode": "deep_eval", "phase": "try_reduce", "focus": {"op": "append", "xs": null, ...}, ...}, ...},
  {"pattern": {"mode": "deep_eval", "phase": "try_reduce", "focus": {"op": "append", "xs": {...}, ...}, ...}, ...},

  // If no domain projection matched, transition to navigate phase
  {"pattern": {"mode": "deep_eval", "phase": "try_reduce", ...}, "body": {..., "phase": "navigate", ...}},

  // NAVIGATE phase projections
  {"pattern": {"mode": "deep_eval", "phase": "navigate", "focus": {"var": "d"}, "context": [...], ...}, ...}
]
```

## Alternative: Inline domain projections

For simplicity in v0, we could INLINE the domain projections into the machine:

```json
// Combined projection: if focus matches append.base, reduce it
{
  "pattern": {
    "mode": "deep_eval",
    "focus": {"op": "append", "xs": null, "ys": {"var": "ys"}},
    ...
  },
  "body": {
    "mode": "deep_eval",
    "focus": {"var": "ys"},
    "changed": true,
    ...
  }
}
```

**Pros**: Simpler, no phase state
**Cons**: Domain projections are baked into machine (not configurable)

For Phase 3 proof-of-concept, inline is acceptable. Later versions can parameterize.

## Decision: Inline + Ordering

For DeepStep v0:
1. **Inline domain projections** into the machine projections
2. **Use projection ordering** for guards (domain first, then navigate)
3. **Pattern matching** distinguishes dict vs list vs primitive
4. **List patterns** for empty vs non-empty remaining

No host logic needed. Pure structural.

## Final Projection Order

```
1. REDUCE projections (inlined domain logic)
   - append.base wrapped in deep_eval
   - append.recursive wrapped in deep_eval

2. DESCEND projections (focus is dict/list, not reducible)
   - descend_dict
   - descend_list

3. LEAF projection (focus is primitive)
   - triggers sibling or ascend

4. SIBLING projections (remaining non-empty)
   - sibling_dict
   - sibling_list

5. ASCEND projections (remaining empty)
   - ascend_dict
   - ascend_list

6. RESTART projection (context=[], changed=true)

7. UNWRAP projection (context=[], changed=false)

8. WRAP projection (not yet in deep_eval mode)
```

The order IS the logic.
