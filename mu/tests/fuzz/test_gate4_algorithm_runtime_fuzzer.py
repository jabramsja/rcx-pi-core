"""
Gate 4 Prep Fuzzer - Property-Based Tests for Algorithm-Runtime Validation

Tests the Gate 4 infrastructure: validate_algorithm_runtime_fields(),
ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS, kernel_mode dispatch,
and validation_mode dispatch on step_kernel_mu().

Mirrors test_security_boundary_fuzzer.py structure for the new
algorithm-runtime validation boundary.

Added 2026-02-07 after orchestrator review found zero fuzzer coverage
for Gate 4 prep code.
"""

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from rcx_pi.selfhost.step_mu import (
    ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS,
    ALGORITHM_ENTRYPOINT_KEYS,
    ALGORITHM_INTERNAL_UNRESERVED_FIELDS,
    KERNEL_RESERVED_FIELDS,
    run_algorithm_meta_circular,
    validate_algorithm_runtime_fields,
    validate_no_kernel_reserved_fields,
    step_kernel_mu,
)
from rcx_pi.selfhost.mu_type import is_mu
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed


# =============================================================================
# Strategies
# =============================================================================

# Allowed underscore fields for algorithm runtime
allowed_underscore = st.sampled_from(sorted(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS))

# Non-underscore safe keys
safe_keys = st.text(min_size=1, max_size=10).filter(lambda k: not k.startswith("_"))

# Simple Mu values (no underscore keys)
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
        st.dictionaries(safe_keys, children, max_size=3),
    ),
    max_leaves=10,
)


@st.composite
def unknown_underscore_key(draw):
    """Generate an underscore key NOT in the allowlist."""
    base = draw(st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz"))
    key = f"_{base}"
    assume(key not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)
    return key


@st.composite
def algorithm_state_with_allowed_fields(draw, num_fields=None):
    """Generate a dict using only allowed underscore fields."""
    if num_fields is None:
        num_fields = draw(st.integers(min_value=1, max_value=6))
    keys = draw(
        st.lists(
            allowed_underscore,
            min_size=num_fields,
            max_size=num_fields,
            unique=True,
        )
    )
    result = {}
    for key in keys:
        result[key] = draw(simple_mu)
    return result


@st.composite
def nested_with_unknown_underscore(draw, target_depth=3):
    """Generate a nested structure with an unknown underscore field at depth."""
    bad_key = draw(unknown_underscore_key())
    value = draw(simple_mu)
    payload = {bad_key: value}
    current = payload
    for _ in range(target_depth):
        wrapper_key = draw(safe_keys)
        current = {wrapper_key: current}
    return current, bad_key


@st.composite
def normalized_dict_with_unknown_underscore(draw):
    """Generate a normalized dict encoding containing an unknown underscore key."""
    bad_key = draw(unknown_underscore_key())
    value = draw(simple_mu)
    return {
        "_type": "dict",
        "head": {"head": bad_key, "tail": {"head": value, "tail": None}},
        "tail": None,
    }, bad_key


@st.composite
def normalized_dict_with_allowed_underscore(draw):
    """Generate a normalized dict encoding containing an allowed underscore key."""
    good_key = draw(allowed_underscore)
    value = draw(simple_mu)
    return {
        "_type": "dict",
        "head": {"head": good_key, "tail": {"head": value, "tail": None}},
        "tail": None,
    }, good_key


# Preloaded algorithm seeds for runtime-path fuzzing.
RECURRENCE_PROJECTIONS = load_verified_seed(get_seed_path("recurrence.v1.json"))["projections"]
EXHAUSTION_PROJECTIONS = load_verified_seed(get_seed_path("exhaustion.v1.json"))["projections"]


@st.composite
def algorithm_runtime_entrypoint_state(draw):
    """Generate trusted algorithm-runtime payloads for recurrence/exhaustion."""
    entrypoint = draw(st.sampled_from(sorted(ALGORITHM_ENTRYPOINT_KEYS)))
    underscore_keys = draw(
        st.lists(allowed_underscore, min_size=1, max_size=4, unique=True)
    )
    payload = {k: draw(simple_mu) for k in underscore_keys}

    # Add minimal algorithm-facing fields that commonly appear in real vectors.
    if entrypoint == "_detect_closure":
        payload.setdefault("trace", draw(simple_mu))
        payload.setdefault("result", draw(simple_mu))
    else:
        payload.setdefault("trace", draw(simple_mu))
        payload.setdefault("frozen", draw(simple_mu))
        payload.setdefault("tau_step", draw(st.integers(min_value=0, max_value=20)))

    return {entrypoint: payload}


# =============================================================================
# Allowlist Acceptance Tests
# =============================================================================

class TestAllowedFieldsAccepted:
    """Allowed underscore fields pass algorithm-runtime validation."""

    @given(key=allowed_underscore, value=simple_mu)
    @settings(deadline=5000)
    def test_single_allowed_field_accepted(self, key, value):
        """Any single allowed underscore field passes validation."""
        state = {key: value}
        validate_algorithm_runtime_fields(state, "test")

    @given(state=algorithm_state_with_allowed_fields())
    @settings(deadline=5000)
    def test_multi_allowed_fields_accepted(self, state):
        """Multiple allowed underscore fields pass validation."""
        validate_algorithm_runtime_fields(state, "test")

    @given(value=simple_mu)
    @settings(deadline=5000)
    def test_clean_values_accepted(self, value):
        """Values with no underscore keys pass validation."""
        assume(is_mu(value))
        validate_algorithm_runtime_fields(value, "test")

    @given(data=normalized_dict_with_allowed_underscore())
    @settings(deadline=5000)
    def test_normalized_dict_with_allowed_key_accepted(self, data):
        """Allowed underscore key in normalized dict encoding passes."""
        structure, _key = data
        validate_algorithm_runtime_fields(structure, "test")


# =============================================================================
# Unknown Field Rejection Tests
# =============================================================================

class TestUnknownFieldsRejected:
    """Unknown underscore fields are rejected (fail-closed)."""

    @given(bad_key=unknown_underscore_key(), value=simple_mu)
    @settings(deadline=5000)
    def test_unknown_underscore_top_level_rejected(self, bad_key, value):
        """Unknown underscore field at top level is rejected."""
        malicious = {bad_key: value}
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(malicious, "test")

    @given(data=nested_with_unknown_underscore(target_depth=1))
    @settings(deadline=5000)
    def test_unknown_underscore_depth_1_rejected(self, data):
        """Unknown underscore field at depth 1 is rejected."""
        malicious, _bad_key = data
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(malicious, "test")

    @given(data=nested_with_unknown_underscore(target_depth=5))
    @settings(deadline=5000)
    def test_unknown_underscore_depth_5_rejected(self, data):
        """Unknown underscore field at depth 5 is rejected."""
        malicious, _bad_key = data
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(malicious, "test")

    @given(data=normalized_dict_with_unknown_underscore())
    @settings(deadline=5000)
    def test_unknown_underscore_in_normalized_dict_rejected(self, data):
        """Unknown underscore field in normalized dict encoding is rejected."""
        malicious, _bad_key = data
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(malicious, "test")

    @given(
        bad_key=unknown_underscore_key(),
        good_key=allowed_underscore,
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_mixed_allowed_and_unknown_rejected(self, bad_key, good_key, value):
        """Dict with both allowed and unknown underscore fields is rejected."""
        assume(bad_key != good_key)
        malicious = {good_key: "ok", bad_key: value}
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(malicious, "test")


# =============================================================================
# Depth Guard Tests
# =============================================================================

class TestAlgorithmRuntimeDepthGuard:
    """Depth limit enforcement on algorithm-runtime validator."""

    def test_depth_101_fails_closed(self):
        """Depth 101 raises ValueError regardless of content."""
        current = {"safe": 42}
        for i in range(100):
            current = {f"level_{i}": current}
        with pytest.raises(ValueError, match="depth"):
            validate_algorithm_runtime_fields(current, "test")

    @given(st.integers(min_value=101, max_value=130))
    @settings(max_examples=10, deadline=30000)
    def test_excessive_depth_always_rejected(self, depth):
        """Any depth > 100 is rejected."""
        current = {"safe": 42}
        for i in range(depth - 1):
            current = {f"level_{i}": current}
        with pytest.raises(ValueError, match="depth"):
            validate_algorithm_runtime_fields(current, "test")

    def test_depth_100_clean_accepted(self):
        """Clean structure at exactly depth 100 is accepted."""
        current = {"safe": 42}
        for i in range(99):
            current = {f"level_{i}": current}
        validate_algorithm_runtime_fields(current, "test")


# =============================================================================
# List Traversal Tests
# =============================================================================

class TestAlgorithmRuntimeListTraversal:
    """Unknown underscore fields inside lists are caught."""

    @given(bad_key=unknown_underscore_key(), value=simple_mu)
    @settings(deadline=5000)
    def test_unknown_underscore_in_list_element_rejected(self, bad_key, value):
        """Unknown underscore field inside a list element is rejected."""
        malicious = [{"safe": 1}, {bad_key: value}]
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(malicious, "test")

    def test_nested_list_with_unknown_underscore(self):
        """Unknown underscore field in nested list structure is rejected."""
        malicious = [[[{"_evil_injected": "attack"}]]]
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(malicious, "test")


# =============================================================================
# Domain vs Algorithm-Runtime Mode Interaction
# =============================================================================

class TestModeInteraction:
    """Verify domain mode rejects what algorithm-runtime accepts, and vice versa."""

    @given(key=st.sampled_from(sorted(
        KERNEL_RESERVED_FIELDS & ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS
    )))
    @settings(deadline=5000)
    def test_kernel_reserved_allowed_in_runtime_rejected_in_domain(self, key):
        """Fields in both KERNEL_RESERVED and RUNTIME_ALLOWED:
        accepted by algorithm-runtime, rejected by domain."""
        value = {key: "test_value"}
        # Algorithm-runtime accepts
        validate_algorithm_runtime_fields(value, "test")
        # Domain rejects (unless inside algorithm entrypoint subtree)
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(value, "test")

    @given(bad_key=unknown_underscore_key())
    @settings(deadline=5000)
    def test_unknown_underscore_rejected_by_both_modes(self, bad_key):
        """Unknown underscore fields not in either allowlist rejected by algorithm-runtime."""
        value = {bad_key: "test"}
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(value, "test")


# =============================================================================
# Allowlist Composition Integrity
# =============================================================================

class TestAllowlistComposition:
    """Verify the allowlist is composed correctly from its parts."""

    def test_entrypoint_keys_are_subset(self):
        """ALGORITHM_ENTRYPOINT_KEYS are included in the allowlist."""
        assert ALGORITHM_ENTRYPOINT_KEYS.issubset(
            ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS
        )

    def test_internal_unreserved_are_subset(self):
        """ALGORITHM_INTERNAL_UNRESERVED_FIELDS are included in the allowlist."""
        assert ALGORITHM_INTERNAL_UNRESERVED_FIELDS.issubset(
            ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS
        )

    def test_all_allowed_fields_start_with_underscore(self):
        """Every field in the allowlist starts with underscore."""
        for field in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS:
            assert field.startswith("_"), f"Allowlist field {field!r} missing underscore prefix"

    def test_allowlist_is_frozen(self):
        """Allowlist is a frozenset (immutable)."""
        assert isinstance(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS, frozenset)

    def test_no_empty_field_names(self):
        """No empty or underscore-only field names in allowlist."""
        for field in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS:
            assert len(field) > 1, f"Allowlist contains bare underscore: {field!r}"


# =============================================================================
# step_kernel_mu Mode Dispatch Fuzzer
# =============================================================================

class TestStepKernelMuModeFuzzer:
    """Fuzz the kernel_mode and validation_mode dispatch on step_kernel_mu."""

    @given(mode=st.text(min_size=1, max_size=20).filter(
        lambda m: m not in ("core", "bridge")
    ))
    @settings(deadline=5000)
    def test_invalid_kernel_mode_always_rejected(self, mode):
        """Any kernel_mode other than core/bridge is rejected."""
        with pytest.raises(ValueError, match="invalid kernel_mode"):
            step_kernel_mu([], {"ok": True}, kernel_mode=mode)

    @given(mode=st.text(min_size=1, max_size=20).filter(
        lambda m: m not in ("domain", "algorithm_runtime")
    ))
    @settings(deadline=5000)
    def test_invalid_validation_mode_always_rejected(self, mode):
        """Any validation_mode other than domain/algorithm_runtime is rejected."""
        with pytest.raises(ValueError, match="invalid validation_mode"):
            step_kernel_mu([], {"ok": True}, validation_mode=mode)

    @given(
        km=st.sampled_from(["core", "bridge"]),
        vm=st.sampled_from(["domain", "algorithm_runtime"]),
        value=st.dictionaries(safe_keys, simple_mu, max_size=2),
    )
    @settings(deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_mode_combinations_dont_crash(self, km, vm, value):
        """All valid mode combinations run without crashing on clean input."""
        assume(is_mu(value))
        result = step_kernel_mu([], value, kernel_mode=km, validation_mode=vm)
        assert is_mu(result)

    @given(state=algorithm_state_with_allowed_fields())
    @settings(deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_algorithm_state_accepted_in_runtime_mode(self, state):
        """Algorithm state with allowed fields passes in algorithm_runtime mode."""
        result = step_kernel_mu(
            [], state, kernel_mode="core", validation_mode="algorithm_runtime"
        )
        assert is_mu(result)

    @given(
        key=st.sampled_from(sorted(
            KERNEL_RESERVED_FIELDS & ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS
        )),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_reserved_field_rejected_in_domain_mode_via_step_kernel(self, key, value):
        """Reserved fields rejected through step_kernel_mu in domain mode."""
        state = {key: value}
        with pytest.raises(ValueError, match="kernel-reserved field"):
            step_kernel_mu([], state, validation_mode="domain")


# =============================================================================
# Gate 4 Runtime Path Fuzzing
# =============================================================================

class TestRunAlgorithmMetaCircularFuzzer:
    """Fuzz run_algorithm_meta_circular trusted algorithm-runtime path."""

    @given(state=algorithm_runtime_entrypoint_state())
    @settings(deadline=5000, suppress_health_check=[HealthCheck.too_slow], max_examples=40)
    def test_accepts_allowed_runtime_payloads(self, state):
        # Choose projections that match the generated entrypoint.
        if "_detect_closure" in state:
            projections = RECURRENCE_PROJECTIONS
        else:
            projections = EXHAUSTION_PROJECTIONS

        result = run_algorithm_meta_circular(projections, state)
        assert is_mu(result)

    @given(bad_key=unknown_underscore_key(), value=simple_mu)
    @settings(deadline=5000, max_examples=30)
    def test_rejects_unknown_runtime_underscore_fields(self, bad_key, value):
        assume(bad_key not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)
        payload = {"_detect_closure": {bad_key: value}}
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            run_algorithm_meta_circular(RECURRENCE_PROJECTIONS, payload)


# =============================================================================
# Near-Miss Boundary Tests
# =============================================================================

class TestNearMissBoundary:
    """Test fields that are close to but not in the allowlist."""

    @given(
        field=allowed_underscore,
        suffix=st.text(min_size=1, max_size=5, alphabet="abcdefghijklmnopqrstuvwxyz"),
    )
    @settings(deadline=5000)
    def test_allowed_field_with_suffix_rejected(self, field, suffix):
        """An allowed field with extra suffix is unknown and rejected."""
        near_miss = field + suffix
        assume(near_miss not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)
        value = {near_miss: "test"}
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(value, "test")

    @given(
        field=allowed_underscore,
    )
    @settings(deadline=5000)
    def test_allowed_field_uppercased_rejected(self, field):
        """Uppercase version of allowed field is rejected (case-sensitive)."""
        upper = field.upper()
        assume(upper not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)
        assume(upper.startswith("_"))
        value = {upper: "test"}
        with pytest.raises(ValueError, match="unsupported algorithm underscore field"):
            validate_algorithm_runtime_fields(value, "test")
