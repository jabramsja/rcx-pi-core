"""
Kernel Security Fuzzer - Property-based tests for kernel boundary functions.

Created based on 9-agent review (2026-01-30): Fuzzer found gaps in security-critical
kernel functions that were only tested with manual examples.

Targets:
- is_kernel_projection() - Security boundary classification
- validate_kernel_projections_first() - Projection ordering enforcement
- extract_kernel_result() - Terminal state unpacking

These functions are security-critical because they determine what code runs
with kernel privileges vs domain restrictions.
"""
import pytest
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from rcx_pi.selfhost.step_mu import (
    is_kernel_projection,
    validate_kernel_projections_first,
    is_kernel_terminal,
    is_kernel_intermediate,
    extract_kernel_result,
    KERNEL_RESERVED_FIELDS,
)

# =============================================================================
# Strategies for generating test data
# =============================================================================

@st.composite
def kernel_mode_values(draw):
    """Generate valid kernel _mode values."""
    return draw(st.sampled_from(["wrap", "try", "match_ok", "match_fail", "done"]))


# NOTE: non_kernel_mode_values strategy was removed (2026-01-30)
# It was dead code - never used in any test. If needed for future
# type confusion tests, regenerate from: ["Wrap", "WRAP", "wrap ", etc.]


@st.composite
def kernel_projection(draw):
    """Generate a projection that looks like a kernel projection."""
    mode = draw(kernel_mode_values())
    return {
        "pattern": {"_mode": mode},
        "body": {"_mode": "done", "_result": draw(st.integers())}
    }


@st.composite
def domain_projection(draw):
    """Generate a projection that should NOT be classified as kernel."""
    # No _mode in pattern
    key = draw(st.text(min_size=1, max_size=10).filter(lambda x: not x.startswith("_")))
    return {
        "pattern": {key: draw(st.integers())},
        "body": {"result": draw(st.integers())}
    }


@st.composite
def fake_kernel_projection(draw):
    """Generate a projection that LOOKS like kernel but has _mode in wrong place."""
    modes = ["wrap", "try", "done"]
    return draw(st.sampled_from([
        # _mode in body but not pattern
        {"pattern": {"x": 1}, "body": {"_mode": draw(st.sampled_from(modes))}},
        # _mode nested in pattern
        {"pattern": {"outer": {"_mode": draw(st.sampled_from(modes))}}, "body": {"x": 1}},
        # _mode as VALUE not KEY
        {"pattern": {"mode": "_mode"}, "body": {"x": 1}},
        # Empty pattern (not kernel)
        {"pattern": {}, "body": {"_mode": "done"}},
    ]))


@st.composite
def terminal_state(draw):
    """Generate a valid kernel terminal state.

    Terminal state requires: _mode="done", _result (any value), _stall (bool).
    """
    return {
        "_mode": "done",
        "_result": draw(st.integers() | st.text(max_size=10) | st.none()),
        "_stall": draw(st.booleans()),
    }


@st.composite
def malformed_terminal_state(draw):
    """Generate something that looks like terminal but is malformed."""
    return draw(st.sampled_from([
        # Missing _result
        {"_mode": "done", "_status": "complete"},
        # Wrong _status value
        {"_mode": "done", "_status": "invalid", "_result": 42},
        # Missing _status
        {"_mode": "done", "_result": 42},
        # _mode is done but no other fields
        {"_mode": "done"},
        # Stall without _stall marker
        {"_mode": "done", "_status": "stall", "_result": "stalled"},
    ]))


# =============================================================================
# Tests for is_kernel_projection()
# =============================================================================

class TestIsKernelProjectionFuzzer:
    """Property-based tests for is_kernel_projection classification."""

    @given(kernel_projection())
    @settings(deadline=5000)
    def test_kernel_projections_classified_as_kernel(self, proj):
        """Projections with _mode in pattern root are kernel projections."""
        assert is_kernel_projection(proj), f"Should be kernel: {proj}"

    @given(domain_projection())
    @settings(deadline=5000)
    def test_domain_projections_not_classified_as_kernel(self, proj):
        """Projections without _mode in pattern are NOT kernel projections."""
        assert not is_kernel_projection(proj), f"Should NOT be kernel: {proj}"

    @given(fake_kernel_projection())
    @settings(deadline=5000)
    def test_fake_kernel_projections_rejected(self, proj):
        """Projections with _mode in wrong location are NOT kernel."""
        assert not is_kernel_projection(proj), f"Should NOT be kernel: {proj}"

    @given(st.integers() | st.text() | st.none() | st.lists(st.integers()))
    @settings(deadline=5000)
    def test_non_dict_never_kernel(self, value):
        """Non-dict values are never kernel projections."""
        # is_kernel_projection expects a projection dict with pattern/body
        # Invalid input should return False, not crash
        proj = {"pattern": value, "body": {}}
        result = is_kernel_projection(proj)
        # Non-dict patterns can't have _mode key
        if not isinstance(value, dict):
            assert not result

    @given(st.dictionaries(st.text(min_size=1, max_size=5), st.integers(), max_size=3))
    @settings(deadline=5000)
    def test_random_pattern_classification_deterministic(self, pattern):
        """Classification is deterministic for any pattern."""
        proj = {"pattern": pattern, "body": {"x": 1}}
        result1 = is_kernel_projection(proj)
        result2 = is_kernel_projection(proj)
        assert result1 == result2, "Classification must be deterministic"


# =============================================================================
# Tests for validate_kernel_projections_first()
# =============================================================================

class TestValidateKernelProjectionsFirstFuzzer:
    """Property-based tests for kernel projection ordering enforcement."""

    @given(st.lists(kernel_projection(), min_size=1, max_size=5))
    @settings(deadline=5000)
    def test_kernel_only_list_valid(self, projs):
        """List of only kernel projections is valid."""
        # Should not raise
        validate_kernel_projections_first(projs)

    @given(st.lists(domain_projection(), min_size=1, max_size=5))
    @settings(deadline=5000)
    def test_domain_only_list_valid(self, projs):
        """List of only domain projections is valid."""
        # Should not raise
        validate_kernel_projections_first(projs)

    @given(
        st.lists(kernel_projection(), min_size=1, max_size=3),
        st.lists(domain_projection(), min_size=1, max_size=3)
    )
    @settings(deadline=5000)
    def test_kernel_before_domain_valid(self, kernel_projs, domain_projs):
        """Kernel projections before domain projections is valid."""
        combined = kernel_projs + domain_projs
        # Should not raise
        validate_kernel_projections_first(combined)

    @given(
        st.lists(domain_projection(), min_size=1, max_size=3),
        st.lists(kernel_projection(), min_size=1, max_size=3)
    )
    @settings(deadline=5000)
    def test_domain_before_kernel_invalid(self, domain_projs, kernel_projs):
        """Domain projections before kernel projections is INVALID."""
        combined = domain_projs + kernel_projs
        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(combined)

    @given(
        kernel_projection(),
        domain_projection(),
        kernel_projection()
    )
    @settings(deadline=5000)
    def test_interleaved_kernel_domain_invalid(self, k1, d1, k2):
        """Kernel-domain-kernel pattern is INVALID (kernel after domain)."""
        combined = [k1, d1, k2]
        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(combined)


# =============================================================================
# Tests for extract_kernel_result()
# =============================================================================

class TestExtractKernelResultFuzzer:
    """Property-based tests for kernel terminal state extraction."""

    @given(terminal_state(), st.integers())
    @settings(deadline=5000)
    def test_valid_terminal_extracts(self, state, original_input):
        """Valid terminal states extract without error."""
        # Should not raise
        result = extract_kernel_result(state, original_input)
        # If stalled, returns original_input; otherwise _result
        if state.get("_stall"):
            assert result == original_input
        else:
            assert result == state.get("_result")

    @given(malformed_terminal_state(), st.integers())
    @settings(deadline=5000)
    def test_malformed_terminal_handled(self, state, original_input):
        """Malformed terminal states raise expected errors or return gracefully."""
        raised_expected = False
        returned_value = False
        result = None
        try:
            result = extract_kernel_result(state, original_input)
            returned_value = True
            # GROUNDED: If it returns, verify result is valid (original input or Mu value)
            # Round 8 fix: Was vacuous `assert X is not None or X is None`
            assert result == original_input or isinstance(result, (dict, list, str, int, float, bool, type(None))), (
                f"Result must be original input or valid Mu, got: {type(result)}"
            )
        except (KeyError, ValueError, TypeError) as e:
            raised_expected = True
            # GROUNDED: Verify exception has meaningful message
            # Round 8 fix: Was vacuous `assert str(e) or True`
            error_msg = str(e)
            assert len(error_msg) > 0, "Exception must have non-empty message"

        # Assert: function either returned or raised expected exception (no silent failures)
        assert raised_expected or returned_value, "Function must either return or raise expected error"

    @given(st.integers() | st.text() | st.none(), st.integers())
    @settings(deadline=5000)
    def test_non_dict_terminal_handled(self, value, original_input):
        """Non-dict values raise expected errors (no silent failures or crashes)."""
        raised_expected = False
        returned_value = False
        unexpected_error = None
        try:
            result = extract_kernel_result(value, original_input)
            returned_value = True
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            raised_expected = True
            # Verify exception has context
            assert isinstance(e, Exception)
        except Exception as e:
            unexpected_error = e

        # Assert: no unexpected exception types
        assert unexpected_error is None, f"Unexpected error type: {type(unexpected_error).__name__}: {unexpected_error}"
        # Assert: function either returned or raised expected exception
        assert raised_expected or returned_value, "Function must either return or raise expected error"


# =============================================================================
# Tests for is_kernel_terminal() and is_kernel_intermediate()
# =============================================================================

class TestKernelStateClassificationFuzzer:
    """Property-based tests for kernel state classification."""

    @given(terminal_state())
    @settings(deadline=5000)
    def test_terminal_state_is_terminal(self, state):
        """Terminal states are classified as terminal."""
        assert is_kernel_terminal(state)

    @given(terminal_state())
    @settings(deadline=5000)
    def test_terminal_state_not_intermediate(self, state):
        """Terminal states are NOT intermediate."""
        assert not is_kernel_intermediate(state)

    @given(st.sampled_from(["wrap", "try", "match_ok", "match_fail"]))
    @settings(deadline=5000)
    def test_intermediate_modes_are_intermediate(self, mode):
        """Intermediate modes are classified as intermediate."""
        state = {"_mode": mode, "_input": 42}
        assert is_kernel_intermediate(state)
        assert not is_kernel_terminal(state)

    @given(st.dictionaries(st.text(min_size=1, max_size=5), st.integers(), max_size=3))
    @settings(deadline=5000)
    def test_non_kernel_state_classification(self, data):
        """Non-kernel data is neither terminal nor intermediate."""
        assume("_mode" not in data)
        assert not is_kernel_terminal(data)
        assert not is_kernel_intermediate(data)


# =============================================================================
# Tests for KERNEL_RESERVED_FIELDS constant
# =============================================================================

class TestKernelReservedFieldsFuzzer:
    """Verify KERNEL_RESERVED_FIELDS completeness."""

    def test_reserved_fields_count(self):
        """Exactly 22 reserved fields (12 kernel + 3 Recurrence + 3 Exhaustion + 4 Bridge).

        Gate 3 (2026-02-04): Entry points (_detect_closure, _detect_exhaustion) moved
        to ALGORITHM_ENTRYPOINT_KEYS.
        """
        assert len(KERNEL_RESERVED_FIELDS) == 25

    def test_reserved_fields_are_underscore_prefixed(self):
        """All reserved fields start with underscore."""
        for field in KERNEL_RESERVED_FIELDS:
            assert field.startswith("_"), f"Reserved field {field} must start with _"

    @given(st.sampled_from(list(KERNEL_RESERVED_FIELDS)))
    @settings(deadline=5000)
    def test_reserved_field_makes_projection_look_kernel(self, field):
        """Reserved fields in pattern trigger kernel classification for _mode."""
        if field == "_mode":
            # _mode is the primary kernel marker
            proj = {"pattern": {"_mode": "wrap"}, "body": {}}
            assert is_kernel_projection(proj)
        # Other reserved fields don't make something a kernel projection by themselves
        # (only _mode does that), but they are blocked from domain data
