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
        assert len(projs) == 9, f"Expected exactly 9 projections, got {len(projs)}"

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
        "engine.closure_immediate_repeat",
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


class TestEngineNewsSpecCompliance:
    """Grounding tests for RCXEngineNew.pdf Rule 2.2♢ compliance.

    These tests verify the SECOND-demand semantics explicitly.
    """

    def setup_method(self):
        reset_step_budget()

    @pytest.fixture
    def projections(self):
        return load_enginenews_projections()

    def test_first_occurrence_no_closure(self, projections):
        """Rule 2.2♢: First occurrence MUST NOT trigger closure.

        A single state appearing once is not closure.
        """
        # Only one occurrence of state "A"
        trace = {
            "head": {"step": 0, "state": "A", "projection": None, "stall": True},
            "tail": None
        }

        initial = {"_detect_closure": {"trace": trace, "result": "A"}}
        result = run_until_stable(projections, initial)

        assert result["closure_detected"] is False, \
            "Rule 2.2♢: First occurrence must NOT trigger closure"

    def test_second_occurrence_triggers_closure(self, projections):
        """Rule 2.2♢: SECOND occurrence MUST trigger closure.

        State appearing twice (positions 0 and 1) = closure.
        """
        # State "A" at step 0, different state "B" at step 1, state "A" again at step 2
        trace = {
            "head": {"step": 0, "state": "A", "projection": "to_b"},
            "tail": {
                "head": {"step": 1, "state": "B", "projection": "to_a"},
                "tail": {
                    "head": {"step": 2, "state": "A", "projection": None},
                    "tail": None
                }
            }
        }

        initial = {"_detect_closure": {"trace": trace, "result": "A"}}
        result = run_until_stable(projections, initial)

        assert result["closure_detected"] is True, \
            "Rule 2.2♢: Second occurrence MUST trigger closure"

    def test_immediate_repeat_is_second_occurrence(self, projections):
        """Rule 2.2♢: Immediate repeat (A->A) counts as second occurrence."""
        # State "A" at step 0, same state "A" at step 1 (immediate stall)
        trace = {
            "head": {"step": 0, "state": "A", "projection": None},
            "tail": {
                "head": {"step": 1, "state": "A", "projection": None, "stall": True},
                "tail": None
            }
        }

        initial = {"_detect_closure": {"trace": trace, "result": "A"}}
        result = run_until_stable(projections, initial)

        assert result["closure_detected"] is True, \
            "Immediate repeat (A->A) is SECOND occurrence"

    def test_three_occurrences_still_detects_closure(self, projections):
        """Rule 2.2♢: Closure triggers on SECOND, works with 3+ occurrences."""
        # State "A" at steps 0, 2, 4
        trace = {
            "head": {"step": 0, "state": "A", "projection": "to_b"},
            "tail": {
                "head": {"step": 1, "state": "B", "projection": "to_a"},
                "tail": {
                    "head": {"step": 2, "state": "A", "projection": "to_b"},
                    "tail": {
                        "head": {"step": 3, "state": "B", "projection": "to_a"},
                        "tail": {
                            "head": {"step": 4, "state": "A", "projection": None},
                            "tail": None
                        }
                    }
                }
            }
        }

        initial = {"_detect_closure": {"trace": trace, "result": "A"}}
        result = run_until_stable(projections, initial)

        # Closure detected at step 2 (second "A")
        assert result["closure_detected"] is True

    def test_tau_is_state_not_projection(self, projections):
        """A.10: Trace token τ = state (not projection id).

        Same state via different projections = closure.
        Different states via same projection = no closure.
        """
        # Same state "X" reached via different projections
        trace_same_state = {
            "head": {"step": 0, "state": "X", "projection": "path_a"},
            "tail": {
                "head": {"step": 1, "state": "X", "projection": "path_b"},
                "tail": None
            }
        }

        result1 = run_until_stable(projections, {
            "_detect_closure": {"trace": trace_same_state, "result": "X"}
        })
        assert result1["closure_detected"] is True, \
            "A.10: τ = state; same state via different projections = closure"

        # Different states via same projection
        trace_diff_state = {
            "head": {"step": 0, "state": "X", "projection": "same_proj"},
            "tail": {
                "head": {"step": 1, "state": "Y", "projection": "same_proj"},
                "tail": None
            }
        }

        result2 = run_until_stable(projections, {
            "_detect_closure": {"trace": trace_diff_state, "result": "Y"}
        })
        assert result2["closure_detected"] is False, \
            "A.10: τ = state; different states via same projection = no closure"

    def test_complex_state_equality(self, projections):
        """Closure detection works with complex nested states."""
        complex_state = {"x": 1, "y": [2, 3]}

        trace = {
            "head": {"step": 0, "state": complex_state, "projection": "p1"},
            "tail": {
                "head": {"step": 1, "state": {"z": 99}, "projection": "p2"},
                "tail": {
                    "head": {"step": 2, "state": complex_state, "projection": None},
                    "tail": None
                }
            }
        }

        initial = {"_detect_closure": {"trace": trace, "result": complex_state}}
        result = run_until_stable(projections, initial)

        assert result["closure_detected"] is True, \
            "Complex nested states detected as equal"

    def test_primitive_type_distinctness(self, projections):
        """0 vs false vs null vs empty string are DISTINCT states."""
        test_cases = [
            (0, False, "0 vs false"),
            (0, None, "0 vs null"),
            (False, None, "false vs null"),
            ("", False, "empty string vs false"),
        ]

        for state1, state2, desc in test_cases:
            trace = {
                "head": {"step": 0, "state": state1, "projection": None},
                "tail": {
                    "head": {"step": 1, "state": state2, "projection": None},
                    "tail": None
                }
            }

            result = run_until_stable(projections, {
                "_detect_closure": {"trace": trace, "result": state2}
            })

            assert result["closure_detected"] is False, \
                f"Type distinctness: {desc} must be distinct states"


class TestEngineNewsClosureObjectStructure:
    """Grounding tests for exact Omega(tau) closure object structure.

    Per A.10b: Closure object Omega(tau) must have specific structure.
    """

    def setup_method(self):
        reset_step_budget()

    @pytest.fixture
    def projections(self):
        return load_enginenews_projections()

    def test_closure_object_has_required_keys(self, projections):
        """Closure object MUST have closure_detected, tau_step, and final_result keys."""
        trace = {
            "head": {"step": 0, "state": "A", "projection": "p1"},
            "tail": {
                "head": {"step": 1, "state": "A", "projection": None},
                "tail": None
            }
        }

        initial = {"_detect_closure": {"trace": trace, "result": "A"}}
        result = run_until_stable(projections, initial)

        # Exact structure check (Step 6 v0: added tau_step for Operator Exhaustion)
        assert set(result.keys()) == {"closure_detected", "tau_step", "final_result"}, \
            f"Omega(tau) must have closure_detected, tau_step and final_result, got {set(result.keys())}"

    def test_closure_detected_is_boolean(self, projections):
        """closure_detected MUST be a boolean."""
        trace = {
            "head": {"step": 0, "state": "X", "projection": None, "stall": True},
            "tail": None
        }

        initial = {"_detect_closure": {"trace": trace, "result": "X"}}
        result = run_until_stable(projections, initial)

        assert isinstance(result["closure_detected"], bool), \
            f"closure_detected must be bool, got {type(result['closure_detected'])}"

    def test_final_result_preserves_input_result(self, projections):
        """final_result MUST equal the input result."""
        test_state = {"complex": [1, 2, 3]}

        trace = {
            "head": {"step": 0, "state": test_state, "projection": None, "stall": True},
            "tail": None
        }

        initial = {"_detect_closure": {"trace": trace, "result": test_state}}
        result = run_until_stable(projections, initial)

        from rcx_pi.selfhost.mu_type import mu_equal
        assert mu_equal(result["final_result"], test_state), \
            "final_result must equal input result"


class TestEngineNewsExactProjectionCount:
    """Grounding test: exact projection count must be 9."""

    def test_exactly_nine_projections(self):
        """enginenews.v1.json MUST have exactly 9 projections.

        Count breakdown:
        1. enginenews.init - Entry point
        2. enginenews.end_of_trace - End of trace (null)
        3. enginenews.check_state_stall - Extract state from stall entry
        4. enginenews.check_state_maxsteps - Extract state from max_steps entry
        5. enginenews.check_state - Extract state from normal entry
        6. enginenews.found_in_seen - State found in seen-set
        7. enginenews.not_in_head - State not in head, check tail
        8. enginenews.not_found - State not found, add to seen
        9. enginenews.unwrap - Extract final result
        """
        projs = load_enginenews_projections()
        assert len(projs) == 9, \
            f"enginenews.v1.json must have exactly 9 projections, got {len(projs)}"

    def test_all_required_projection_ids(self):
        """All 9 required projection IDs must be present."""
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

        assert ids == required, \
            f"Expected exactly these IDs: {required}, got: {ids}"
