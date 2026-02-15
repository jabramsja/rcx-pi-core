<!--
DOC_STATUS
TYPE: REFERENCE
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

# Orbit visualization (DOT) from engine_run JSON (v1)

This is a pure consumer tool: it reads an existing `rcx.engine_run.v1` JSON file and emits a Graphviz `.dot` graph.

- Input: `mu/docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json`
- Output (golden): `mu/docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot`

Orbit notion (v1):
- Each trace event has a `payload`.
- We connect consecutive payloads as directed edges.
- Edge label includes: step_index | phase | route

Generate DOT (from repo root):

    ./scripts/orbit_engine_run_to_dot.py mu/docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json /tmp/orbit.dot

Optional render (if graphviz is installed):

    dot -Tsvg /tmp/orbit.dot > /tmp/orbit.svg
