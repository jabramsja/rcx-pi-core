"""
L4 Gate: evidence_walker.v1.json structural walker verification.

Proves the L4_STRUCTURAL semantic shift: trace walking for ontology
evidence collection is now structural (no host iteration loop).

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_evidence_walker_gate.py -v
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import (
    run_mu,  # SPEED_OK: boundary wrapper tested via run_mu
)
from rcx_pi.selfhost.seed_integrity import (
    load_verified_seed,
    get_seed_path,
    EXPECTED_PROJECTION_IDS,
)


# ---------------------------------------------------------------------------
# Gate Tests
# ---------------------------------------------------------------------------

class TestEvidenceWalkerSeedGate:
    """Gate: evidence_walker.v1.json loaded and verified in Python."""

    def test_seed_loads_with_4_projections(self):
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        assert len(seed["projections"]) == 4

    def test_projection_ids_registered(self):
        assert "evidence_walker.v1.json" in EXPECTED_PROJECTION_IDS
        assert len(EXPECTED_PROJECTION_IDS["evidence_walker.v1.json"]) == 4


@pytest.mark.slow
class TestEvidenceWalkerWiringGate:
    """Gate: evidence walker produces correct output for trace inputs."""

    def test_null_trace_produces_done(self):
        """Null trace → evidence_done with null collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        wrapped = {"evidence_walk": {"trace": None}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert isinstance(result, dict)
        assert "evidence_done" in result
        assert result["evidence_done"]["collected"] is None

    def test_trace_with_projection_collects_entry(self):
        """Trace entry with projection → raw entry collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {"head": {"state": "a", "step": 0, "projection": "test.id"}, "tail": None}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        # Mu runtime normalizes single-element {head,tail:null} to Python list
        if isinstance(collected, list):
            assert len(collected) == 1
            assert collected[0]["projection"] == "test.id"
        else:
            assert collected["head"]["projection"] == "test.id"

    def test_trace_without_projection_collects_entry(self):
        """Trace entry without projection → raw entry still collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {"head": {"state": "a", "step": 0}, "tail": None}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        if isinstance(collected, list):
            assert len(collected) == 1
            assert "projection" not in collected[0]
        else:
            assert "projection" not in collected["head"]

    def test_multi_entry_trace(self):
        """Multi-entry trace → all entries collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {
            "head": {"state": "a", "step": 0, "projection": "p1"},
            "tail": {
                "head": {"state": "b", "step": 1},
                "tail": {
                    "head": {"state": "c", "step": 2, "projection": "p2"},
                    "tail": None,
                },
            },
        }
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=30)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        # Count entries
        count = 0
        node = collected
        if isinstance(node, list):
            count = len(node)
        else:
            while isinstance(node, dict) and "head" in node:
                count += 1
                node = node.get("tail")
        assert count == 3
