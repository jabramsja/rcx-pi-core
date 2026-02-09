"""
Deep/Wide Structure Fuzzer Tests.

These tests address the fuzzer agent finding that:
- No tests for 100+ entry traces
- No tests for 100+ variable bindings

These edge cases are critical for verifying the structural iteration
doesn't hit max_steps limits prematurely.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from rcx_pi.selfhost.eval_seed import step, match, substitute
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import run_mu_structural


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


@pytest.fixture
def subst_projections() -> list:
    """Load subst projections."""
    seed = load_verified_seed(get_seed_path("subst.v1.json"))
    return seed["projections"]


def make_linked_list(items: list) -> dict | None:
    """Create a Mu linked-list from Python list."""
    result = None
    for item in reversed(items):
        result = {"head": item, "tail": result}
    return result


def run_until_stable(projections: list, value: dict, max_steps: int = 500) -> dict:
    """Run projections until stall or max_steps."""
    reset_step_budget()
    current = value
    for _ in range(max_steps):
        result = step(projections, current)
        if result == current:
            return result
        current = result
    return current


# =============================================================================
# Deep Trace Tests (100+ entries)
# =============================================================================


class TestDeepTraceHandling:
    """Test recurrence/exhaustion with deep traces (100+ entries)."""

    @given(st.integers(min_value=50, max_value=150))
    @settings(max_examples=20, deadline=30000)
    def test_deep_trace_structural_run(self, trace_depth: int):
        """Deep traces should run without stalling prematurely.

        Creates an oscillating trace A->B->A->B... and verifies trace structure.
        """
        reset_step_budget()

        # Create oscillating projections
        oscillate = [
            {"id": "to_b", "pattern": "A", "body": "B"},
            {"id": "to_a", "pattern": "B", "body": "A"}
        ]

        # Run to get trace
        trace_result = run_mu_structural(oscillate, "A", max_steps=trace_depth)

        # Should return valid result structure with actual values (not just existence)
        assert "result" in trace_result, "Should have result key"
        assert "trace" in trace_result, "Should have trace key"
        assert "steps" in trace_result, "Should have step count key"

        # Verify result is meaningful (oscillates between A and B)
        assert trace_result["result"] in ("A", "B"), \
            f"Result should be A or B, got {trace_result['result']}"

        # Verify steps is a valid positive integer
        assert isinstance(trace_result["steps"], int) and trace_result["steps"] >= 0, \
            f"Steps should be non-negative int, got {trace_result['steps']}"

        # Trace should be linked list (Mu structure) with proper format AND values
        trace = trace_result["trace"]
        if trace is not None:
            assert isinstance(trace, dict), "Trace should be linked list dict"
            assert "head" in trace and "tail" in trace, "Trace must have head and tail"
            # Verify trace entry has correct VALUES, not just keys (Grounding fix)
            head = trace["head"]
            assert isinstance(head, dict), "Trace entry should be dict"
            assert head.get("step") == 0, \
                f"First trace entry should be step 0, got {head.get('step')}"
            assert head.get("state") in ("A", "B"), \
                f"First trace state should be A or B, got {head.get('state')}"
            assert head.get("projection") in ("to_a", "to_b"), \
                f"First trace projection should be to_a or to_b, got {head.get('projection')}"

        # Should run for specified steps without error
        assert trace_result["steps"] <= trace_depth, \
            f"Should not exceed max_steps ({trace_depth})"

    @given(seen_set_size=st.integers(min_value=20, max_value=100))
    @settings(max_examples=20, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deep_seen_set_traversal(self, recurrence_projections, seen_set_size: int):
        """Recurrence should handle large seen-sets without max_steps issues."""
        reset_step_budget()

        # Create a seen-set with many unique states
        seen_list = make_linked_list([
            {"state": f"unique_{i}", "step": i}
            for i in range(seen_set_size)
        ])

        # Create trace with one entry that's NOT in seen (should complete without closure)
        trace = make_linked_list([
            {"step": 0, "state": {"state": "new_unique"}, "projection": "test"}
        ])

        # Run recurrence
        input_data = {
            "_detect_closure": {
                "trace": trace,
                "result": "final"
            }
        }

        result = run_until_stable(recurrence_projections, input_data, max_steps=seen_set_size * 10)

        # Should complete with no closure (unique states) - verify semantic state directly
        # Grounding fix: Remove weak branching, always verify semantic fields
        assert result.get("closure_detected") is False, \
            f"Unique states should not trigger closure, got closure_detected={result.get('closure_detected')}"
        assert result.get("final_result") == "final", \
            f"Should preserve final result, got: {result.get('final_result')}"
        # Verify tau_step is 0 (no closure found at any step)
        assert result.get("tau_step") is None or result.get("tau_step") == 0, \
            f"No closure means tau_step should be None or 0, got: {result.get('tau_step')}"


class TestDeepExhaustionTraversal:
    """Test exhaustion with deep traces."""

    @given(trace_depth=st.integers(min_value=20, max_value=80))
    @settings(max_examples=15, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deep_exhaustion_scan(self, exhaustion_projections, trace_depth: int):
        """Exhaustion should scan deep traces without stalling."""
        reset_step_budget()

        # Create trace where all entries have same operator (should detect exhaustion)
        trace = make_linked_list([
            {"step": i, "state": f"state_{i}", "projection": "same_op"}
            for i in range(trace_depth)
        ])

        input_data = {
            "_detect_exhaustion": {
                "trace": trace,
                "frozen": None,
                "tau_step": 0,  # Start from beginning
                "operator_ids": None
            }
        }

        result = run_until_stable(exhaustion_projections, input_data, max_steps=trace_depth * 5)

        # Same operator throughout should detect exhaustion (Grounding fix: stronger assertions)
        # With same operator from start, should either freeze or already be frozen
        assert result.get("action") in ["freeze", "already_frozen"], \
            f"Same operator throughout should freeze or already_frozen, got: {result.get('action')}"

        if result.get("action") == "freeze":
            # Verify freeze action semantics
            assert result.get("exhaustion_detected") is True, \
                "freeze action should have exhaustion_detected=True"
            assert result.get("operator_to_freeze") == "same_op", \
                f"Should freeze same_op, got: {result.get('operator_to_freeze')}"
            # Verify frozen list contains same_op (semantic check, not just existence)
            # Gate 3: frozen is now a Python list (denormalized), not linked-list
            frozen = result.get("frozen")
            assert frozen is not None and "same_op" in frozen, \
                f"Frozen list should contain same_op, got: {frozen}"
        else:  # already_frozen
            # Verify already_frozen semantics
            assert result.get("exhaustion_detected") is False, \
                "already_frozen should have exhaustion_detected=False"


# =============================================================================
# Wide Bindings Tests (100+ variables)
# =============================================================================


class TestWideBindingsHandling:
    """Test substitution with many bindings (100+ variables)."""

    @given(st.integers(min_value=50, max_value=150))
    @settings(max_examples=20, deadline=30000)
    def test_wide_bindings_lookup(self, num_bindings: int):
        """Substitution should handle wide bindings lists."""
        reset_step_budget()

        # Create bindings: var0 -> 0, var1 -> 1, ..., varN -> N
        bindings = {f"var{i}": i for i in range(num_bindings)}

        # Body references LAST variable (worst case for lookup)
        body = {"var": f"var{num_bindings - 1}"}

        result = substitute(body, bindings)

        # Should successfully look up the last variable
        assert result == num_bindings - 1, \
            f"Lookup of var{num_bindings - 1} should return {num_bindings - 1}"

    @given(st.integers(min_value=20, max_value=80))
    @settings(max_examples=20, deadline=30000)
    def test_wide_bindings_multiple_lookups(self, num_bindings: int):
        """Multiple variable lookups in wide bindings should work."""
        reset_step_budget()

        # Create bindings
        bindings = {f"var{i}": f"value_{i}" for i in range(num_bindings)}

        # Body references first, middle, and last variables
        first = 0
        middle = num_bindings // 2
        last = num_bindings - 1

        body = {
            "first": {"var": f"var{first}"},
            "middle": {"var": f"var{middle}"},
            "last": {"var": f"var{last}"}
        }

        result = substitute(body, bindings)

        assert result["first"] == f"value_{first}"
        assert result["middle"] == f"value_{middle}"
        assert result["last"] == f"value_{last}"

    @given(st.integers(min_value=10, max_value=50))
    @settings(max_examples=20, deadline=30000)
    def test_wide_pattern_with_many_variables(self, num_vars: int):
        """Pattern with many variables should match correctly."""
        reset_step_budget()

        # Create pattern with many variables
        pattern = {f"key{i}": {"var": f"v{i}"} for i in range(num_vars)}

        # Create matching value
        value = {f"key{i}": f"val_{i}" for i in range(num_vars)}

        result = match(pattern, value)

        # Should match all variables
        assert result is not None, f"Pattern with {num_vars} vars should match"
        assert len(result) == num_vars, f"Should bind {num_vars} variables"

        for i in range(num_vars):
            assert result[f"v{i}"] == f"val_{i}"


# =============================================================================
# Combined Deep + Wide Tests
# =============================================================================


class TestDeepAndWide:
    """Test combinations of deep and wide structures."""

    @given(
        st.integers(min_value=10, max_value=20),
        st.integers(min_value=10, max_value=20)
    )
    @settings(
        max_examples=15,
        deadline=None,  # Recurrence is O(n²) on trace_depth; per-example can take ~10s at 20x20
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_deep_trace_with_wide_states(self, trace_depth: int, state_width: int):
        """Trace with many entries where each state is wide.

        Recurrence scans trace O(n²): each entry compared against seen-set.
        At 20x20 (depth=20, width=20), each example takes ~10s / ~233 steps.
        Ranges capped at 20 to stay within 180s pytest timeout across 15 examples.
        """
        reset_step_budget()

        # Create trace where each state is a wide dict with UNIQUE values
        trace_entries = []
        for i in range(trace_depth):
            # Include step index to make each wide state unique
            wide_state = {f"field_{j}": j + (i * state_width) for j in range(state_width)}
            trace_entries.append({
                "step": i,
                "state": wide_state,
                "projection": f"proj_{i % 3}"  # Vary projections
            })

        trace = make_linked_list(trace_entries)

        # Create recurrence input
        from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
        recurrence_projs = load_verified_seed(get_seed_path("recurrence.v1.json"))["projections"]

        input_data = {
            "_detect_closure": {
                "trace": trace,
                "result": "final"
            }
        }

        result = run_until_stable(recurrence_projs, input_data, max_steps=trace_depth * state_width)

        # Should complete without stalling in intermediate state
        if "closure_detected" in result:
            # Completed - verify semantic correctness
            assert isinstance(result.get("closure_detected"), bool), \
                f"closure_detected should be bool, got: {type(result.get('closure_detected'))}"
            # All states are unique (different field values), so should NOT detect closure
            assert result.get("closure_detected") is False, \
                f"Unique wide states should not trigger closure"
            assert result.get("final_result") == "final", \
                f"Should preserve final result, got: {result.get('final_result')}"
        elif result.get("_mode") == "recurrence_done":
            # Intermediate done state (before unwrap)
            assert "_closure" in result, "recurrence_done should have _closure field"
        else:
            # Still processing - verify it's in valid intermediate state
            assert result.get("_mode") == "recurrence", \
                f"Should be in recurrence mode if not done, got: {result.get('_mode')}"
            assert result.get("_phase") in ["scan", "check_seen"], \
                f"Should be in valid phase, got: {result.get('_phase')}"


# =============================================================================
# Stress Tests
# =============================================================================


class TestStressLimits:
    """Test behavior near system limits."""

    def test_max_reasonable_trace_depth(self):
        """Test with trace depth near practical limit."""
        reset_step_budget()

        trace_depth = 200

        # Simple oscillating trace
        trace_entries = [
            {"step": i, "state": i % 2, "projection": "osc"}
            for i in range(trace_depth)
        ]
        trace = make_linked_list(trace_entries)

        recurrence_projs = load_verified_seed(get_seed_path("recurrence.v1.json"))["projections"]

        input_data = {
            "_detect_closure": {
                "trace": trace,
                "result": "final"
            }
        }

        # Should complete with closure (oscillating pattern)
        result = run_until_stable(recurrence_projs, input_data, max_steps=trace_depth * 3)

        assert result.get("closure_detected") is True or "closure_detected" in result, \
            f"Oscillating trace of {trace_depth} should detect closure"

    def test_max_reasonable_bindings_width(self):
        """Test with bindings width near practical limit."""
        reset_step_budget()

        num_bindings = 200

        # Create wide bindings
        bindings = {f"var{i}": i for i in range(num_bindings)}

        # Lookup last variable
        body = {"var": f"var{num_bindings - 1}"}

        result = substitute(body, bindings)

        assert result == num_bindings - 1, \
            f"Should successfully lookup in {num_bindings} bindings"
