<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-20
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/research/test_json_to_dag_roundtrip.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Mu DAG ABI Spike v0

**Status:** Research evidence (not a runtime change)
**Compiler:** `tools/compilers/json_to_dag.py`
**Tests:** `tests/research/test_json_to_dag_roundtrip.py` (22 tests)

---

## What This Proves

1. **Deterministic compilation.** Mu seed JSON (match.v2.json, subst.v2.json) compiles to a flat, integer-indexed DAG. Same input produces byte-identical serialized output across runs and reloads.

2. **Lossless roundtrip.** JSON -> DAG -> JSON preserves all structural content (meta, projection IDs, patterns, bodies). Description fields are intentionally dropped (human documentation, not structural data).

3. **Content-addressed sharing.** Identical subtrees share the same node ID. The DAG has fewer nodes than a naive tree expansion. Both seeds exhibit sharing.

4. **Sequential integer IDs.** Nodes are numbered 0..N-1 with bottom-up assignment (children get lower IDs than parents). All internal references are valid.

## What This Does NOT Prove

- Runtime performance improvement (no engine changes)
- Binary ABI stability (format may change)
- Completeness for all possible Mu values (tested on match.v2 and subst.v2 only)
- That this format is necessary or sufficient for L4 compilation

## Metrics (Baseline)

| Seed | Nodes | Edges | Projections |
|------|-------|-------|-------------|
| match.v2.json | 70 | 206 | 8 |
| subst.v2.json | 95 | 372 | 12 |

These counts are locked by `tests/research/test_json_to_dag_roundtrip.py::TestBaselineCounts`.

## DAG Format

```json
{
  "meta": { ... },
  "nodes": [
    {"id": 0, "type": "string", "value": "match"},
    {"id": 1, "type": "var", "name": "x"},
    {"id": 2, "type": "dict", "entries": [{"key": 0, "value": 1}]},
    {"id": 3, "type": "array", "children": [0, 2]}
  ],
  "projections": [
    {"id": "match.done", "pattern_root": 2, "body_root": 3}
  ],
  "metrics": {
    "node_count": 4,
    "edge_count": 3,
    "projection_count": 1
  }
}
```

Node types: `null`, `bool`, `number`, `string`, `var`, `array`, `dict`.

## Design Decisions

- **Sorted dict keys** for canonical interning (deterministic). Roundtrip preserves sorted order, not original insertion order.
- **Bottom-up ID assignment** so children always have lower IDs than parents. This enables single-pass forward reconstruction.
- **`{"var": x}` special-cased** as `var` node type (not a generic dict) since Mu variables are structural primitives.
- **No description passthrough** in projections. Descriptions are human documentation; the DAG captures structural semantics only.

## Future Directions (Not Authorized)

These are observations, not work items. None may proceed without explicit VECTOR promotion.

- Binary serialization (flatbuffers, msgpack) for size/speed
- Incremental compilation (reuse DAG nodes across seed versions)
- DAG-level optimization passes (dead node elimination, subtree hoisting)
- Runtime integration (load DAG directly instead of JSON)
