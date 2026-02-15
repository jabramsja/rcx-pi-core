<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-02-03
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

# Universal Eval Seed (L4 Alternative Design)

**Status:** SINK (research question) - 9-agent reviewed 2026-02-02
**Supersedes:** None (alternative to RecursiveKernel.v0.md approach)
**Related:** `mu/docs/core/RecursiveKernel.v0.md`, `mu/docs/core/MetaCircularKernel.v0.md`

---

## Overview

This document captures an alternative L4 design ("Golden Loop") that expresses the meta-circular evaluator loop as Mu projections. Unlike the approach in `RecursiveKernel.v0.md` (which accepts bootstrap primitives as irreducible), this design attempts to make the kernel loop itself structural.

**Key difference from RecursiveKernel.v0.md:**
- RecursiveKernel: Accept `eval_step` for-loop as PRIMITIVE (like Forth's NEXT)
- UniversalEval: Express the loop as 5-7 vm.* projections

**9-Agent Review Summary (2026-02-02):**

| Agent | Verdict | Key Finding |
|-------|---------|-------------|
| Advisor | OPTIONS_PROVIDED | Recommends VECTOR status, not immediate implementation |
| Verifier | NEEDS_DISCUSSION | Structurally sound but needs concrete projections |
| Adversary | SECURE | Existing L2 defenses cover this design |
| Expert | MINIMAL (with gap) | Missing kernel.stall and kernel.unwrap equivalents |
| Structural-proof | PROVEN (L2) | Continuation threading IS structural |
| Grounding | UNGROUNDED | L4 doesn't exist; 3 of 5 test cases grounded for L2 |
| Fuzzer | ROBUST (L2) | L2 passes 10,400+ fuzz inputs; L4 cursor untestable |
| Translator | NEEDS_DISCUSSION | L4 spec doesn't exist in codebase yet |
| Visualizer | Diagrams provided | 6 Mermaid diagrams of L2 state machine |

---

## The Spec (universal_eval.v0.json)

```json
{
  "meta": {
    "version": "0.1.0",
    "name": "UNIVERSAL_EVAL_SEED",
    "description": "Meta-circular evaluator loop expressed as Mu projections (protocol-compatible with kernel.v1 + match.v2 + subst.v2)",
    "doc": "mu/docs/core/UniversalEval.v0.md",
    "invariants": [
      "Use existing kernel ABI: _step/_projs entry, match.v2 and subst.v2 protocols",
      "Continuations carried only via _match_ctx and _subst_ctx",
      "No new host semantics (pure Mu)",
      "Kernel projections must run first",
      "First-match-wins ordering is security-critical"
    ]
  },
  "projections": [
    {
      "id": "vm.boot",
      "description": "BOOT: Lift BOOT_L4 into VM state; use existing kernel _step/_projs",
      "pattern": {
        "_step": {
          "BOOT_L4": {
            "universe": { "var": "U" },
            "target_state": { "var": "S" }
          }
        },
        "_projs": { "var": "_ignore" }
      },
      "body": {
        "_step": {
          "vm": {
            "cursor": { "var": "U" },
            "root":   { "var": "U" },
            "state":  { "var": "S" }
          }
        },
        "_projs": { "var": "U" }
      }
    },

    {
      "id": "vm.try",
      "description": "FETCH/TEST: Prepare match against current projection in VM cursor",
      "pattern": {
        "_mode": "kernel",
        "_phase": "try",
        "_input": {
          "vm": {
            "cursor": {
              "head": {
                "pattern": { "var": "P" },
                "body":    { "var": "B" }
              },
              "tail": { "var": "REST" }
            },
            "root":  { "var": "ROOT" },
            "state": { "var": "S" }
          }
        },
        "_remaining": { "var": "_unused" }
      },
      "body": {
        "match": {
          "pattern": { "var": "P" },
          "value":   { "var": "S" }
        },
        "_match_ctx": {
          "vm_state": { "var": "S" },
          "vm_body":  { "var": "B" },
          "vm_rest":  { "var": "REST" },
          "vm_root":  { "var": "ROOT" }
        }
      }
    },

    {
      "id": "vm.match_success",
      "description": "CHECK_MATCH success -> delegate to subst with ctx",
      "pattern": {
        "_mode": "match_done",
        "_status": "success",
        "_bindings": { "var": "BIND" },
        "_match_ctx": {
          "vm_state": { "var": "S" },
          "vm_body":  { "var": "BODY" },
          "vm_rest":  { "var": "REST" },
          "vm_root":  { "var": "ROOT" }
        }
      },
      "body": {
        "subst": {
          "body":     { "var": "BODY" },
          "bindings": { "var": "BIND" }
        },
        "_subst_ctx": {
          "vm_rest": { "var": "REST" },
          "vm_root": { "var": "ROOT" }
        }
      }
    },

    {
      "id": "vm.match_fail",
      "description": "CHECK_MATCH failure -> advance cursor (structural recursion)",
      "pattern": {
        "_mode": "match_done",
        "_status": "no_match",
        "_match_ctx": {
          "vm_state": { "var": "S" },
          "vm_body":  { "var": "_ignore" },
          "vm_rest":  { "var": "REST" },
          "vm_root":  { "var": "ROOT" }
        }
      },
      "body": {
        "_mode": "kernel",
        "_phase": "try",
        "_input": {
          "vm": {
            "cursor": { "var": "REST" },
            "root":   { "var": "ROOT" },
            "state":  { "var": "S" }
          }
        },
        "_remaining": null
      }
    },

    {
      "id": "vm.subst_success",
      "description": "FINALIZE: Subst result -> restart scan at root",
      "pattern": {
        "_mode": "subst_done",
        "_result": { "var": "NEW_STATE" },
        "_subst_ctx": {
          "vm_rest": { "var": "_ignore" },
          "vm_root": { "var": "ROOT" }
        }
      },
      "body": {
        "_mode": "kernel",
        "_phase": "try",
        "_input": {
          "vm": {
            "cursor": { "var": "ROOT" },
            "root":   { "var": "ROOT" },
            "state":  { "var": "NEW_STATE" }
          }
        },
        "_remaining": null
      }
    }
  ]
}
```

---

## Design Analysis

### What This Achieves

1. **VM State as Mu Data**: `{cursor, root, state}` is pure JSON
2. **Continuation Threading**: Uses existing `_match_ctx`/`_subst_ctx` protocol
3. **First-Match-Wins**: Projection ordering provides dispatch
4. **Structural Cursor**: Linked-list advancement (head→tail), no arithmetic

### What This Does NOT Achieve

1. **Bootstrap Elimination**: Something still runs vm.boot (Python or meta-kernel)
2. **eval_step Replacement**: The projection application primitive remains
3. **True Meta-Circularity**: Projections don't select themselves without host

### Expert Finding: Missing Projections

The spec has 5 projections but is **missing 2 equivalents** from kernel.v1.json:

| kernel.v1 | universal_eval | Purpose |
|-----------|----------------|---------|
| kernel.wrap | vm.boot | Entry point |
| kernel.stall | **MISSING** | Handle cursor=null (all tried) |
| kernel.try | vm.try | Start matching |
| kernel.match_success | vm.match_success | Match worked |
| kernel.match_fail | vm.match_fail | Match failed, advance |
| kernel.subst_success | vm.subst_success | Subst done, restart |
| kernel.unwrap | **MISSING** | Extract final result |

**Recommendation:** Add vm.stall and vm.unwrap for completeness.

---

## Test Plan

### 1. BOOT_L4 Lifts Into VM State

**Input:**
```json
{
  "_step": {
    "BOOT_L4": {
      "universe": null,
      "target_state": {"x": 1}
    }
  },
  "_projs": null
}
```

**Expected (after one kernel step):**
```json
{
  "vm": {
    "cursor": null,
    "root": null,
    "state": {"x": 1}
  }
}
```

### 2. Match Success -> Subst -> Restart

**Universe (single projection):**
```json
{
  "head": {
    "pattern": {"x": {"var": "v"}},
    "body": {"x": {"var": "v"}, "y": 2}
  },
  "tail": null
}
```

**Input:**
```json
{
  "_step": {
    "BOOT_L4": {
      "universe": {"head": {...}, "tail": null},
      "target_state": {"x": 1}
    }
  },
  "_projs": null
}
```

**Expected:** VM state transformed to `{"x": 1, "y": 2}`

### 3. Match Failure -> Advance Cursor

**Universe:** Two projections, first doesn't match
**Input:** State matches only second projection
**Expected:** Cursor advances, second projection applied

### 4. Stall (No Match)

**Universe:** Single projection that doesn't match
**Input:** State incompatible with projection
**Expected:** VM state unchanged, cursor=null (stall)

### 5. Fuzzer Property

**Property:** For any (universe, state), one meta-step produces either:
- Identical VM state (stall), OR
- New VM state changed by exactly one projection

---

## The Bootstrap Question

### RecursiveKernel.v0.md Answer

> "Is 'iterate until stable' a PRIMITIVE or DERIVED operation?"
> - If **PRIMITIVE** → Accept Python substrate (honest boundary)
> - If **DERIVED** → Must express as projections (infinite regress)

RecursiveKernel chose: **PRIMITIVE** (accept for-loop like Forth's NEXT)

### UniversalEval Alternative

This spec attempts DERIVED but doesn't solve the fundamental question:

**Who runs vm.boot?**

Options:
1. Python `eval_step()` runs it → Just moved the boundary
2. vm.* projections run themselves → Infinite regress
3. Minimal fixed interpreter → Same as option 1

**Advisor recommendation:** This is valuable as a DESIGN SPEC even if the bootstrap question remains open. Document in VECTOR, don't implement until semantic question clarifies.

---

## Relationship to Existing Architecture

### Projection Load Order (If Implemented)

```
1. vm.* projections (L4 - match on BOOT_L4 or _mode: "vm")
2. kernel.* projections (L2 - match on _step/_projs or _mode: "kernel")
3. match.v2 projections (match on "match": {...})
4. subst.v2 projections (match on "subst": {...})
5. Domain projections (user-defined)
```

### Compatibility

- Uses existing `_match_ctx`/`_subst_ctx` protocol
- Uses existing `_mode`/`_phase` state machine pattern
- Uses existing `_step`/`_projs` entry format
- **No new protocol fields required**

---

## Open Questions

1. **Bootstrap elimination**: Can we make `eval_step` itself a projection? (See `RecursiveKernel.v0.md` for analysis)

2. **Termination**: How does the VM halt intentionally? Need vm.halt or reuse kernel.unwrap?

3. **Universe immutability**: ROOT never changes during evaluation - is this enforced structurally?

4. **L3 parity**: If implemented, would need JavaScript port for cross-substrate verification

5. **Debt impact**: Would this REDUCE debt (eliminate for-loop) or just MOVE it?

---

## Decision

**Current Status:** SINK (research question)

**Promotion Criteria (SINK → VECTOR):**
1. Answer: "What semantic question does this resolve that L2 doesn't?"
2. Add missing projections (`vm.stall`, `vm.unwrap`).
3. Clarify bootstrap: who runs the first projection?

**Promotion Criteria (VECTOR → NEXT):**
1. 9-agent consensus on design completeness.
2. Test plan grounded with executable tests.
3. JavaScript parity strategy defined.

---

## References

- `mu/docs/core/RecursiveKernel.v0.md` - L4 "honest boundaries" approach (implemented Phase 8a/8b)
- `mu/docs/core/MetaCircularKernel.v0.md` - L2 kernel.v1.json design (COMPLETE)
- `mu/docs/core/BootstrapPrimitives.v0.md` - The 4 irreducible primitives (mu_equal eliminated, canonical)
- `STATUS.md` - Current phase (L1/L2/L3 complete, L4 SINK)
- `mu/substrate/kernel.v1.json` - Current L2 kernel (7 projections)

---

**Author:** Claude Code (9-agent review)
**Date:** 2026-02-02
**Status:** SINK - Design captured for future reference
