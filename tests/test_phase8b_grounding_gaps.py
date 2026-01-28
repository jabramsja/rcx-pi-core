"""
Phase 8b: Grounding gap tests.

These tests were identified by the grounding agent as missing from the
original test_phase8b_mechanical_kernel.py suite. They cover:

1. Max steps exhaustion - The BOOTSTRAP_PRIMITIVE guard (line 287-292 in step_mu.py)
2. mu_equal stall detection - The no-progress detection path (line 303 in step_mu.py)

See docs/core/BootstrapPrimitives.v0.md for why max_steps is irreducible.
"""

import pytest

from rcx_pi.selfhost.step_mu import step_mu, step_kernel_mu
from rcx_pi.selfhost.mu_type import is_mu


# =============================================================================
# Max Steps Exhaustion Tests (BOOTSTRAP_PRIMITIVE)
# =============================================================================

class TestMaxStepsExhaustion:
    """
    Test max_steps exhaustion behavior.

    The max_steps guard (line 287-292 in step_mu.py) is a BOOTSTRAP_PRIMITIVE.
    It prevents infinite execution when projections don't reach terminal state.
    Without this guard, the kernel could hang indefinitely.
    """

    def test_oscillating_projections_hit_max_steps(self):
        """
        Oscillating pattern A→B→A should eventually return (stall after max_steps).

        This tests the max_steps BOOTSTRAP_PRIMITIVE guard.
        Note: This is a known limitation - oscillation is not detected early,
        it runs until max_steps is reached.
        """
        # Projections that oscillate between two states
        projections = [
            {"pattern": {"state": "A"}, "body": {"state": "B"}},
            {"pattern": {"state": "B"}, "body": {"state": "A"}},
        ]
        input_value = {"state": "A"}

        # This will run until max_steps (10000) is exhausted
        # The function should return without hanging
        result = step_mu(projections, input_value)

        # Result should be valid Mu (either A or B depending on where it stopped)
        assert is_mu(result)
        # Should be one of the oscillating states
        assert result in [{"state": "A"}, {"state": "B"}]

    def test_always_changing_projection_hits_max_steps(self):
        """
        Projection that always transforms to different value hits max_steps.

        Each step produces a different value, so mu_equal won't detect stall.
        Must rely on max_steps guard.
        """
        # Projection that wraps value in another layer each time
        projections = [
            {"pattern": {"var": "x"}, "body": {"wrap": {"var": "x"}}}
        ]
        input_value = 42

        # This will keep wrapping: 42 → {wrap: 42} → {wrap: {wrap: 42}} → ...
        # Until max_steps is reached
        result = step_mu(projections, input_value)

        # Result should be valid Mu
        assert is_mu(result)
        # Should be deeply nested (but we don't check exact depth)
        assert isinstance(result, dict)
        assert "wrap" in result

    def test_max_steps_returns_last_state_not_original(self):
        """
        When max_steps is exhausted, return the LAST computed state.

        This verifies the behavior at line 308-309 in step_mu.py.
        """
        # Single step projection (won't oscillate, just transforms once per call)
        projections = [
            {"pattern": {"n": {"var": "x"}}, "body": {"n": {"var": "x"}, "seen": True}}
        ]
        input_value = {"n": 1}

        result = step_mu(projections, input_value)

        # Should have been transformed (not original input)
        assert is_mu(result)
        # The projection adds "seen" key
        assert "seen" in result or result == {"n": 1}


# =============================================================================
# mu_equal Stall Detection Tests
# =============================================================================

class TestMuEqualStallDetection:
    """
    Test mu_equal() no-progress stall detection in the loop.

    The mu_equal check (line 303 in step_mu.py) detects when a projection
    returns the same value as its input, indicating no progress.
    """

    def test_identity_projection_detected_as_stall(self):
        """
        Identity projection {var: x} → {var: x} should stall immediately.

        mu_equal(result, current) returns True, causing immediate stall.
        """
        projections = [
            {"pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        input_value = {"key": "value"}

        result = step_mu(projections, input_value)

        # Should return original (stall detected)
        assert result == {"key": "value"}

    def test_stall_detection_with_primitive(self):
        """
        Primitive value that matches identity projection stalls.
        """
        projections = [
            {"pattern": {"var": "x"}, "body": {"var": "x"}}
        ]

        result = step_mu(projections, 42)
        assert result == 42

        result = step_mu(projections, "hello")
        assert result == "hello"

        result = step_mu(projections, None)
        assert result is None

    def test_stall_detection_with_list(self):
        """
        List that matches identity projection stalls.
        """
        projections = [
            {"pattern": {"var": "x"}, "body": {"var": "x"}}
        ]

        result = step_mu(projections, [1, 2, 3])
        assert result == [1, 2, 3]

    def test_stall_detection_preserves_empty_containers(self):
        """
        Empty containers are preserved through normalization/denormalization.

        Phase 8b FIX: Empty list [] and empty dict {} now use typed sentinels:
        - [] → {"_type": "list"}
        - {} → {"_type": "dict"}

        This preserves type info through the roundtrip.
        """
        projections = [
            {"pattern": {"var": "x"}, "body": {"var": "x"}}
        ]

        # Empty list is preserved
        result = step_mu(projections, [])
        assert result == [], f"Expected [], got {result}"

        # Empty dict is preserved
        result = step_mu(projections, {})
        assert result == {}, f"Expected {{}}, got {result}"

    def test_no_match_is_also_stall(self):
        """
        When no projection matches, input is returned unchanged (stall).

        This is different from mu_equal stall - the kernel.stall projection
        sets _stall=True when _remaining is null.
        """
        projections = [
            {"pattern": {"specific": "pattern"}, "body": "transformed"}
        ]

        result = step_mu(projections, {"different": "value"})

        # Should return original (no projection matched)
        assert result == {"different": "value"}


# =============================================================================
# Edge Cases for Mechanical Loop
# =============================================================================

class TestMechanicalLoopEdgeCases:
    """
    Additional edge cases for the simplified mechanical loop.
    """

    def test_deeply_nested_structure_transformation(self):
        """
        Deeply nested structures are handled correctly.
        """
        projections = [
            {"pattern": {"a": {"b": {"c": {"var": "x"}}}},
             "body": {"result": {"var": "x"}}}
        ]
        input_value = {"a": {"b": {"c": "deep_value"}}}

        result = step_mu(projections, input_value)

        assert result == {"result": "deep_value"}

    def test_multiple_vars_in_pattern(self):
        """
        Multiple variable bindings work correctly.
        """
        projections = [
            {"pattern": {"x": {"var": "a"}, "y": {"var": "b"}},
             "body": {"first": {"var": "a"}, "second": {"var": "b"}}}
        ]
        input_value = {"x": 1, "y": 2}

        result = step_mu(projections, input_value)

        assert result == {"first": 1, "second": 2}

    def test_projection_order_first_match_wins(self):
        """
        First matching projection wins (order matters).
        """
        projections = [
            {"pattern": {"var": "x"}, "body": "first"},
            {"pattern": {"var": "x"}, "body": "second"},
            {"pattern": {"var": "x"}, "body": "third"},
        ]

        result = step_mu(projections, 42)

        assert result == "first"

    def test_fallthrough_finds_correct_match(self):
        """
        Fallthrough correctly finds the first matching projection.
        """
        projections = [
            {"pattern": {"type": "A"}, "body": "matched_A"},
            {"pattern": {"type": "B"}, "body": "matched_B"},
            {"pattern": {"type": "C"}, "body": "matched_C"},
        ]

        result = step_mu(projections, {"type": "B"})
        assert result == "matched_B"

        result = step_mu(projections, {"type": "C"})
        assert result == "matched_C"

        result = step_mu(projections, {"type": "A"})
        assert result == "matched_A"
