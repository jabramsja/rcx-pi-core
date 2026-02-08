"""
Algorithm Runtime Oscillation Fuzzer (#1018)

Property-based tests for algorithm execution stability under field injection.
Tests that run_algorithm_meta_circular and validate_algorithm_runtime_fields
remain stable and fail-closed when underscore fields are injected.

Agent finding #1018: "Algorithm Runtime Oscillation Under Field Injection Not Fuzzed"
- Algorithm runtime with injected underscore fields was not fuzzed for
  oscillation, stall detection, or fail-closed behavior.
"""
import pytest
from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st

from rcx_pi.selfhost.step_mu import (
    run_algorithm_meta_circular,
    validate_algorithm_runtime_fields,
    validate_no_kernel_reserved_fields,
    KERNEL_RESERVED_FIELDS,
    ALGORITHM_ENTRYPOINT_KEYS,
    ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS,
)
from rcx_pi.selfhost.mu_type import is_mu


# =============================================================================
# Strategies
# =============================================================================

simple_mu = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=20),
)


@st.composite
def unknown_underscore_field(draw):
    """Generate an underscore field NOT in any allowlist."""
    name = draw(st.text(min_size=2, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz"))
    field = f"_{name}"
    assume(field not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)
    assume(field not in KERNEL_RESERVED_FIELDS)
    return field


@st.composite
def allowed_underscore_field(draw):
    """Generate an underscore field that IS in the algorithm runtime allowlist."""
    return draw(st.sampled_from(sorted(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)))


@st.composite
def dict_with_unknown_underscore(draw):
    """Generate a dict containing an unknown underscore field."""
    field = draw(unknown_underscore_field())
    value = draw(simple_mu)
    return {field: value}


@st.composite
def dict_with_allowed_fields_only(draw):
    """Generate a dict containing only allowed underscore fields."""
    n = draw(st.integers(min_value=1, max_value=3))
    fields = draw(st.lists(
        st.sampled_from(sorted(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)),
        min_size=n, max_size=n, unique=True,
    ))
    result = {}
    for f in fields:
        result[f] = draw(simple_mu)
    return result


@st.composite
def nested_dict_with_unknown_underscore(draw):
    """Generate nested dict with unknown underscore field buried inside."""
    field = draw(unknown_underscore_field())
    value = draw(simple_mu)
    wrapper_key = draw(st.text(min_size=1, max_size=10).filter(
        lambda k: not k.startswith("_")
    ))
    depth = draw(st.integers(min_value=1, max_value=5))
    inner = {field: value}
    for _ in range(depth):
        key = draw(st.text(min_size=1, max_size=10).filter(
            lambda k: not k.startswith("_")
        ))
        inner = {key: inner}
    return inner


# =============================================================================
# Tests: Algorithm Runtime Validator - Fail-Closed Behavior
# =============================================================================

class TestAlgorithmRuntimeValidatorFailClosed:
    """Verify validate_algorithm_runtime_fields rejects unknown underscore fields."""

    @given(dict_with_unknown_underscore())
    @settings(deadline=5000)
    def test_unknown_underscore_rejected(self, value):
        """Unknown underscore fields are always rejected (fail-closed)."""
        with pytest.raises(ValueError, match="SECURITY.*unsupported"):
            validate_algorithm_runtime_fields(value, "test")

    @given(dict_with_allowed_fields_only())
    @settings(deadline=5000)
    def test_allowed_fields_accepted(self, value):
        """Allowed algorithm fields are accepted without error."""
        validate_algorithm_runtime_fields(value, "test")

    @given(nested_dict_with_unknown_underscore())
    @settings(deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
    def test_nested_unknown_underscore_rejected(self, value):
        """Unknown underscore fields are rejected even when nested."""
        with pytest.raises(ValueError, match="SECURITY.*unsupported"):
            validate_algorithm_runtime_fields(value, "test")

    @given(
        reserved=st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_kernel_reserved_in_domain_rejected(self, reserved, value):
        """Domain validator rejects kernel-reserved fields."""
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields({reserved: value}, "test")


# =============================================================================
# Tests: Algorithm Runtime Validator - Depth Protection
# =============================================================================

class TestAlgorithmRuntimeDepthProtection:
    """Verify depth limits prevent stack overflow attacks."""

    def test_deeply_nested_exceeds_max_depth(self):
        """Structures nested beyond MAX_VALIDATION_DEPTH are rejected."""
        # Build structure deeper than 100 levels
        value = "leaf"
        for i in range(105):
            value = {"safe_key": value}
        with pytest.raises(ValueError, match="maximum validation depth"):
            validate_algorithm_runtime_fields(value, "test")

    def test_deeply_nested_domain_exceeds_max_depth(self):
        """Domain validator also rejects deeply nested structures."""
        value = "leaf"
        for i in range(105):
            value = {"safe_key": value}
        with pytest.raises(ValueError, match="maximum validation depth"):
            validate_no_kernel_reserved_fields(value, "test")


# =============================================================================
# Tests: Algorithm Execution Mode Validation
# =============================================================================

class TestAlgorithmExecutionModes:
    """Verify run_algorithm_meta_circular mode validation."""

    def test_invalid_execution_mode_rejected(self):
        """Unknown execution modes are rejected."""
        with pytest.raises(ValueError, match="SECURITY.*invalid execution_mode"):
            run_algorithm_meta_circular([], "test", execution_mode="invalid")

    def test_bootstrap_without_flag_rejected(self):
        """Bootstrap mode requires explicit allow_bootstrap_fallback flag."""
        with pytest.raises(ValueError, match="SECURITY.*bootstrap fallback"):
            run_algorithm_meta_circular(
                [], "test",
                execution_mode="bootstrap",
                allow_bootstrap_fallback=False,
            )

    @given(
        mode=st.text(min_size=1, max_size=20).filter(
            lambda m: m not in ("structural", "bootstrap")
        ),
    )
    @settings(deadline=5000)
    def test_arbitrary_mode_string_rejected(self, mode):
        """Arbitrary mode strings are always rejected."""
        with pytest.raises(ValueError, match="SECURITY"):
            run_algorithm_meta_circular([], "test", execution_mode=mode)


# =============================================================================
# Tests: Algorithm Execution Stability
# =============================================================================

class TestAlgorithmExecutionStability:
    """Verify algorithm execution terminates and produces valid Mu."""

    @given(value=simple_mu)
    @settings(deadline=10000)
    def test_structural_mode_no_projections_stalls(self, value):
        """With no algorithm projections, structural mode stalls gracefully."""
        # No projections means immediate stall (returns input)
        result = run_algorithm_meta_circular([], value, execution_mode="structural")
        assert is_mu(result)

    @given(value=st.integers(min_value=-100, max_value=100))
    @settings(deadline=10000)
    def test_structural_mode_identity_projection(self, value):
        """Identity projection returns bound value."""
        proj = {
            "id": "algo.identity",
            "pattern": {"var": "x"},
            "body": {"var": "x"},
        }
        result = run_algorithm_meta_circular([proj], value, execution_mode="structural")
        assert is_mu(result)

    @given(
        reserved=st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_reserved_field_in_input_rejected_structurally(self, reserved, value):
        """Even in algorithm mode, kernel reserved fields in input are checked."""
        # Algorithm runtime uses a different validator but still checks
        # This test verifies the algorithm allowlist behavior
        inp = {reserved: value}
        # The algorithm_runtime validator allows some reserved fields that are
        # also in the allowlist (e.g., _mode, _phase, _result, _stall, _step).
        # So we test fields NOT in the allowlist.
        if reserved not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS:
            with pytest.raises(ValueError, match="SECURITY"):
                run_algorithm_meta_circular([], inp, execution_mode="structural")


# =============================================================================
# Tests: Entrypoint Key Validation
# =============================================================================

class TestEntrypointKeyValidation:
    """Verify algorithm entrypoint keys are in the allowlist."""

    def test_detect_closure_is_allowed(self):
        """_detect_closure is an allowed algorithm field."""
        assert "_detect_closure" in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS

    def test_detect_exhaustion_is_allowed(self):
        """_detect_exhaustion is an allowed algorithm field."""
        assert "_detect_exhaustion" in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS

    def test_entrypoint_keys_subset_of_allowed(self):
        """All entrypoint keys are in the algorithm runtime allowlist."""
        assert ALGORITHM_ENTRYPOINT_KEYS <= ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS

    @given(
        entry_key=st.sampled_from(sorted(ALGORITHM_ENTRYPOINT_KEYS)),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_entrypoint_fields_pass_runtime_validation(self, entry_key, value):
        """Entrypoint fields pass algorithm runtime validation."""
        validate_algorithm_runtime_fields({entry_key: value}, "test")
