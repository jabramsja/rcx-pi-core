"""
Compile Mu seed JSON to a deterministic integer-indexed DAG.

This is a research spike — it does NOT replace the runtime engine.
It proves that Mu projections can be compiled to a flat, content-addressed
DAG format with lossless roundtrip to canonical JSON.

Usage:
    python tools/compilers/json_to_dag.py mu/substrate/match.v2.json
    python tools/compilers/json_to_dag.py mu/substrate/subst.v2.json

Output: JSON DAG with integer node IDs, deterministic across runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def compile_to_dag(seed: dict) -> dict:
    """Compile a Mu seed to a deterministic integer-indexed DAG.

    Returns a dict with:
        meta: original seed meta (passthrough)
        nodes: list of {id: int, type: str, value: ...} — the flat node table
        projections: list of {id: str, pattern_root: int, body_root: int}
        metrics: {node_count: int, edge_count: int, projection_count: int}
    """
    intern_table: dict[str, int] = {}  # canonical JSON -> node id
    nodes: list[dict] = []
    edge_count = 0

    def intern(value: Any) -> int:
        """Intern a Mu value, returning its integer node ID.

        Identical subtrees get the same ID (content-addressed).
        Children are interned before the parent so node IDs are sequential.
        """
        nonlocal edge_count
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if canonical in intern_table:
            return intern_table[canonical]

        if value is None:
            node_id = len(nodes)
            intern_table[canonical] = node_id
            nodes.append({"id": node_id, "type": "null", "value": None})
        elif isinstance(value, bool):
            node_id = len(nodes)
            intern_table[canonical] = node_id
            nodes.append({"id": node_id, "type": "bool", "value": value})
        elif isinstance(value, (int, float)):
            node_id = len(nodes)
            intern_table[canonical] = node_id
            nodes.append({"id": node_id, "type": "number", "value": value})
        elif isinstance(value, str):
            node_id = len(nodes)
            intern_table[canonical] = node_id
            nodes.append({"id": node_id, "type": "string", "value": value})
        elif isinstance(value, list):
            # Intern children first so they get lower IDs (bottom-up)
            children = [intern(item) for item in value]
            node_id = len(nodes)
            intern_table[canonical] = node_id
            edge_count += len(children)
            nodes.append({"id": node_id, "type": "array", "children": children})
        elif isinstance(value, dict):
            if "var" in value and len(value) == 1:
                node_id = len(nodes)
                intern_table[canonical] = node_id
                nodes.append({"id": node_id, "type": "var", "name": value["var"]})
            else:
                # Intern children first so they get lower IDs (bottom-up)
                entries = []
                for k in sorted(value.keys()):
                    key_id = intern(k)
                    val_id = intern(value[k])
                    entries.append({"key": key_id, "value": val_id})
                    edge_count += 2
                node_id = len(nodes)
                intern_table[canonical] = node_id
                nodes.append({"id": node_id, "type": "dict", "entries": entries})
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

        return node_id

    compiled_projections = []
    for proj in seed.get("projections", []):
        pattern_root = intern(proj["pattern"])
        body_root = intern(proj["body"])
        compiled_projections.append({
            "id": proj["id"],
            "pattern_root": pattern_root,
            "body_root": body_root,
        })

    return {
        "meta": seed["meta"],
        "nodes": nodes,
        "projections": compiled_projections,
        "metrics": {
            "node_count": len(nodes),
            "edge_count": edge_count,
            "projection_count": len(compiled_projections),
        },
    }


def dag_to_json_seed(dag: dict) -> dict:
    """Reconstruct a Mu seed from a DAG (lossless roundtrip).

    Returns a seed dict with meta + projections (pattern/body as JSON trees).
    """
    nodes = dag["nodes"]

    def reconstruct(node_id: int) -> Any:
        node = nodes[node_id]
        ntype = node["type"]

        if ntype == "null":
            return None
        elif ntype == "bool":
            return node["value"]
        elif ntype == "number":
            return node["value"]
        elif ntype == "string":
            return node["value"]
        elif ntype == "var":
            return {"var": node["name"]}
        elif ntype == "array":
            return [reconstruct(child_id) for child_id in node["children"]]
        elif ntype == "dict":
            result = {}
            for entry in node["entries"]:
                key = reconstruct(entry["key"])
                val = reconstruct(entry["value"])
                result[key] = val
            return result
        else:
            raise ValueError(f"Unknown node type: {ntype}")

    projections = []
    for proj in dag["projections"]:
        projections.append({
            "id": proj["id"],
            "pattern": reconstruct(proj["pattern_root"]),
            "body": reconstruct(proj["body_root"]),
        })

    return {
        "meta": dag["meta"],
        "projections": projections,
    }


def serialize_dag(dag: dict) -> str:
    """Serialize DAG to deterministic JSON (byte-identical across runs)."""
    return json.dumps(dag, sort_keys=True, indent=2, ensure_ascii=True)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/compilers/json_to_dag.py <seed.json>", file=sys.stderr)
        sys.exit(1)

    seed_path = Path(sys.argv[1])
    with open(seed_path) as f:
        seed = json.load(f)

    dag = compile_to_dag(seed)
    print(serialize_dag(dag))

    metrics = dag["metrics"]
    print(
        f"\n# {seed_path.name}: {metrics['node_count']} nodes, "
        f"{metrics['edge_count']} edges, "
        f"{metrics['projection_count']} projections",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
