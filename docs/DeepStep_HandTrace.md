# DeepStep Hand Trace: append([1,2], [3])

This document traces through the work-stack machine step by step.

## Setup

### Input
```json
{
  "op": "append",
  "xs": {"head": 1, "tail": {"head": 2, "tail": null}},
  "ys": {"head": 3, "tail": null}
}
```

### Domain Projections
```json
[
  {
    "id": "append.base",
    "pattern": {"op": "append", "xs": null, "ys": {"var": "ys"}},
    "body": {"var": "ys"}
  },
  {
    "id": "append.recursive",
    "pattern": {"op": "append", "xs": {"head": {"var": "h"}, "tail": {"var": "t"}}, "ys": {"var": "ys"}},
    "body": {"head": {"var": "h"}, "tail": {"op": "append", "xs": {"var": "t"}, "ys": {"var": "ys"}}}
  }
]
```

### Expected Result
```json
{"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": null}}}
```

---

## State Schema

```
{
  "mode": "deep_eval",
  "focus": <current node>,
  "context": [<stack of frames>],
  "changed": <bool>
}
```

Context frame for dict:
```
{"type": "dict", "key": <current_key>, "done": {<processed>}, "remaining": [<unprocessed_keys>], "parent_keys": [<all_keys>]}
```

---

## Trace

### Step 0: Initial (not wrapped yet)
```
Input: {"op": "append", "xs": {...}, "ys": {...}}
```

### Step 1: WRAP
Projection `deep.wrap` matches any non-wrapped value.

**Before:**
```json
{"op": "append", "xs": {"head": 1, "tail": {"head": 2, "tail": null}}, "ys": {"head": 3, "tail": null}}
```

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"op": "append", "xs": {"head": 1, "tail": {"head": 2, "tail": null}}, "ys": {"head": 3, "tail": null}},
  "context": [],
  "changed": false
}
```

### Step 2: TRY_REDUCE at focus
Focus is `{"op": "append", "xs": {...}, "ys": {...}}`.
Check domain projections:
- `append.base`: pattern has `"xs": null`, focus has `"xs": {"head":1,...}` → NO MATCH
- `append.recursive`: pattern has `"xs": {"head": {"var":"h"}, "tail": {"var":"t"}}`, focus matches!
  - Bindings: `{h: 1, t: {"head": 2, "tail": null}, ys: {"head": 3, "tail": null}}`

**After (reduced):**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 1, "tail": {"op": "append", "xs": {"head": 2, "tail": null}, "ys": {"head": 3, "tail": null}}},
  "context": [],
  "changed": true
}
```

### Step 3: RESTART (changed=true, context=[])
Since `changed=true` and `context=[]`, we restart with `changed=false`.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 1, "tail": {"op": "append", "xs": {"head": 2, "tail": null}, "ys": {"head": 3, "tail": null}}},
  "context": [],
  "changed": false
}
```

### Step 4: TRY_REDUCE at focus
Focus is `{"head": 1, "tail": {...}}`.
Check domain projections:
- `append.base`: needs `"op": "append"` → NO MATCH (focus has "head", "tail")
- `append.recursive`: needs `"op": "append"` → NO MATCH

No domain projection matches. Need to DESCEND.

### Step 5: DESCEND_DICT
Focus is dict with keys `["head", "tail"]` (sorted).
Push frame, focus on first value.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": 1,
  "context": [
    {
      "type": "dict",
      "key": "head",
      "done": {},
      "remaining": ["tail"],
      "parent": {"head": 1, "tail": {"op": "append", ...}}
    }
  ],
  "changed": false
}
```

### Step 6: TRY_REDUCE at focus
Focus is `1` (primitive).
No domain projection matches primitives. Not a dict or list, so can't descend.
This is a LEAF - move to sibling.

### Step 7: SIBLING_DICT
Focus `1` is done. `remaining = ["tail"]` is non-empty.
Record result, move to next key.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"op": "append", "xs": {"head": 2, "tail": null}, "ys": {"head": 3, "tail": null}},
  "context": [
    {
      "type": "dict",
      "key": "tail",
      "done": {"head": 1},
      "remaining": [],
      "parent": {...}
    }
  ],
  "changed": false
}
```

### Step 8: TRY_REDUCE at focus
Focus is `{"op": "append", "xs": {"head": 2, "tail": null}, "ys": {...}}`.
Check domain projections:
- `append.base`: needs `"xs": null` → NO MATCH
- `append.recursive`: pattern matches!
  - Bindings: `{h: 2, t: null, ys: {"head": 3, "tail": null}}`

**After (reduced):**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 2, "tail": {"op": "append", "xs": null, "ys": {"head": 3, "tail": null}}},
  "context": [
    {
      "type": "dict",
      "key": "tail",
      "done": {"head": 1},
      "remaining": [],
      "parent": {...}
    }
  ],
  "changed": true
}
```

### Step 9: Check - still have context, so continue traversal
Focus changed, but we're mid-traversal. Keep going (or restart?).

**Decision point**: After a reduction mid-traversal, do we:
A) Continue traversal from current position
B) Restart from root

Option A is more efficient. Option B is simpler (always restart when changed).

Let's go with **Option B** for simplicity in v0.

### Step 9 (revised): RESTART
Since `changed=true`, restart from root.
First, we need to ASCEND to rebuild the tree, then restart.

Actually, let me reconsider. If we've reduced something mid-tree, we need to:
1. Ascend (rebuild the tree with the new value)
2. Once at root with context=[], then restart

Let me redo from Step 8...

### Step 8 (continued): After reduction, ASCEND
We reduced the focus. Now `remaining=[]` so we should ascend.

**After ASCEND:**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 1, "tail": {"head": 2, "tail": {"op": "append", "xs": null, "ys": {"head": 3, "tail": null}}}},
  "context": [],
  "changed": true
}
```

### Step 9: RESTART
Context is empty, changed=true. Restart.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 1, "tail": {"head": 2, "tail": {"op": "append", "xs": null, "ys": {"head": 3, "tail": null}}}},
  "context": [],
  "changed": false
}
```

### Step 10: TRY_REDUCE at focus
Focus is `{"head": 1, "tail": {...}}`. No match on domain projections.

### Step 11: DESCEND_DICT
Focus on "head" value.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": 1,
  "context": [{"type": "dict", "key": "head", "done": {}, "remaining": ["tail"], ...}],
  "changed": false
}
```

### Step 12: SIBLING (1 is leaf)
Move to "tail".

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 2, "tail": {"op": "append", "xs": null, "ys": {"head": 3, "tail": null}}},
  "context": [{"type": "dict", "key": "tail", "done": {"head": 1}, "remaining": [], ...}],
  "changed": false
}
```

### Step 13: TRY_REDUCE
Focus is `{"head": 2, "tail": {...}}`. No match.

### Step 14: DESCEND_DICT
Focus on "head" value.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": 2,
  "context": [
    {"type": "dict", "key": "head", "done": {}, "remaining": ["tail"], ...},
    {"type": "dict", "key": "tail", "done": {"head": 1}, "remaining": [], ...}
  ],
  "changed": false
}
```

### Step 15: SIBLING
Move to "tail".

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"op": "append", "xs": null, "ys": {"head": 3, "tail": null}},
  "context": [
    {"type": "dict", "key": "tail", "done": {"head": 2}, "remaining": [], ...},
    {"type": "dict", "key": "tail", "done": {"head": 1}, "remaining": [], ...}
  ],
  "changed": false
}
```

### Step 16: TRY_REDUCE
Focus is `{"op": "append", "xs": null, "ys": {...}}`.
- `append.base`: pattern `{"op": "append", "xs": null, "ys": {"var": "ys"}}` MATCHES!
  - Bindings: `{ys: {"head": 3, "tail": null}}`

**After (reduced):**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 3, "tail": null},
  "context": [
    {"type": "dict", "key": "tail", "done": {"head": 2}, "remaining": [], ...},
    {"type": "dict", "key": "tail", "done": {"head": 1}, "remaining": [], ...}
  ],
  "changed": true
}
```

### Step 17: ASCEND (remaining=[], context non-empty)
Rebuild inner dict.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 2, "tail": {"head": 3, "tail": null}},
  "context": [
    {"type": "dict", "key": "tail", "done": {"head": 1}, "remaining": [], ...}
  ],
  "changed": true
}
```

### Step 18: ASCEND (remaining=[], context non-empty)
Rebuild outer dict.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": null}}},
  "context": [],
  "changed": true
}
```

### Step 19: RESTART
Context empty, changed=true.

**After:**
```json
{
  "mode": "deep_eval",
  "focus": {"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": null}}},
  "context": [],
  "changed": false
}
```

### Step 20-28: Full traversal, no reductions
Traverse entire tree, find no `{"op": "append", ...}` nodes.
Eventually return to root with `changed=false`.

### Step 29: UNWRAP
Context empty, changed=false. Done!

**Final result:**
```json
{"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": null}}}
```

---

## Summary

| Phase | Steps | What happened |
|-------|-------|---------------|
| First reduction | 1-3 | Reduced root append, got nested append in tail |
| Second reduction | 4-9 | Descended to tail, reduced append, ascended |
| Third reduction | 10-18 | Descended deep, reduced final append, ascended |
| Verification | 19-29 | Full traversal, no more appends, unwrap |

**Total steps**: ~29 kernel iterations for append([1,2], [3])

**Reductions**: 3 (one per element in first list, plus base case)

---

## Key Observations

1. **Restart-on-change is simple but expensive**: We restart from root after each reduction, causing repeated traversal.

2. **Alternative**: Continue from current position after reduction. More complex projections but fewer steps.

3. **Context stack works**: The zipper-like context correctly tracks position and rebuilds tree.

4. **Projections needed**:
   - WRAP (entry)
   - TRY_REDUCE (apply domain projections)
   - DESCEND_DICT (push frame, focus on first value)
   - DESCEND_LIST (similar for lists)
   - SIBLING_DICT (move to next key)
   - SIBLING_LIST (move to next element)
   - ASCEND_DICT (pop frame, rebuild dict)
   - ASCEND_LIST (pop frame, rebuild list)
   - RESTART (changed=true at root)
   - UNWRAP (changed=false at root)
   - LEAF (primitive, trigger sibling/ascend)

---

## Open Questions Resolved

1. **What happens after mid-tree reduction?**
   → Immediately ascend (rebuild tree), then restart from root.

2. **How do we know when to ascend vs sibling?**
   → Check `remaining`: if empty, ascend; if non-empty, sibling.

3. **How do we handle primitives?**
   → They're leaves. Trigger sibling (if remaining) or ascend (if not).
