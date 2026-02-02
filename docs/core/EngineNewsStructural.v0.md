# Recurrence Structural Specification v0

**Status:** IMPLEMENTED (Step 5 complete 2026-01-30)
**Created:** 2026-01-30
**Origin:** 7-agent review requirement before Step 5 implementation
**Canonical Reference:** RCXEngineNew.pdf (RCX Core Engine Stateless Specification, May 2025)

---

## Purpose

This document specifies the **structural requirements** for Recurrence (Step 5).
It exists to prevent "success theater" where Python implements closure detection
instead of Mu projections.

**Why this matters:**
- If Recurrence runs via Python loops/logic, emergence might be a Python artifact
- For structural honesty, closure detection must be pattern matching on traces
- The bootstrap (eval_step, mu_equal) is acceptable - the LOGIC must be projections

---

## Alignment with RCX Core Engine Spec

The original RCX Core Engine specification defines the formal closure mechanism:

| Spec Rule | Description | Our Implementation |
|-----------|-------------|-------------------|
| **Rule 2.2♢** | Closure-on-Second-Demand | `run_mu_structural()` trace enables this |
| **Rule 0.7c′** | LeafInvariance (logs τ) | Stall detection in trace |
| **Rule 3.1** | Operator Exhaustion | Max steps / freeze operator |
| **A.10** | Trace Token τ | Our trace linked-list captures this |
| **A.10b** | Closure Object Ω(τ) | The "closure evidence" we emit |

**Key insight from spec:** "A second, independent derivation that encounters the same τ
triggers Rule 2.2♢, projecting a closure object Ω(τ) such as ω."

Our implementation must:
1. Capture trace tokens (τ) as structural data
2. Detect recurrence of the same trace pattern
3. Project closure evidence structurally (not via Python conditionals)

---

## North Star Constraint

> "Emergence must be attributable to RCX dynamics, not 'Python did it.'"
> — TASKS.md, North Star #5

This means:
- Recurrence rules MUST be expressed as Mu projections in JSON
- Python provides only the 5 bootstrap primitives
- Closure detection is structural pattern matching, NOT Python conditionals

---

## Implemented Projections

`mu/closures/recurrence.v1.json` contains 9 projections:

| Projection ID | Purpose |
|---------------|---------|
| `recurrence.init` | Entry point: _detect_closure -> internal state |
| `recurrence.end_of_trace` | End of trace (null) -> no closure |
| `recurrence.check_state_stall` | Extract state from stall entry |
| `recurrence.check_state_maxsteps` | Extract state from max_steps entry |
| `recurrence.check_state` | Extract state from normal trace entry |
| `recurrence.found_in_seen` | State found in seen-set -> closure detected! |
| `recurrence.not_in_head` | State not in head -> check tail |
| `recurrence.not_found` | State not found -> add to seen, advance |
| `recurrence.unwrap` | Extract final closure evidence |

**Key design:** Non-linear patterns for state equality. `recurrence.found_in_seen` uses
`{"var": "state"}` twice - binding conflict detection in eval_seed.match() enforces equality.

**Underscore prefix convention:** All engine state fields use underscore prefix (`_mode`, `_phase`,
`_seen`, `_current`, `_result`, etc.) to distinguish engine-internal state from domain data.
This prevents domain data from accidentally colliding with engine state (same convention as
kernel.v1.json, match.v2.json, subst.v2.json). See also MetaCircularKernel.v0.md.

---

## Trace Format (Input to Recurrence)

Recurrence projections consume the trace produced by `run_mu_structural()`:

```json
{
  "result": <final_value>,
  "trace": {
    "head": {"step": 0, "state": <value>, "projection": <id|null>},
    "tail": {
      "head": {"step": 1, "state": <value>, "projection": <id|null>},
      "tail": ...
    }
  },
  "stall": true|false,
  "steps": <int>
}
```

Each trace entry has:
- `step`: Integer step number
- `state`: The Mu value at that step
- `projection`: Which projection matched (null = stall)

---

## Success Criteria (ALL MET)

Step 5 is COMPLETE:

### 1. Projections Exist ✅
- [x] `mu/closures/recurrence.v1.json` contains 9 projections
- [x] Each projection has `id`, `pattern`, `body` fields
- [x] SHA256 checksum verified on load (seed_integrity.py)

### 2. Execution is Structural ✅
- [x] Recurrence runs via `eval_seed.step()`, NOT Python loops
- [x] Closure detection uses pattern matching on trace
- [x] No Python `if/for/while` in closure detection path (only in bootstrap)
- [x] Seen-set is Mu linked-list, NOT Python set

### 3. Cross-Substrate Parity ✅
- [x] Same projections produce same results on Python
- [x] Parity tests in `tests/test_enginenews_parity.py` (23+ tests)
- [x] Fuzzer tests in `tests/test_enginenews_fuzzer.py`
- [x] JS tests in `mu/host/js/eval_step.js` (v5, with Recurrence support)
- [x] ACTUAL cross-substrate comparison via JSON API (2026-01-31)

### 4. Closure Evidence is Structural ✅
- [x] Closure detection is a projection (`recurrence.found_in_seen`) using non-linear patterns
- [x] Closure evidence is emitted as Mu data: `{closure_detected: bool, final_result: <state>}`
- [x] Evidence can be consumed by other projections

---

## Anti-Patterns (Violations)

**DO NOT:**

1. **Python conditional for closure:**
   ```python
   # WRONG - Python decides closure
   if state in seen_states:
       return ClosureEvidence(...)
   ```

2. **Python loop for trace scan:**
   ```python
   # WRONG - Python iterates trace
   for entry in trace:
       if mu_equal(entry.state, current):
           ...
   ```

3. **Python set for seen-states:**
   ```python
   # WRONG - Python data structure
   seen = set()
   seen.add(state_hash)
   ```

**DO:**

1. **Projection for seen-check:**
   ```json
   {
     "id": "recurrence.check_seen",
     "pattern": {"state": {"var": "s"}, "seen": {"head": {"var": "s"}, "tail": {"var": "_"}}},
     "body": {"found": true}
   }
   ```

2. **Linked-list for seen-set:**
   ```json
   {"head": <state1>, "tail": {"head": <state2>, "tail": null}}
   ```

3. **Kernel execution for iteration:**
   ```python
   # ALLOWED - kernel provides iteration
   result = step_kernel_mu(enginenews_projections + kernel_projections, trace_input)
   ```

---

## Allowed Bootstrap Primitives

These Python operations are ALLOWED (irreducible substrate):

| Primitive | Location | Why Allowed |
|-----------|----------|-------------|
| `eval_step` | `eval_seed.step()` | Applies projections |
| `mu_equal` | `mu_type.mu_equal()` | Structural equality |
| `max_steps` | `step_mu.py:241` | Termination guarantee |
| `stack_guard` | `mu_type.MAX_MU_DEPTH` | Resource limit |
| `projection_loader` | `seed_integrity.load_verified_seed()` | Load JSON seeds |

All Recurrence logic must be **above** these primitives.

---

## Cross-Substrate Parity Vectors

Minimum parity tests for Step 5:

| Vector ID | Input | Expected | Tests |
|-----------|-------|----------|-------|
| `engine.stall` | Non-matching input | `stall: true` | Stall detection |
| `engine.single_fix` | One transformation | Trace with 1 projection | Single step |
| `engine.oscillate` | A→B→A cycle | Repeated states in trace | Cycle capture |
| `engine.closure` | Repeated state | Closure evidence emitted | Closure detection |
| `engine.max_steps` | Infinite cycle | `stall: false, steps: max` | Termination |

These vectors MUST pass on:
- Python: `tests/test_enginenews_parity.py`
- JavaScript: `mu/host/js/eval_step.js`

---

## Implementation Sequence

1. **Create `mu/closures/recurrence.v1.json`** with 4 initial projections
2. **Create parity vectors** in `tests/fixtures/enginenews_vectors.json`
3. **Create Python tests** in `tests/test_enginenews_parity.py`
4. **Verify kernel execution** (no Python control flow in closure path)
5. **Port to JS** and verify same results
6. **Demo script** showing closure detection on both substrates

---

## Verification Commands

```bash
# Run Recurrence parity tests
pytest tests/test_enginenews_parity.py -v

# Verify structural execution (no Python loops in closure path)
grep -n "for.*in.*trace\|if.*in.*seen" rcx_pi/selfhost/ --include="*.py"
# Should return EMPTY or only in bootstrap primitives

# Run cross-substrate demo
python scripts/enginenews_demo.py
node mu/host/js/eval_step.js --test-enginenews
```

---

## Grounding Tests Required

Before Step 5 is COMPLETE, these grounding tests must exist:

1. **Projection count test:** `recurrence.v1.json` has 4 projections
2. **Projection schema test:** Each projection has id/pattern/body
3. **Kernel execution test:** Closure detection uses step_kernel_mu
4. **No-Python-logic test:** Grep for forbidden patterns returns empty
5. **Parity test:** Python and JS produce same closure evidence

---

## Related Documents

- **RCXEngineNew.pdf** - Canonical RCX Core Engine Stateless Specification (May 2025)
- `docs/core/BootstrapPrimitives.v0.md` - What Python can do
- `docs/core/MetaCircularKernel.v0.md` - How kernel executes projections
- `TASKS.md` - Step 5 task definition
- `STATUS.md` - Current project phase

---

## Spec Rule Mapping

From RCX Core Engine Stateless Specification:

### Rule 2.2♢ Closure-on-Second-Demand
> "A stalled derivation encounters the trace-token τ a second time via an operator O′
> that is independent of the first... Action: Project the closure object Ω(τ) and log ⟨closFix, τ⟩."

**Our implementation:** The trace from `run_mu_structural()` captures repeated states.
Recurrence projections must pattern-match on this trace to detect τ recurrence.

### Rule 0.7c′ LeafInvariance
> "If... the recursion is degenerate. Log a tracetoken τ, freeze the operator..."

**Our implementation:** When `mu_equal(before, after)` in step loop → stall detected.
This is the τ logging moment.

### A.5 Independence
> "Two derivations must diverge before the first encounter of τ"

**Our implementation:** Cross-substrate parity (Python + JS) provides independence.
Same projections, different substrates = independent derivations.

---

## Changelog

- **v0 (2026-01-30):** Initial design doc, pre-Step 5 gate (7-agent review requirement)
- **v0.1 (2026-01-30):** Added alignment with RCX Core Engine spec (Rule 2.2♢, A.10, etc.)
- **v0.2 (2026-01-30):** IMPLEMENTED - 9 projections, 7-agent review complete, all criteria met
