<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-03-01
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md Ra [P6 decided]
GROUNDING_TESTS: tests/l4_gates/test_numeric_hash_safety_lock_gate.py

This header enables automated doc drift detection.
Scope: P6 VECTOR decision packet — typed numeric envelopes for cross-substrate int/float lexical parity.
-->

# P6: Typed Numeric Envelopes — Decision Packet

> **Status:** DECIDED — Option A (NO strict lexical parity) with containment discipline
> **Decision date:** 2026-03-01 (founder)
> **Policy lock:** `TestNumericNonLinearPolicyLock` in `tests/l4_gates/test_numeric_hash_safety_lock_gate.py`
> **Tracker:** TASKS.md Ra section `[P6]`

---

## Decision Record

**Decision:** Option A — NO strict cross-substrate int/float lexical parity. Accept current substrate-model difference as intentional and permanent unless evidence triggers re-evaluation.

**Rationale (founder):** Lowest-regret choice. Preserves current correctness, keeps runtime/debt stable. Option B is a large semantic migration with no current workload demand. No real seed or production vector requires mixed numeric forms in non-linear matching today.

**Containment discipline (mandatory with Option A):**

1. **Policy lock tests remain enforced.** `TestNumericNonLinearPolicyLock` in `test_numeric_hash_safety_lock_gate.py` documents and locks the exact substrate-model difference. These tests must not be deleted or weakened.

2. **Canonical seeds remain integer-only.** No float literals in seed files (`mu/substrate/`, `mu/closures/`, `mu/bridge/`, `mu/programs/`) unless explicitly promoted with founder sign-off and P6 re-evaluation.

3. **Hard promotion triggers for P6 re-evaluation (any one suffices):**
   - First real workload requiring mixed numeric forms (int + float) in non-linear pattern matching.
   - Observed closure/routing divergence from numeric lexical mismatch in production vectors.
   - New seed file that requires float literals for correctness.

4. **If triggered:** Re-open P6 as NEXT with this design packet as baseline. Option B envelope schema candidates (Section 4) are ready for implementation.

---

## 1. Decision To Make

**Should RCX require strict cross-substrate int/float lexical parity in non-linear pattern matching?**

- **YES** = `match([{"var":"x"},{"var":"x"}], [1.0, 1])` must produce the same result (MATCH or NO_MATCH) on both Python and JavaScript.
- **NO** = The current substrate-model difference is accepted as intentional and permanent.

This is a binary founder decision. The options below describe what each answer entails.

---

## 2. Baseline Truth (Current Behavior)

### Python substrate

```python
from rcx_pi.selfhost.eval_seed import match, NO_MATCH
match([{"var": "x"}, {"var": "x"}], [1.0, 1])  # => NO_MATCH
```

- `int` and `float` are distinct types in CPython.
- Content hash (`mu_hash_cached`) serializes via `json.dumps(sort_keys=True)`.
- `json.dumps(1)` = `"1"`, `json.dumps(1.0)` = `"1.0"` — different strings, different hashes.
- Non-linear binding conflict: `x` binds to `1.0`, then `1` fails equality check.

### JavaScript substrate

```javascript
match([{var: "x"}, {var: "x"}], [1.0, 1])  // => {x: 1}  (match succeeds)
```

- JS has a single `Number` type. `1.0 === 1` is `true`.
- Content hash (`muHashCached`) serializes via `JSON.stringify` with sorted keys.
- `JSON.stringify(1.0)` = `JSON.stringify(1)` = `"1"` — same string, same hash.
- Non-linear binding: `x` binds to `1`, then `1` passes equality check.

### Where the policy lock lives

| Artifact | Location |
|----------|----------|
| Python policy test | `tests/l4_gates/test_numeric_hash_safety_lock_gate.py::TestNumericNonLinearPolicyLock::test_policy_python_int_float_nonlinear_conflict` |
| JS policy test | `tests/l4_gates/test_numeric_hash_safety_lock_gate.py::TestNumericNonLinearPolicyLock::test_policy_js_number_model_nonlinear_no_conflict` |
| Content hash (Py) | `mu_type.py::mu_hash_cached` (type-preserving) |
| Content hash (JS) | `types.js::muHashCached` (type-preserving within Number model) |
| Control hash (Py) | `mu_type.py::mu_hash_control_cached` (canonicalizes integral float to int) |
| Control hash (JS) | `types.js::muHashControlCached` (canonicalizes integral float to int) |
| Canonicalizer (Py) | `mu_type.py::_canonicalize_hash_numeric` |

### Why the difference exists

The divergence is not a bug — it is an unavoidable consequence of the host language's type system:

- Python: `type(1) is int`, `type(1.0) is float`, `1 == 1.0` but `type(1) != type(1.0)`.
- JavaScript: `typeof 1 === typeof 1.0 === "number"`, `1 === 1.0` (no distinction possible at language level).

Content hash faithfully reflects what each substrate can distinguish. Control hash canonicalizes across this boundary (integral float to int) specifically for stall/convergence detection, where type-level distinction would cause false non-convergence.

---

## 3. Option Set

### Option A: Keep Current Policy (NO strict lexical parity)

**What:** Accept that non-linear matching on mixed int/float inputs produces substrate-dependent results. Policy lock tests document and enforce this. No code changes.

**Semantic consequences:**
- Non-linear patterns with mixed numeric types are substrate-dependent.
- All other matching (linear patterns, non-numeric, control hash paths) is already cross-substrate identical.
- Seed files use integers only (no float literals in production seeds), so this affects only domain-input edge cases.

**Blast radius:** Zero files changed.

**Migration cost:** None.

**Debt/marker effect:** No change. Debt stays at 11 Python + 19 JS.

**Test impact:** Existing policy lock tests remain as-is. No new tests needed.

**Risk:** If future seeds or domain programs rely on non-linear float/int matching, behavior will silently differ between substrates. Mitigated by seed files being integer-only today.

---

### Option B: Typed Numeric Envelopes (YES strict lexical parity)

**What:** Wrap all numeric values in explicit type-preserving structures at substrate boundaries, making int vs float distinction visible as JSON structure rather than host type.

**Semantic consequences:**
- `1` becomes `{"_mu_int": 1}`, `1.0` becomes `{"_mu_float": 1.0}` (or equivalent schema — see Section 4).
- Both substrates can distinguish int from float at the Mu level, regardless of host type system.
- Non-linear matching becomes cross-substrate identical: `[x,x]` with `[envelope(1.0), envelope(1)]` produces conflict on both substrates.
- All numeric comparisons, hashing, pattern matching, and substitution must unwrap/rewrap envelopes.

**Blast radius:**

| System | Files affected | Nature of change |
|--------|---------------|------------------|
| Mu type system | `mu_type.py`, `types.js` | `is_mu`, `mu_equal`, hash functions must recognize envelopes |
| Match | `eval_seed.py`, `bootstrap_core.js` | `_match_inner`/`match` must unwrap for comparison |
| Substitute | `eval_seed.py`, `bootstrap_core.js` | Must preserve envelope through substitution |
| Normalization | `match_mu.py`, `bootstrap_core.js` | `normalize`/`denormalize` must handle envelopes |
| Kernel | `step_mu.py`, `kernel.js` | Step/stall detection must handle enveloped values |
| Seed files | All 14 in `mu/substrate/`, `mu/closures/`, `mu/bridge/`, `mu/programs/` | Numeric literals → envelopes |
| Reserved fields | `step_mu.py`, `constants.js` | `_mu_int`, `_mu_float` added to reserved set |
| JSON API | `json_handlers.js`, CLI tools | Input/output normalization layer |
| Tests | ~100+ test files | Numeric assertions, fixtures, parity tests |

**Migration cost:** HIGH. Estimated 30-50 files, 500-1000 line changes. Requires coordinated simultaneous update of both substrates, all seeds, and all tests. Cannot be done incrementally — envelope-aware and non-envelope code cannot coexist without a compatibility layer.

**Debt/marker effect:** Adds host markers for envelope wrapping/unwrapping (new `@host_builtin` sites). Estimated +3-5 new debt sites (Python + JS). Increases bootstrap complexity — envelopes must be recognized before match/substitute can operate, adding a layer below the current bootstrap floor.

**Test impact:** All numeric test fixtures change. Parity tests must verify envelope round-trip. New envelope validation tests. Estimated 200+ test lines changed.

**Risk:** High. Fundamental data representation change touching every layer. Envelope wrapping is a new form of host semantics — the decision of when to wrap/unwrap is a host-language operation, not a structural one.

---

### Option C: Boundary Normalization (Hybrid/Compat)

**What:** Add an optional normalization pass at the JSON API boundary that converts ambiguous numeric inputs to canonical form. Default behavior unchanged; opt-in via API flag or projection-level annotation.

**Semantic consequences:**
- When enabled, all numbers entering the system are normalized to a canonical form (e.g., all integers stay int, all floats with `.0` suffix become int).
- This makes both substrates see the same canonical input, producing identical results.
- Does NOT make the substrates internally type-aware — just ensures inputs are pre-normalized.
- Non-linear matching on pre-normalized inputs agrees across substrates.
- Raw API without normalization retains current substrate-model behavior.

**Blast radius:**

| System | Files affected | Nature of change |
|--------|---------------|------------------|
| JSON API boundary | `json_handlers.js`, CLI entry points | Add normalization pass |
| Python API boundary | `step_mu.py` top-level functions | Add normalization pass |
| Tests | 5-10 test files | New normalization tests, opt-in flag tests |

**Migration cost:** LOW. 5-10 files, ~100 lines. Existing behavior unchanged by default.

**Debt/marker effect:** +1-2 new `@host_builtin` sites for the normalization function. Minimal.

**Test impact:** New tests for normalization layer. Existing tests unchanged (default off).

**Risk:** Medium. Does not achieve true lexical parity — only input-normalized parity. If a projection produces `1.0` internally (via substitution), the substrate difference reappears. Solves the symptom but not the root cause. May create false confidence that parity is solved.

---

## 4. Envelope Schema Candidates (If Option B)

### Schema A: Flat typed keys

```json
{"_mu_int": 1}
{"_mu_float": 1.0}
```

- Minimal nesting, easy to read.
- Two new reserved keys: `_mu_int`, `_mu_float`.
- Validation: value of `_mu_int` must be integer, value of `_mu_float` must be number.
- Hashing: content hash operates on the envelope structure — `{"_mu_int": 1}` and `{"_mu_float": 1.0}` produce different hashes on all substrates.
- Seed compatibility: all numeric literals in seeds become `{"_mu_int": N}`.

### Schema B: Structured envelope

```json
{"_mu_num": {"kind": "int", "value": 1}}
{"_mu_num": {"kind": "float", "value": 1.0}}
```

- Single reserved key `_mu_num`.
- Extensible to future numeric types (bigint, decimal).
- More verbose, deeper nesting.
- Validation: `kind` must be `"int"` or `"float"`, `value` must be number.
- Hashing: `kind` field ensures different hashes.
- Seed compatibility: same migration burden as Schema A.

### Schema C: String-encoded value

```json
{"_mu_int": "1"}
{"_mu_float": "1.0"}
```

- Value encoded as string — no host numeric type dependency at all.
- Eliminates JSON round-trip ambiguity (JSON parsers may parse `1.0` as int).
- Requires explicit parsing at every numeric operation (arithmetic, comparison).
- Heaviest runtime cost — string-to-number conversion on every use.

### Schema comparison

| Criterion | A (flat typed) | B (structured) | C (string-encoded) |
|-----------|:-:|:-:|:-:|
| Reserved keys added | 2 | 1 | 2 |
| Nesting depth | +1 | +2 | +1 |
| Extensibility | Limited | Good | Limited |
| Parse cost per use | None | None | String→Number |
| JSON round-trip safety | Host-dependent | Host-dependent | Safe |
| Readability | Good | Moderate | Poor |

### Reserved-field implications

Any envelope key (`_mu_int`, `_mu_float`, `_mu_num`) must be added to `KERNEL_RESERVED_FIELDS` in both substrates. Current reserved set has 22 fields (Python) / 22 fields (JS). Adding 1-2 more is within budget but expands the security boundary. Parity test `test_cross_substrate_constants.py` would need updating.

### Hashing implications

- **Content hash:** Operates on envelope JSON — automatically distinguishes types. No change to hash functions needed.
- **Control hash:** `_canonicalize_hash_numeric` must be updated to canonicalize *through* envelopes: `{"_mu_float": 1.0}` → `{"_mu_int": 1}` for stall detection. Adds complexity but preserves stall semantics.

### Seed compatibility strategy

All 14 seed files use integer literals only (verified by grep). Migration is mechanical: replace bare integers with `{"_mu_int": N}`. No float literals exist in seeds today. The migration script would be deterministic and verifiable by checksum comparison.

---

## 5. Invariants and Non-Goals

### Invariants (must hold regardless of option chosen)

1. **Control-hash stall semantics preserved.** `mu_hash_control_cached` / `muHashControlCached` must continue to canonicalize integral floats for convergence detection. If envelopes are adopted, control hash must canonicalize through envelopes.

2. **Bootstrap primitive count unchanged.** Currently 4 primitives (`eval_step`, `max_steps`, `projection_loader`, `stack_guard`). No option may add a new bootstrap primitive.

3. **No hidden host smuggling.** If envelopes are adopted, the wrapping/unwrapping must be explicit and debt-marked. No silent type coercion behind public API.

4. **Kernel reserved field parity.** Python `KERNEL_RESERVED_FIELDS` and JS `KERNEL_RESERVED_FIELDS` must remain identical sets.

5. **Existing seed integrity.** Seed checksums must remain verifiable. If seeds are migrated, new checksums must be established atomically.

### Non-goals for this decision

- Arbitrary-precision numeric support (bigint, decimal).
- Numeric tower / type promotion rules.
- Float NaN/Infinity handling (already excluded by `is_mu` validation).
- Performance optimization of numeric operations.
- Changes to control-hash canonicalization behavior.

---

## 6. Promotion Criteria: VECTOR to NEXT

For Option B or C to promote from VECTOR to NEXT, ALL of the following must be satisfied:

- [ ] Founder decision: explicit YES on strict lexical parity (this document's decision).
- [ ] Envelope schema chosen (A, B, or C) with rationale documented.
- [ ] Blast radius audit: complete file list with line-level change estimates.
- [ ] Migration script prototype: at least one seed file converted and verified.
- [ ] Parity test prototype: at least one cross-substrate envelope round-trip test.
- [ ] Debt impact assessment: exact count of new `@host_builtin` / `@host_recursion` markers.
- [ ] No blocking L4 gate regression: envelope work must not invalidate existing G1-G8 evidence.
- [ ] Reserved field impact reviewed by adversary agent.
- [ ] Boot0 checklist impact assessed (which N-track items are affected).

For Option A (NO decision), the checklist is:

- [ ] Founder decision: explicit NO on strict lexical parity.
- [ ] Policy lock tests confirmed passing (already done).
- [ ] P6 moved to Ra with decision record.

---

## 7. Recommendation

**Recommendation: Option A (NO strict lexical parity).**

### Rationale

1. **The difference is principled, not accidental.** Content hash faithfully reflects each substrate's type system. Python distinguishes int/float; JS does not. This is a substrate-model fact, not a bug.

2. **No production impact today.** All seed files use integers only. No existing projection relies on non-linear matching with mixed int/float inputs. The divergence is observable only in synthetic edge cases.

3. **Envelopes violate structural minimalism.** RCX's design principle is minimal bootstrap — adding an envelope layer below match/substitute increases the bootstrap surface, adds host-semantics debt, and makes every numeric operation more complex. This runs counter to the self-hosting goal.

4. **Blast radius is disproportionate to benefit.** Option B touches 30-50 files, 500-1000 lines, all 14 seeds, and many test files — for an edge case that does not affect any production path.

5. **The hybrid (Option C) is a half-measure.** It normalizes inputs but not intermediate values, creating false parity confidence. If strict parity matters, only full envelopes achieve it — and the cost is prohibitive.

6. **Future-proofing is already in place.** The policy lock tests document the exact behavior. If strict parity becomes necessary (e.g., a future seed requires non-linear float/int matching), the envelope design is ready to implement.

### Tradeoff Table

| Criterion | A (Keep) | B (Envelopes) | C (Boundary) |
|-----------|:--------:|:-------------:|:------------:|
| Implementation cost | None | Very High | Low |
| Cross-substrate parity | Partial | Full | Partial+ |
| Bootstrap complexity | Unchanged | Increased | Unchanged |
| Debt impact | None | +3-5 sites | +1-2 sites |
| Seed migration | None | All 14 files | None |
| Risk of regression | None | High | Medium |
| Future flexibility | Preserved | Committed | Ambiguous |
| Structural minimalism | Best | Worst | Moderate |

---

## Founder Decision Prompt

```
P6 Decision: Typed Numeric Envelopes

Question: Should RCX require strict cross-substrate int/float
lexical parity in non-linear pattern matching?

Current state: Python and JS produce different results for
match([x,x], [1.0, 1]) due to host type system differences.
This is documented, tested, and policy-locked.

Recommendation: NO (Option A — keep current policy).

Options:
  A) NO  — Accept substrate-model difference. Zero cost. [RECOMMENDED]
  B) YES — Typed numeric envelopes. Full parity. ~50 files, ~1000 lines.
  C) HYBRID — Boundary normalization. Partial parity. ~10 files, ~100 lines.

Decision: _____ (A / B / C)
```
