# Gate 3 Architectural Decision: Dict Key Ordering Strategy

> **Status**: See [`STATUS.md`](../STATUS.md) for current phase
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document defines the key ordering DECISION for Gate 3 only.

**Decision Status:** DECIDED - Option C (Hybrid) selected 2026-02-06
**Context:** Gate 3 requires rewriting algorithm seeds for normalized state

## Decision

**Option C (Hybrid)** selected:
- Use **strict canonical ordering** (sorted keys) for Gates 3-5
- Dicts normalize with lexicographically sorted key order
- Algorithm projections match normalized linked-list structure in that order
- This unblocks Gate 3/4 with minimal refactor risk
- L4 can introduce dict-field-access projections later to remove ordering dependence

**Rationale:**
1. Matches existing `normalize_for_match()` behavior (already sorts keys)
2. Aligns with existing docs (SelfHosting.v0.md, GuardrailsAudit.v0.md)
3. Avoids unnecessary TCB growth (no new projection types needed)
4. L4 is SINK - defer complexity until needed

---

## The Problem

Gate 3 must update `recurrence.v1.json` and `exhaustion.v1.json` to work with
normalized state. The challenge is dict key ordering in the normalized form.

### Current State (Raw Dict)
```json
{"_mode": "recurrence", "_detect_closure": true}
```

### Normalized State (Linked-List Dict)
```json
{
  "_type": "dict",
  "head": {
    "head": "_mode",
    "tail": {"head": "recurrence", "tail": null}
  },
  "tail": {
    "head": {
      "head": "_detect_closure",
      "tail": {"head": true, "tail": null}
    },
    "tail": null
  }
}
```

The normalized form encodes dict entries as a linked list. The ORDER of keys
in this list affects pattern matching - patterns must match the exact structure.

## Options

### Option A: Strict Key Ordering

Define a canonical key order for algorithm state dicts. Patterns in seeds match
this exact order.

**Example pattern:**
```json
{
  "_type": "dict",
  "head": {"head": "_mode", "tail": {"head": {"_var": "mode"}, "tail": null}},
  "tail": {"head": {"head": "_detect_closure", "tail": ...}, "tail": ...}
}
```

**Pros:**
- Simple: patterns mirror exact structure
- No new projection types needed
- Clear, auditable 1:1 mapping

**Cons:**
- Brittle: adding a new field requires updating all patterns
- Order-dependent: different normalization order = broken patterns
- L4 risk: non-Python substrates might normalize differently

### Option B: Dict Field-Access Projections

Add structural projections that can access dict fields by key, independent of
physical ordering.

**Example pattern (conceptual):**
```json
{"_dict_get": "mode", "_from": {"_var": "state"}}
```

**Pros:**
- Robust: order-independent field access
- Extensible: adding fields doesn't break existing patterns
- L4-friendly: works regardless of substrate-specific ordering

**Cons:**
- More complex: requires new projection type
- Additional work: must design and implement dict-access projection
- Larger TCB: increases minimal substrate requirements

### Option C: Hybrid Approach

Use strict ordering for Gate 3-5 (simple, gets us through L3), but design
the ordering convention with L4 in mind. Add dict-access projections later
when approaching L4.

**Pros:**
- Pragmatic: unblocks Gate 3 now
- Planned: explicitly defer complexity to when it's needed
- Documented: ordering convention serves as L4 reference

**Cons:**
- Technical debt: known refactor point at L4
- Migration: patterns must change when dict-access arrives

## Key Questions for Review

1. **Which option best serves Gates 4-5?** Gate 4 requires structural execution,
   Gate 5 requires parity. Which approach has lower risk?

2. **What's the L4 impact?** Boot0/Boot1 will need minimal substrate. Does
   dict-access projection belong in minimal TCB or is it a higher-level utility?

3. **Are there hybrid approaches** not listed here?

4. **Security implications?** Does either approach create new attack surfaces
   or validation gaps?

5. **Maintenance/auditability tradeoffs?** Which is easier to verify correct?

## Relevant Files

- `mu/closures/recurrence.v1.json` - Current algorithm seed (raw dict patterns)
- `mu/closures/exhaustion.v1.json` - Current algorithm seed
- `rcx_pi/selfhost/algorithm_adapters.py` - Gate 2 adapters
- `roadmap/AlgorithmNormalizationSpec.v0.md` - Gate 1 spec
- `roadmap/MetaCircular_Boot0_GatePlan.md` - Gate plan with L4 context
