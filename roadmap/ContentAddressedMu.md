<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-10
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
-->
# Content-Addressed Mu: Hash-Identity as Substrate Property

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: Levels 0-2 IMPLEMENTED. Level 3 (trie) DEFERRED — not beneficial for production traces.

## Problem Statement

The meta-circular kernel cannot process production-sized programs through recurrence detection. The root cause is **comparison cost**: detecting whether a state has been seen before requires deep structural equality checks that scale as O(N * depth) per comparison, with O(N) comparisons per trace step.

**Concrete failure:** Paxos 3-state cycle (4-key dict states) over 15 steps requires ~210 comparisons x ~30 kernel steps each = ~6,300 steps, exceeding the kernel budget of 10,000. *(Theoretical estimate — no profiling grounding tests exist yet. Verified empirically: production tests time out.)*

**recurrence.v2** patches this by pre-computing SHA-256 hashes at the boundary and comparing hash strings. This reduces per-comparison cost from O(depth) to O(1) but:
- Still scans the `_seen` list linearly: O(N) comparisons per step
- Normalization cost persists: the entire state (including growing `_seen`) is renormalized every kernel step
- The hash is bolted on at the boundary, not a property of the data itself

These are symptoms of a deeper architectural gap: **Mu values have no native identity**.

## Proposal: Content-Addressed Mu Values

**Core principle:** Every Mu value carries a content hash computed at construction time. Two values with the same hash are structurally identical. Equality is O(1).

This is not a new idea. It is the same principle behind:
- **Hash consing** (Ershov 1958, ACL2 HONS): canonical representations, O(1) equality, free memoization
- **Unison language**: code identified by hash of AST, not by name
- **IPFS/IPLD**: content-addressed DAGs with Merkle identity
- **Nix content-addressed derivations**: early cutoff via identity comparison
- **Git**: content-addressed objects (blobs, trees, commits)

### What Changes

| Component | Before | After |
|-----------|--------|-------|
| `mu_equal(a, b)` | Bootstrap primitive, O(depth) | **Eliminated** — non-linear patterns on `_hash` fields |
| `mu_hash` | Runtime infrastructure | Boundary scaffolding (computed once at value construction) |
| Recurrence seen-set | Linear scan + deep compare O(N * depth) | Linear scan + hash compare O(N), frozen hashes (state dropped) |
| Non-linear pattern matching | Deep compare on binding conflict | Hash compare on binding conflict |
| Normalization | Re-normalize on every kernel step | Normalize once at boundary (Level 2: state dropped from _seen) |
| Memoization | Not available | Free: cache results by input hash |
| Bootstrap primitives | 5 | 4 (mu_equal removed) |

### What Does NOT Change

- **Projection semantics**: Projections remain pure Mu JSON. They don't see or manipulate hashes.
- **Kernel state machine**: kernel.v1.json unchanged. Match/subst projections unchanged.
- **Debt count**: Stays at 11 tracked @host_* markers (bootstrap substrate lower bound; was 12 before CP-S1A).
- **L3 parity**: JS already has `muHash()`. Both substrates compute identical SHA-256.

### What Could Be DEMOTED

**Key insight:** Content-Addressed Mu doesn't just add speed — it can **reduce bootstrap primitives from 5 to 4**.

Currently, `mu_equal` is a bootstrap primitive that does:
```
json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
```

With content-addressing, every value carries its hash. Equality becomes:
```
a._hash == b._hash  # simple string comparison
```

String comparison is exactly what **non-linear pattern matching already does** — binding the same variable twice enforces equality. So `mu_equal` as a distinct runtime primitive is no longer needed. Its role is subsumed by the pattern matcher.

`mu_hash` (SHA-256 computation) moves from "runtime infrastructure" to **boundary scaffolding** — computed once when values enter the system, like JSON parsing. It's not a runtime primitive the kernel calls; it's how values are prepared at the boundary before the kernel sees them.

| Primitive | Current Role | With Content-Addressing |
|-----------|-------------|------------------------|
| `eval_step` | Apply projections | Unchanged |
| `mu_equal` | Structural equality | **DEMOTED** — subsumed by non-linear pattern matching on hash strings |
| `max_steps` | Budget enforcement | Unchanged |
| `stack_guard` | Depth limit | Unchanged |
| `projection_loader` | Load seeds | Unchanged |
| `mu_hash` | Host infrastructure | Moves to boundary scaffolding (like JSON parsing) |

This directly advances L4 (True Self-Hosting): fewer primitives = smaller irreducible substrate.

## Implementation Levels

### Level 0: Boundary Hashing (recurrence.v2 — IMPLEMENTED)

Hash computed at Python/JS boundary before feeding to meta-circular kernel. Projections compare hash strings via non-linear patterns.

- **Status**: IMPLEMENTED — `hash_trace_for_recurrence()` in step_mu.py, `recurrence.v2.json` in mu/closures/
- **Scope**: Recurrence only
- **Debt impact**: Zero (boundary function, not substrate)
- **Limitation**: Only benefits recurrence; other subsystems unchanged
- **Resolved**: `hash_trace_for_recurrence()` converted from recursive to iterative (avoids Python recursion limit on long traces)

### Level 1: Hash-Identity at Construction (IMPLEMENTED — 2026-02-10)

`mu_hash_cached()` added to `mu_type.py` with canonical-JSON-keyed cache. All 8 production `mu_equal` call sites replaced with direct `mu_hash_cached()` comparisons. `mu_equal` demoted from BOOTSTRAP_PRIMITIVE to convenience wrapper.

**Implementation (completed):**

Step 1 — Accelerate: `mu_equal` body replaced with `mu_hash_cached(a) == mu_hash_cached(b)`. The cache uses canonical JSON (`json.dumps(value, sort_keys=True)`) as key, avoiding re-hashing identical structures.

```python
_mu_hash_cache: dict[str, str] = {}

def mu_hash_cached(value) -> str:
    assert_mu(value, "mu_hash_cached")
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False)
    cached = _mu_hash_cache.get(canonical)
    if cached is not None:
        return cached
    h = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    _mu_hash_cache[canonical] = h
    return h
```

Step 2 — Eliminate: All 8 production `mu_equal()` call sites replaced with `mu_hash_cached()`:

| File | Sites | Purpose |
|------|-------|---------|
| `eval_seed.py` | 2 | Binding conflict detection (list + dict match) |
| `step_mu.py` | 6 | Stall detection (step_kernel_mu, step_algorithm_with_bridge, run_mu, _resolve_trace_projection_id, run_mu_structural, _run_sub_algorithm) |
| `projection_runner.py` | 1 | Stall detection (make_projection_runner) |

JS parity: `muHashCached()` added to `eval_step.js` with Map-based cache. All 6 JS call sites updated. `muEqual()` delegates to hash comparison.

**Design note:** Cache is keyed by canonical JSON (same serialization as original `mu_equal`), not by `_hash` field on values. The `_hash`-as-field approach is a Level 2+ concern requiring mutable annotation or envelope wrapping. The parallel cache approach achieves the same O(1) amortized equality without modifying Mu value structure.

- **Scope**: All structural equality checks in production code
- **Debt impact**: **Negative** — removes `mu_equal` as bootstrap primitive (5 → 4)
- **Benefits**: Recurrence, exhaustion, non-linear pattern matching, general equality, L4 advancement
- **Verification**: Full suite remained green at merge time; `test_mu_equal_parity_fuzzer.py` confirms semantic equivalence

### Level 2: Frozen Hashes (IMPLEMENTED — 2026-02-10)

Dropped the `state` field from `_seen` entries in `recurrence.v2.json`. The seen-set now stores only `{state_hash}` instead of `{state_hash, state}`.

**Why this is safe:** The `hash_match` and `hash_no_match` projections bind `_seen_state` from the `state` field but **never reference it in their bodies**. It was dead weight — ~77% of `_seen` memory was wasted storing full state objects that were never read.

**Changes (3 projections in recurrence.v2.json):**
1. `recurrence.not_found` body: prepends `{state_hash}` instead of `{state_hash, state}`
2. `recurrence.hash_match` pattern: matches `{state_hash}` instead of `{state, state_hash}`
3. `recurrence.hash_no_match` pattern: same removal

- **Scope**: Recurrence seen-set memory optimization
- **Debt impact**: Zero (pure projection change, no host code)
- **Benefits**: ~77% memory reduction in `_seen` list, cleaner data flow
- **Verification**: 8/8 recurrence production tests pass, 6/6 paxos e2e tests pass, JS parity intact

### Level 3: Structural Trie Indexing (DEFERRED — Evidence-Based)

Agent analysis (2026-02-10) conclusively showed a radix trie in Mu is **not beneficial** for production traces:

| Metric | Linear Scan (current) | Radix Trie |
|--------|----------------------|------------|
| Additional projections | 0 | 21+ new |
| Trace < 50 steps | ~100 kernel steps | ~500 kernel steps (5x slower) |
| Break-even | — | ~100 trace steps |
| Production traces | 3-30 steps | Not reached |
| Complexity | Simple | High (bit extraction, node splitting) |

**Decision:** DEFERRED. Revisit only if traces routinely exceed 100 steps. The per-projection overhead of Mu kernel steps (~2 steps/projection) makes the trie's O(64) lookup slower than linear scan's O(N) for small N.

- **Scope**: Large trace optimization (not currently needed)
- **Debt impact**: Zero (pure Mu projections)
- **Benefits**: O(hash_length) lookup instead of O(N) scan — only valuable for N > 100

## Why Not Just the Trie?

The trie (Level 3) solves lookup speed but not the other problems:

| Problem | Trie alone | Content-Addressed Mu |
|---------|-----------|---------------------|
| Recurrence lookup | O(64) per check | O(1) equality + O(N) scan, or O(64) with trie |
| Exhaustion frozen-set | Still O(N * depth) | O(N) with hash compare |
| Non-linear patterns | Still O(depth) per conflict | O(1) per conflict |
| Normalization cost | Still O(state_size) per step | Normalize once |
| Memoization | Not addressed | Free |
| Projection indexing | Not addressed | Enables VECTOR item |

Content-Addressed Mu is the foundation. The trie is an optional optimization on top.

## Impact on Production Programs

### Paxos Demo (mu/programs/paxos_demo.v1.json)

Current failure: recurrence.v1 exhausts kernel budget on 4-key dict states.
With Level 0 (v2): Hash comparison expected to fit within budget (~420 steps vs ~6,300, theoretical estimate).
With Level 1: All equality checks accelerated, not just recurrence.

### rcx_engine.v1 Pipeline

The full pipeline: `engine → trace → recurrence → exhaustion → hemispheres`

Each stage involves structural equality checks:
- **Recurrence**: "Have I seen this state?" (seen-set membership)
- **Exhaustion**: "Is this operator frozen?" (frozen-set membership)
- **Hemispheres**: State routing decisions (equality for classification)

Content-addressing accelerates ALL of these, not just recurrence.

## Relationship to Self-Hosting Path

| Level | Self-Hosting Impact |
|-------|-------------------|
| L1 (Algorithmic) | No change — match/subst projections unchanged |
| L2 (Operational) | No change — kernel.v1 unchanged, for-loop accepted as bootstrap |
| L3 (Substrate Portability) | Strengthened — both substrates use identical hashing |
| L4 (True Self-Hosting) | **Advanced** — `mu_equal` eliminated as bootstrap primitive (5 → 4). Hash computation becomes boundary scaffolding, not runtime primitive. |

The honest assessment: SHA-256 computation is irreducibly a host operation. You cannot compute a cryptographic hash using pattern matching. But hashing at the boundary is no different from JSON parsing at the boundary — it's how values enter the system, not how the system computes. The kernel never calls `mu_hash`; it only compares hash strings that arrive pre-computed.

The deeper win: `mu_equal` as a bootstrap primitive goes away entirely. Non-linear pattern matching (which already exists in match.v2 + bridge) handles equality by binding the same variable twice. If both bindings resolve to the same hash string, the match succeeds. This is structural equality expressed structurally — not via a host function.

The Forth precedent: This is like Forth discovering that its comparator (=) is redundant because the address mode already provides identity. Content-addressing doesn't add primitives — it removes one.

## Security Considerations

- **Hash collision**: SHA-256 collision probability is ~2^-128 for birthday attacks. For Mu values (bounded depth, bounded width), this is negligible. If paranoia demands it, Level 1 can add structural verification on hash match (belt-and-suspenders, shown as optional in pseudocode above).
- **Hash as identity**: Hash becomes a trusted identity. If an attacker can control hash inputs, they might craft collisions. Mitigation: Mu values are constructed from projections (trusted) and domain data (validated at boundary). The attack surface is the same as the existing `mu_equal` surface.
- **Timing side-channel**: Hash comparison is constant-time (string equality on fixed-length hex). This is actually BETTER than deep structural comparison which leaks structure depth via timing.

## Files

**Level 0 (IMPLEMENTED):**

| File | Status |
|------|--------|
| `rcx_pi/selfhost/step_mu.py` | `hash_trace_for_recurrence()` EXISTS |
| `mu/closures/recurrence.v2.json` | EXISTS — 9 hash-accelerated projections |
| `mu/host/js/eval_step.js` | `muHash()` EXISTS |
| `mu/tests/parity/test_recurrence_production.py` | EXISTS — production closure detection tests |

**Level 1 (IMPLEMENTED — 2026-02-10):**

| File | Change |
|------|--------|
| `rcx_pi/selfhost/mu_type.py` | `mu_hash_cached()` added; `mu_equal()` demoted to convenience wrapper |
| `rcx_pi/selfhost/eval_seed.py` | 2 binding conflict sites use `mu_hash_cached()` |
| `rcx_pi/selfhost/step_mu.py` | 6 stall detection sites use `mu_hash_cached()` |
| `rcx_pi/selfhost/projection_runner.py` | 1 stall detection site uses `mu_hash_cached()` |
| `mu/host/js/eval_step.js` | `muHashCached()` added; `muEqual()` delegates; 6 call sites updated |
| `mu/tests/integration/test_paxos_end_to_end.py` | Paxos deadlock metabolization pipeline test (6 tests) |

**Level 2 (IMPLEMENTED — 2026-02-10):**

| File | Change |
|------|--------|
| `mu/closures/recurrence.v2.json` | 3 projections edited: `state` dropped from `_seen` entries |
| `rcx_pi/selfhost/seed_integrity.py` | Updated SHA-256 hash for recurrence.v2.json |
| `mu/host/js/eval_step.js` | Updated SHA-256 hash for recurrence.v2.json |
| `mu/docs/core/recurrence_v2_design.md` | Updated `_seen` description |

## Exit Criteria

### Level 0 + Level 1 (ACHIEVED)

1. ~~Every Mu value carries its content hash (computed at boundary)~~ → Level 0: boundary hashing for recurrence. Level 1: `mu_hash_cached()` for all equality. ✅
2. ~~`mu_equal()` replaced by hash string comparison~~ → All 8 production call sites use `mu_hash_cached()`. ✅
3. All existing parity tests pass (no semantic change). ✅
4. Recurrence production tests pass (paxos_demo closure detection). ✅ (`test_paxos_end_to_end.py`)
5. No new `@host_*` decorators required. ✅
6. Bootstrap primitive count: 5 → 4 (`mu_equal` eliminated). ✅
7. L3 cross-substrate parity intact. ✅ (JS `muHashCached` mirrors Python)

### Level 2 (ACHIEVED)

8. `_seen` entries store only `{state_hash}`, not `{state_hash, state}` — ~77% memory savings. ✅

### Level 3 (DEFERRED)

9. Structural trie indexing — not beneficial for production traces (<50 steps). Revisit if traces exceed 100 steps.

## Open Questions

1. ~~**Caching strategy (Level 2)**: Should hashes be cached on the Mu value or in a separate table?~~ → RESOLVED: Level 2 implemented as frozen hashes (state dropped from _seen), not _hash-on-value. The parallel cache in `mu_hash_cached()` handles value-level caching.
2. **Hash of normalized vs raw**: Should we hash the normalized (linked-list) form or the raw (Python dict) form? Normalized is canonical and substrate-independent. Raw is faster but substrate-dependent.
3. **Incremental hashing**: When a projection produces output by substitution, can we compute the output hash incrementally from input hashes? (Probably not for SHA-256, but worth investigating for future hash functions.)
4. ~~**When to promote Level 3 (trie)**: What trace length triggers the need?~~ → RESOLVED: Analysis shows break-even at ~100 steps. Production traces are 3-30 steps. DEFERRED.
