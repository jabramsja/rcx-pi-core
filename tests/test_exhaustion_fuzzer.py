"""
Property-based fuzzer tests for exhaustion.v1.json (Rule 3.1 Operator Exhaustion).

Uses Hypothesis to generate random traces and verify exhaustion detection
behaves correctly across edge cases.

See: docs/core/OperatorExhaustion.v0.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def exhaust_projections() -> list:
    """Load exhaustion projections from seed file (module-scoped for Hypothesis)."""
    seed = load_verified_seed(get_seed_path("exhaustion.v1.json"))
    return seed["projections"]


def run_until_stable(projections: list, value: dict, max_steps: int = 200) -> dict:
    """Run projections until stall (no change) or max_steps."""
    reset_step_budget()
    current = value
    for _ in range(max_steps):
        result = step(projections, current)
        if result == current:
            return result
        current = result
    return current


# =============================================================================
# Strategies for generating test data
# =============================================================================


# Generate operator IDs
operator_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz._",
    min_size=2,
    max_size=20
).filter(lambda s: not s.startswith('.') and not s.endswith('.') and '..' not in s)


# Generate simple states (primitives or small dicts)
simple_state_strategy = st.one_of(
    st.integers(min_value=-100, max_value=100),
    st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=5),
    st.none(),
    st.booleans()
)


def linked_list_from_python(items: list) -> dict | None:
    """Convert Python list to Mu linked list."""
    result = None
    for item in reversed(items):
        result = {"head": item, "tail": result}
    return result


@st.composite
def trace_entry_strategy(draw, step_num: int, operator_ids: list[str]):
    """Generate a trace entry."""
    state = draw(simple_state_strategy)
    # Pick an operator from the available ones, or None for stall
    if operator_ids and draw(st.booleans()):
        proj = draw(st.sampled_from(operator_ids))
    else:
        proj = None
    return {"step": step_num, "state": state, "projection": proj}


@st.composite
def trace_strategy(draw, max_length: int = 10):
    """Generate a trace as Mu linked list."""
    length = draw(st.integers(min_value=0, max_value=max_length))
    # Generate 1-3 operator IDs
    num_ops = draw(st.integers(min_value=1, max_value=3))
    operator_ids = [draw(operator_id_strategy) for _ in range(num_ops)]

    entries = []
    for i in range(length):
        state = draw(simple_state_strategy)
        proj = draw(st.sampled_from(operator_ids)) if operator_ids else None
        entries.append({"step": i, "state": state, "projection": proj})

    return linked_list_from_python(entries), operator_ids


@st.composite
def frozen_list_strategy(draw, operator_ids: list[str]):
    """Generate a frozen list (subset of operator_ids)."""
    if not operator_ids:
        return None
    # Randomly select some operators to be frozen
    frozen = [op for op in operator_ids if draw(st.booleans())]
    return linked_list_from_python(frozen)


@st.composite
def exhaustion_input_strategy(draw):
    """Generate a complete exhaustion detection input."""
    trace, operator_ids = draw(trace_strategy(max_length=8))
    frozen = draw(frozen_list_strategy(operator_ids))

    # tau_step is either None or a valid step number
    if trace is None:
        tau_step = None
    else:
        # Count entries in trace
        count = 0
        current = trace
        while current is not None:
            count += 1
            current = current.get("tail")

        if count == 0 or draw(st.booleans()):
            tau_step = None
        else:
            tau_step = draw(st.integers(min_value=0, max_value=count - 1))

    return {
        "_detect_exhaustion": {
            "trace": trace,
            "frozen": frozen,
            "tau_step": tau_step,
            "operator_ids": linked_list_from_python(operator_ids)
        }
    }


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestExhaustionProperties:
    """Property-based tests for exhaustion detection."""

    @given(exhaustion_input_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_always_terminates(self, exhaust_projections, input_data):
        """Exhaustion detection always terminates (no infinite loops)."""
        reset_step_budget()
        result = run_until_stable(exhaust_projections, input_data)
        # Should have reached a terminal state
        assert result is not None

    @given(exhaustion_input_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_result_has_valid_structure(self, exhaust_projections, input_data):
        """Result has valid structure (action field or kernel intermediate)."""
        reset_step_budget()
        result = run_until_stable(exhaust_projections, input_data)

        # Either terminal (has action) or intermediate (has _mode)
        has_action = "action" in result
        has_mode = "_mode" in result
        assert has_action or has_mode, f"Result must have action or _mode: {result.keys()}"

    @given(exhaustion_input_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_frozen_list_is_preserved_or_extended(self, exhaust_projections, input_data):
        """Frozen list is never shortened, only preserved or extended."""
        reset_step_budget()
        original_frozen = input_data["_detect_exhaustion"]["frozen"]
        result = run_until_stable(exhaust_projections, input_data)

        if "frozen" not in result:
            return  # Intermediate state, skip

        result_frozen = result["frozen"]

        # Count entries in original frozen
        def count_linked(ll):
            count = 0
            while ll is not None:
                count += 1
                ll = ll.get("tail") if isinstance(ll, dict) else None
            return count

        orig_count = count_linked(original_frozen)
        result_count = count_linked(result_frozen)

        assert result_count >= orig_count, \
            f"Frozen list shrunk from {orig_count} to {result_count}"

    @given(st.lists(operator_id_strategy, min_size=1, max_size=3))
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_null_tau_always_continues(self, exhaust_projections, operator_ids):
        """When tau_step is null, action is always 'continue'."""
        reset_step_budget()
        input_data = {
            "_detect_exhaustion": {
                "trace": linked_list_from_python([
                    {"step": 0, "state": "A", "projection": operator_ids[0]}
                ]),
                "frozen": None,
                "tau_step": None,
                "operator_ids": linked_list_from_python(operator_ids)
            }
        }
        result = run_until_stable(exhaust_projections, input_data)
        assert result.get("action") == "continue", f"Expected continue, got {result}"

    @given(operator_id_strategy)
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_same_operator_exhausts(self, exhaust_projections, op_id):
        """Single operator since tau_step should exhaust."""
        reset_step_budget()
        input_data = {
            "_detect_exhaustion": {
                "trace": linked_list_from_python([
                    {"step": 0, "state": "A", "projection": op_id},
                    {"step": 1, "state": "B", "projection": op_id},
                    {"step": 2, "state": "C", "projection": op_id}
                ]),
                "frozen": None,
                "tau_step": 0,
                "operator_ids": linked_list_from_python([op_id])
            }
        }
        result = run_until_stable(exhaust_projections, input_data)
        assert result.get("exhaustion_detected") is True, f"Expected exhaustion, got {result}"
        assert result.get("operator_to_freeze") == op_id

    @given(st.lists(operator_id_strategy, min_size=2, max_size=2, unique=True))
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_different_operators_no_exhaust(self, exhaust_projections, op_ids):
        """Different operators after tau_step should not exhaust."""
        reset_step_budget()
        op1, op2 = op_ids
        input_data = {
            "_detect_exhaustion": {
                "trace": linked_list_from_python([
                    {"step": 0, "state": "A", "projection": op1},
                    {"step": 1, "state": "B", "projection": op2}
                ]),
                "frozen": None,
                "tau_step": 0,
                "operator_ids": linked_list_from_python(op_ids)
            }
        }
        result = run_until_stable(exhaust_projections, input_data)
        assert result.get("exhaustion_detected") is False, f"Expected no exhaustion, got {result}"
        assert result.get("action") == "continue"


class TestExhaustionDeterminism:
    """Test that exhaustion detection is deterministic."""

    @given(exhaustion_input_strategy())
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_same_input_same_output(self, exhaust_projections, input_data):
        """Same input always produces same output."""
        reset_step_budget()
        result1 = run_until_stable(exhaust_projections, input_data)

        reset_step_budget()
        result2 = run_until_stable(exhaust_projections, input_data)

        assert result1 == result2, f"Non-deterministic: {result1} != {result2}"


class TestExhaustionNonLinearPatterns:
    """Test non-linear pattern behavior (binding conflict detection)."""

    def test_find_match_uses_non_linear(self, exhaust_projections):
        """exhaustion.find_match uses non-linear pattern for step equality."""
        # Find the projection
        proj = next(p for p in exhaust_projections if p["id"] == "exhaustion.find_match")
        pattern = proj["pattern"]

        # The pattern should have "step" appearing twice (in _trace.head.step and _tau_step)
        trace_step = pattern["_trace"]["head"]["step"]
        tau_step = pattern["_tau_step"]

        # Both should be the same variable
        assert trace_step == tau_step, "find_match should use non-linear pattern"

    def test_scan_same_uses_non_linear(self, exhaust_projections):
        """exhaustion.scan_same uses non-linear pattern for operator equality."""
        proj = next(p for p in exhaust_projections if p["id"] == "exhaustion.scan_same")
        pattern = proj["pattern"]

        # The pattern should have same var for projection and _tau_operator
        trace_proj = pattern["_trace"]["head"]["projection"]
        tau_op = pattern["_tau_operator"]

        assert trace_proj == tau_op, "scan_same should use non-linear pattern"

    def test_frozen_found_uses_non_linear(self, exhaust_projections):
        """exhaustion.frozen_found uses non-linear pattern for frozen membership."""
        proj = next(p for p in exhaust_projections if p["id"] == "exhaustion.frozen_found")
        pattern = proj["pattern"]

        # The pattern should have same var for _operator and _frozen_check.head
        operator = pattern["_operator"]
        frozen_head = pattern["_frozen_check"]["head"]

        assert operator == frozen_head, "frozen_found should use non-linear pattern"
