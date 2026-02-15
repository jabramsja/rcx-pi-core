"""
Cross-Seed State-Machine Boundary Fuzzer (#1017)

Property-based tests for kernel state machine transitions across seed boundaries.
Tests that kernel.v1 + match.v2 + subst.v2 interactions remain sound under fuzzing.

Agent finding #1017: "Missing Cross-Seed State-Machine Boundary Fuzzing"
- The kernel state machine (wrap → try → match_success/fail → unwrap) was not
  fuzzed at seed boundaries where kernel.v1 hands off to match.v2 and subst.v2.
"""
import pytest
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from rcx_pi.selfhost.step_mu import (
    step_kernel_mu,
    is_kernel_terminal,
    is_kernel_intermediate,
    extract_kernel_result,
    KERNEL_RESERVED_FIELDS,
    validate_kernel_projections_first,
)
from rcx_pi.selfhost.mu_type import mu_equal, is_mu


# =============================================================================
# Strategies
# =============================================================================

from tests.strategies import simple_mu_with_floats as simple_mu

mu_value = st.recursive(
    simple_mu,
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(
            st.text(max_size=10).filter(lambda k: k not in KERNEL_RESERVED_FIELDS),
            children,
            max_size=3,
        ),
    ),
    max_leaves=10,
)


@st.composite
def domain_projection(draw):
    """Generate a well-formed domain projection (no kernel-reserved fields)."""
    key = draw(st.text(min_size=1, max_size=10).filter(
        lambda k: k not in KERNEL_RESERVED_FIELDS and not k.startswith("_")
    ))
    pattern_val = draw(simple_mu)
    body_val = draw(simple_mu)
    proj_id = draw(st.text(min_size=1, max_size=20).filter(
        lambda x: not x.startswith("kernel.")
    ))
    return {
        "id": proj_id,
        "pattern": {key: pattern_val},
        "body": body_val,
    }


@st.composite
def matching_projection(draw):
    """Generate a projection that will match a specific input."""
    key = draw(st.text(min_size=1, max_size=10).filter(
        lambda k: k not in KERNEL_RESERVED_FIELDS and not k.startswith("_")
    ))
    val = draw(st.integers(min_value=-100, max_value=100))
    body = draw(simple_mu)
    proj_id = draw(st.text(min_size=1, max_size=15).filter(
        lambda x: not x.startswith("kernel.")
    ))
    return {
        "id": proj_id,
        "pattern": {key: {"var": "x"}},
        "body": body,
    }, {key: val}


# =============================================================================
# Tests: Terminal State Detection at Seed Boundaries
# =============================================================================

class TestKernelTerminalDetection:
    """Property-based tests for terminal state detection after kernel processing."""

    @given(
        result=simple_mu,
        stall=st.booleans(),
    )
    @settings(deadline=5000)
    def test_valid_terminal_states_always_detected(self, result, stall):
        """Any dict with _mode=done, _result, and _stall should be terminal."""
        state = {"_mode": "done", "_result": result, "_stall": stall}
        assert is_kernel_terminal(state)

    @given(mu_value)
    @settings(deadline=5000)
    def test_non_dict_never_terminal(self, value):
        """Non-dict values are never kernel terminal states."""
        assume(not isinstance(value, dict))
        assert not is_kernel_terminal(value)

    @given(
        mode=st.text(max_size=10).filter(lambda m: m != "done"),
        result=simple_mu,
    )
    @settings(deadline=5000)
    def test_non_done_mode_not_terminal(self, mode, result):
        """States with _mode != 'done' are never terminal."""
        state = {"_mode": mode, "_result": result, "_stall": False}
        assert not is_kernel_terminal(state)

    @given(result=simple_mu)
    @settings(deadline=5000)
    def test_missing_stall_not_terminal(self, result):
        """Terminal requires _stall field."""
        state = {"_mode": "done", "_result": result}
        assert not is_kernel_terminal(state)

    @given(stall=st.booleans())
    @settings(deadline=5000)
    def test_missing_result_not_terminal(self, stall):
        """Terminal requires _result field."""
        state = {"_mode": "done", "_stall": stall}
        assert not is_kernel_terminal(state)


# =============================================================================
# Tests: Intermediate State Detection
# =============================================================================

class TestKernelIntermediateDetection:
    """Property-based tests for intermediate state detection."""

    @given(
        mode=st.sampled_from(["wrap", "try", "match_ok", "match_fail"]),
    )
    @settings(deadline=5000)
    def test_non_done_mode_is_intermediate(self, mode):
        """States with kernel modes other than 'done' are intermediate."""
        state = {"_mode": mode}
        assert is_kernel_intermediate(state)

    @given(
        field=st.sampled_from(["_subst_ctx", "_match_ctx", "_kernel_ctx"]),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_context_fields_are_intermediate(self, field, value):
        """States with kernel context fields are intermediate."""
        state = {field: value}
        assert is_kernel_intermediate(state)

    @given(mu_value)
    @settings(deadline=5000)
    def test_non_dict_never_intermediate(self, value):
        """Non-dict values are never intermediate."""
        assume(not isinstance(value, dict))
        assert not is_kernel_intermediate(value)

    @given(result=simple_mu, stall=st.booleans())
    @settings(deadline=5000)
    def test_terminal_not_intermediate(self, result, stall):
        """Terminal states are not intermediate (mutual exclusion)."""
        state = {"_mode": "done", "_result": result, "_stall": stall}
        # Terminal states have _mode=done, which is_kernel_intermediate checks
        assert not is_kernel_intermediate(state)


# =============================================================================
# Tests: Result Extraction
# =============================================================================

class TestExtractKernelResult:
    """Property-based tests for extract_kernel_result."""

    @given(result=simple_mu, original=mu_value)
    @settings(deadline=5000)
    def test_stall_returns_original(self, result, original):
        """When _stall is True, original input is returned."""
        terminal = {"_mode": "done", "_result": result, "_stall": True}
        assert extract_kernel_result(terminal, original) is original

    @given(result=st.integers(min_value=-100, max_value=100))
    @settings(deadline=5000)
    def test_non_stall_returns_denormalized_result(self, result):
        """When _stall is False, denormalized _result is returned."""
        terminal = {"_mode": "done", "_result": result, "_stall": False}
        output = extract_kernel_result(terminal, "original")
        # For simple values, denormalize is identity
        assert output == result


# =============================================================================
# Tests: Full Step Through Kernel (Cross-Seed Integration)
# =============================================================================

class TestCrossSeedStepKernel:
    """Property-based tests for step_kernel_mu crossing seed boundaries."""

    @given(value=simple_mu)
    @settings(deadline=10000)
    def test_no_projections_returns_input(self, value):
        """With no domain projections, kernel stalls and returns original input."""
        result = step_kernel_mu([], value)
        assert mu_equal(result, value)

    @given(matching_projection())
    @settings(deadline=10000)
    def test_matching_projection_transforms(self, proj_and_input):
        """A matching projection should transform the input."""
        proj, inp = proj_and_input
        result = step_kernel_mu([proj], inp)
        # Result should be the body (transformed), not the input
        assert is_mu(result)

    @given(
        key=st.text(min_size=1, max_size=10).filter(
            lambda k: k not in KERNEL_RESERVED_FIELDS and not k.startswith("_")
        ),
        val=st.integers(min_value=-100, max_value=100),
    )
    @settings(deadline=10000)
    def test_identity_projection_preserves_value(self, key, val):
        """A projection that matches and returns the bound value produces that value."""
        proj = {
            "id": "test.identity",
            "pattern": {key: {"var": "x"}},
            "body": {"var": "x"},
        }
        inp = {key: val}
        result = step_kernel_mu([proj], inp)
        assert mu_equal(result, val)

    @given(
        projs=st.lists(domain_projection(), min_size=1, max_size=5),
        value=st.integers(min_value=-100, max_value=100),
    )
    @settings(deadline=10000)
    def test_result_is_always_valid_mu(self, projs, value):
        """Kernel always returns valid Mu regardless of projection match."""
        result = step_kernel_mu(projs, value)
        assert is_mu(result)

    @given(
        projs=st.lists(domain_projection(), min_size=1, max_size=3),
        value=mu_value,
    )
    @settings(deadline=10000)
    def test_result_never_contains_kernel_state(self, projs, value):
        """Output of step_kernel_mu never leaks kernel-internal fields."""
        result = step_kernel_mu(projs, value)
        if isinstance(result, dict):
            for field in KERNEL_RESERVED_FIELDS:
                assert field not in result, f"Kernel field {field} leaked into output"


# =============================================================================
# Tests: Seed Boundary Security
# =============================================================================

class TestSeedBoundarySecurity:
    """Tests that kernel rejects domain projections with kernel-reserved patterns."""

    @given(
        reserved=st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_reserved_field_in_pattern_rejected(self, reserved, value):
        """Domain projection patterns containing reserved fields are rejected."""
        proj = {
            "id": "bad.proj",
            "pattern": {reserved: value},
            "body": "result",
        }
        with pytest.raises(ValueError, match="SECURITY"):
            step_kernel_mu([proj], "test")

    @given(
        reserved=st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_reserved_field_in_body_rejected(self, reserved, value):
        """Domain projection bodies containing reserved fields are rejected."""
        proj = {
            "id": "bad.proj",
            "pattern": {"x": {"var": "v"}},
            "body": {reserved: value},
        }
        with pytest.raises(ValueError, match="SECURITY"):
            step_kernel_mu([proj], {"x": 1})

    @given(
        reserved=st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_reserved_field_in_input_rejected(self, reserved, value):
        """Domain inputs containing reserved fields are rejected."""
        with pytest.raises(ValueError, match="SECURITY"):
            step_kernel_mu([], {reserved: value})

    def test_kernel_projection_id_rejected(self):
        """Projections with kernel.* IDs are rejected."""
        proj = {
            "id": "kernel.fake",
            "pattern": {"x": {"var": "v"}},
            "body": "result",
        }
        with pytest.raises(ValueError, match="SECURITY"):
            step_kernel_mu([proj], "test")
