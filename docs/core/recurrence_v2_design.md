<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-10
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/test_recurrence_production.py
-->
# Recurrence v2 Design — Hash-Trie Closure Detection

## Problem Statement

The `recurrence.v1.json` seed successfully detects closures in small test cases but **fails on production programs**. When running the Paxos deadlock demo (a 15-step trace), recurrence stalls in `_phase: "check_seen"` with `_check_list: null` and never emits `closure_detected`.

## Root Cause Analysis

**Current Implementation (recurrence.v1.json):**
- Treats `_seen` as a flat linked-list: `{"head": StateA, "tail": {"head": StateB, "tail": ...}}`
- For each new state in the trace, scans the entire `_seen` list linearly
- Uses projections `recurrence.not_in_head` to recursively traverse the list
- **Complexity: O(N²)** where N = trace length
- For 15 states: ~210 deep structural comparisons via pattern matching
- Pattern matching engine exhausts steps before completing the scan

**Evidence:**
```python
# prototypes/run_paxos_demo.py output:
# Closure Detection Output shows:
{
  "_mode": "recurrence",
  "_phase": "check_seen",  # Stuck in scanning phase
  "_check_list": null,      # Exhausted without finding match
  "_seen": null,            # Never completed building seen set
  # NO "closure_detected" field emitted
}
```

## Proposed Solution: Hash-Trie `_seen` Structure

**Design:**
1. Replace flat list with nested dictionary (radix tree) keyed by `mu_hash`
2. New `_seen` structure:
```json
{
  "c": {
    "c": {
      "2": {
        "...": {
          "_leaf": {
            "state": StateA,
            "hash": "cc2..."
          }
        }
      }
    }
  }
}
```

3. New algorithm:
   - Step A: Compute `mu_hash(new_state)` (existing primitive)
   - Step B: Navigate hash tree char-by-char using pattern matching
   - Step C: On hit, use non-linear matcher for final equality check (handles hash collisions)
   - **Complexity: O(N·k)** where k = hash length (~64 chars)

4. New projections needed (recurrence.v2.json):
   - `recurrence.hash_state` - compute state hash
   - `recurrence.navigate_hash_trie` - traverse tree by hash characters
   - `recurrence.insert_into_trie` - add new state at correct path
   - `recurrence.found_in_trie` - hash collision check with non-linear matcher

**Why this is architecturally pure:**
- Uses existing `mu_hash` primitive (already part of Fix/Xi layer)
- Navigation is pure pattern matching (no iteration primitives)
- Content-addressable by design (aligns with RCX philosophy)
- No new bootstrap primitives required

## Current Status

- **recurrence.v1.json** metadata claims:
  - `"execution_layer": "META_CIRCULAR"`
  - `"production_execution": "META_CIRCULAR"`
  - `"meta_circular_proven": "Gate 4 (2026-02-07)"`
- **Reality:** Works in tests, fails in production
- **Gate 5** claims closure detection complete, but it's unusable for real programs

## Files to Review

1. `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/closures/recurrence.v1.json` - Current implementation
2. `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/prototypes/run_paxos_demo.py` - Failing production program
3. `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/prototypes/paxos_demo.v1.json` - Simple 3-projection livelock
4. `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/rcx_pi/selfhost/mu_type.py` (lines 427-441) - Existing `mu_hash` primitive

## Questions for Agent Review

1. **Is the hash-trie approach the best architectural solution?**
   - Are there simpler alternatives we're missing?
   - Does this align with RCX's structural philosophy?

2. **Should this be recurrence.v2.json or fix recurrence.v1.json in-place?**
   - Current v1 tests pass - do we preserve them?
   - Should v1 be marked "PROOF_OF_CONCEPT_ONLY"?

3. **Are there other algorithmic improvements needed?**
   - Early termination strategies?
   - Projection ordering optimizations?
   - Alternative data structures (Bloom filters, skip lists)?

4. **What's the correct promotion path?**
   - TASKS.md NEXT (urgent production blocker)?
   - TASKS.md VECTOR (design-phase first)?
   - Fix v1 in-place vs create v2?

5. **Will this fix apply to all RCX programs or just Paxos?**
   - Is O(N²) the real bottleneck for all programs?
   - Are there other closure detection patterns we should support?
   - What trace lengths should recurrence.v2 handle (100? 1000? 10000 steps)?

6. **Testing strategy:**
   - Reproduce Paxos failure in test suite?
   - Performance benchmarks for hash-trie vs list?
   - Cross-substrate parity (Python AND JavaScript)?

## North Star Alignment Check

From TASKS.md North Star #12:
> "Every task must answer: 'Does this reduce host smuggling and increase native emergence?'"

**This proposal:**
- ✅ Reduces host smuggling: Uses pattern matching (not Python loops) for navigation
- ✅ Increases native emergence: Makes closure detection actually work in production
- ✅ Structural purity: Content-addressable hash-trie is more RCX-native than linear lists
- ⚠️ Trade-off: Adds complexity (more projections, tree navigation logic)

Please review and provide:
1. Architectural assessment (is hash-trie the right approach?)
2. Alternative solutions (if any exist)
3. Implementation recommendations (v2 vs fix v1, promotion path)
4. Risk analysis (what could go wrong?)
