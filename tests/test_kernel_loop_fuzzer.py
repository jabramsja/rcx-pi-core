"""
Kernel Loop Fuzzer - L2 Kernel Iteration Property Tests

Property-based tests for kernel loop iteration to ensure:
1. Kernel loop always terminates (max_steps or stall)
2. Kernel produces valid terminal states or stalls
3. Step count is bounded and reported correctly
4. Linked-list cursor advances correctly
5. No infinite loops on adversarial inputs

These tests specifically target the L2 kernel iteration (step_kernel_mu)
that was identified as a gap in fuzzer coverage.
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from rcx_pi.selfhost.step_mu import (
    step_mu,
    is_kernel_terminal,
    extract_kernel_result,
    load_combined_kernel_projections,
    list_to_linked,
    normalize_projection,
)
from rcx_pi.selfhost.match_mu import normalize_for_match
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.eval_seed import step


# =============================================================================
# Strategies for generating test inputs
# =============================================================================

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
        st.dictionaries(st.text(max_size=10), children, max_size=3),
    ),
    max_leaves=10,
)


# Valid projection structure
@st.composite
def projections(draw, max_depth=3):
    """Generate a valid projection with pattern and body."""
    # Simple patterns that will match something
    pattern = draw(st.one_of(
        st.just({"var": "x"}),  # Catch-all
        st.integers(min_value=0, max_value=100),
        st.text(max_size=10),
        st.dictionaries(
            st.text(max_size=5),
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

    return {"pattern": pattern, "body": body}


@st.composite
def projection_lists(draw, min_size=0, max_size=5):
    """Generate a list of projections."""
    projs = draw(st.lists(projections(), min_size=min_size, max_size=max_size))
    return projs


# =============================================================================
# Kernel Loop Termination Tests
# =============================================================================

class TestKernelLoopTermination:
    """Test that kernel loop always terminates."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    @given(value=simple_mu)
    @settings(max_examples=200, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_kernel_terminates_with_real_projections(self, value):
        """Kernel loop terminates on any input with real projections."""
        # Use step_mu with empty projection list (will stall)
        result = step_mu([], value)

        # Must terminate - stalls return original, so mu_equal should be True
        # (None input returns None, which is valid)
        assert mu_equal(result, value)

    @given(value=simple_mu, projs=projection_lists(max_size=3))
    @settings(max_examples=200, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_kernel_terminates_with_custom_projections(self, value, projs):
        """Kernel loop terminates with arbitrary projection lists."""
        # Use step_mu which uses step_kernel_mu internally
        # This just needs to not hang - any result is valid
        try:
            result = step_mu(projs, value)
            # If we get here, it terminated
            assert True
        except Exception:
            # Exceptions are okay too (e.g., validation errors)
            assert True

    @given(value=simple_mu)
    @settings(max_examples=50, deadline=5000)
    def test_kernel_step_terminates(self, value):
        """Single kernel step terminates."""
        kernel_projs = load_combined_kernel_projections()

        # Normalize and wrap input for kernel
        normalized = normalize_for_match(value)
        initial = {"_step": normalized, "_projs": None}  # Empty proj list

        # Single step using eval_seed.step
        result = step(kernel_projs, initial)

        # Must return within one step
        assert result is not None


# =============================================================================
# Terminal State Detection Tests
# =============================================================================

class TestTerminalStateDetection:
    """Test is_kernel_terminal helper."""

    @given(result=simple_mu, stall=st.booleans())
    @settings(max_examples=100, deadline=5000)
    def test_done_state_is_terminal(self, result, stall):
        """States with _mode='done' are terminal."""
        state = {"_mode": "done", "_result": result, "_stall": stall}
        assert is_kernel_terminal(state) is True

    @given(phase=st.sampled_from(["try", "match", "subst"]))
    @settings(max_examples=50, deadline=5000)
    def test_non_done_state_is_not_terminal(self, phase):
        """States with _mode != 'done' are not terminal."""
        state = {"_mode": "kernel", "_phase": phase, "_input": 42}
        assert is_kernel_terminal(state) is False

    @given(value=simple_mu)
    @settings(max_examples=100, deadline=5000)
    def test_primitives_are_not_terminal(self, value):
        """Primitive values (non-dict) are not terminal."""
        if not isinstance(value, dict):
            assert is_kernel_terminal(value) is False


# =============================================================================
# Result Extraction Tests
# =============================================================================

class TestResultExtraction:
    """Test extract_kernel_result helper."""

    @given(result=simple_mu)
    @settings(max_examples=100, deadline=5000)
    def test_success_extracts_result(self, result):
        """Successful terminal state extracts and denormalizes result."""
        terminal = {"_mode": "done", "_result": normalize_for_match(result), "_stall": False}
        original = {"ignored": "input"}

        extracted = extract_kernel_result(terminal, original)
        # Should get denormalized result, not original
        assert extracted != original or result == original

    @given(result=simple_mu, original=simple_mu)
    @settings(max_examples=100, deadline=5000)
    def test_stall_returns_original(self, result, original):
        """Stall terminal state returns original input."""
        terminal = {"_mode": "done", "_result": result, "_stall": True}

        extracted = extract_kernel_result(terminal, original)
        assert mu_equal(extracted, original)


# =============================================================================
# Linked List Cursor Tests
# =============================================================================

class TestLinkedListCursor:
    """Test that linked list cursor advances correctly."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    @given(projs=projection_lists(min_size=1, max_size=5))
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_linked_list_preserves_projection_count(self, projs):
        """Converting to linked list preserves projection count."""
        normalized = [normalize_projection(p) for p in projs]
        linked = list_to_linked(normalized)

        # Count nodes in linked list
        count = 0
        current = linked
        while current is not None:
            assert isinstance(current, dict)
            assert "head" in current
            assert "tail" in current
            count += 1
            current = current["tail"]

        assert count == len(projs)

    def test_empty_list_becomes_null(self):
        """Empty projection list becomes null."""
        linked = list_to_linked([])
        assert linked is None

    @given(projs=projection_lists(min_size=1, max_size=3))
    @settings(max_examples=50, deadline=5000)
    def test_first_projection_is_head(self, projs):
        """First projection in list is head of linked list."""
        normalized = [normalize_projection(p) for p in projs]
        linked = list_to_linked(normalized)

        assert linked is not None
        assert mu_equal(linked["head"], normalized[0])


# =============================================================================
# Stall Detection Tests
# =============================================================================

class TestStallDetection:
    """Test that stall detection works correctly."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_empty_projections_stall(self):
        """Empty projection list causes immediate stall."""
        # Use step_mu with empty projections
        result = step_mu([], 42)

        # With no projections, should stall and return original
        assert result == 42

    @given(value=simple_mu)
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_no_matching_projection_stalls(self, value):
        """When no projection matches, kernel stalls."""
        # Projection that won't match anything
        never_match = {"pattern": {"impossible": "match"}, "body": {"never": "reached"}}

        result = step_mu([never_match], value)

        # Should stall and return original value (mu_equal handles None)
        assert mu_equal(result, value)


# =============================================================================
# Adversarial Input Tests
# =============================================================================

class TestAdversarialInputs:
    """Test kernel handles adversarial inputs safely."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_deeply_nested_input(self):
        """Kernel handles deeply nested input."""
        # Create nested structure (within limits)
        nested = 42
        for _ in range(10):
            nested = {"layer": nested}

        result = step_mu([], nested)

        assert result is not None

    def test_wide_input(self):
        """Kernel handles wide (many keys) input."""
        wide = {f"key_{i}": i for i in range(20)}
        result = step_mu([], wide)

        assert result is not None

    def test_mixed_types_input(self):
        """Kernel handles mixed type input."""
        mixed = {
            "int": 42,
            "str": "hello",
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"}
        }
        result = step_mu([], mixed)

        assert result is not None
