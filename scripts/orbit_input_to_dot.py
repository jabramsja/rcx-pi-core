#!/usr/bin/env python3
"""
RCX Orbit Input → DOT
====================

Consumes orbit_input_v1.json and produces a deterministic Graphviz DOT.
This is a strict boundary: orbit does NOT depend on raw engine_run.
"""

import json
import sys

if len(sys.argv) != 3:
    print("usage: orbit_input_to_dot.py <orbit_input.json> <out.dot>", file=sys.stderr)
    sys.exit(2)

inp, outp = sys.argv[1:3]

with open(inp) as f:
    data = json.load(f)

if data.get("schema_version") != "rcx.orbit_input.v1":
    print("FAIL: unsupported orbit_input schema_version", file=sys.stderr)
    sys.exit(2)

nodes = data.get("nodes", [])
edges = data.get("edges", [])

with open(outp, "w") as f:
    f.write("digraph RCX {\n")

    for n in nodes:
        nid = n.get("id")
        label = n.get("label", nid)
        if nid is None:
            continue
        f.write(f'  "{nid}" [label="{label}"];\n')

    for e in edges:
        src = e.get("from")
        dst = e.get("to")
        if src is None or dst is None:
            continue
        f.write(f'  "{src}" -> "{dst}";\n')

    f.write("}\n")

print(f"OK: wrote {outp}")
