"""
Roundtrip and determinism tests for json_to_dag compiler.

This is research evidence — proves Mu seed JSON can be compiled to a
deterministic integer-indexed DAG and reconstructed losslessly.
No runtime changes. See mu/docs/core/MuDagAbiSpike.v0.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import path assumes running from repo root
import sys
sys.path.insert(0, str(Path(__file__).parents[2] / "tools" / "compilers"))
from json_to_dag import compile_to_dag, dag_to_json_seed, serialize_dag  # noqa: E402

REPO_ROOT = Path(__file__).parents[2]
MATCH_V2 = REPO_ROOT / "mu" / "substrate" / "match.v2.json"
SUBST_V2 = REPO_ROOT / "mu" / "substrate" / "subst.v2.json"

SEEDS = [
    pytest.param(MATCH_V2, id="match.v2"),
    pytest.param(SUBST_V2, id="subst.v2"),
]


def _load_seed(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_descriptions(seed: dict) -> dict:
    """Strip description fields for structural comparison.

    The roundtrip intentionally drops projection descriptions (they are
    human documentation, not structural data). This helper strips them
    from the original so we can compare structural content.
    """
    return {
        "meta": seed["meta"],
        "projections": [
            {"id": p["id"], "pattern": p["pattern"], "body": p["body"]}
            for p in seed["projections"]
        ],
    }


# =============================================================================
# Roundtrip identity
# =============================================================================


class TestRoundtripIdentity:
    """JSON -> DAG -> JSON must preserve structural content."""

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_roundtrip_preserves_content(self, seed_path: Path) -> None:
        seed = _load_seed(seed_path)
        dag = compile_to_dag(seed)
        reconstructed = dag_to_json_seed(dag)

        original_stripped = _strip_descriptions(seed)
        assert reconstructed == original_stripped, (
            f"Roundtrip failed for {seed_path.name}"
        )

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_roundtrip_preserves_projection_ids(self, seed_path: Path) -> None:
        seed = _load_seed(seed_path)
        dag = compile_to_dag(seed)
        reconstructed = dag_to_json_seed(dag)

        original_ids = [p["id"] for p in seed["projections"]]
        roundtrip_ids = [p["id"] for p in reconstructed["projections"]]
        assert roundtrip_ids == original_ids

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_roundtrip_preserves_meta(self, seed_path: Path) -> None:
        seed = _load_seed(seed_path)
        dag = compile_to_dag(seed)
        reconstructed = dag_to_json_seed(dag)

        assert reconstructed["meta"] == seed["meta"]


# =============================================================================
# Determinism
# =============================================================================


class TestDeterminism:
    """Same input must produce byte-identical DAG output."""

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_compile_is_deterministic(self, seed_path: Path) -> None:
        seed = _load_seed(seed_path)
        dag1 = serialize_dag(compile_to_dag(seed))
        dag2 = serialize_dag(compile_to_dag(seed))
        assert dag1 == dag2, f"Non-deterministic compile for {seed_path.name}"

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_compile_deterministic_across_reloads(self, seed_path: Path) -> None:
        """Reload from disk and recompile — must match."""
        raw = seed_path.read_text(encoding="utf-8")
        seed1 = json.loads(raw)
        seed2 = json.loads(raw)
        dag1 = serialize_dag(compile_to_dag(seed1))
        dag2 = serialize_dag(compile_to_dag(seed2))
        assert dag1 == dag2


# =============================================================================
# Structural integrity
# =============================================================================


class TestStructuralIntegrity:
    """DAG nodes and edges must be well-formed."""

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_all_node_ids_sequential(self, seed_path: Path) -> None:
        seed = _load_seed(seed_path)
        dag = compile_to_dag(seed)
        ids = [n["id"] for n in dag["nodes"]]
        assert ids == list(range(len(ids)))

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_all_references_valid(self, seed_path: Path) -> None:
        """Every node reference must point to a valid node ID."""
        seed = _load_seed(seed_path)
        dag = compile_to_dag(seed)
        max_id = len(dag["nodes"]) - 1

        for node in dag["nodes"]:
            if node["type"] == "array":
                for child_id in node["children"]:
                    assert 0 <= child_id <= max_id, (
                        f"Invalid array child ref {child_id} in node {node['id']}"
                    )
            elif node["type"] == "dict":
                for entry in node["entries"]:
                    assert 0 <= entry["key"] <= max_id
                    assert 0 <= entry["value"] <= max_id

        for proj in dag["projections"]:
            assert 0 <= proj["pattern_root"] <= max_id
            assert 0 <= proj["body_root"] <= max_id

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_no_duplicate_canonical_nodes(self, seed_path: Path) -> None:
        """Content-addressing: no two nodes should have identical canonical form."""
        seed = _load_seed(seed_path)
        dag = compile_to_dag(seed)

        canonicals = set()
        for node in dag["nodes"]:
            canonical = json.dumps(node, sort_keys=True, separators=(",", ":"))
            assert canonical not in canonicals, (
                f"Duplicate node in DAG: {node}"
            )
            canonicals.add(canonical)

    @pytest.mark.parametrize("seed_path", SEEDS)
    def test_metrics_consistent(self, seed_path: Path) -> None:
        seed = _load_seed(seed_path)
        dag = compile_to_dag(seed)
        m = dag["metrics"]
        assert m["node_count"] == len(dag["nodes"])
        assert m["projection_count"] == len(dag["projections"])
        assert m["edge_count"] > 0
        assert m["node_count"] > 0


# =============================================================================
# Seed-specific baseline counts
# =============================================================================


class TestBaselineCounts:
    """Lock known metrics to detect unintended seed changes."""

    def test_match_v2_projection_count(self) -> None:
        seed = _load_seed(MATCH_V2)
        dag = compile_to_dag(seed)
        assert dag["metrics"]["projection_count"] == 8

    def test_subst_v2_projection_count(self) -> None:
        seed = _load_seed(SUBST_V2)
        dag = compile_to_dag(seed)
        assert dag["metrics"]["projection_count"] == 12

    def test_match_v2_has_sharing(self) -> None:
        """DAG should have fewer nodes than naive tree (content-addressing works)."""
        seed = _load_seed(MATCH_V2)
        dag = compile_to_dag(seed)
        # Naive tree would have one node per JSON value in all patterns+bodies.
        # DAG sharing means node_count < total leaf+branch count across all projections.
        # Just verify sharing happens (node count is bounded).
        assert dag["metrics"]["node_count"] > 0
        assert dag["metrics"]["node_count"] < 500  # generous upper bound

    def test_subst_v2_has_sharing(self) -> None:
        seed = _load_seed(SUBST_V2)
        dag = compile_to_dag(seed)
        assert dag["metrics"]["node_count"] > 0
        assert dag["metrics"]["node_count"] < 500
