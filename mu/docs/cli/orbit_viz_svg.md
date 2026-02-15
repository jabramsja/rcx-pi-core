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

# Orbit visualization (SVG) from DOT fixture (v1)

This is a thin, deterministic rendering step:

- Golden DOT: `mu/docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot`
- Golden SVG: `mu/docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg`

Generate (requires Graphviz):

    ./scripts/render_orbit_dot_to_svg.sh

The SVG is a stable “viewable artifact” derived from the DOT, which is derived deterministically from `rcx.engine_run.v1`.
