"""
Phase 8b: Tests for mechanical kernel helpers.

These tests verify that:
1. is_kernel_terminal() detects the structural marker correctly
2. extract_kernel_result() unpacks results without semantic decisions
3. The simplified step_kernel_mu loop still works correctly

See docs/core/BootstrapPrimitives.v0.md for the honest boundary design.
"""

import pytest

from rcx_pi.selfhost.step_mu import (
    is_kernel_terminal,
    extract_kernel_result,
    step_kernel_mu,
    step_mu,
)
from rcx_pi.selfhost.mu_type import mu_equal


# =============================================================================
# is_kernel_terminal() Tests
# =============================================================================

class TestIsKernelTerminal:
    """Test is_kernel_terminal() helper - simple structural marker detection."""

    def test_done_state_is_terminal(self):
        """Standard done state with success."""
        state = {"_mode": "done", "_result": 42, "_stall": False}
        assert is_kernel_terminal(state) is True

    def test_stall_state_is_terminal(self):
        """Done state with stall flag."""
        state = {"_mode": "done", "_result": {"x": 1}, "_stall": True}
        assert is_kernel_terminal(state) is True

    def test_kernel_state_not_terminal(self):
        """Kernel internal state (in-progress)."""
        state = {"_mode": "kernel", "_phase": "try", "_input": 42, "_remaining": None}
        assert is_kernel_terminal(state) is False

    def test_match_state_not_terminal(self):
        """Match internal state."""
        state = {"mode": "match", "pattern_focus": 1, "value_focus": 2}
        assert is_kernel_terminal(state) is False

    def test_subst_state_not_terminal(self):
        """Subst internal state."""
        state = {"mode": "subst", "template_focus": {"var": "x"}, "bindings": {}}
        assert is_kernel_terminal(state) is False

    def test_primitive_not_terminal(self):
        """Primitive values are not terminal states."""
        assert is_kernel_terminal(42) is False
        assert is_kernel_terminal("hello") is False
        assert is_kernel_terminal(None) is False
        assert is_kernel_terminal(True) is False
        assert is_kernel_terminal(3.14) is False

    def test_list_not_terminal(self):
        """Lists are not terminal states."""
        assert is_kernel_terminal([1, 2, 3]) is False
        assert is_kernel_terminal([]) is False

    def test_incomplete_done_missing_result(self):
        """Done state missing _result is not terminal."""
        assert is_kernel_terminal({"_mode": "done", "_stall": False}) is False

    def test_incomplete_done_missing_stall(self):
        """Done state missing _stall is not terminal."""
        assert is_kernel_terminal({"_mode": "done", "_result": 42}) is False

    def test_incomplete_done_missing_mode(self):
        """State with _result and _stall but no _mode is not terminal."""
        assert is_kernel_terminal({"_result": 42, "_stall": False}) is False

    def test_wrong_mode_not_terminal(self):
        """State with wrong _mode value is not terminal."""
        assert is_kernel_terminal({"_mode": "kernel", "_result": 42, "_stall": False}) is False
        assert is_kernel_terminal({"_mode": "match", "_result": 42, "_stall": False}) is False

    def test_empty_dict_not_terminal(self):
        """Empty dict is not terminal."""
        assert is_kernel_terminal({}) is False


# =============================================================================
# extract_kernel_result() Tests
# =============================================================================

class TestExtractKernelResult:
    """Test extract_kernel_result() helper - mechanical unpacking."""

    def test_success_extracts_and_denormalizes_list(self):
        """Success case denormalizes linked list to Python list."""
        terminal = {"_mode": "done", "_result": {"head": 1, "tail": None}, "_stall": False}
        result = extract_kernel_result(terminal, {"original": "input"})
        assert result == [1]

    def test_success_extracts_nested_list(self):
        """Success case denormalizes nested linked list."""
        terminal = {
            "_mode": "done",
            "_result": {"head": 1, "tail": {"head": 2, "tail": None}},
            "_stall": False
        }
        result = extract_kernel_result(terminal, "ignored")
        assert result == [1, 2]

    def test_stall_returns_original(self):
        """Stall case returns original input unchanged."""
        terminal = {"_mode": "done", "_result": {"head": 1, "tail": None}, "_stall": True}
        original = {"original": "input"}
        result = extract_kernel_result(terminal, original)
        assert result == {"original": "input"}

    def test_stall_preserves_empty_list(self):
        """Stall case preserves empty list type info."""
        terminal = {"_mode": "done", "_result": None, "_stall": True}
        original = []
        result = extract_kernel_result(terminal, original)
        assert result == []

    def test_primitive_result_unchanged(self):
        """Primitive results pass through unchanged."""
        terminal = {"_mode": "done", "_result": 42, "_stall": False}
        result = extract_kernel_result(terminal, "ignored")
        assert result == 42

    def test_string_result_unchanged(self):
        """String results pass through unchanged."""
        terminal = {"_mode": "done", "_result": "hello", "_stall": False}
        result = extract_kernel_result(terminal, "ignored")
        assert result == "hello"

    def test_none_result_unchanged(self):
        """None results pass through unchanged."""
        terminal = {"_mode": "done", "_result": None, "_stall": False}
        result = extract_kernel_result(terminal, "ignored")
        assert result is None

    def test_dict_result_denormalized(self):
        """Dict results get denormalized from head/tail format."""
        # A normalized dict looks like a linked list of key-value pairs
        terminal = {"_mode": "done", "_result": {"x": 1, "y": 2}, "_stall": False}
        result = extract_kernel_result(terminal, "ignored")
        assert result == {"x": 1, "y": 2}


# =============================================================================
# Integration Tests - Simplified Loop
# =============================================================================

class TestSimplifiedLoop:
    """Verify the simplified loop still produces correct results."""

    def test_simple_match_and_transform(self):
        """Basic projection matching works."""
        projections = [{"pattern": {"var": "x"}, "body": {"doubled": {"var": "x"}}}]
        result = step_mu(projections, 42)
        assert result == {"doubled": 42}

    def test_no_match_returns_original(self):
        """No matching projection returns input unchanged."""
        projections = [{"pattern": {"impossible": "value"}, "body": "never"}]
        result = step_mu(projections, 42)
        assert result == 42

    def test_empty_projections_stalls(self):
        """Empty projection list returns input unchanged."""
        result = step_mu([], {"some": "value"})
        assert result == {"some": "value"}

    def test_first_match_wins(self):
        """First matching projection is used."""
        projections = [
            {"pattern": {"var": "x"}, "body": "first"},
            {"pattern": {"var": "y"}, "body": "second"},
        ]
        result = step_mu(projections, 42)
        assert result == "first"

    def test_fallthrough_to_second(self):
        """Falls through to second projection if first doesn't match."""
        projections = [
            {"pattern": {"specific": "value"}, "body": "first"},
            {"pattern": {"var": "x"}, "body": "second"},
        ]
        result = step_mu(projections, 42)
        assert result == "second"

    def test_list_transformation(self):
        """Lists are properly normalized and denormalized."""
        projections = [{"pattern": {"var": "x"}, "body": {"wrapped": {"var": "x"}}}]
        result = step_mu(projections, [1, 2, 3])
        assert result == {"wrapped": [1, 2, 3]}

    def test_nested_dict_transformation(self):
        """Nested dicts are properly handled."""
        projections = [{"pattern": {"a": {"var": "x"}}, "body": {"b": {"var": "x"}}}]
        result = step_mu(projections, {"a": {"nested": "value"}})
        assert result == {"b": {"nested": "value"}}


# =============================================================================
# Regression Tests - Parity with Previous Behavior
# =============================================================================

class TestParityWithPreviousBehavior:
    """Ensure Phase 8b changes don't break existing behavior."""

    def test_identity_projection_stalls(self):
        """Identity projection causes immediate stall."""
        projections = [{"pattern": {"var": "x"}, "body": {"var": "x"}}]
        result = step_mu(projections, 42)
        # Identity returns same value, detected as stall
        assert result == 42

    def test_unbound_var_stalls(self):
        """Unbound variable in body causes stall (not error)."""
        projections = [{"pattern": 42, "body": {"var": "unbound"}}]
        result = step_mu(projections, 42)
        # Phase 7d-1 changed: unbound vars stall instead of KeyError
        assert result == 42

    def test_empty_list_handled(self):
        """Empty lists are handled correctly."""
        projections = [{"pattern": {"var": "x"}, "body": {"got": {"var": "x"}}}]
        result = step_mu(projections, [])
        # Empty list normalizes to None, but original preserved on stall
        assert result == {"got": []} or result == {"got": None}

    def test_empty_dict_handled(self):
        """Empty dicts are handled correctly."""
        projections = [{"pattern": {"var": "x"}, "body": {"got": {"var": "x"}}}]
        result = step_mu(projections, {})
        assert result == {"got": {}} or result == {"got": None}
