"""
Structural Trace Fuzzer - Property-Based Tests for run_mu_structural()

CRITICAL: This fuzzer was identified as a gap by the 7-agent review.
The trace model MUST be robust for closure detection to be trustworthy.

Property-based tests for run_mu_structural() to ensure:
1. Always terminates within max_steps
2. Returns valid structure with required fields
3. Trace is proper Mu linked-list
4. Stall detection is consistent
5. Steps count matches trace length
6. Determinism: same input → same output
7. Oscillation states captured for EngineNews closure detection
"""

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from rcx_pi.selfhost.step_mu import run_mu_structural, list_to_linked
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget


# =============================================================================
# Strategies for generating test inputs
# =============================================================================

# Dict keys that don't start with underscore (kernel-reserved)
domain_safe_keys = st.text(max_size=10).filter(lambda k: not k.startswith("_") and len(k) > 0)

# Simple Mu values (max_depth=3 to prevent pathological nesting)
simple_mu = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=20),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(domain_safe_keys, children, max_size=3),
    ),
    max_leaves=10,
)


@st.composite
def projections_with_id(draw, max_depth=3):
    """Generate a valid projection with pattern, body, and id."""
    # Simple patterns
    pattern = draw(st.one_of(
        st.just({"var": "x"}),  # Catch-all
        st.integers(min_value=0, max_value=100),
        st.text(max_size=10),
        st.dictionaries(
            st.text(min_size=1, max_size=5),
            st.one_of(st.just({"var": "v"}), st.integers()),
            max_size=2
        ),
    ))

    # Simple bodies
    body = draw(st.one_of(
        st.just({"var": "x"}),
        st.just({"result": {"var": "x"}}),
        st.integers(),
        st.text(max_size=10),
    ))

    # Unique ID for trace tracking
    proj_id = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Ll", "Lu"))))

    return {"id": proj_id, "pattern": pattern, "body": body}


@st.composite
def projection_lists(draw, min_size=0, max_size=5):
    """Generate a list of projections with IDs."""
    return draw(st.lists(projections_with_id(), min_size=min_size, max_size=max_size))


# =============================================================================
# Structure Validity Tests
# =============================================================================

class TestStructureValidity:
    """Test that run_mu_structural returns valid structure."""

    def setup_method(self):
        reset_step_budget()

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_returns_required_fields(self, value, projs):
        """Result always has result, trace, stall, steps."""
        result = run_mu_structural(projs, value, max_steps=5)

        assert "result" in result, "Missing 'result' field"
        assert "trace" in result, "Missing 'trace' field"
        assert "stall" in result, "Missing 'stall' field"
        assert "steps" in result, "Missing 'steps' field"

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_stall_is_boolean(self, value, projs):
        """Stall field is always boolean."""
        result = run_mu_structural(projs, value, max_steps=5)
        assert isinstance(result["stall"], bool)

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_steps_is_positive_int(self, value, projs):
        """Steps field is always positive integer."""
        result = run_mu_structural(projs, value, max_steps=5)
        assert isinstance(result["steps"], int)
        assert result["steps"] >= 1


# =============================================================================
# Trace Format Tests
# =============================================================================

class TestTraceFormat:
    """Test that trace is valid Mu linked-list."""

    def setup_method(self):
        reset_step_budget()

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_trace_is_linked_list(self, value, projs):
        """Trace is Mu linked-list (head/tail structure)."""
        result = run_mu_structural(projs, value, max_steps=5)
        trace = result["trace"]

        # Walk the linked list to verify structure
        node = trace
        while node is not None:
            assert isinstance(node, dict), f"Node not dict: {type(node)}"
            assert "head" in node, f"Missing 'head' in node: {node}"
            assert "tail" in node, f"Missing 'tail' in node: {node}"
            node = node["tail"]

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_trace_entries_have_required_fields(self, value, projs):
        """Each trace entry has step, state, projection."""
        result = run_mu_structural(projs, value, max_steps=5)

        node = result["trace"]
        while node is not None:
            entry = node["head"]
            assert "step" in entry, f"Missing 'step' in entry: {entry}"
            assert "state" in entry, f"Missing 'state' in entry: {entry}"
            assert "projection" in entry, f"Missing 'projection' in entry: {entry}"
            node = node["tail"]

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_trace_length_matches_steps(self, value, projs):
        """Trace has steps + 1 entries (initial + each step)."""
        result = run_mu_structural(projs, value, max_steps=5)

        # Count linked list entries
        count = 0
        node = result["trace"]
        while node is not None:
            count += 1
            node = node["tail"]

        # Trace has initial state + one entry per step
        assert count == result["steps"] + 1, f"Expected {result['steps'] + 1} entries, got {count}"


# =============================================================================
# Termination Tests
# =============================================================================

class TestTermination:
    """Test that run_mu_structural always terminates."""

    def setup_method(self):
        reset_step_budget()

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_always_terminates(self, value, projs):
        """Always terminates within max_steps."""
        # This test passes if we reach this point without timeout
        result = run_mu_structural(projs, value, max_steps=5)

        # Steps never exceeds max_steps
        assert result["steps"] <= 5

    @given(value=simple_mu, max_steps=st.integers(min_value=1, max_value=10))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_respects_max_steps(self, value, max_steps):
        """Never exceeds max_steps."""
        # Oscillating projections to force max_steps
        toggle = [
            {"id": "to_1", "pattern": 0, "body": 1},
            {"id": "to_0", "pattern": 1, "body": 0},
        ]
        # Only test with 0 or 1 to trigger oscillation
        if value not in (0, 1):
            value = 0

        result = run_mu_structural(toggle, value, max_steps=max_steps)
        assert result["steps"] <= max_steps


# =============================================================================
# Stall Detection Tests
# =============================================================================

class TestStallDetection:
    """Test that stall detection is consistent."""

    def setup_method(self):
        reset_step_budget()

    @given(value=simple_mu)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_empty_projections_stall(self, value):
        """Empty projection list causes immediate stall."""
        result = run_mu_structural([], value, max_steps=5)

        assert result["stall"] is True
        assert result["steps"] == 1

    @given(value=simple_mu)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_no_match_stalls(self, value):
        """No matching projection causes stall."""
        never_match = [{"id": "never", "pattern": {"impossible": "match"}, "body": "never"}]

        result = run_mu_structural(never_match, value, max_steps=5)

        assert result["stall"] is True

    def test_identity_projection_stalls(self):
        """Projection that returns same value causes stall."""
        # Pattern catches all, body returns same
        identity = [{"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}}]

        result = run_mu_structural(identity, {"test": 42}, max_steps=5)

        # First step matches but returns same value → stall
        assert result["stall"] is True
        assert result["steps"] == 1

    @given(value=simple_mu, projs=projection_lists(min_size=1, max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_stall_result_equals_final_state(self, value, projs):
        """When stall=True, result equals the state that caused stall."""
        result = run_mu_structural(projs, value, max_steps=5)

        if result["stall"]:
            # Walk to last entry
            node = result["trace"]
            last_entry = None
            while node is not None:
                last_entry = node["head"]
                node = node["tail"]

            # Result should equal the stalled state
            assert mu_equal(result["result"], last_entry["state"])


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Test that same input produces same output."""

    def setup_method(self):
        reset_step_budget()

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_deterministic_result(self, value, projs):
        """Same input produces same result."""
        reset_step_budget()
        result1 = run_mu_structural(projs, value, max_steps=5)

        reset_step_budget()
        result2 = run_mu_structural(projs, value, max_steps=5)

        assert mu_equal(result1["result"], result2["result"])
        assert result1["stall"] == result2["stall"]
        assert result1["steps"] == result2["steps"]

    @given(value=simple_mu, projs=projection_lists(max_size=2))
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_deterministic_trace(self, value, projs):
        """Same input produces same trace."""
        reset_step_budget()
        result1 = run_mu_structural(projs, value, max_steps=5)

        reset_step_budget()
        result2 = run_mu_structural(projs, value, max_steps=5)

        # Compare trace linked lists
        node1 = result1["trace"]
        node2 = result2["trace"]
        while node1 is not None and node2 is not None:
            assert mu_equal(node1["head"]["state"], node2["head"]["state"])
            assert node1["head"]["projection"] == node2["head"]["projection"]
            node1 = node1["tail"]
            node2 = node2["tail"]

        assert node1 is None and node2 is None, "Trace lengths differ"


# =============================================================================
# Oscillation Detection Tests (EngineNews Rule 2.2)
# =============================================================================

class TestOscillationDetection:
    """Test that oscillating states are captured for closure detection."""

    def setup_method(self):
        reset_step_budget()

    def test_ab_oscillation_captured(self):
        """A→B→A oscillation captured in trace."""
        toggle = [
            {"id": "a_to_b", "pattern": "A", "body": "B"},
            {"id": "b_to_a", "pattern": "B", "body": "A"},
        ]

        result = run_mu_structural(toggle, "A", max_steps=10)

        # Collect states from trace
        states = []
        node = result["trace"]
        while node is not None:
            states.append(node["head"]["state"])
            node = node["tail"]

        # Should see A, B, A, B, ... pattern
        assert states[0] == "A"
        assert states[1] == "B"
        assert states[2] == "A"
        # Repeating pattern continues until max_steps
        assert len(states) > 5

    def test_numeric_oscillation_captured(self):
        """0→1→0 oscillation captured in trace."""
        toggle = [
            {"id": "inc", "pattern": 0, "body": 1},
            {"id": "dec", "pattern": 1, "body": 0},
        ]

        result = run_mu_structural(toggle, 0, max_steps=10)

        # Should not stall (always transforming)
        assert result["stall"] is False
        assert result["steps"] == 10

        # Collect all states
        states = []
        node = result["trace"]
        while node is not None:
            states.append(node["head"]["state"])
            node = node["tail"]

        # Pattern: 0, 1, 0, 1, ...
        for i, state in enumerate(states[:-1]):  # Skip last (may be partial)
            assert state == i % 2

    @given(initial=st.sampled_from(["A", "B", 0, 1]))
    @settings(max_examples=20, deadline=None)
    def test_oscillation_projections_recorded(self, initial):
        """Projection IDs are recorded during oscillation."""
        toggle = [
            {"id": "step_a", "pattern": "A", "body": "B"},
            {"id": "step_b", "pattern": "B", "body": "A"},
            {"id": "step_0", "pattern": 0, "body": 1},
            {"id": "step_1", "pattern": 1, "body": 0},
        ]

        result = run_mu_structural(toggle, initial, max_steps=10)

        # Collect projections from trace
        projections = []
        node = result["trace"]
        while node is not None:
            projections.append(node["head"]["projection"])
            node = node["tail"]

        # At least one projection should be non-null (matched)
        non_null = [p for p in projections if p is not None]
        assert len(non_null) > 0, "No projections matched"


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        reset_step_budget()

    def test_none_input(self):
        """None input handled correctly."""
        result = run_mu_structural([], None, max_steps=10)
        assert result["result"] is None
        assert result["stall"] is True

    def test_empty_dict_input(self):
        """Empty dict input handled correctly."""
        result = run_mu_structural([], {}, max_steps=10)
        assert result["stall"] is True

    def test_empty_list_input(self):
        """Empty list input handled correctly."""
        result = run_mu_structural([], [], max_steps=10)
        assert result["stall"] is True

    def test_max_steps_one(self):
        """max_steps=1 terminates after one step."""
        toggle = [
            {"id": "to_1", "pattern": 0, "body": 1},
            {"id": "to_0", "pattern": 1, "body": 0},
        ]

        result = run_mu_structural(toggle, 0, max_steps=1)
        assert result["steps"] == 1

    def test_single_transformation(self):
        """Single successful transformation then stall."""
        once = [{"id": "double", "pattern": 0, "body": 1}]

        result = run_mu_structural(once, 0, max_steps=10)

        # First step: 0 → 1
        # Second step: 1 doesn't match, stall
        assert result["result"] == 1
        assert result["stall"] is True
        assert result["steps"] == 2

    @given(value=simple_mu)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_immediate_stall_preserves_input(self, value):
        """Immediate stall preserves original input."""
        result = run_mu_structural([], value, max_steps=5)

        assert mu_equal(result["result"], value)
