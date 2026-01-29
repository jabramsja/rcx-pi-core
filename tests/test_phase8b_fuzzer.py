"""
Phase 8b Property-Based Fuzzing - Mechanical Kernel Simplification

This test suite validates Phase 8b changes with 1000+ random inputs:
1. Normalization roundtrip (all Mu types)
2. Normalization idempotency (typed sentinels)
3. Type preservation (empty containers under stress)
4. Kernel terminal detection (malicious state injection)

Run with: pytest tests/test_phase8b_fuzzer.py --hypothesis-show-statistics -v

Phase 8b Changes:
- Empty containers now use typed sentinels: [] -> {"_type": "list"}
- Kernel terminal detection: is_kernel_terminal(), extract_kernel_result()
- Simplified loop: no semantic decisions inside for-loop

See docs/core/BootstrapPrimitives.v0.md for Phase 8 design.

This file was created based on fuzzer agent recommendations during 9-agent review.
"""

import pytest

# Skip all tests if hypothesis is not installed
hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.mu_type import is_mu, mu_equal
from rcx_pi.selfhost.match_mu import (
    normalize_for_match,
    denormalize_from_match,
    validate_type_tag,
    VALID_TYPE_TAGS,
)
from rcx_pi.selfhost.step_mu import (
    is_kernel_terminal,
    extract_kernel_result,
    step_mu,
)


# =============================================================================
# Hypothesis Strategies for Phase 8b
# =============================================================================

mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31),
    st.floats(
        allow_nan=False,
        allow_infinity=False,
        min_value=-1e10,
        max_value=1e10
    ),
    st.text(max_size=50),
)


# Dict keys that don't start with underscore (underscore-prefixed are kernel-reserved)
# See step_mu.py KERNEL_RESERVED_FIELDS for the security rationale.
domain_safe_keys = st.text(min_size=1, max_size=10).filter(lambda k: not k.startswith("_"))


@composite
def mu_values(draw, max_depth=3):
    """Generate valid Mu values recursively.

    Note: max_depth=3 prevents pathological nesting after normalization
    (each dict level can triple during normalization to linked-list form).
    Keys filtered to exclude underscore-prefixed (kernel-reserved) fields.
    """
    if max_depth <= 0:
        return draw(mu_primitives)

    return draw(st.one_of(
        mu_primitives,
        st.lists(
            st.deferred(lambda: mu_values(max_depth=max_depth-1)),
            max_size=5
        ),
        st.dictionaries(
            domain_safe_keys,
            st.deferred(lambda: mu_values(max_depth=max_depth-1)),
            max_size=5
        ),
    ))


@composite
def empty_containers(draw):
    """Generate empty containers and nested empty structures."""
    empty_type = draw(st.sampled_from(["list", "dict"]))
    nesting_depth = draw(st.integers(min_value=0, max_value=3))

    if empty_type == "list":
        result = []
        for _ in range(nesting_depth):
            result = [result]
    else:
        result = {}
        for _ in range(nesting_depth):
            result = {"nested": result}

    return result


@composite
def typed_sentinel_values(draw):
    """Generate already-normalized typed sentinel values."""
    _type = draw(st.sampled_from(list(VALID_TYPE_TAGS)))
    return {"_type": _type}


@composite
def malicious_type_tags(draw):
    """Generate invalid type tag values for security testing."""
    malicious = draw(st.one_of(
        st.text(min_size=1, max_size=20),  # Random strings
    ))
    # Ensure it's NOT a valid type tag
    assume(malicious not in VALID_TYPE_TAGS)
    return malicious


@composite
def kernel_state_forgery_attempts(draw):
    """Generate structures that try to forge kernel terminal state."""
    mode = draw(st.sampled_from(["done", "kernel", "match", "subst", "other"]))
    result = draw(mu_primitives)
    stall = draw(st.booleans())

    # Generate complete or incomplete terminal states
    complete = draw(st.booleans())
    if complete:
        return {"_mode": mode, "_result": result, "_stall": stall}
    else:
        # Missing one or more required fields
        fields = {}
        if draw(st.booleans()):
            fields["_mode"] = mode
        if draw(st.booleans()):
            fields["_result"] = result
        if draw(st.booleans()):
            fields["_stall"] = stall
        return fields


# =============================================================================
# Property 1: Normalization Roundtrip (COMPREHENSIVE)
# =============================================================================

class TestNormalizationRoundtripFuzzer:
    """
    Test normalize -> denormalize roundtrip for ALL Mu types.

    Property: denormalize(normalize(x)) == x for all valid Mu

    Phase 8b fix: Empty containers must roundtrip correctly:
    - [] -> {"_type": "list"} -> []
    - {} -> {"_type": "dict"} -> {}
    """

    @given(mu_values(max_depth=3))
    @settings(max_examples=1000, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_roundtrip_all_mu_types(self, value):
        """Normalization roundtrip preserves ALL Mu values."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(denormalized, value), (
            f"Roundtrip failed:\n"
            f"  Original: {value}\n"
            f"  Normalized: {normalized}\n"
            f"  Denormalized: {denormalized}"
        )

    @given(empty_containers())
    @settings(max_examples=500, deadline=5000)
    def test_roundtrip_empty_containers(self, empty):
        """Empty and nested-empty containers roundtrip correctly."""
        assume(is_mu(empty))

        normalized = normalize_for_match(empty)
        denormalized = denormalize_from_match(normalized)

        # Type must be preserved
        assert type(denormalized) == type(empty), (
            f"Type lost in roundtrip:\n"
            f"  Original type: {type(empty)}\n"
            f"  Result type: {type(denormalized)}\n"
            f"  Normalized: {normalized}"
        )

        assert mu_equal(denormalized, empty), (
            f"Empty container roundtrip failed:\n"
            f"  Original: {empty}\n"
            f"  Normalized: {normalized}\n"
            f"  Denormalized: {denormalized}"
        )

    @given(mu_primitives)
    @settings(max_examples=500, deadline=5000)
    def test_roundtrip_primitives_unchanged(self, primitive):
        """Primitives pass through normalization unchanged."""
        assume(is_mu(primitive))

        normalized = normalize_for_match(primitive)
        denormalized = denormalize_from_match(normalized)

        # Primitives should be identity operations
        assert normalized == primitive, "Primitive changed during normalization"
        assert denormalized == primitive, "Primitive changed during denormalization"


# =============================================================================
# Property 2: Normalization Idempotency
# =============================================================================

class TestNormalizationIdempotencyFuzzer:
    """
    Test normalize(normalize(x)) == normalize(x).

    Property: Normalization is idempotent (applying twice doesn't change result)

    Phase 8b critical: Typed sentinels {"_type": "list"} must NOT be re-normalized.
    Lines 189-195 in match_mu.py handle this case.
    """

    @given(mu_values(max_depth=3))
    @settings(max_examples=1000, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_normalize_idempotent_all_types(self, value):
        """normalize(normalize(x)) == normalize(x) for all Mu."""
        assume(is_mu(value))

        normalized_once = normalize_for_match(value)
        normalized_twice = normalize_for_match(normalized_once)

        assert mu_equal(normalized_once, normalized_twice), (
            f"Normalization not idempotent:\n"
            f"  Original: {value}\n"
            f"  Once: {normalized_once}\n"
            f"  Twice: {normalized_twice}"
        )

    @given(typed_sentinel_values())
    @settings(max_examples=200, deadline=5000)
    def test_typed_sentinels_not_renormalized(self, sentinel):
        """Typed sentinels {"_type": "list"} stay unchanged under normalization."""
        assume(is_mu(sentinel))

        normalized = normalize_for_match(sentinel)

        # Should be identity - typed sentinels are already normalized
        assert normalized == sentinel, (
            f"Typed sentinel changed under normalization:\n"
            f"  Original: {sentinel}\n"
            f"  Normalized: {normalized}"
        )

    @given(empty_containers())
    @settings(max_examples=500, deadline=5000)
    def test_empty_container_idempotent(self, empty):
        """Empty containers become typed sentinels, which are then stable."""
        assume(is_mu(empty))

        normalized_once = normalize_for_match(empty)
        normalized_twice = normalize_for_match(normalized_once)

        assert mu_equal(normalized_once, normalized_twice), (
            f"Empty container normalization not idempotent:\n"
            f"  Original: {empty}\n"
            f"  Once: {normalized_once}\n"
            f"  Twice: {normalized_twice}"
        )


# =============================================================================
# Property 3: Type Preservation Under Stress
# =============================================================================

class TestTypePreservationFuzzer:
    """
    Test type(denormalize(normalize(container))) preserves Python type.

    Phase 8b fix: Empty containers use typed sentinels to preserve type info:
    - [] -> {"_type": "list"} -> []  (type preserved)
    - {} -> {"_type": "dict"} -> {}  (type preserved)
    """

    @given(st.lists(mu_primitives, max_size=0))
    @settings(max_examples=500, deadline=5000)
    def test_empty_list_type_preserved(self, empty_list):
        """Empty list [] preserves list type through roundtrip."""
        assert empty_list == []

        normalized = normalize_for_match(empty_list)
        denormalized = denormalize_from_match(normalized)

        assert isinstance(denormalized, list), (
            f"Empty list lost type:\n"
            f"  Normalized: {normalized}\n"
            f"  Denormalized type: {type(denormalized)}"
        )
        assert denormalized == [], f"Empty list became {denormalized}"

    @given(st.dictionaries(st.text(), st.none(), max_size=0))
    @settings(max_examples=500, deadline=5000)
    def test_empty_dict_type_preserved(self, empty_dict):
        """Empty dict {} preserves dict type through roundtrip."""
        assert empty_dict == {}

        normalized = normalize_for_match(empty_dict)
        denormalized = denormalize_from_match(normalized)

        assert isinstance(denormalized, dict), (
            f"Empty dict lost type:\n"
            f"  Normalized: {normalized}\n"
            f"  Denormalized type: {type(denormalized)}"
        )
        assert denormalized == {}, f"Empty dict became {denormalized}"


# =============================================================================
# Property 4: Typed Sentinel Safety (SECURITY)
# =============================================================================

class TestTypedSentinelSafetyFuzzer:
    """
    Test that invalid type tags are rejected.

    Security property: Only whitelisted type tags ("list", "dict") allowed.
    """

    @given(malicious_type_tags())
    @settings(max_examples=500, deadline=5000)
    def test_invalid_type_tags_rejected(self, malicious_tag):
        """validate_type_tag rejects non-whitelisted tags."""
        assume(malicious_tag not in VALID_TYPE_TAGS)

        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag(malicious_tag, "fuzzer_test")

    @given(st.sampled_from(list(VALID_TYPE_TAGS)))
    @settings(max_examples=50, deadline=5000)
    def test_valid_type_tags_accepted(self, valid_tag):
        """validate_type_tag accepts whitelisted tags."""
        # Should not raise
        validate_type_tag(valid_tag, "fuzzer_test")

    @given(malicious_type_tags(), mu_values())
    @settings(max_examples=300, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_malicious_typed_sentinel_rejected_in_denormalize(self, malicious_tag, value):
        """Denormalize rejects structures with invalid _type tags."""
        assume(is_mu(value))
        assume(isinstance(malicious_tag, str))  # Only string tags are checked
        assume(malicious_tag not in VALID_TYPE_TAGS)

        # Forge malicious typed structure
        malicious_structure = {
            "_type": malicious_tag,
            "head": value,
            "tail": None
        }

        # Should raise ValueError during denormalization
        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious_structure)


# =============================================================================
# Property 5: Kernel Terminal Detection
# =============================================================================

class TestKernelTerminalDetectionFuzzer:
    """
    Test is_kernel_terminal() consistency under attack.

    Property: Terminal detection is consistent for all inputs (no forgery).
    """

    @given(kernel_state_forgery_attempts())
    @settings(max_examples=1000, deadline=5000)
    def test_is_kernel_terminal_consistent(self, state):
        """is_kernel_terminal behaves consistently on all inputs."""
        # Should not crash
        result = is_kernel_terminal(state)

        # Must return boolean
        assert isinstance(result, bool), f"is_kernel_terminal returned non-bool: {type(result)}"

        # Run twice - must be deterministic
        result2 = is_kernel_terminal(state)
        assert result == result2, "is_kernel_terminal not deterministic"

    @given(kernel_state_forgery_attempts())
    @settings(max_examples=1000, deadline=5000)
    def test_only_valid_terminal_states_detected(self, state):
        """Only states with EXACT structure {"_mode": "done", "_result": X, "_stall": Y} are terminal."""
        is_terminal = is_kernel_terminal(state)

        # Check the logic
        has_mode_done = isinstance(state, dict) and state.get("_mode") == "done"
        has_result = isinstance(state, dict) and "_result" in state
        has_stall = isinstance(state, dict) and "_stall" in state

        expected_terminal = has_mode_done and has_result and has_stall

        assert is_terminal == expected_terminal, (
            f"Terminal detection mismatch:\n"
            f"  State: {state}\n"
            f"  Detected as terminal: {is_terminal}\n"
            f"  Expected: {expected_terminal}"
        )

    @given(mu_primitives)
    @settings(max_examples=500, deadline=5000)
    def test_primitives_never_terminal(self, primitive):
        """Primitives are never kernel terminal states."""
        assert not is_kernel_terminal(primitive), (
            f"Primitive incorrectly detected as terminal: {primitive}"
        )

    @given(st.lists(mu_primitives, max_size=5))
    @settings(max_examples=500, deadline=5000)
    def test_lists_never_terminal(self, lst):
        """Lists are never kernel terminal states."""
        assert not is_kernel_terminal(lst), (
            f"List incorrectly detected as terminal: {lst}"
        )


# =============================================================================
# Property 6: extract_kernel_result Consistency
# =============================================================================

class TestExtractKernelResultFuzzer:
    """
    Test extract_kernel_result() behavior under stress.

    Property: Result extraction is deterministic and type-preserving.
    """

    @given(mu_values(), mu_values(), st.booleans())
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_extract_respects_stall_flag(self, result_value, original_input, stall_flag):
        """When _stall is True, return original; else denormalize result."""
        assume(is_mu(result_value))
        assume(is_mu(original_input))

        terminal_state = {
            "_mode": "done",
            "_result": result_value,
            "_stall": stall_flag
        }

        extracted = extract_kernel_result(terminal_state, original_input)

        if stall_flag:
            # Should return original input unchanged
            assert extracted == original_input, (
                f"Stall should return original:\n"
                f"  Original: {original_input}\n"
                f"  Extracted: {extracted}"
            )
        else:
            # Should denormalize result - check it's valid Mu
            assert is_mu(extracted), "Extracted result must be valid Mu"

    @given(empty_containers())
    @settings(max_examples=300, deadline=5000)
    def test_extract_preserves_empty_container_type_on_stall(self, empty):
        """When stalled, empty containers preserve their type."""
        assume(is_mu(empty))

        terminal_state = {
            "_mode": "done",
            "_result": None,  # Stalled, so result doesn't matter
            "_stall": True
        }

        extracted = extract_kernel_result(terminal_state, empty)

        # Should return original, preserving type
        assert type(extracted) == type(empty), (
            f"Empty container type lost on stall:\n"
            f"  Original: {empty} (type: {type(empty)})\n"
            f"  Extracted: {extracted} (type: {type(extracted)})"
        )


# =============================================================================
# Integration: End-to-End Kernel Loop Properties
# =============================================================================

class TestKernelLoopIntegrationFuzzer:
    """
    End-to-end property tests for the simplified kernel loop.

    Phase 8b simplified loop: no semantic decisions inside for-loop.
    """

    @given(mu_values())
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_empty_projections_is_identity(self, value):
        """Empty projection list returns input unchanged (always stalls)."""
        assume(is_mu(value))

        result = step_mu([], value)

        assert mu_equal(result, value), (
            f"Empty projections should be identity:\n"
            f"  Input: {value}\n"
            f"  Output: {result}"
        )

    @given(mu_values())
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_identity_projection_is_stable(self, value):
        """Identity projection {var: x} -> {var: x} is stable (stalls immediately)."""
        assume(is_mu(value))

        identity_proj = {"pattern": {"var": "x"}, "body": {"var": "x"}}
        result = step_mu([identity_proj], value)

        # Should return input unchanged (stall detected via mu_equal)
        assert mu_equal(result, value), (
            f"Identity projection should stall:\n"
            f"  Input: {value}\n"
            f"  Output: {result}"
        )

    @given(mu_values())
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_step_mu_deterministic(self, value):
        """step_mu is deterministic - same input gives same output."""
        assume(is_mu(value))

        # Simple projection
        proj = {"pattern": {"var": "x"}, "body": {"wrapped": {"var": "x"}}}

        result1 = step_mu([proj], value)
        result2 = step_mu([proj], value)
        result3 = step_mu([proj], value)

        assert mu_equal(result1, result2), "step_mu not deterministic (1 vs 2)"
        assert mu_equal(result2, result3), "step_mu not deterministic (2 vs 3)"
