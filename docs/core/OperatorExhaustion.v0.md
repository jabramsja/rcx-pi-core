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

# Operator Exhaustion Structural Specification v0

**Status:** IMPLEMENTED (Step 6 complete 2026-02-02)
**Created:** 2026-02-01
**Origin:** RCXEngineNew.pdf Rule 3.1
**Depends on:** Step 5 (Recurrence Rule 2.2♢) - COMPLETE

---

## Purpose

This document specifies the **structural requirements** for Rule 3.1 (Operator Exhaustion).
It builds on Step 5's trace infrastructure to detect when an operator (projection) has been
applied continuously without making progress, and must be "frozen" to allow other operators to try.

**Why this matters:**
- Prevents infinite loops where one projection keeps matching without progress
- Enables graceful fallback to other projections in the pool
- Required for proper globalstall detection (meta-stall termination)
- Must be structural (projections), not Python conditionals

---

## Alignment with RCX Core Engine Spec

From RCXEngineNew.pdf Rule 3.1 (page 10):

> **Rule 3.1 Operator Exhaustion** When a single recursive operator (e.g. Ξ_succ) has been
> applied continuously since the tracetoken τ was logged and:
> - each state S_{n+1} is generated solely by applying the same operator to S_n;
> - no new fixers or alternative transformations are detected;
>
> the system must enter **Post-Closure Recursion Mode**:
> - the exhausted operator is frozen;
> - subsequent steps must employ a different unary operator (if any remain in the scheduler's pool);
> - continued recursion with a frozen operator is invalid unless it yields novel fixers or conflict;
> - the derivation may not restart from ∅; progress must occur inside the same run until
>   either a new fixer appears or τ is encountered a second time, thereby activating Rule 2.2♢.

**Key insight:** An operator is "exhausted" when it has been the sole contributor to state
transitions since a trace token τ was logged, and keeps producing the same pattern without
introducing new structure.

---

## Relationship to Existing Implementation

| Component | Status | Role in Rule 3.1 |
|-----------|--------|------------------|
| `run_mu_structural()` | DONE (Step 5) | Provides trace with projection IDs |
| `recurrence.v1.json` | DONE (Step 5) | Detects state recurrence (τ logging) |
| Trace format | DONE | Already has `projection` field per entry |
| Frozen set | **NEW** | Track exhausted operators |
| Exhaustion detection | **NEW** | Detect same-operator-since-τ pattern |

The trace from Step 5 already captures which projection matched at each step:
```json
{
  "step": 0,
  "state": <value>,
  "projection": "some.projection.id"  // or null for stall
}
```

Rule 3.1 needs to:
1. Detect when τ is logged (state recurrence - already done by Recurrence)
2. Track which operator was active when τ was logged
3. Detect if the same operator continues to be the sole contributor
4. Freeze the operator when exhaustion is detected

---

## Formal Definition

### Exhaustion Predicate

An operator O is **exhausted** at step t if:

```
exhausted(O, t, τ) :=
  τ_logged_at(t₀) ∧                      // τ was logged at some step t₀
  t > t₀ ∧                                // we're past the τ logging point
  ∀i ∈ [t₀, t]: projection(i) = O ∧      // O was the only operator since τ
  stall(t) ∨ state_recurs(t, [t₀..t])    // either stalled or state repeats
```

### Freeze Action

When `exhausted(O, t, τ)` holds:
1. Add O to the frozen set: `frozen := cons(O, frozen)`
2. Skip O in subsequent projection matching
3. Log `⟨operatorFreeze, O, τ⟩`

### Post-Closure Mode

After freezing, the kernel enters Post-Closure Recursion Mode:
- Only unfrozen operators may match
- If all operators frozen → globalstall
- If new operator succeeds → normal execution resumes

---

## Structural Design

### Input Format (Extension to Recurrence)

```json
{
  "_detect_exhaustion": {
    "trace": <linked_list>,         // From run_mu_structural
    "frozen": <linked_list>,        // Currently frozen operator IDs
    "tau_step": <int_or_null>,      // Step where τ was logged (from Recurrence)
    "operator_ids": <linked_list>   // All known operator IDs (for globalstall)
  }
}
```

**Note:** `tau_step` comes from Recurrence output (see Q2 resolution below).

### Output Format

```json
{
  "exhaustion_detected": true|false,
  "operator_to_freeze": <id_or_null>,
  "frozen": <updated_linked_list>,
  "action": "freeze"|"continue"|"globalstall"
}
```

### Required Projections (Simplified per Expert Review)

The Expert agent suggested reducing from 10 to ~6 projections by merging related
logic. The simplified design:

| Projection ID | Purpose |
|---------------|---------|
| `exhaustion.init` | Entry: no tau_step → continue (no exhaustion possible) |
| `exhaustion.scan_start` | Begin scanning trace from tau_step |
| `exhaustion.scan_same` | Current entry has same operator, continue scan |
| `exhaustion.scan_different` | Different operator found → not exhausted |
| `exhaustion.exhausted` | End of scan, same operator throughout → freeze |
| `exhaustion.unwrap` | Extract final result |

**Merged logic:**
- `exhaustion.init` handles both entry AND no-tau case (originally 2 projections)
- `exhaustion.scan_same` and `exhaustion.scan_different` use non-linear patterns for
  operator equality checking (originally 4 projections)
- Frozen list membership is checked via non-linear pattern in `exhaustion.exhausted`

**Estimated:** ~6 projections (simpler than Recurrence's 9)

**Note:** Globalstall detection can be added as a separate projection if needed,
but the primary use case (single operator exhaustion) is served by the 6 above.

---

## Detection Algorithm (Structural)

```
Given: trace (linked list), frozen (linked list), tau_step (int or null)

1. If tau_step is null → no exhaustion possible, return {action: "continue"}

2. Find operator O that matched at tau_step (from trace)

3. Walk trace from tau_step to end:
   - For each entry, check if projection == O
   - If any entry has different projection → not exhausted, return {action: "continue"}

4. If all entries have same O since tau_step:
   - Check if O is in frozen list
   - If yes → already frozen, try next operator (not exhaustion, but skip)
   - If no → O is exhausted, return {action: "freeze", operator: O}

5. After freezing, check if all known operators are frozen:
   - If yes → return {action: "globalstall"}
   - If no → return {action: "continue"} (other operators available)
```

---

## Integration with Kernel

### Option A: Separate exhaustion.v1.json seed (Recommended)

Create new seed file with exhaustion projections, loaded after recurrence.v1.json.
Keeps seeds modular and follows existing pattern.

### Option B: Extend recurrence.v1.json

Add exhaustion projections to existing seed. Simpler but less modular.

**Recommendation:** Option A - separate seed for clarity and testability.

### Kernel Execution Flow

```
1. run_mu_structural() produces trace
2. Recurrence (_detect_closure) checks for state recurrence → may log τ
3. Exhaustion (_detect_exhaustion) checks for operator exhaustion
4. If exhaustion detected:
   a. Add operator to frozen set
   b. Re-run with frozen operator excluded from projection pool
5. If globalstall detected:
   a. Log globalstall event
   b. Terminate run
```

---

## Frozen Set as Linked List

The frozen set must be structural (Mu linked list), not a Python set:

```json
// Empty frozen set
null

// One frozen operator
{"head": "proj.id.1", "tail": null}

// Multiple frozen operators
{"head": "proj.id.2", "tail": {"head": "proj.id.1", "tail": null}}
```

### Membership Check (Structural)

Uses same pattern as Recurrence seen-set:
```json
{
  "id": "exhaustion.in_frozen",
  "pattern": {
    "_check": {"var": "op_id"},
    "_frozen": {"head": {"var": "op_id"}, "tail": {"var": "_"}}
  },
  "body": {"found": true}
}
```

This uses non-linear pattern matching (same var `op_id` twice) to detect equality.

---

## Success Criteria

### 1. Projections Exist
- [x] `mu/closures/exhaustion.v1.json` exists (see `test_seed_counts.py` for count)
- [x] Each projection has `id`, `pattern`, `body` fields (enforced by `seed_integrity.py`)
- [x] SHA256 checksum verified on load (enforced by `seed_integrity.py`)

### 2. Execution is Structural (HYBRID)
- [x] Exhaustion detection runs via `eval_seed.step()` (bootstrap primitive)
- [x] Frozen set is Mu linked-list, NOT Python set
- [x] Exhaustion LOGIC is in projections (exhaustion.v1.json)
- **Note:** Uses `run_algorithm_meta_circular()` which delegates to Python match/substitute. This is the HYBRID execution model - projections define semantics, bootstrap provides execution. True meta-circular requires non-linear pattern support in structural kernel.

### 3. Cross-Substrate Parity
- [x] Same projections produce same results on Python and JS
- [x] Parity tests in `tests/test_exhaustion_parity.py`
- [x] JS loads exhaustion.v1.json in `mu/host/js/eval_step.js`
- **Note:** JS uses its own bootstrap match/substitute implementation. Cross-substrate parity tests verify identical results.

### 4. Integration Tests
- [ ] Single operator exhaustion detected and frozen
- [ ] Multiple operator exhaustion leads to fallback
- [ ] All operators frozen leads to globalstall
- [ ] Already-frozen operators skipped correctly

---

## Test Vectors

| Vector ID | Scenario | Expected |
|-----------|----------|----------|
| `exhaustion.no_tau` | No τ logged | `action: "continue"` |
| `exhaustion.single_op_exhausted` | Same op since τ | `action: "freeze"` |
| `exhaustion.different_op` | Different op after τ | `action: "continue"` |
| `exhaustion.already_frozen` | Op already in frozen | Skip, try next |
| `exhaustion.globalstall` | All ops frozen | `action: "globalstall"` |
| `exhaustion.recovery` | New op after freeze | Normal execution |

---

## Anti-Patterns (Violations)

**DO NOT:**

1. **Python loop for trace scan:**
   ```python
   # WRONG - Python iterates trace
   for entry in trace:
       if entry.projection != target_op:
           return not_exhausted
   ```

2. **Python set for frozen operators:**
   ```python
   # WRONG - Python data structure
   frozen = set()
   frozen.add(op_id)
   ```

3. **Python conditional for exhaustion:**
   ```python
   # WRONG - Python decides exhaustion
   if all(e.projection == op for e in trace[tau_step:]):
       return freeze(op)
   ```

**DO:**

1. **Structural trace scan with projections**
2. **Mu linked-list for frozen set**
3. **Pattern matching for equality checks**

---

## Security Considerations (Adversary Review)

The Adversary agent identified two CRITICAL vulnerabilities that must be
addressed before implementation.

### V2: Reserved Fields Must Include Exhaustion Fields

**Vulnerability:** Without reserved field protection, domain data could contain
`_detect_exhaustion`, `_frozen`, or `_tau_step`, potentially bypassing validation.

**Mitigation:** Add exhaustion-related fields to `KERNEL_RESERVED_FIELDS` in
`rcx_pi/selfhost/step_mu.py`:

```python
KERNEL_RESERVED_FIELDS = frozenset({
    # Existing fields (12)
    "_mode", "_phase", "_input", "_remaining", "_status", "_bindings",
    "_match_ctx", "_subst_ctx", "_result", "_stall", "_step", "_projs",
    # NEW: Exhaustion detection fields (4)
    "_detect_exhaustion", "_frozen", "_tau_step", "_operator_ids",
})
```

This ensures `validate_no_kernel_reserved_fields()` rejects domain data with
these fields, preventing injection attacks.

### V3: Frozen List Structure Validation

**Vulnerability:** A forged frozen list containing all operator IDs would trigger
premature globalstall, causing denial of service.

**Mitigation:** The frozen list should only be modified by the exhaustion
detection projections themselves, not accepted from external input.

**Implementation approach:**
1. Initialize `frozen` to `null` (empty) at the start of each run
2. Only `exhaustion.freeze` projection can add to the frozen list
3. Validate that frozen list entries are strings (operator IDs)
4. Never accept pre-populated frozen list from domain input

**Boundary validation:**
```python
def validate_frozen_list(frozen: Mu) -> None:
    """Validate frozen list structure (linked list of strings)."""
    current = frozen
    while current is not None:
        if not isinstance(current, dict):
            raise ValueError("Frozen list must be linked list")
        if set(current.keys()) != {"head", "tail"}:
            raise ValueError("Frozen list entry must have head/tail")
        if not isinstance(current.get("head"), str):
            raise ValueError("Frozen operator ID must be string")
        current = current.get("tail")
```

---

## Implementation Sequence

1. **Update KERNEL_RESERVED_FIELDS** with exhaustion fields (V2 fix)
2. **Update Recurrence** to return tau_step (Q2 resolution)
3. **Create `mu/closures/exhaustion.v1.json`** with ~6 projections (Expert simplification)
4. **Add frozen list validation** in step_mu.py (V3 fix)
5. **Create parity vectors** in `tests/fixtures/exhaustion_vectors.json`
6. **Create Python tests** in `tests/test_exhaustion_parity.py`
7. **Port to JS** and verify same results
8. **Demo script** showing exhaustion detection

---

## Complexity Estimate (Revised)

| Item | Estimate |
|------|----------|
| KERNEL_RESERVED_FIELDS update | 4 new fields |
| Recurrence tau_step extension | 3 projection edits |
| Projections | ~6 new (down from 10) |
| Frozen list validation | ~20 lines Python |
| Test vectors | ~6 |
| Parity tests | ~15 |
| Integration tests | ~10 |
| JS port | ~50 lines |

**Total effort:** Smaller than Step 5 (Recurrence had 9 projections, this has 6)

---

## Open Questions (RESOLVED)

### Q1: Projection pool management - How does the kernel know which operators exist?

**Resolution: Pass projection IDs as linked list in input**

The exhaustion detector needs to know which operators exist to detect globalstall
(all operators frozen). Solution: extract IDs from the projection list and pass
explicitly.

**Input format:**
```json
{
  "_detect_exhaustion": {
    "trace": <linked_list>,
    "frozen": <linked_list>,
    "tau_step": <int_or_null>,
    "operator_ids": <linked_list_of_strings>  // NEW: all known operator IDs
  }
}
```

**Rationale:**
- Explicit is better than implicit (projection list structure may change)
- Caller already has the projection list; extracting IDs is trivial
- Enables globalstall detection: `length(frozen) >= length(operator_ids)`

**Implementation:** `run_mu_structural()` extracts projection IDs before calling
exhaustion detection.

---

### Q2: τ logging coordination - Who sets tau_step?

**Resolution: Recurrence returns tau_step in closure evidence**

When Recurrence detects closure (`recurrence.found_in_seen`), it already has the
step number in the `_step` field. Extend the output format to include it.

**Current Recurrence output:**
```json
{
  "closure_detected": true|false,
  "final_result": <value>
}
```

**Extended output (v1.1):**
```json
{
  "closure_detected": true|false,
  "final_result": <value>,
  "tau_step": <int_or_null>  // Step where closure detected (null if no closure)
}
```

**Required changes to recurrence.v1.json:**

1. Modify `recurrence.found_in_seen` to preserve step in output:
```json
{
  "id": "recurrence.found_in_seen",
  "body": {
    "_mode": "enginenews_done",
    "_closure": true,
    "_tau_step": {"var": "step"},  // NEW: preserve the step
    "_result": {"var": "result"}
  }
}
```

2. Modify `recurrence.end_of_trace` to set tau_step null:
```json
{
  "id": "recurrence.end_of_trace",
  "body": {
    "_mode": "enginenews_done",
    "_closure": false,
    "_tau_step": null,  // NEW: no closure = no tau
    "_result": {"var": "result"}
  }
}
```

3. Modify `recurrence.unwrap` to include tau_step:
```json
{
  "id": "recurrence.unwrap",
  "body": {
    "closure_detected": {"var": "closure"},
    "final_result": {"var": "result"},
    "tau_step": {"var": "tau"}  // NEW
  }
}
```

**Rationale:**
- Recurrence already detects the τ moment (state recurrence)
- Natural integration point - no separate phase needed
- Backward compatible: existing tests still work (just ignore tau_step)

---

### Q3: Recovery from freeze - Can a frozen operator be unfrozen?

**Resolution: No automatic unfreezing in Step 6**

The spec says "unless it yields novel fixers" but defining "novel" requires
additional infrastructure (fixer tracking, state comparison). For Step 6:

**Decision:** Frozen operators stay frozen until the run terminates.

**Rationale:**
- Keep Step 6 simple and focused on exhaustion detection
- The primary use case (prevent infinite loops) is fully served
- Unfreezing can be added as Step 7 enhancement if needed

**Future work (not Step 6):**
- Track "fixers" (projections that make genuine progress)
- Define "novel" = fixer not seen since last τ
- Allow unfreezing when novel fixer detected

**Spec compliance note:** Rule 3.1 says unfreezing is valid "unless it yields
novel fixers" - our implementation is MORE RESTRICTIVE (never unfreeze), which
is safe. We can relax later without breaking correctness.

---

## Related Documents

- **RCXEngineNew.pdf** - Rule 3.1 (page 10)
- `docs/core/RecurrenceStructural.v0.md` - Step 5 (Rule 2.2♢)
- `docs/core/MetaCircularKernel.v0.md` - Kernel architecture
- `mu/closures/recurrence.v1.json` - Closure detection projections

---

## Changelog

- **v0.2 (2026-02-02):** IMPLEMENTED - Step 6 complete
  - Created `mu/closures/exhaustion.v1.json` with 11 projections (more than estimated due to three-phase state machine)
  - Non-linear patterns for equality detection (step, operator, frozen membership)
  - First-match-wins ordering for scan_same before scan_different
  - 17 parity tests in `tests/test_exhaustion_parity.py`
  - 10 fuzzer tests in `tests/test_exhaustion_fuzzer.py`
  - 6 test vectors in `tests/fixtures/exhaustion_vectors.json`
  - Cross-substrate parity: Python and JavaScript produce identical results
  - JS loads exhaustion.v1.json (47 total projections across all seeds)
  - KERNEL_RESERVED_FIELDS updated to 22 (12 kernel + 3 Recurrence + 3 Exhaustion + 4 Bridge)
  - Automated parity test verifies Python/JS reserved fields match
- **v0.1 (2026-02-01):** Address open questions and agent review findings:
  - Q1 RESOLVED: Pass operator_ids explicitly in input
  - Q2 RESOLVED: Recurrence returns tau_step in closure evidence
  - Q3 RESOLVED: No automatic unfreezing in Step 6 (keep simple)
  - V2 FIX: Add exhaustion fields to KERNEL_RESERVED_FIELDS
  - V3 FIX: Add frozen list structure validation
  - SIMPLIFIED: Reduce from 10 to ~6 projections (Expert review)
- **v0 (2026-02-01):** Initial design doc for Rule 3.1 (Operator Exhaustion)
