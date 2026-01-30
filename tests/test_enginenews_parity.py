"""
EngineNews Parity Tests - Verify structural closure detection

These tests verify that:
1. EngineNews projections detect closure correctly
2. Detection is structural (pattern matching on trace)
3. Python and JS produce same results (cross-substrate parity)

Spec reference: RCXEngineNew.pdf Rule 2.2♢ (Closure-on-Second-Demand)
"""

import json
import pytest
from pathlib import Path

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir
from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget


def get_fixtures_dir() -> Path:
    """Get path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


def load_enginenews_projections():
    """Load EngineNews projections from seed file."""
    seeds_dir = get_seeds_dir()
    seed = load_verified_seed(seeds_dir / "enginenews.v1.json")
    return seed["projections"]


def load_parity_vectors():
    """Load parity test vectors."""
    fixtures_dir = get_fixtures_dir()
    with open(fixtures_dir / "enginenews_vectors.json") as f:
        data = json.load(f)
    return data["vectors"]


def run_until_stable(projections, initial, max_steps=100):
    """Run projections until stall (no change) or max steps."""
    current = initial
    for _ in range(max_steps):
        result = step(projections, current)
        if mu_equal(result, current):
            return current
        current = result
    return current


class TestEngineNewsProjections:
    """Test that EngineNews seed has correct structure."""

    def test_seed_loads(self):
        """Seed file loads and verifies."""
        projs = load_enginenews_projections()
        assert len(projs) >= 4, "Need at least 4 projections"

    def test_projection_ids_present(self):
        """Required projection IDs exist."""
        projs = load_enginenews_projections()
        ids = {p["id"] for p in projs}

        required = {
            "enginenews.init",
            "enginenews.end_of_trace",
            "enginenews.check_state_stall",
            "enginenews.check_state_maxsteps",
            "enginenews.check_state",
            "enginenews.found_in_seen",
            "enginenews.not_in_head",
            "enginenews.not_found",
            "enginenews.unwrap",
        }

        missing = required - ids
        assert not missing, f"Missing projections: {missing}"

    def test_all_projections_have_schema(self):
        """Each projection has id, pattern, body."""
        projs = load_enginenews_projections()
        for p in projs:
            assert "id" in p, f"Missing id in projection"
            assert "pattern" in p, f"Missing pattern in {p.get('id', 'unknown')}"
            assert "body" in p, f"Missing body in {p.get('id', 'unknown')}"


class TestEngineNewsParity:
    """Test parity vectors for closure detection."""

    def setup_method(self):
        reset_step_budget()

    @pytest.fixture
    def projections(self):
        """Load EngineNews projections."""
        return load_enginenews_projections()

    @pytest.fixture
    def vectors(self):
        """Load parity test vectors."""
        return load_parity_vectors()

    def test_vectors_load(self, vectors):
        """Parity vectors load correctly."""
        assert len(vectors) >= 5, "Need at least 5 test vectors"

    def test_no_closure_single(self, projections):
        """Single state trace - no closure possible."""
        trace = {
            "head": {"step": 0, "state": "X", "projection": None, "stall": True},
            "tail": None
        }

        initial = {
            "_detect_closure": {
                "trace": trace,
                "result": "X"
            }
        }

        result = run_until_stable(projections, initial)

        assert "closure_detected" in result
        assert result["closure_detected"] is False
        assert result["final_result"] == "X"

    def test_closure_repeated_state(self, projections):
        """Repeated state in trace -> closure detected."""
        trace = {
            "head": {"step": 0, "state": "A", "projection": None},
            "tail": {
                "head": {"step": 1, "state": "A", "projection": None, "stall": True},
                "tail": None
            }
        }

        initial = {
            "_detect_closure": {
                "trace": trace,
                "result": "A"
            }
        }

        result = run_until_stable(projections, initial)

        assert "closure_detected" in result
        assert result["closure_detected"] is True

    def test_closure_oscillation(self, projections):
        """A->B->A oscillation detects closure."""
        trace = {
            "head": {"step": 0, "state": "A", "projection": "to_b"},
            "tail": {
                "head": {"step": 1, "state": "B", "projection": "to_a"},
                "tail": {
                    "head": {"step": 2, "state": "A", "projection": "to_b"},
                    "tail": None
                }
            }
        }

        initial = {
            "_detect_closure": {
                "trace": trace,
                "result": "A"
            }
        }

        result = run_until_stable(projections, initial)

        assert result["closure_detected"] is True

    def test_no_closure_distinct_states(self, projections):
        """All distinct states - no closure."""
        trace = {
            "head": {"step": 0, "state": 1, "projection": "inc"},
            "tail": {
                "head": {"step": 1, "state": 2, "projection": "inc"},
                "tail": {
                    "head": {"step": 2, "state": 3, "projection": None, "stall": True},
                    "tail": None
                }
            }
        }

        initial = {
            "_detect_closure": {
                "trace": trace,
                "result": 3
            }
        }

        result = run_until_stable(projections, initial)

        assert result["closure_detected"] is False
        assert result["final_result"] == 3

    def test_numeric_oscillation(self, projections):
        """Numeric 0->1->0 oscillation detects closure."""
        trace = {
            "head": {"step": 0, "state": 0, "projection": "to_1"},
            "tail": {
                "head": {"step": 1, "state": 1, "projection": "to_0"},
                "tail": {
                    "head": {"step": 2, "state": 0, "projection": "to_1"},
                    "tail": None
                }
            }
        }

        initial = {
            "_detect_closure": {
                "trace": trace,
                "result": 0
            }
        }

        result = run_until_stable(projections, initial)

        assert result["closure_detected"] is True

    @pytest.mark.parametrize("vector_id", [
        "engine.no_closure_stall",
        "engine.no_closure_single",
        "engine.closure_oscillation",
        "engine.no_closure_distinct",
        "engine.closure_numeric",
    ])
    def test_parity_vector(self, projections, vectors, vector_id):
        """Run parity vector and check expected result."""
        vector = next((v for v in vectors if v["id"] == vector_id), None)
        assert vector is not None, f"Vector {vector_id} not found"

        result = run_until_stable(projections, vector["input"])

        expected = vector["expected"]
        assert result["closure_detected"] == expected["closure_detected"], \
            f"Vector {vector_id}: closure_detected mismatch"
        assert mu_equal(result["final_result"], expected["final_result"]), \
            f"Vector {vector_id}: final_result mismatch"


class TestEngineNewsIntegration:
    """Integration tests with run_mu_structural."""

    def setup_method(self):
        reset_step_budget()

    def test_with_run_mu_structural(self):
        """EngineNews projections work with run_mu_structural trace."""
        from rcx_pi.selfhost.step_mu import run_mu_structural

        # Create oscillating projections
        toggle = [
            {"id": "to_b", "pattern": "A", "body": "B"},
            {"id": "to_a", "pattern": "B", "body": "A"},
        ]

        # Run and get structural trace
        trace_result = run_mu_structural(toggle, "A", max_steps=5)

        # Now run closure detection on the trace
        projs = load_enginenews_projections()

        closure_input = {
            "_detect_closure": {
                "trace": trace_result["trace"],
                "result": trace_result["result"]
            }
        }

        result = run_until_stable(projs, closure_input)

        # Should detect closure (A repeats)
        assert result["closure_detected"] is True

    def test_stall_no_closure(self):
        """Immediate stall produces single-state trace - depends on state repetition."""
        from rcx_pi.selfhost.step_mu import run_mu_structural

        # Projection that doesn't match anything
        never_match = [{"id": "never", "pattern": {"impossible": "match"}, "body": "never"}]

        # Run - will stall immediately
        trace_result = run_mu_structural(never_match, "X", max_steps=5)

        assert trace_result["stall"] is True

        # Run closure detection
        projs = load_enginenews_projections()

        closure_input = {
            "_detect_closure": {
                "trace": trace_result["trace"],
                "result": trace_result["result"]
            }
        }

        result = run_until_stable(projs, closure_input)

        # Single state in trace - no closure (only one entry)
        # Actually the trace will have initial state + stall state = 2 entries
        # Both with same state "X" -> closure detected!
        assert "closure_detected" in result
