"""
Invariant tests for fix.v1.json (GAP-04-FIX Rule 0.6).

Tests the 5 invariants declared in fix.v1.json meta.invariants:
  I1: Minimality — add exactly one structural element (edge or vertex)
  I2: Structural purity — all projections are pure Mu, no host escapes
  I3: Idempotence safety — double-apply returns fix_applied=false or same output
  I4: Stall-breaking — fixed_state hash differs from stall_hash when fix_applied=true
  I5: No semantic drift — fixed_state is valid engine input
"""

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow]

from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.mu_type import is_mu, mu_hash
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from rcx_pi.selfhost.step_mu import (
    KERNEL_RESERVED_FIELDS,
    run_algorithm_meta_circular,
)
from tests.repo_root import REPO_ROOT

ROOT = REPO_ROOT
ZERO = {"_num": None}
ONE = {"_num": {"xH": None}}
TWO = {"_num": {"xO": {"xH": None}}}
THREE = {"_num": {"xI": {"xH": None}}}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fix_projections():
    seed = load_verified_seed(get_seed_path("fix.v1.json"))
    return seed["projections"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_fix(fix_projections, stalled_state, *, stall_hash=None, tau_step=ONE):
    """Run fix seed to completion (loop until stall)."""
    if stall_hash is None:
        stall_hash = mu_hash(stalled_state)

    fix_input = {
        "apply_fix": {
            "stalled_state": stalled_state,
            "stall_hash": stall_hash,
            "tau_step": tau_step,
            "engine_iteration": ZERO,
        }
    }

    reset_step_budget()
    current = fix_input
    for _ in range(10):
        result = run_algorithm_meta_circular(fix_projections, current)
        if mu_hash(result) == mu_hash(current):
            break
        current = result
    return current


def _check_no_reserved_fields(value):
    """Recursively verify no kernel-reserved fields in a Mu value."""
    if isinstance(value, dict):
        for k in value:
            assert k not in KERNEL_RESERVED_FIELDS, (
                f"Reserved field '{k}' found in fixed_state"
            )
            _check_no_reserved_fields(value[k])
    elif isinstance(value, list):
        for item in value:
            _check_no_reserved_fields(item)


# ---------------------------------------------------------------------------
# Test inputs
# ---------------------------------------------------------------------------

GRAPH_WITH_EDGES = {
    "graph": {
        "vertices": [ONE, TWO],
        "edges": [{"src": ONE, "dst": TWO}],
    }
}
GRAPH_WITHOUT_EDGES = {"graph": {"vertices": [ONE, TWO, THREE]}}
NON_GRAPH = {"value": ONE, "status": "stalled"}


# ===========================================================================
# I1: Minimality
# ===========================================================================


class TestI1Minimality:
    """I1: Add exactly one structural element (edge or vertex)."""

    def test_edge_add_adds_exactly_one_edge(self, fix_projections):
        """edge_add prepends one edge to the edges list."""
        result = run_fix(fix_projections, GRAPH_WITH_EDGES)
        assert result["fix_applied"] is True
        assert result["fix_type"] == "edge_add"

        original_edges = GRAPH_WITH_EDGES["graph"]["edges"]
        fixed_edges = result["fixed_state"]["graph"]["edges"]
        assert len(fixed_edges) == len(original_edges) + 1, (
            f"Expected exactly one edge added: {len(original_edges)} -> {len(fixed_edges)}"
        )

    def test_edge_add_preserves_original_edges(self, fix_projections):
        """Original edges preserved in fixed output."""
        result = run_fix(fix_projections, GRAPH_WITH_EDGES)
        fixed_edges = result["fixed_state"]["graph"]["edges"]
        original_edge = GRAPH_WITH_EDGES["graph"]["edges"][0]
        assert original_edge in fixed_edges, (
            f"Original edge {original_edge} not found in {fixed_edges}"
        )

    def test_edge_add_preserves_vertices(self, fix_projections):
        """edge_add does not modify vertices."""
        result = run_fix(fix_projections, GRAPH_WITH_EDGES)
        assert result["fixed_state"]["graph"]["vertices"] == GRAPH_WITH_EDGES["graph"]["vertices"]

    def test_vertex_add_adds_exactly_one_vertex(self, fix_projections):
        """vertex_add prepends one vertex to graph.vertices."""
        result = run_fix(fix_projections, GRAPH_WITHOUT_EDGES)
        assert result["fix_applied"] is True
        assert result["fix_type"] == "vertex_add"

        original_verts = GRAPH_WITHOUT_EDGES["graph"]["vertices"]
        fixed_state = result["fixed_state"]
        # Shape-preserving: vertex added INSIDE graph.vertices
        assert "graph" in fixed_state
        assert "vertices" in fixed_state["graph"], (
            f"fixed_state.graph must have 'vertices' key, got: {list(fixed_state['graph'].keys())}"
        )
        fixed_verts = fixed_state["graph"]["vertices"]
        assert len(fixed_verts) == len(original_verts) + 1, (
            f"Expected exactly one vertex added: {len(original_verts)} -> {len(fixed_verts)}"
        )

    def test_vertex_add_preserves_original_vertices(self, fix_projections):
        """Original vertices preserved in fixed output."""
        result = run_fix(fix_projections, GRAPH_WITHOUT_EDGES)
        fixed_verts = result["fixed_state"]["graph"]["vertices"]
        for v in GRAPH_WITHOUT_EDGES["graph"]["vertices"]:
            assert v in fixed_verts, (
                f"Original vertex {v} not found in {fixed_verts}"
            )

    def test_pass_through_no_change(self, fix_projections):
        """pass_through returns state unchanged."""
        result = run_fix(fix_projections, NON_GRAPH)
        assert result["fix_applied"] is False
        assert result["fixed_state"] == NON_GRAPH


# ===========================================================================
# I2: Structural purity
# ===========================================================================


class TestI2StructuralPurity:
    """I2: All projections are pure Mu, no host escapes."""

    def test_seed_passes_seed_police(self):
        """fix.v1.json passes seed_police structural checks."""
        result = subprocess.run(
            ["bash", "tools/checks/linters/seed_police.sh"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"Seed police failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "fix.v1.json" in result.stdout

    def test_seed_passes_integrity_check(self):
        """fix.v1.json passes checksum + projection ID verification."""
        seed_path = get_seed_path("fix.v1.json")
        seed = load_verified_seed(seed_path, verify=True)
        assert seed is not None
        assert len(seed["projections"]) >= 4


# ===========================================================================
# I3: Idempotence safety
# ===========================================================================


class TestI3IdempotenceSafety:
    """I3: Double-apply returns fix_applied=false or same output."""

    def test_edge_add_double_apply(self, fix_projections):
        """Applying fix to an already-fixed graph-with-edges is idempotent."""
        first = run_fix(fix_projections, GRAPH_WITH_EDGES)
        assert first["fix_applied"] is True

        second = run_fix(fix_projections, first["fixed_state"])
        assert second["fix_applied"] is False or second["fixed_state"] == first["fixed_state"], (
            f"I3 violated: double-apply should return fix_applied=false or same output.\n"
            f"First:  fix_applied={first['fix_applied']}, fix_type={first['fix_type']}\n"
            f"Second: fix_applied={second['fix_applied']}, fix_type={second['fix_type']}"
        )

    def test_vertex_add_double_apply(self, fix_projections):
        """Applying fix to an already-fixed graph-without-edges is idempotent."""
        first = run_fix(fix_projections, GRAPH_WITHOUT_EDGES)
        assert first["fix_applied"] is True

        second = run_fix(fix_projections, first["fixed_state"])
        assert second["fix_applied"] is False or second["fixed_state"] == first["fixed_state"], (
            f"I3 violated: double-apply should return fix_applied=false or same output.\n"
            f"First:  fix_applied={first['fix_applied']}, fix_type={first['fix_type']}\n"
            f"Second: fix_applied={second['fix_applied']}, fix_type={second['fix_type']}"
        )

    def test_pass_through_double_apply(self, fix_projections):
        """Double-apply on non-graph is trivially idempotent."""
        first = run_fix(fix_projections, NON_GRAPH)
        assert first["fix_applied"] is False

        second = run_fix(fix_projections, first["fixed_state"])
        assert second["fix_applied"] is False
        assert second["fixed_state"] == first["fixed_state"]


# ===========================================================================
# I4: Stall-breaking
# ===========================================================================


class TestI4StallBreaking:
    """I4: When fix_applied=true, fixed_state hash differs from stall_hash."""

    def test_edge_add_breaks_stall(self, fix_projections):
        """Fixed graph-with-edges has different hash than original."""
        stall_hash = mu_hash(GRAPH_WITH_EDGES)
        result = run_fix(fix_projections, GRAPH_WITH_EDGES, stall_hash=stall_hash)
        assert result["fix_applied"] is True

        fixed_hash = mu_hash(result["fixed_state"])
        assert fixed_hash != stall_hash, (
            f"I4 violated: fixed_state hash should differ from stall_hash.\n"
            f"stall_hash: {stall_hash}\nfixed_hash: {fixed_hash}"
        )

    def test_vertex_add_breaks_stall(self, fix_projections):
        """Fixed graph-without-edges has different hash than original."""
        stall_hash = mu_hash(GRAPH_WITHOUT_EDGES)
        result = run_fix(fix_projections, GRAPH_WITHOUT_EDGES, stall_hash=stall_hash)
        assert result["fix_applied"] is True

        fixed_hash = mu_hash(result["fixed_state"])
        assert fixed_hash != stall_hash, (
            f"I4 violated: fixed_state hash should differ from stall_hash.\n"
            f"stall_hash: {stall_hash}\nfixed_hash: {fixed_hash}"
        )

    def test_pass_through_no_break(self, fix_projections):
        """pass_through does not claim to break stall."""
        result = run_fix(fix_projections, NON_GRAPH)
        assert result["fix_applied"] is False


# ===========================================================================
# I5: No semantic drift
# ===========================================================================


class TestI5NoSemanticDrift:
    """I5: fixed_state is valid engine input."""

    def test_edge_add_output_is_mu_valid(self, fix_projections):
        result = run_fix(fix_projections, GRAPH_WITH_EDGES)
        assert is_mu(result["fixed_state"]), "fixed_state must be valid Mu"

    def test_vertex_add_output_is_mu_valid(self, fix_projections):
        result = run_fix(fix_projections, GRAPH_WITHOUT_EDGES)
        assert is_mu(result["fixed_state"]), "fixed_state must be valid Mu"

    def test_edge_add_no_reserved_fields(self, fix_projections):
        result = run_fix(fix_projections, GRAPH_WITH_EDGES)
        _check_no_reserved_fields(result["fixed_state"])

    def test_vertex_add_no_reserved_fields(self, fix_projections):
        result = run_fix(fix_projections, GRAPH_WITHOUT_EDGES)
        _check_no_reserved_fields(result["fixed_state"])

    def test_pass_through_identity(self, fix_projections):
        """pass_through fixed_state is identical to input."""
        result = run_fix(fix_projections, NON_GRAPH)
        assert result["fixed_state"] == NON_GRAPH
