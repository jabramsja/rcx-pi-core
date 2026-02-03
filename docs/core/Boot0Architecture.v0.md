# Boot0 Architecture: Staged Bootstrap for RCX

**Version:** 0.4
**Status:** DESIGN PROPOSAL (not yet implemented)
**Date:** 2026-01-31

**v0.4 changes:** Clarified "stable semantics, shrinking substrate" (primitives can migrate to smaller substrates), documented JSON as "Phase 0" format, explicit Boot0↔Boot1 handshake ABI, added security invariant for bootstrap code, added explicit L3 parity contract.

> **NOTE:** This document describes a PROPOSED architecture for future migration.
> The Boot0/Boot1/Boot2 modules do not exist yet. The components (seeds, primitives)
> exist and are tested, but the explicit layering is not yet implemented in code.

## Overview

This document describes a Hex0-inspired staged bootstrap architecture for RCX. Like the Hex0/Hex1/Hex2 chain in bootstrappable builds, we create a tower where each stage is built using only the previous stage.

**Key insight:** The current L1/L2/L3 self-hosting levels already approximate this structure. This is a MIGRATION to formalize and harden the boundaries, not a rewrite.

## The Bootstrap Tower

```
┌─────────────────────────────────────────────────────────────┐
│ Boot2: Full System                                          │
│   - kernel.v1.json (kernel state machine)                   │
│   - recurrence.v1.json (closure detection)                  │
│   - eval.v1.json, classify.v1.json                          │
│   Built using: Boot1 match/subst                            │
├─────────────────────────────────────────────────────────────┤
│ Boot1: Self-Hosting Foundation                              │
│   - match.v2.json (pattern matching as projections)         │
│   - subst.v2.json (substitution as projections)             │
│   Built using: Boot0 primitives                             │
├─────────────────────────────────────────────────────────────┤
│ Boot0: Trusted Kernel (Hex0 equivalent)                     │
│   - 5 bootstrap primitives (Python, ~150-200 LOC)           │
│   - Includes bootstrap match/subst (replaced by Boot1)      │
│   - Must be audited, minimal changes                        │
│   Built using: Host language (Python)                       │
└─────────────────────────────────────────────────────────────┘
```

## Boot0: The Trusted Kernel

Boot0 is the Hex0 equivalent - the minimal trusted base that must be implemented in the host language. Everything else is built on top of it.

### The 5 Bootstrap Primitives

| Primitive | Purpose | Current Location |
|-----------|---------|------------------|
| `eval_step` | Single projection application | `eval_seed.py:step()` |
| `mu_equal` | Structural equality comparison | `mu_type.py:mu_equal()` |
| `max_steps` | Termination guarantee | `step_mu.py:step_kernel_mu()` |
| `stack_guard` | Recursion depth limit | `mu_type.py:MAX_MU_DEPTH` |
| `projection_loader` | Load seeds from JSON | `seed_integrity.py:load_verified_seed()` |

**Note on projection_loader:** JSON is the "Phase 0" seed format - a convenience for current development. For true Hex0-style bootstrap, a future substrate might use a simpler format (binary image, S-expression) that requires minimal parsing. The semantics are stable; the format may evolve.

### Bootstrap vs Permanent Code

**Important distinction:**

- The 5 primitives above have STABLE SEMANTICS - their behavior is fixed, but their implementation may migrate to smaller substrates over time (Python → C/Rust → minimal VM → verified VM). This is the Hex0 precedent: the trusted base shrinks, it doesn't stay "Python forever"
- `eval_step` internally uses `match()` and `substitute()` functions
- These match/subst functions are BOOTSTRAP CODE - temporary Python implementations
- Boot1 REPLACES bootstrap match/subst with projection-based implementations
- After Boot1, `eval_step` delegates to match.v2/subst.v2 projections instead

```
Boot0 (initial):  eval_step uses Python match() and substitute()
Boot1 (mature):   eval_step delegates to match.v2.json and subst.v2.json projections
```

This is exactly like Hex0: the initial assembler is hand-written, then replaced by a self-hosted version.

### Transition Mechanism: Bootstrap to Boot1

**How does `eval_step` switch from bootstrap match/subst to Boot1 projections?**

The transition is NOT a runtime flag or mode switch. It is a **compile-time/load-time decision**:

```
Option A (Recommended): Projection-First Detection
─────────────────────────────────────────────────
1. Boot0 loads match.v2.json and subst.v2.json
2. When eval_step needs match/subst, it checks: "Are match projections loaded?"
3. If YES: Wrap request as {"_match_ctx": ...} and apply projections
4. If NO: Fall back to bootstrap Python match()

This is how the CURRENT implementation works (step_mu.py:step_kernel_mu).
The "bootstrap" path is only used during initial seed loading.

Option B (Alternative): Separate Binaries
─────────────────────────────────────────────────
1. boot0_standalone.py: Contains bootstrap match/subst (for seed verification)
2. boot0_integrated.py: Delegates to Boot1 projections (for production)

Two separate modules, no runtime detection needed.
```

**Current Implementation:** The system uses Option A. `step_kernel_mu()` loads combined projections (match.v2 + subst.v2 + kernel.v1) and always uses the projection path. The bootstrap `match()` and `substitute()` in `eval_seed.py` are only used by `step()` for low-level debugging/testing.

**Security Implication:** There is no "mode switch" that an attacker can manipulate. The projection path is always used in production. Bootstrap functions are not exposed at runtime boundaries.

### Boot0 Contract

```python
# Boot0 interface (conceptual)

# PERMANENT PRIMITIVE - stays in host language forever
def eval_step(projections: list, value: Mu) -> Mu:
    """Apply first matching projection to value."""
    # GUARDRAILS (permanent, not bootstrap)
    # Note: In current implementation, depth/width validation is embedded in is_mu()
    # which returns False for invalid values. The pseudocode below is conceptual.
    assert_mu(value)                      # Reject non-Mu input (includes depth/width)
    assert_not_lambda_calculus(value)     # Block higher-order smuggling

    for proj in projections:
        bindings = match(proj["pattern"], value)  # Bootstrap or Boot1
        if bindings is not NO_MATCH:
            return substitute(proj["body"], bindings)  # Bootstrap or Boot1
    return value  # No match = identity

# BOOTSTRAP CODE - replaced by Boot1 projections
# These exist in Boot0 only to bootstrap the system.
# Once Boot1 is loaded, eval_step delegates to projections instead.

def match(pattern: Mu, value: Mu) -> Bindings | NO_MATCH:
    """Structural pattern matching (recursive). ~60 LOC."""
    # Handles: literals, variables, lists, dicts
    # REPLACED BY: match.v2.json projections in Boot1

def substitute(body: Mu, bindings: Bindings) -> Mu:
    """Substitute bindings into body (recursive). ~40 LOC."""
    # Handles: variables, lists, dicts
    # REPLACED BY: subst.v2.json projections in Boot1

# PERMANENT GUARDRAILS (part of Boot0, never replaced)
def assert_mu(value: Mu) -> None:
    """Reject non-Mu values. Includes:
    - Type check (callables, NaN, Infinity rejected)
    - Depth check (MAX_MU_DEPTH = 300)
    - Width check (MAX_MU_WIDTH = 1000)
    Current implementation: mu_type.py:is_mu()
    """

def assert_not_lambda_calculus(value: Mu) -> None:
    """Block patterns that match projection structures (higher-order smuggling).
    Current implementation: eval_seed.py:assert_not_lambda_calculus()
    """
```

**Total Boot0 LOC:** ~150-200 lines (5 primitives + bootstrap match/subst + guardrails)

### What Boot0 Does NOT Include

- No kernel state machine (_mode, _phase)
- No EngineNews closure detection
- No type tags (_type field)
- No projection selection logic beyond linear scan
- No caching or optimization

Boot0 is deliberately minimal. It can run projections but has no concept of "kernel state" or "engine cycles".

### Validation Boundaries

**Which layer validates what?** This is critical for security.

| Boundary | Layer | Validations | Current Implementation |
|----------|-------|-------------|------------------------|
| External → Boot0 | Boot0 | `is_mu()`, `MAX_MU_DEPTH`, `MAX_MU_WIDTH` | `mu_type.py:is_mu()` |
| Boot0 → Boot1 | Boot0 | `assert_not_lambda_calculus()` | `eval_seed.py:176-215` |
| Boot1 → Boot2 | Boot2 | `validate_kernel_projections_first()` | `step_mu.py:72-102` |
| Boot2 → Domain | Boot2 | `validate_no_kernel_reserved_fields()` | `step_mu.py:122-166` |

**Key Security Properties:**

1. **Boot0 validates ALL input** - No untrusted data bypasses `is_mu()` and depth/width checks
2. **Reserved field validation is at Boot2** - Only Boot2 knows about `_mode`, `_phase`, etc.
3. **Projection order validation is at Boot2** - Kernel projections must come before domain
4. **Lambda calculus guard is at Boot0** - Blocks higher-order patterns before they reach any layer

**Why validation is layered this way:**

- Boot0 doesn't know about kernel reserved fields (that's a Boot2 concept)
- Boot1 doesn't know about projection ordering (that's Boot2's kernel state machine)
- Each layer validates what IT introduces, not what lower layers introduce

```
External Input
     │
     ▼
┌─────────────────────────────────────┐
│ Boot0: is_mu, depth, width, lambda  │  ← Structural validity
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│ Boot1: (no additional validation)   │  ← Just wraps match/subst
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│ Boot2: reserved fields, proj order  │  ← Kernel-specific security
└─────────────────────────────────────┘
     │
     ▼
  Domain Projections
```

## Boot1: Self-Hosting Foundation

Boot1 replaces Boot0's `boot0_match` and `boot0_subst` with projection-based implementations.

### Seeds Loaded in Boot1

| Seed | Projections | Purpose |
|------|-------------|---------|
| `match.v2.json` | 8 | Pattern matching as Mu projections |
| `subst.v2.json` | 12 | Substitution as Mu projections |

### How Boot1 Works

1. Boot0 loads `match.v2.json` and `subst.v2.json`
2. Match requests become `{"_match_ctx": {"pattern": P, "value": V, ...}}`
3. Boot0's `eval_step` applies match projections to reduce the request
4. Same for subst: `{"_subst_ctx": {"body": B, "bindings": {...}, ...}}`

**Boot0↔Boot1 Handshake ABI:** The envelope types `_match_ctx` and `_subst_ctx` are the stable interface between Boot0 and Boot1. Boot0 wraps requests in these envelopes; Boot1 projections consume them. These are part of the kernel reserved fields (`KERNEL_RESERVED_FIELDS` in step_mu.py) and cannot be forged by domain data.

### Boot1 Contract

```
Boot1.match(P, V) = Boot0.run_until_done(match_projections, {"_match_ctx": ...})
Boot1.subst(B, bindings) = Boot0.run_until_done(subst_projections, {"_subst_ctx": ...})
```

**Note on `run_until_done`:** This is a DERIVED function, not a 6th primitive. It is composed from existing primitives:

```python
def run_until_done(projections, value):
    """Apply projections until stall (mu_equal) or max_steps."""
    for _ in range(max_steps):        # Primitive: max_steps
        next_value = eval_step(projections, value)  # Primitive: eval_step
        if mu_equal(next_value, value):             # Primitive: mu_equal
            return value  # Stalled
        value = next_value
    return value  # Max steps reached
```

This is marked `@host_iteration` in current code (`step_mu.py:run_mu`) because the loop is host Python, not a projection. It remains host scaffolding even in Boot1.

### Current Implementation Status

- `match.v2.json`: EXISTS, 8 projections, tested
- `subst.v2.json`: EXISTS, 12 projections, tested
- `step_mu.py`: Orchestrates Boot0 + Boot1 integration
- Parity tests: `test_match_v2_parity.py`, `test_subst_v2_parity.py`

**Boot1 is ~90% complete.** The seeds exist and work. Migration formalizes the boundary.

## Boot2: Full System

Boot2 adds the kernel state machine and EngineNews closure detection, built using Boot1's match/subst.

### Seeds Loaded in Boot2

| Seed | Projections | Purpose |
|------|-------------|---------|
| `kernel.v1.json` | 7 | Kernel state machine (_mode, _phase) |
| `recurrence.v1.json` | 9 | Closure detection (Rule 2.2) |
| `eval.v1.json` | 7 | Evaluation orchestration |
| `classify.v1.json` | 6 | Value classification |

### How Boot2 Works

1. Boot1 is available (match/subst as projections)
2. Kernel state: `{"_mode": "match", "_phase": "start", ...}`
3. EngineNews tracks seen values for cycle detection
4. Full projection selection with priority

### Boot2 Contract

```
Boot2.eval(projections, value) =
    Boot1.run_until_done(
        kernel_projections + engine_projections + domain_projections,
        {"_mode": "eval", "_value": value, ...}
    )
```

### Current Implementation Status

- `kernel.v1.json`: EXISTS, 7 projections
- `recurrence.v1.json`: EXISTS, 9 projections (Step 5 complete)
- Integration: `step_mu.py:step_kernel_mu()` orchestrates
- Tests: `test_enginenews_parity.py`, `test_kernel_projections.py`

**Boot2 is ~80% complete.** The seeds exist. Migration clarifies the layering.

## Migration Path

### What Changes

| Current | Boot Architecture | Change Required |
|---------|-------------------|-----------------|
| `eval_seed.py:match()` | Boot0 primitive | Extract to clean interface |
| `eval_seed.py:substitute()` | Boot0 primitive | Extract to clean interface |
| `step_mu.py` | Boot1 orchestrator | Rename/restructure |
| `kernel.py` | Boot2 orchestrator | Clarify boundary |
| `mu_type.py:mu_equal()` | Boot0 primitive | Already clean |

### What Stays the Same

- All seed files (match.v2.json, subst.v2.json, kernel.v1.json, recurrence.v1.json)
- All parity tests
- All grounding tests
- The fundamental algorithms

### Migration Steps

1. **Create Boot0 module** (`rcx_pi/selfhost/boot0.py`)
   - Extract 5 primitives with clean interfaces
   - ~100 LOC total
   - Full test coverage

2. **Refactor Boot1 boundary** (`rcx_pi/selfhost/boot1.py`)
   - Wrap Boot0 + match.v2 + subst.v2
   - Clear contract: "Boot1 provides match/subst as projections"
   - Verify parity tests still pass

3. **Refactor Boot2 boundary** (`rcx_pi/selfhost/boot2.py`)
   - Wrap Boot1 + kernel.v1 + enginenews.v1
   - Clear contract: "Boot2 provides full evaluation"
   - Verify integration tests still pass

4. **Update imports**
   - Existing code imports from boot2 (or boot1/boot0 for lower-level access)
   - Gradual migration, not big-bang

## Verification Strategy

### Boot0 Verification

- **Fuzzer coverage:** `test_bootstrap_fuzzer.py` (1000+ inputs)
- **Adversarial review:** 9-agent rig on boot0.py
- **Formal property:** `boot0_step(boot0_step(x)) converges or hits max_steps`

### Boot1 Verification

- **Parity tests:** `test_match_v2_parity.py`, `test_subst_v2_parity.py`
- **Property:** `Boot1.match(P, V) == Boot0.match(P, V)` for all P, V
- **Roundtrip:** `test_normalization_roundtrip_fuzzer.py`, `test_bindings_roundtrip_fuzzer.py`

### Boot2 Verification

- **Integration tests:** `test_kernel_projections.py`, `test_enginenews_parity.py`
- **Closure detection:** `test_structural_trace_fuzzer.py`
- **JS parity:** `test_js_parity_automated.py` (both substrates run same seeds)

### Cross-Layer Verification

- **L3 parity:** Python and JS both implement Boot0, load same seeds
- **Determinism:** `PYTHONHASHSEED=0` ensures reproducibility
- **Debt tracking:** 12/12 markers, ratchet prevents regression

**L3 Parity Contract (explicit definition):**
- Same input seed set (kernel.v1 + match.v2 + subst.v2 + enginenews.v1)
- Same input value
- → Identical final value
- → Identical trace format (including stall behavior and step counts)

This contract is verified by `tests/test_js_parity_automated.py` which runs the same 20 parity vectors through both Python and JavaScript substrates and compares actual outputs.

## Mapping to Current Code

| Boot Layer | Current Files | Seeds |
|------------|---------------|-------|
| Boot0 | `eval_seed.py` (match, substitute), `mu_type.py` (mu_equal), `kernel.py` (budget) | None (pure Python) |
| Boot1 | `step_mu.py`, `match_mu.py`, `subst_mu.py` | `match.v2.json`, `subst.v2.json` |
| Boot2 | `kernel.py`, `eval_seed.py` (step) | `kernel.v1.json`, `recurrence.v1.json`, `eval.v1.json`, `classify.v1.json` |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Migration is additive; old imports continue working |
| Performance regression | Boot0 is simpler than current code; should be faster |
| Boundary confusion | Clear module names (boot0.py, boot1.py, boot2.py) |
| Incomplete migration | Each step is independently testable and deployable |

## Security Considerations

### Attack Resistance by Layer

| Attack Vector | Defended At | Defense Mechanism |
|---------------|-------------|-------------------|
| Non-Mu input (callables, NaN) | Boot0 | `is_mu()` rejects at entry |
| Stack overflow (deep nesting) | Boot0 | `MAX_MU_DEPTH = 300` |
| Memory exhaustion (wide dicts) | Boot0 | `MAX_MU_WIDTH = 1000` |
| Infinite loops | Boot0 | `max_steps = 10000` |
| Lambda calculus smuggling | Boot0 | `assert_not_lambda_calculus()` |
| Kernel state forgery | Boot2 | `validate_no_kernel_reserved_fields()` |
| Projection order tampering | Boot2 | `validate_kernel_projections_first()` |
| Stall detection bypass | Boot2 | `mu_equal()` for cycle detection |

### Why 3 Layers Doesn't Triple Attack Surface

The Adversary review noted that 3 layers could triple the attack surface. Here's why it doesn't:

1. **Validation happens ONCE at entry** - Boot0 validates all input. Boot1/Boot2 trust Boot0's validation.

2. **Each layer adds validation for ITS concepts only**:
   - Boot0: Structural validity (is this valid Mu?)
   - Boot1: Nothing new (just wraps match/subst)
   - Boot2: Kernel semantics (reserved fields, projection order)

3. **No redundant validation** - Each check happens exactly once, at the layer that introduces the concept.

4. **Defense in depth** - If Boot0 validation fails, Boot2 validation is a backstop (but shouldn't be needed).

### Bootstrap Code Security

The bootstrap `match()` and `substitute()` functions are NOT exposed to external input:

1. They are only called during seed loading (trusted data)
2. Production code uses Boot1 projections (step_kernel_mu path)
3. The functions exist for debugging/testing, not runtime use

**Security Invariants:**

1. No external input reaches bootstrap code without first passing Boot0 validation.
2. **After Boot1 seeds are loaded, Boot0 must never call Python match/subst on untrusted inputs.** The projection path is always used for domain data. Bootstrap functions handle only seed verification (trusted, audited data).

## Success Criteria

1. **Boot0 isolated:** 5 primitives + bootstrap code in single module, <250 LOC
2. **Boot1 parity:** All match/subst parity tests pass
3. **Boot2 parity:** All kernel/enginenews tests pass
4. **JS parity maintained:** Both substrates run same boot sequence
5. **No new debt:** Migration doesn't increase debt count

## Timeline Estimate

| Phase | Scope | Estimate |
|-------|-------|----------|
| Boot0 extraction | Create boot0.py, extract primitives | Day 1 |
| Boot1 boundary | Refactor step_mu.py integration | Day 1-2 |
| Boot2 boundary | Clarify kernel.py layering | Day 2-3 |
| Verification | Full audit pass, agent review | Day 3-4 |
| Documentation | Update STATUS.md, TASKS.md | Day 4-5 |

## Open Questions

1. **Should Boot0 be a single file or a subpackage?**
   - Single file is simpler and easier to audit
   - Subpackage allows cleaner separation of primitives

2. **How do we handle the JS substrate?**
   - Option A: JS implements Boot0 only, loads seeds for Boot1/Boot2
   - Option B: JS mirrors Python structure exactly
   - Current: JS is closer to Option A already

3. **What about the legacy modules (match_mu.py, subst_mu.py)?**
   - Keep as compatibility shims during migration
   - Deprecate after Boot1 is stable

## References

- [Hex0 Bootstrap](https://bootstrappable.org/) - Inspiration for staged architecture
- `docs/core/BootstrapPrimitives.v0.md` - Current primitive documentation (Boot0 formalizes this)
- `docs/core/MetaCircularKernel.v0.md` - Kernel state machine spec (Boot2)
- `docs/core/EngineNewsStructural.v0.md` - Closure detection spec (Boot2)

## Relationship to Other Docs

This document is CONSISTENT with `BootstrapPrimitives.v0.md`:

- BootstrapPrimitives lists 5 primitives - Boot0 has the same 5
- BootstrapPrimitives notes match/subst are "bootstrap code" - Boot0 makes this explicit
- Boot0 formalizes the staged replacement that BootstrapPrimitives describes

The key addition here is the Hex0 framing and explicit Boot1/Boot2 layering.
