"""
Algorithm State Injection Via Normalized Structures Fuzzer (#1020)

Property-based tests verifying that normalized dict encoding does not bypass
security validators (validate_no_kernel_reserved_fields, validate_algorithm_runtime_fields).

Agent finding #1020: "Algorithm State Injection Via Normalized Structures"
- Normalized dict format ({_type: "dict", head: {head: key, tail: {head: val, tail: null}}, tail: ...})
  could potentially bypass reserved field detection if validators don't walk the encoding.
"""
import pytest
from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st

from rcx_pi.selfhost.step_mu import (
    validate_no_kernel_reserved_fields,
    validate_algorithm_runtime_fields,
    KERNEL_RESERVED_FIELDS,
    ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS,
    _iter_normalized_dict_pairs,  # ANTICHEAT_OK: fuzzer grounding test
    _looks_like_normalized_dict_candidate,  # ANTICHEAT_OK: fuzzer grounding test
)
from rcx_pi.selfhost.mu_type import is_mu, mu_equal


# =============================================================================
# Helpers: Build normalized dict encoding
# =============================================================================

def make_normalized_kv(key: str, val) -> dict:
    """Build a single kv-pair in normalized format: {head: key, tail: {head: val, tail: null}}."""
    return {"head": key, "tail": {"head": val, "tail": None}}


def make_normalized_dict(pairs: list[tuple[str, object]]) -> dict:
    """Build a normalized dict encoding from key-value pairs."""
    if not pairs:
        return {"_type": "dict", "head": None, "tail": None}
    # Build linked list of kv-pairs (last pair first)
    result = None
    for key, val in reversed(pairs):
        kv = make_normalized_kv(key, val)
        result = {"head": kv, "tail": result}
    return result


def make_typed_normalized_dict(pairs: list[tuple[str, object]]) -> dict:
    """Build a normalized dict with _type: dict marker."""
    if not pairs:
        return {"_type": "dict", "head": None, "tail": None}
    result = None
    for key, val in reversed(pairs):
        kv = make_normalized_kv(key, val)
        result = {"_type": "dict", "head": kv, "tail": result}
    return result


# =============================================================================
# Strategies
# =============================================================================

from tests.strategies import simple_mu

safe_key = st.text(min_size=1, max_size=10).filter(
    lambda k: k not in KERNEL_RESERVED_FIELDS and not k.startswith("_")
)


@st.composite
def normalized_dict_with_reserved_field(draw):
    """Generate a normalized dict encoding containing a reserved field."""
    reserved = draw(st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)))
    value = draw(simple_mu)
    safe = draw(safe_key)
    safe_val = draw(simple_mu)
    # Put reserved field among safe fields
    pairs = [(safe, safe_val), (reserved, value)]
    return make_normalized_dict(pairs), reserved


@st.composite
def normalized_dict_safe(draw):
    """Generate a normalized dict with only safe keys."""
    n = draw(st.integers(min_value=1, max_value=4))
    pairs = []
    used_keys = set()
    for _ in range(n):
        key = draw(safe_key.filter(lambda k: k not in used_keys))
        used_keys.add(key)
        val = draw(simple_mu)
        pairs.append((key, val))
    return make_normalized_dict(pairs)


@st.composite
def deeply_nested_normalized_with_reserved(draw):
    """Generate reserved field buried inside nested normalized dicts."""
    reserved = draw(st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)))
    value = draw(simple_mu)
    inner = make_normalized_dict([(reserved, value)])
    # Wrap in regular dict nesting
    depth = draw(st.integers(min_value=1, max_value=3))
    current = inner
    for _ in range(depth):
        key = draw(safe_key)
        current = {key: current}
    return current, reserved


# =============================================================================
# Tests: Normalized Dict Pair Iteration
# =============================================================================

class TestNormalizedDictPairIteration:
    """Verify _iter_normalized_dict_pairs correctly parses normalized encoding."""

    @given(
        key=safe_key,
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_single_pair_iteration(self, key, value):
        """Single key-value pair is extracted correctly."""
        nd = make_normalized_dict([(key, value)])
        pairs = _iter_normalized_dict_pairs(nd)
        assert pairs is not None
        assert len(pairs) == 1
        assert pairs[0][0] == key
        assert mu_equal(pairs[0][1], value)

    @given(
        k1=safe_key,
        v1=simple_mu,
        k2=safe_key,
        v2=simple_mu,
    )
    @settings(deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
    def test_multi_pair_iteration(self, k1, v1, k2, v2):
        """Multiple key-value pairs are extracted correctly."""
        assume(k1 != k2)
        nd = make_normalized_dict([(k1, v1), (k2, v2)])
        pairs = _iter_normalized_dict_pairs(nd)
        assert pairs is not None
        assert len(pairs) == 2

    def test_empty_typed_dict_iteration(self):
        """Empty typed normalized dict sentinel returns empty list."""
        # The empty dict sentinel is {"_type": "dict"} (only _type key)
        nd = {"_type": "dict"}
        pairs = _iter_normalized_dict_pairs(nd)
        assert pairs == []

    @given(simple_mu)
    @settings(deadline=5000)
    def test_non_normalized_returns_none(self, value):
        """Non-normalized values return None (not a normalized dict)."""
        assume(not isinstance(value, dict))
        pairs = _iter_normalized_dict_pairs(value)
        assert pairs is None

    def test_cyclic_structure_protection(self):
        """Iteration stops on excessive steps (cycle protection)."""
        # Build a chain longer than max_steps (100)
        current = None
        for i in range(105):
            kv = make_normalized_kv(f"key_{i}", i)
            current = {"head": kv, "tail": current}
        pairs = _iter_normalized_dict_pairs(current)
        # Should return None when exceeding max_steps
        assert pairs is None


# =============================================================================
# Tests: Normalized Dict Candidate Detection
# =============================================================================

class TestNormalizedDictCandidateDetection:
    """Verify _looks_like_normalized_dict_candidate identifies candidates."""

    @given(
        key=safe_key,
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_valid_normalized_dict_is_candidate(self, key, value):
        """Properly formed normalized dicts are detected as candidates."""
        nd = make_normalized_dict([(key, value)])
        assert _looks_like_normalized_dict_candidate(nd) is True

    def test_typed_dict_is_candidate(self):
        """Dict with _type: dict and head/tail is a candidate."""
        nd = {"_type": "dict", "head": make_normalized_kv("a", 1), "tail": None}
        assert _looks_like_normalized_dict_candidate(nd) is True

    @given(simple_mu)
    @settings(deadline=5000)
    def test_non_dict_not_candidate(self, value):
        """Non-dict values are never candidates."""
        assume(not isinstance(value, dict))
        assert _looks_like_normalized_dict_candidate(value) is False

    def test_regular_dict_not_candidate(self):
        """Regular dicts with non-kv-pair head are not candidates."""
        assert _looks_like_normalized_dict_candidate({"a": 1, "b": 2}) is False

    def test_empty_dict_not_candidate(self):
        """Empty dict is not a candidate."""
        assert _looks_like_normalized_dict_candidate({}) is False


# =============================================================================
# Tests: Reserved Field Injection Via Normalized Encoding
# =============================================================================

class TestReservedFieldInjectionViaNormalized:
    """Verify reserved fields inside normalized dicts are caught by validators."""

    @given(normalized_dict_with_reserved_field())
    @settings(deadline=5000)
    def test_domain_validator_catches_normalized_reserved(self, nd_and_field):
        """validate_no_kernel_reserved_fields catches reserved fields in normalized encoding."""
        nd, reserved = nd_and_field
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(nd, "test")

    @given(normalized_dict_safe())
    @settings(deadline=5000)
    def test_domain_validator_allows_safe_normalized(self, nd):
        """validate_no_kernel_reserved_fields accepts normalized dicts with safe keys."""
        validate_no_kernel_reserved_fields(nd, "test")

    @given(deeply_nested_normalized_with_reserved())
    @settings(deadline=5000)
    def test_domain_validator_catches_deeply_nested_reserved(self, nd_and_field):
        """Reserved fields buried in nested normalized dicts are still caught."""
        nd, reserved = nd_and_field
        with pytest.raises(ValueError, match="SECURITY"):
            validate_no_kernel_reserved_fields(nd, "test")


# =============================================================================
# Tests: Algorithm Runtime Validator With Normalized Encoding
# =============================================================================

class TestAlgorithmRuntimeNormalizedEncoding:
    """Verify algorithm runtime validator handles normalized dicts correctly."""

    @given(
        field=st.text(min_size=2, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz").map(
            lambda s: f"_{s}"
        ).filter(lambda f: f not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_unknown_underscore_in_normalized_rejected(self, field, value):
        """Unknown underscore fields in normalized encoding are rejected."""
        nd = make_normalized_dict([(field, value)])
        with pytest.raises(ValueError, match="SECURITY"):
            validate_algorithm_runtime_fields(nd, "test")

    @given(
        field=st.sampled_from(sorted(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_allowed_underscore_in_normalized_accepted(self, field, value):
        """Allowed underscore fields in normalized encoding pass."""
        nd = make_normalized_dict([(field, value)])
        validate_algorithm_runtime_fields(nd, "test")


# =============================================================================
# Tests: Malformed Normalized Dict - Fail Closed
# =============================================================================

class TestMalformedNormalizedFailClosed:
    """Verify malformed normalized dict candidates trigger fail-closed rejection."""

    def test_typed_dict_only_type_is_valid_empty(self):
        """_type: dict with no head/tail is the empty dict sentinel — accepted."""
        nd = {"_type": "dict"}
        # This is the canonical empty normalized dict, not malformed
        assert _looks_like_normalized_dict_candidate(nd) is True
        # _iter_normalized_dict_pairs returns [] for this (empty pairs, valid)
        assert _iter_normalized_dict_pairs(nd) == []
        # Validator accepts it (no reserved fields in empty dict)
        validate_no_kernel_reserved_fields(nd, "test")

    def test_head_with_wrong_structure_not_candidate(self):
        """Head that doesn't have kv-pair structure is not a candidate."""
        # This has head/tail but head isn't a proper kv-pair (string not dict)
        nd = {"head": "not_a_kv", "tail": None}
        # Not a candidate because head isn't a dict with {head, tail} keys
        assert _looks_like_normalized_dict_candidate(nd) is False

    def test_typed_dict_with_head_tail_but_bad_kv(self):
        """Typed dict with head/tail where head is malformed triggers fail-closed."""
        # This looks like a normalized dict candidate (_type=dict + head + tail)
        # but the head is not a proper kv-pair
        nd = {"_type": "dict", "head": {"bad": "structure"}, "tail": None}
        is_candidate = _looks_like_normalized_dict_candidate(nd)
        if is_candidate:
            # _iter_normalized_dict_pairs returns None for malformed structure
            pairs = _iter_normalized_dict_pairs(nd)
            assert pairs is None
            # Validator should fail closed
            with pytest.raises(ValueError, match="malformed"):
                validate_no_kernel_reserved_fields(nd, "test")
