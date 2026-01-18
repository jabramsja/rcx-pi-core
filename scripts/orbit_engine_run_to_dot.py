#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def eprint(*a):
    print(*a, file=sys.stderr)

def dot_escape(s: str) -> str:
    # Keep it simple and deterministic.
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

def load_engine_run(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("engine_run json must be an object")
    schema = data.get("schema")
    if schema != "rcx.engine_run.v1":
        raise ValueError(f"unexpected schema: {schema!r} (expected rcx.engine_run.v1)")
    if "trace" not in data or not isinstance(data["trace"], list):
        raise ValueError("missing/invalid trace array")
    return data

def build_edges(data: dict):
    # Orbit notion (v1): connect consecutive trace payloads.
    # Edge label includes step_index + phase + route.
    edges = []
    prev_payload = None

    for ev in data["trace"]:
        step = ev.get("step_index", ev.get("step"))
        phase = ev.get("phase", "")
        route = ev.get("route", "")
        payload = ev.get("payload", "")

        if not isinstance(payload, str):
            payload = str(payload)

        if prev_payload is not None:
            label = f"{step}|{phase}|{route}"
            edges.append((prev_payload, payload, label))

        prev_payload = payload

    return edges

def to_dot(world: str, edges):
    nodes = {}
    def node_id(payload: str) -> str:
        if payload not in nodes:
            nodes[payload] = f"n{len(nodes)+1}"
        return nodes[payload]

    # Deterministic by first appearance order.
    lines = []
    lines.append("digraph rcx_orbit {")
    lines.append('  rankdir=LR;')
    lines.append('  labelloc="t";')
    lines.append(f'  label="{dot_escape(world)} | rcx.engine_run.v1 orbit";')
    lines.append("  node [shape=box];")

    for a, b, _label in edges:
        node_id(a)
        node_id(b)

    for payload, nid in nodes.items():
        lines.append(f'  {nid} [label="{dot_escape(payload)}"];')

    for a, b, label in edges:
        ida = node_id(a)
        idb = node_id(b)
        lines.append(f'  {ida} -> {idb} [label="{dot_escape(label)}"];')

    lines.append("}")
    return "\n".join(lines) + "\n"

def usage():
    eprint("usage:")
    eprint("  orbit_engine_run_to_dot.py <engine_run_json> <out.dot>")
    eprint("example:")
    eprint("  orbit_engine_run_to_dot.py docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json /tmp/orbit.dot")
    sys.exit(2)

def main():
    if len(sys.argv) != 3:
        usage()

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = load_engine_run(in_path)
    world = data.get("world", "unknown_world")
    edges = build_edges(data)
    dot = to_dot(world, edges)

    out_path.write_text(dot, encoding="utf-8")
    print(f"OK: wrote {out_path}")

if __name__ == "__main__":
    main()
