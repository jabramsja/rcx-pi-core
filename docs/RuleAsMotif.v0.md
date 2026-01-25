# Rule-as-Motif Representation v0

Status: IMPLEMENTED (observability + validation)

**Implementation status:**
- ✅ Rule Motif Observability v0 (`rules --print-rule-motifs`, `rule_motifs_v0()`)
- ✅ Rule Motif Validation Gate v0 (`rules --check-rule-motifs`, `validate_rule_motifs_v0()`)

This document defines the minimal representation of an RCX reduction rule as a motif, such that rules become first-class structural data that the VM can match, inspect, and (eventually) apply.

---

## Purpose

For RCX to be meta-circular, rules cannot remain opaque Python functions. They must be represented as motifs—structural data that follows the same laws as all other RCX values. This document defines what a "rule motif" looks like, without defining how the VM applies it.

**This is the code=data foundation for self-hosting.**

---

## Semantic Question

> What is the minimal representation of an RCX reduction rule as a motif, such that:
> 1. The rule is fully structural (no host-language closures or functions)
> 2. The representation is deterministic and hashable (value_hash works on it)
> 3. The representation contains enough information to perform pattern matching and substitution
> 4. The representation does not leak host semantics

---

## Definitions

### Rule Motif

A motif representing a reduction rule. Contains:
- **pattern**: The structural pattern to match against
- **body**: The structural template to substitute into

Bindings are implicit: variable sites in the pattern with matching names in the body establish the connection. No explicit "bindings" field exists in the representation.

### Pattern

A motif with **variable sites** (placeholders). When matched against a value, variable sites bind to sub-structures.

### Body

A motif with **variable references**. When instantiated, variable references are replaced by their bound values.

### Variable Site

A distinguished leaf in a pattern that binds to whatever appears at that position in the matched value. Representation: `{"var": "<name>"}` where `<name>` is a string identifier.

### Variable Reference

A reference to a bound variable in the body. Same representation as variable site: `{"var": "<name>"}`.

**Context disambiguates usage:** `{"var": ...}` in a pattern is a binding site; in a body it is a variable reference.

---

## Proposed Representation (v0)

A rule motif is a JSON object with the following structure:

```json
{
  "rule": {
    "id": "<rule_id>",
    "pattern": <pattern_motif>,
    "body": <body_motif>
  }
}
```

### Example: add.zero rule

The reduction rule `0 + b → b` (add with zero on the left yields the right operand):

```json
{
  "rule": {
    "id": "add.zero",
    "pattern": {
      "op": "add",
      "a": {"value": 0},
      "b": {"var": "b"}
    },
    "body": {"var": "b"}
  }
}
```

### Example: add.succ rule

The reduction rule `succ(n) + b → succ(n + b)`:

```json
{
  "rule": {
    "id": "add.succ",
    "pattern": {
      "op": "add",
      "a": {"op": "succ", "n": {"var": "n"}},
      "b": {"var": "b"}
    },
    "body": {
      "op": "succ",
      "n": {"op": "add", "a": {"var": "n"}, "b": {"var": "b"}}
    }
  }
}
```

---

## Invariants (Must Not Break)

1. **Determinism**: A rule motif has a unique value_hash. Same rule → same hash.

2. **Structural equality**: Two rule motifs are equal iff their canonical JSON is byte-identical.

3. **No host leakage**: The rule motif contains no Python/Rust callables, no function pointers, no host-specific types.

4. **Canonicalization**: Rule motifs follow the same deep-sort canonicalization as all other motifs (per EntropyBudget.md).

5. **Variable scoping**: All variable references in the body must have corresponding variable sites in the pattern. Unbound variable references are invalid.

6. **Trace compatibility**: Rule motifs can appear in v2 trace events. When a rule is applied, the trace may reference the rule's id or hash.

---

## Non-Goals (Explicit)

1. **Execution semantics**: This document does NOT define how the VM applies a rule motif. That requires VECTOR → NEXT promotion with implementation.

2. **Rule compilation**: No bytecode generation from rule motifs.

3. **Pattern matching algorithm**: How matching works is out of scope. Only the representation is defined.

4. **Rule ordering/priority**: How to select among multiple matching rules is out of scope.

5. **Higher-order rules**: Rules that produce or consume other rules are out of scope for v0.

6. **Rule validation**: Whether a rule motif is "well-formed" is out of scope (no implementation).

7. **Performance**: Representation efficiency is not a v0 concern.

---

## Observability Precedes Mechanics

Following the project principle:

- **v0 (this document)**: Define what a rule looks like as data. ✅
- **NEXT #14**: Emit `rule.loaded` trace events via `rules --print-rule-motifs`. ✅
- **NEXT #15**: Validate rule motifs via `rules --check-rule-motifs`. ✅
- **Future NEXT**: Implement structural pattern matching on rule motifs (mechanics).

No mechanics without prior observability. No implementation without prior design.

---

## Relationship to Existing Docs

| Document | Relationship |
|----------|--------------|
| `MinimalNativeExecutionPrimitive.v0.md` | This extends: rules are part of the substrate |
| `BytecodeMapping.v1.md` | OP_REDUCE will eventually consume rule motifs |
| `MetaCircularReadiness.v1.md` | This unblocks M4 (Organism extraction) |
| `EntropyBudget.md` | Rule motifs must comply with canonicalization |
| `IndependentEncounter.v0.md` | Stall detection may reference rule.id or rule hash |

---

## Promotion Gates (VECTOR → NEXT) ✅ PASSED

All gates passed for observability implementation:

1. **Representation locked**: ✅ The JSON structure for rule motifs is finalized.

2. **Examples validated**: ✅ All 8 rules from rules_pure.py translated to rule motifs (add.zero, add.succ, mult.zero, mult.succ, pred.zero, pred.succ, activation, classify).

3. **value_hash tested**: ✅ Rule motifs produce deterministic output under PYTHONHASHSEED=0 (verified by 11 + 16 CLI tests).

4. **Scope bounded**: ✅ Implementation is read-only: emit to trace, validate structure, no matching.

5. **Observability first**: ✅ `rules --print-rule-motifs` emits `rule.loaded` events; `rules --check-rule-motifs` validates invariants.

---

## Future Work (Not This Document)

These items remain in SINK until this VECTOR is promoted and implemented:

- Structural pattern matching on rule motifs
- Substitution of bindings into body
- Rule sets as motifs (collections of rules)
- Meta-rules (rules that generate rules)
- Self-modifying rule sets

---

## Version

Document version: v0
Last updated: 2026-01-25
Status: IMPLEMENTED (observability + validation)
Implementation:
- `rcx_pi/rule_motifs_v0.py` (RULE_IDS, rule_motifs_v0, validate_rule_motifs_v0)
- `tests/test_rule_motifs_cli.py` (11 tests)
- `tests/test_rule_motif_validation_cli.py` (16 tests)
Dependencies:
- `docs/MinimalNativeExecutionPrimitive.v0.md`
- `docs/BytecodeMapping.v1.md`
- `docs/MetaCircularReadiness.v1.md`
- `EntropyBudget.md`
