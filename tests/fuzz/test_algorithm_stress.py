"""
Gate 3 Exit Criteria: Algorithm Stress Tests

These tests address specific gaps identified in Gate 3 planning:
1. test_large_frozen_list_stress - exhaustion with 50-100 pre-frozen operators
2. test_multi_state_cycle_detection - recurrence with 3-5 state cycles
3. test_quadruple_nonlinear_var - 4+ occurrences of same variable in pattern
4. test_mixed_linear_nonlinear_patterns - combined linear and non-linear vars

These tests verify that algorithm projections can handle stress cases
after the Gate 3 entry point renaming (_detect_closure, _detect_exhaustion).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from rcx_pi.selfhost.eval_seed import step, match, substitute, NO_MATCH
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.mu_type import mu_equal


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def recurrence_projections() -> list:
    """Load recurrence projections."""
    seed = load_verified_seed(get_seed_path("recurrence.v1.json"))
    return seed["projections"]


@pytest.fixture
def exhaustion_projections() -> list:
    """Load exhaustion projections."""
    seed = load_verified_seed(get_seed_path("exhaustion.v1.json"))
    return seed["projections"]


def make_linked_list(items: list) -> dict | None:
    """Create a Mu linked-list from Python list."""
    if not items:
        return None
    result = None
    for item in reversed(items):
        result = {"head": item, "tail": result}
    return result


def run_until_stable(projections: list, value: dict, max_steps: int = 500) -> dict:
    """Run projections until stall (no change) or max_steps."""
    reset_step_budget()
    current = value
    for _ in range(max_steps):
        result = step(projections, current)
        if mu_equal(result, current):
            return result
        current = result
    return current


# =============================================================================
# Test 1: Large Frozen List Stress (50-100 pre-frozen operators)
# =============================================================================


class TestLargeFrozenListStress:
    """Exhaustion detection with many pre-frozen operators."""

    def test_50_frozen_operators(self, exhaustion_projections):
        """Exhaustion handles 50 pre-frozen operators."""
        reset_step_budget()

        # Create 50 frozen operators
        frozen_ops = [f"op_{i}" for i in range(50)]
        frozen_list = make_linked_list(frozen_ops)

        # Trace with a NEW operator (not in frozen list)
        trace = make_linked_list([
            {"step": 0, "state": "A", "projection": "new_op"},
            {"step": 1, "state": "B", "projection": "new_op"},
        ])

        input_data = {
            "_detect_exhaustion": {
                "trace": trace,
                "frozen": frozen_list,
                "tau_step": 0,
                "operator_ids": make_linked_list(["new_op"] + frozen_ops)
            }
        }

        result = run_until_stable(exhaustion_projections, input_data)

        # Should detect exhaustion and freeze new_op
        assert result.get("exhaustion_detected") is True
        assert result.get("operator_to_freeze") == "new_op"
        assert result.get("action") == "freeze"

    def test_100_frozen_operators_already_frozen(self, exhaustion_projections):
        """Exhaustion handles 100 frozen operators when operator already frozen."""
        reset_step_budget()

        # Create 100 frozen operators including target_op
        frozen_ops = [f"op_{i}" for i in range(100)]
        target_op = "op_50"  # Already in frozen list
        frozen_list = make_linked_list(frozen_ops)

        # Trace with an operator that's already frozen
        trace = make_linked_list([
            {"step": 0, "state": "A", "projection": target_op},
            {"step": 1, "state": "B", "projection": target_op},
        ])

        input_data = {
            "_detect_exhaustion": {
                "trace": trace,
                "frozen": frozen_list,
                "tau_step": 0,
                "operator_ids": make_linked_list(frozen_ops)
            }
        }

        result = run_until_stable(exhaustion_projections, input_data, max_steps=1000)

        # Should NOT detect exhaustion (already frozen)
        assert result.get("exhaustion_detected") is False
        assert result.get("action") == "already_frozen"

    @given(st.integers(min_value=50, max_value=100))
    @settings(deadline=30000, max_examples=5, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_variable_frozen_list_size(self, exhaustion_projections, n_frozen):
        """Exhaustion handles variable frozen list sizes (50-100)."""
        reset_step_budget()

        frozen_ops = [f"op_{i}" for i in range(n_frozen)]
        frozen_list = make_linked_list(frozen_ops)

        # New operator not in frozen list
        trace = make_linked_list([
            {"step": 0, "state": "X", "projection": "new_op"},
            {"step": 1, "state": "Y", "projection": "new_op"},
        ])

        input_data = {
            "_detect_exhaustion": {
                "trace": trace,
                "frozen": frozen_list,
                "tau_step": 0,
                "operator_ids": make_linked_list(["new_op"])
            }
        }

        result = run_until_stable(exhaustion_projections, input_data, max_steps=1000)

        # Should detect exhaustion
        assert result.get("exhaustion_detected") is True
        assert result.get("operator_to_freeze") == "new_op"


# =============================================================================
# Test 2: Multi-State Cycle Detection (3-5 state cycles)
# =============================================================================


class TestMultiStateCycleDetection:
    """Recurrence detection with multi-state cycles."""

    def test_3_state_cycle(self, recurrence_projections):
        """Detect closure in A -> B -> C -> A cycle."""
        reset_step_budget()

        # A -> B -> C -> A cycle
        trace = make_linked_list([
            {"step": 0, "state": "A", "projection": "to_b"},
            {"step": 1, "state": "B", "projection": "to_c"},
            {"step": 2, "state": "C", "projection": "to_a"},
            {"step": 3, "state": "A", "projection": "to_b"},  # A recurs!
        ])

        input_data = {
            "_detect_closure": {
                "trace": trace,
                "result": "A"
            }
        }

        result = run_until_stable(recurrence_projections, input_data)

        assert result.get("closure_detected") is True
        assert result.get("tau_step") == 3

    def test_4_state_cycle(self, recurrence_projections):
        """Detect closure in A -> B -> C -> D -> A cycle."""
        reset_step_budget()

        trace = make_linked_list([
            {"step": 0, "state": "A", "projection": "to_b"},
            {"step": 1, "state": "B", "projection": "to_c"},
            {"step": 2, "state": "C", "projection": "to_d"},
            {"step": 3, "state": "D", "projection": "to_a"},
            {"step": 4, "state": "A", "projection": "to_b"},  # A recurs!
        ])

        input_data = {
            "_detect_closure": {
                "trace": trace,
                "result": "A"
            }
        }

        result = run_until_stable(recurrence_projections, input_data)

        assert result.get("closure_detected") is True
        assert result.get("tau_step") == 4

    def test_5_state_cycle(self, recurrence_projections):
        """Detect closure in 5-state cycle."""
        reset_step_budget()

        states = ["S0", "S1", "S2", "S3", "S4"]
        entries = [{"step": i, "state": states[i], "projection": f"to_{i+1}"} for i in range(5)]
        entries.append({"step": 5, "state": "S0", "projection": "to_1"})  # S0 recurs

        trace = make_linked_list(entries)

        input_data = {
            "_detect_closure": {
                "trace": trace,
                "result": "S0"
            }
        }

        result = run_until_stable(recurrence_projections, input_data)

        assert result.get("closure_detected") is True
        assert result.get("tau_step") == 5

    @given(st.integers(min_value=3, max_value=5))
    @settings(deadline=10000, max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_variable_cycle_length(self, recurrence_projections, cycle_len):
        """Detect closure in variable-length cycles (3-5 states)."""
        reset_step_budget()

        states = [f"state_{i}" for i in range(cycle_len)]
        entries = [{"step": i, "state": states[i], "projection": f"proj_{i}"} for i in range(cycle_len)]
        entries.append({"step": cycle_len, "state": states[0], "projection": "proj_0"})

        trace = make_linked_list(entries)

        input_data = {
            "_detect_closure": {
                "trace": trace,
                "result": states[0]
            }
        }

        result = run_until_stable(recurrence_projections, input_data)

        assert result.get("closure_detected") is True
        assert result.get("tau_step") == cycle_len


# =============================================================================
# Test 3: Quadruple Non-Linear Variable (4+ occurrences)
# =============================================================================


class TestQuadrupleNonlinearVar:
    """Pattern matching with 4+ occurrences of same variable."""

    def test_4_var_occurrences_match(self):
        """Pattern with 4 occurrences of same var matches when all equal."""
        reset_step_budget()

        # Pattern: {a: X, b: X, c: X, d: X} where X must match all 4 positions
        pattern = {
            "a": {"var": "x"},
            "b": {"var": "x"},
            "c": {"var": "x"},
            "d": {"var": "x"}
        }

        # Value with all same
        value = {"a": 42, "b": 42, "c": 42, "d": 42}

        result = match(pattern, value)
        assert result is not NO_MATCH
        assert result.get("x") == 42

    def test_4_var_occurrences_no_match(self):
        """Pattern with 4 occurrences fails when one differs."""
        reset_step_budget()

        pattern = {
            "a": {"var": "x"},
            "b": {"var": "x"},
            "c": {"var": "x"},
            "d": {"var": "x"}
        }

        # Value with one different
        value = {"a": 42, "b": 42, "c": 42, "d": 99}

        result = match(pattern, value)
        # Should fail to match due to binding conflict
        assert result is NO_MATCH

    def test_5_var_occurrences(self):
        """Pattern with 5 occurrences of same var."""
        reset_step_budget()

        pattern = {
            "v1": {"var": "y"},
            "v2": {"var": "y"},
            "v3": {"var": "y"},
            "v4": {"var": "y"},
            "v5": {"var": "y"}
        }

        # All same
        value = {"v1": "same", "v2": "same", "v3": "same", "v4": "same", "v5": "same"}

        result = match(pattern, value)
        assert result is not NO_MATCH
        assert result.get("y") == "same"

    @given(st.integers(min_value=4, max_value=8))
    @settings(deadline=5000, max_examples=10)
    def test_variable_nonlinear_count(self, n_occurrences):
        """Pattern with variable number of same-var occurrences."""
        reset_step_budget()

        pattern = {f"field_{i}": {"var": "z"} for i in range(n_occurrences)}
        value = {f"field_{i}": "constant" for i in range(n_occurrences)}

        result = match(pattern, value)
        assert result is not NO_MATCH
        assert result.get("z") == "constant"


# =============================================================================
# Test 4: Mixed Linear and Non-Linear Patterns
# =============================================================================


class TestMixedLinearNonlinearPatterns:
    """Patterns combining linear and non-linear variables."""

    def test_mixed_pattern_match(self):
        """Pattern with both linear and non-linear vars matches correctly."""
        reset_step_budget()

        # Pattern: {same1: X, same2: X, diff: Y} - X is non-linear, Y is linear
        pattern = {
            "same1": {"var": "x"},
            "same2": {"var": "x"},
            "diff": {"var": "y"}
        }

        value = {"same1": 100, "same2": 100, "diff": 200}

        result = match(pattern, value)
        assert result is not NO_MATCH
        assert result.get("x") == 100
        assert result.get("y") == 200

    def test_mixed_pattern_nonlinear_fail(self):
        """Mixed pattern fails when non-linear var has conflict."""
        reset_step_budget()

        pattern = {
            "same1": {"var": "x"},
            "same2": {"var": "x"},
            "diff": {"var": "y"}
        }

        # same1 and same2 have different values - should fail
        value = {"same1": 100, "same2": 999, "diff": 200}

        result = match(pattern, value)
        assert result is NO_MATCH

    def test_complex_mixed_pattern(self):
        """Complex pattern with multiple non-linear and linear vars."""
        reset_step_budget()

        # Pattern with: a, b same (non-linear), c, d same (non-linear), e unique (linear)
        pattern = {
            "a": {"var": "x"},
            "b": {"var": "x"},
            "c": {"var": "y"},
            "d": {"var": "y"},
            "e": {"var": "z"}
        }

        value = {"a": "alpha", "b": "alpha", "c": "beta", "d": "beta", "e": "gamma"}

        result = match(pattern, value)
        assert result is not NO_MATCH
        assert result.get("x") == "alpha"
        assert result.get("y") == "beta"
        assert result.get("z") == "gamma"

    def test_mixed_in_substitution(self):
        """Substitution with mixed linear/non-linear bindings."""
        reset_step_budget()

        # Body uses x twice (from non-linear match) and y once (from linear)
        body = {
            "result_a": {"var": "x"},
            "result_b": {"var": "x"},
            "result_c": {"var": "y"}
        }

        bindings = {"x": "shared", "y": "unique"}

        result = substitute(body, bindings)

        assert result["result_a"] == "shared"
        assert result["result_b"] == "shared"
        assert result["result_c"] == "unique"

    @given(
        st.integers(min_value=2, max_value=4),
        st.integers(min_value=1, max_value=3)
    )
    @settings(deadline=5000, max_examples=20)
    def test_variable_mixed_pattern(self, n_nonlinear, n_linear):
        """Variable number of non-linear and linear vars in pattern."""
        reset_step_budget()

        # Build pattern with n_nonlinear occurrences of 'x' and n_linear of distinct vars
        pattern = {}
        for i in range(n_nonlinear):
            pattern[f"nonlin_{i}"] = {"var": "x"}
        for i in range(n_linear):
            pattern[f"lin_{i}"] = {"var": f"y_{i}"}

        # Build matching value
        value = {}
        for i in range(n_nonlinear):
            value[f"nonlin_{i}"] = "shared_value"
        for i in range(n_linear):
            value[f"lin_{i}"] = f"unique_{i}"

        result = match(pattern, value)
        assert result is not NO_MATCH
        assert result.get("x") == "shared_value"
        for i in range(n_linear):
            assert result.get(f"y_{i}") == f"unique_{i}"
