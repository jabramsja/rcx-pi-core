# Orbit visualization (SVG) from DOT fixture (v1)

This is a thin, deterministic rendering step:

- Golden DOT: `docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot`
- Golden SVG: `docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg`

Generate (requires Graphviz):

    ./scripts/render_orbit_dot_to_svg.sh

The SVG is a stable “viewable artifact” derived from the DOT, which is derived deterministically from `rcx.engine_run.v1`.
