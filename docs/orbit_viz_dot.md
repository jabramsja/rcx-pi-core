# Orbit visualization (DOT) from engine_run JSON (v1)

This is a pure consumer tool: it reads an existing `rcx.engine_run.v1` JSON file and emits a Graphviz `.dot` graph.

- Input: `docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json`
- Output (golden): `docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot`

Orbit notion (v1):
- Each trace event has a `payload`.
- We connect consecutive payloads as directed edges.
- Edge label includes: step_index | phase | route

Generate DOT (from repo root):

    ./scripts/orbit_engine_run_to_dot.py docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json /tmp/orbit.dot

Optional render (if graphviz is installed):

    dot -Tsvg /tmp/orbit.dot > /tmp/orbit.svg
