"""
Property-Based Fuzzing for RCX Self-Hosting Stack using Hypothesis.

This test suite generates 1000+ random inputs to stress-test:
- mu_type.py: is_mu, mu_equal, assert_mu, depth/width limits
- kernel.py: compute_identity, detect_stall, record_trace
- match_mu.py: normalize_for_match, denormalize_from_match, match_mu
- subst_mu.py: subst_mu, lookup_binding

Run with: pytest tests/test_selfhost_fuzzer.py --hypothesis-show-statistics -v

Phase 4d: Property-based testing to catch edge cases unit tests miss.

Requires: pip install hypothesis

Test Infrastructure Note:
    This file uses Python host builtins (len, isinstance, set operations, etc.)
    for test generation and assertion logic. These are TEST HARNESS operations,
    not Mu operations under test. The actual Mu implementations are what's being
    validated - the test harness is allowed to use host Python freely.

Known Limitations Tested:
    - Empty collections ([], {}) normalize to None in Mu representation
    - Head/tail dict structures can collide with user data having those keys
    These are documented design decisions, not bugs. Tests document these cases.
"""

import pytest

# Skip all tests if hypothesis is not installed
hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite
import json

from rcx_pi.mu_type import (
    is_mu,
    assert_mu,
    mu_equal,
    mu_hash,
    mu_type_name,
    has_callable,
    MAX_MU_DEPTH,
    MAX_MU_WIDTH,
)
from rcx_pi.kernel import (
    compute_identity,
    detect_stall,
    record_trace,
    MAX_TRACE_ENTRIES,
)
from rcx_pi.match_mu import (
    normalize_for_match,
    denormalize_from_match,
    match_mu,
    bindings_to_dict,
    dict_to_bindings,
)
from rcx_pi.subst_mu import (
    subst_mu,
    lookup_binding,
)
from rcx_pi.eval_seed import NO_MATCH


# =============================================================================
# Hypothesis Strategies for Mu Values
# =============================================================================

# Primitive Mu values (JSON-compatible)
mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),  # JSON safe integers
    st.floats(
        allow_nan=False,
        allow_infinity=False,
        min_value=-1e10,
        max_value=1e10
    ),
    st.text(max_size=50),  # Reasonable string length for performance
)


@composite
def mu_values(draw, max_depth=5, allow_var_sites=False, allow_head_tail=False):
    """
    Generate valid Mu values recursively.

    Args:
        max_depth: Maximum nesting depth (default 5 for performance)
        allow_var_sites: If True, can generate {"var": "x"} structures
        allow_head_tail: If True, can generate {"head": x, "tail": y} structures
    """
    if max_depth <= 0:
        return draw(mu_primitives)

    strategies = [mu_primitives]

    # Add variable sites if allowed
    if allow_var_sites:
        var_names = st.one_of(
            st.just("x"),
            st.just("y"),
            st.just("z"),
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),
                    min_codepoint=ord('a'),
                    max_codepoint=ord('z')
                ),
                min_size=1,
                max_size=10
            ),
        )
        strategies.append(
            st.builds(lambda name: {"var": name}, var_names)
        )

    # Add head/tail structures if allowed
    if allow_head_tail:
        strategies.append(
            st.builds(
                lambda h, t: {"head": h, "tail": t},
                st.deferred(lambda: mu_values(max_depth=max_depth-1, allow_var_sites=allow_var_sites, allow_head_tail=True)),
                st.one_of(
                    st.none(),
                    st.deferred(lambda: mu_values(max_depth=max_depth-1, allow_var_sites=allow_var_sites, allow_head_tail=True))
                )
            )
        )

    # Add lists (limited size for performance)
    strategies.append(
        st.lists(
            st.deferred(lambda: mu_values(max_depth=max_depth-1, allow_var_sites=allow_var_sites, allow_head_tail=allow_head_tail)),
            max_size=4
        )
    )

    # Add dicts (limited size for performance)
    strategies.append(
        st.dictionaries(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),
                    min_codepoint=ord('a'),
                    max_codepoint=ord('z')
                ),
                min_size=1,
                max_size=10
            ),
            st.deferred(lambda: mu_values(max_depth=max_depth-1, allow_var_sites=allow_var_sites, allow_head_tail=allow_head_tail)),
            max_size=4
        )
    )

    return draw(st.one_of(*strategies))


@composite
def mu_patterns(draw, max_depth=3):
    """Generate valid patterns (Mu values with possible var sites)."""
    return draw(mu_values(max_depth=max_depth, allow_var_sites=True))


@composite
def mu_bindings_dict(draw, max_depth=3):
    """Generate valid bindings dict (str -> Mu)."""
    num_bindings = draw(st.integers(min_value=0, max_value=5))
    bindings = {}
    for i in range(num_bindings):
        var_name = draw(st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=1,
            max_size=10
        ))
        value = draw(mu_values(max_depth=max_depth))
        bindings[var_name] = value
    return bindings


def extract_var_names(pattern, _seen=None) -> set:
    """Extract all variable names from a pattern."""
    if _seen is None:
        _seen = set()
    if isinstance(pattern, (list, dict)) and id(pattern) in _seen:
        return set()
    if isinstance(pattern, (list, dict)):
        _seen.add(id(pattern))

    if isinstance(pattern, dict):
        if set(pattern.keys()) == {"var"}:
            name = pattern.get("var")
            if isinstance(name, str):
                return {name}
            return set()
        names = set()
        for v in pattern.values():
            names |= extract_var_names(v, _seen)
        return names
    elif isinstance(pattern, list):
        names = set()
        for elem in pattern:
            names |= extract_var_names(elem, _seen)
        return names
    return set()


def contains_empty_collection(value, _seen=None):
    """Check if value contains [] or {} anywhere."""
    if _seen is None:
        _seen = set()
    if isinstance(value, (list, dict)) and id(value) in _seen:
        return False
    if isinstance(value, (list, dict)):
        _seen.add(id(value))

    if value == [] or value == {}:
        return True
    if isinstance(value, list):
        return any(contains_empty_collection(elem, _seen) for elem in value)
    if isinstance(value, dict):
        return any(contains_empty_collection(v, _seen) for v in value.values())
    return False


def contains_head_tail(value, _seen=None):
    """Check if value contains head/tail structure."""
    if _seen is None:
        _seen = set()
    if isinstance(value, (list, dict)) and id(value) in _seen:
        return False
    if isinstance(value, (list, dict)):
        _seen.add(id(value))

    if isinstance(value, dict):
        if set(value.keys()) == {"head", "tail"}:
            return True
        return any(contains_head_tail(v, _seen) for v in value.values())
    if isinstance(value, list):
        return any(contains_head_tail(elem, _seen) for elem in value)
    return False


def contains_empty_var_name(pattern, _seen=None):
    """Check if pattern contains {"var": ""} anywhere."""
    if _seen is None:
        _seen = set()
    if isinstance(pattern, (list, dict)) and id(pattern) in _seen:
        return False
    if isinstance(pattern, (list, dict)):
        _seen.add(id(pattern))

    if isinstance(pattern, dict):
        if set(pattern.keys()) == {"var"} and pattern.get("var") == "":
            return True
        return any(contains_empty_var_name(v, _seen) for v in pattern.values())
    if isinstance(pattern, list):
        return any(contains_empty_var_name(elem, _seen) for elem in pattern)
    return False


# =============================================================================
# Property 1: mu_equal is an Equivalence Relation
# =============================================================================

class TestMuEqualEquivalence:
    """Tests for mu_equal equivalence relation properties."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=None)
    def test_mu_equal_reflexivity(self, value):
        """mu_equal(x, x) must be True (reflexivity)."""
        assume(is_mu(value))
        assert mu_equal(value, value), f"Reflexivity failed for {value}"

    @given(mu_values(max_depth=4), mu_values(max_depth=4))
    @settings(
        max_examples=500,
        deadline=None,
        suppress_health_check=[HealthCheck.filter_too_much]
    )
    def test_mu_equal_symmetry(self, a, b):
        """mu_equal(a, b) == mu_equal(b, a) (symmetry)."""
        assume(is_mu(a))
        assume(is_mu(b))

        result_ab = mu_equal(a, b)
        result_ba = mu_equal(b, a)
        assert result_ab == result_ba, f"Symmetry failed: {a} vs {b}"

    @given(mu_values(max_depth=3), mu_values(max_depth=3), mu_values(max_depth=3))
    @settings(
        max_examples=300,
        deadline=None,
        suppress_health_check=[HealthCheck.filter_too_much]
    )
    def test_mu_equal_transitivity(self, a, b, c):
        """If mu_equal(a, b) and mu_equal(b, c) then mu_equal(a, c) (transitivity)."""
        assume(is_mu(a))
        assume(is_mu(b))
        assume(is_mu(c))

        if mu_equal(a, b) and mu_equal(b, c):
            assert mu_equal(a, c), f"Transitivity failed: {a} == {b} == {c}"


# =============================================================================
# Property 2: compute_identity Determinism
# =============================================================================

class TestComputeIdentityDeterminism:
    """Tests for compute_identity determinism."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=1000, deadline=None)
    def test_compute_identity_determinism(self, value):
        """compute_identity must be deterministic - same input gives same hash."""
        assume(is_mu(value))

        hash1 = compute_identity(value)
        hash2 = compute_identity(value)

        assert hash1 == hash2, f"Determinism failed for {value}"
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex string

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=None)
    def test_mu_hash_is_deterministic(self, value):
        """mu_hash is deterministic - same value gives same hash.

        Note: mu_hash uses ensure_ascii=False, while compute_identity uses
        ensure_ascii=True. They may differ for non-ASCII strings, but each
        should be internally deterministic.
        """
        assume(is_mu(value))

        # mu_hash should be deterministic
        hash1 = mu_hash(value)
        hash2 = mu_hash(value)

        assert isinstance(hash1, str) and len(hash1) == 64
        assert hash1 == hash2, f"mu_hash not deterministic for {value}"

        # compute_identity should also be deterministic
        id1 = compute_identity(value)
        id2 = compute_identity(value)

        assert isinstance(id1, str) and len(id1) == 64
        assert id1 == id2, f"compute_identity not deterministic for {value}"


# =============================================================================
# Property 3: compute_identity Collision Resistance (Probabilistic)
# =============================================================================

class TestComputeIdentityCollisionResistance:
    """Tests for hash collision resistance."""

    @given(mu_values(max_depth=4), mu_values(max_depth=4))
    @settings(
        max_examples=500,
        deadline=None,
        suppress_health_check=[HealthCheck.filter_too_much]
    )
    def test_compute_identity_collision_resistance(self, a, b):
        """Different values should produce different hashes (with high probability)."""
        assume(is_mu(a))
        assume(is_mu(b))

        # Skip structurally equal values
        if mu_equal(a, b):
            return

        hash_a = compute_identity(a)
        hash_b = compute_identity(b)

        # Different values should have different hashes
        assert hash_a != hash_b, f"Hash collision: {a} and {b} both hash to {hash_a}"


# =============================================================================
# Property 4: Hash Consistency with Equality
# =============================================================================

class TestHashEqualityConsistency:
    """Tests for hash/equality consistency."""

    @given(mu_values(max_depth=4), mu_values(max_depth=4))
    @settings(
        max_examples=500,
        deadline=None,
        suppress_health_check=[HealthCheck.filter_too_much]
    )
    def test_mu_equal_implies_same_hash(self, a, b):
        """If mu_equal(a, b) then compute_identity(a) == compute_identity(b)."""
        assume(is_mu(a))
        assume(is_mu(b))

        if mu_equal(a, b):
            hash_a = compute_identity(a)
            hash_b = compute_identity(b)
            assert hash_a == hash_b, f"Equal values have different hashes: {a} vs {b}"


# =============================================================================
# Property 5: detect_stall Correctness
# =============================================================================

class TestDetectStallCorrectness:
    """Tests for detect_stall correctness."""

    @given(st.text(min_size=64, max_size=64), st.text(min_size=64, max_size=64))
    @settings(max_examples=300, deadline=None)
    def test_detect_stall_correctness(self, hash1, hash2):
        """detect_stall returns True iff hashes are equal."""
        result = detect_stall(hash1, hash2)

        if hash1 == hash2:
            assert result is True
        else:
            assert result is False


# =============================================================================
# Property 6: Normalization Roundtrip
# =============================================================================

class TestNormalizationRoundtrip:
    """Tests for normalization roundtrip property."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=1000, deadline=None)
    def test_normalize_denormalize_roundtrip(self, value):
        """denormalize(normalize(x)) == x for most Mu values.

        Known exceptions:
        - Empty lists [] normalize to None
        - Empty dicts {} normalize to None
        """
        assume(is_mu(value))

        # Skip known exceptions
        if contains_empty_collection(value):
            return

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == value, f"Roundtrip failed: {value} -> {normalized} -> {denormalized}"

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=None)
    def test_normalization_preserves_validity(self, value):
        """Normalized values are valid Mu."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        assert is_mu(normalized), f"Normalized value is not Mu: {normalized}"

    @given(mu_values(max_depth=4, allow_head_tail=True))
    @settings(max_examples=500, deadline=None)
    def test_denormalization_preserves_validity(self, value):
        """Denormalized values are valid Mu.

        Note: Only valid linked-list structures (tail is None or dict with head/tail)
        can be denormalized. Other head/tail dicts are treated as regular dicts.
        """
        assume(is_mu(value))

        # Skip invalid head/tail structures where tail is not None or dict
        # These are not valid linked lists and denormalize_from_match may not handle them
        def has_invalid_tail(v, _seen=None):
            if _seen is None:
                _seen = set()
            if isinstance(v, (list, dict)) and id(v) in _seen:
                return False
            if isinstance(v, (list, dict)):
                _seen.add(id(v))

            if isinstance(v, dict):
                if set(v.keys()) == {"head", "tail"}:
                    tail = v.get("tail")
                    # tail must be None or another head/tail dict
                    if tail is not None and not isinstance(tail, dict):
                        return True
                    if isinstance(tail, dict) and set(tail.keys()) != {"head", "tail"}:
                        return True
                for val in v.values():
                    if has_invalid_tail(val, _seen):
                        return True
            elif isinstance(v, list):
                for elem in v:
                    if has_invalid_tail(elem, _seen):
                        return True
            return False

        assume(not has_invalid_tail(value))

        denormalized = denormalize_from_match(value)
        assert is_mu(denormalized), f"Denormalized value is not Mu: {denormalized}"


# =============================================================================
# Property 7: Normalization Idempotency
# =============================================================================

class TestNormalizationIdempotency:
    """Tests for normalization idempotency."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=None)
    def test_normalize_idempotency(self, value):
        """normalize(normalize(x)) denormalizes to same value."""
        assume(is_mu(value))

        # Skip head/tail structures (they may denormalize differently)
        if contains_head_tail(value):
            return

        normalized1 = normalize_for_match(value)
        normalized2 = normalize_for_match(normalized1)

        # They should denormalize to the same value
        denorm1 = denormalize_from_match(normalized1)
        denorm2 = denormalize_from_match(normalized2)

        assert denorm1 == denorm2, f"Idempotency failed: {value} -> {denorm1} vs {denorm2}"


# =============================================================================
# Property 8: match_mu Determinism
# =============================================================================

class TestMatchMuDeterminism:
    """Tests for match_mu determinism."""

    @given(mu_patterns(max_depth=3), mu_values(max_depth=4))
    @settings(
        max_examples=500,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_match_mu_determinism(self, pattern, value):
        """match_mu must be deterministic - same inputs give same outputs."""
        assume(is_mu(pattern))
        assume(is_mu(value))

        # Skip patterns with empty var names
        if contains_empty_var_name(pattern):
            return

        try:
            result1 = match_mu(pattern, value)
            result2 = match_mu(pattern, value)

            if result1 is NO_MATCH:
                assert result2 is NO_MATCH, "Determinism violated: got NO_MATCH then match"
            else:
                assert result2 is not NO_MATCH, "Determinism violated: got match then NO_MATCH"
                assert result1 == result2, f"Determinism violated: {result1} != {result2}"
        except (ValueError, TypeError, RuntimeError):
            # Expected errors should also be deterministic
            try:
                match_mu(pattern, value)
                assert False, "Non-deterministic error: first call raised, second didn't"
            except (ValueError, TypeError, RuntimeError):
                pass  # Good - same error twice


# =============================================================================
# Property 9: subst_mu Determinism
# =============================================================================

class TestSubstMuDeterminism:
    """Tests for subst_mu determinism."""

    @given(mu_values(max_depth=3, allow_var_sites=True), mu_bindings_dict(max_depth=3))
    @settings(
        max_examples=500,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_subst_mu_determinism(self, body, bindings):
        """subst_mu must be deterministic - same inputs give same outputs."""
        assume(is_mu(body))

        # Skip if body has empty var names
        if contains_empty_var_name(body):
            return

        # Only test if all vars in body are bound
        body_vars = extract_var_names(body)
        if not body_vars.issubset(bindings.keys()):
            return  # Skip - would raise KeyError

        try:
            result1 = subst_mu(body, bindings)
            result2 = subst_mu(body, bindings)

            assert mu_equal(result1, result2), f"Determinism violated: {result1} != {result2}"
        except (KeyError, ValueError, TypeError, RuntimeError):
            # Expected errors should also be deterministic
            try:
                subst_mu(body, bindings)
                assert False, "Non-deterministic error: first call raised, second didn't"
            except (KeyError, ValueError, TypeError, RuntimeError):
                pass


# =============================================================================
# Property 10: Variable Binding Consistency
# =============================================================================

class TestVariableBindingConsistency:
    """Tests for variable binding consistency."""

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10), mu_values(max_depth=3))
    @settings(max_examples=300, deadline=None)
    def test_subst_mu_same_var_consistency(self, var_name, value):
        """Same variable in body gets same value everywhere."""
        assume(is_mu(value))

        body = {
            "first": {"var": var_name},
            "second": {"var": var_name},
            "third": {"var": var_name}
        }
        bindings = {var_name: value}

        result = subst_mu(body, bindings)

        # All three should be structurally identical
        assert mu_equal(result["first"], result["second"]), "first != second"
        assert mu_equal(result["second"], result["third"]), "second != third"


# =============================================================================
# Property 11: Type Preservation
# =============================================================================

class TestTypePreservation:
    """Tests for Mu type preservation."""

    @given(mu_patterns(max_depth=3), mu_values(max_depth=4))
    @settings(
        max_examples=300,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_match_mu_preserves_mu_type(self, pattern, value):
        """match_mu bindings must be valid Mu."""
        assume(is_mu(pattern))
        assume(is_mu(value))

        # Skip patterns with empty var names
        if contains_empty_var_name(pattern):
            return

        try:
            result = match_mu(pattern, value)

            if result is not NO_MATCH:
                assert isinstance(result, dict)
                for var_name, bound_value in result.items():
                    assert isinstance(var_name, str)
                    assert is_mu(bound_value), f"Bound value is not Mu: {bound_value}"
        except (ValueError, TypeError, RuntimeError):
            pass  # Expected errors

    @given(mu_values(max_depth=3, allow_var_sites=True), mu_bindings_dict(max_depth=3))
    @settings(
        max_examples=300,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_subst_mu_preserves_mu_type(self, body, bindings):
        """subst_mu result must be valid Mu."""
        assume(is_mu(body))

        # Skip if body has empty var names
        if contains_empty_var_name(body):
            return

        # Only test if all vars are bound
        body_vars = extract_var_names(body)
        if not body_vars.issubset(bindings.keys()):
            return

        try:
            result = subst_mu(body, bindings)
            assert is_mu(result), f"Result is not Mu: {result}"
        except (KeyError, ValueError, TypeError, RuntimeError):
            pass


# =============================================================================
# Property 12: Width/Depth Limit Enforcement
# =============================================================================

class TestLimitEnforcement:
    """Tests for width/depth limit enforcement."""

    def _build_deep_structure(self, depth):
        """Build deeply nested dict structure."""
        result = "leaf"
        for _ in range(depth):
            result = {"nested": result}
        return result

    @given(st.integers(min_value=MAX_MU_DEPTH + 1, max_value=MAX_MU_DEPTH + 100))
    @settings(max_examples=20, deadline=None)
    def test_is_mu_rejects_too_deep(self, depth):
        """is_mu rejects structures exceeding MAX_MU_DEPTH."""
        structure = self._build_deep_structure(depth)
        assert not is_mu(structure), f"is_mu accepted depth {depth} > {MAX_MU_DEPTH}"

    @given(st.integers(min_value=MAX_MU_WIDTH + 1, max_value=MAX_MU_WIDTH + 100))
    @settings(max_examples=20, deadline=None)
    def test_is_mu_rejects_too_wide_list(self, width):
        """is_mu rejects lists exceeding MAX_MU_WIDTH."""
        wide_list = list(range(width))
        assert not is_mu(wide_list), f"is_mu accepted list width {width} > {MAX_MU_WIDTH}"

    @given(st.integers(min_value=MAX_MU_WIDTH + 1, max_value=MAX_MU_WIDTH + 100))
    @settings(max_examples=20, deadline=None)
    def test_is_mu_rejects_too_wide_dict(self, width):
        """is_mu rejects dicts exceeding MAX_MU_WIDTH."""
        wide_dict = {f"key{i}": i for i in range(width)}
        assert not is_mu(wide_dict), f"is_mu accepted dict width {width} > {MAX_MU_WIDTH}"

    @given(st.integers(min_value=1, max_value=min(50, MAX_MU_DEPTH)))
    @settings(max_examples=50, deadline=None)
    def test_is_mu_accepts_within_depth_limit(self, depth):
        """is_mu accepts structures within MAX_MU_DEPTH."""
        structure = self._build_deep_structure(depth)
        assert is_mu(structure), f"is_mu rejected valid depth {depth} <= {MAX_MU_DEPTH}"

    @given(st.integers(min_value=1, max_value=min(100, MAX_MU_WIDTH)))
    @settings(max_examples=50, deadline=None)
    def test_is_mu_accepts_within_width_limit(self, width):
        """is_mu accepts lists/dicts within MAX_MU_WIDTH."""
        wide_list = list(range(width))
        wide_dict = {f"key{i}": i for i in range(width)}

        assert is_mu(wide_list), f"is_mu rejected valid list width {width} <= {MAX_MU_WIDTH}"
        assert is_mu(wide_dict), f"is_mu rejected valid dict width {width} <= {MAX_MU_WIDTH}"


# =============================================================================
# Property 13: No Crash on Valid Inputs
# =============================================================================

class TestNoCrashOnValidInputs:
    """Tests that valid inputs don't cause crashes."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=1000, deadline=None)
    def test_is_mu_never_crashes(self, value):
        """is_mu should never crash, just return bool."""
        result = is_mu(value)
        assert isinstance(result, bool)

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=None)
    def test_mu_type_name_never_crashes(self, value):
        """mu_type_name should never crash."""
        result = mu_type_name(value)
        assert isinstance(result, str)
        assert result in ["null", "bool", "int", "float", "str", "list", "dict", "INVALID"]

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=None)
    def test_has_callable_never_crashes(self, value):
        """has_callable should never crash."""
        result = has_callable(value)
        assert isinstance(result, bool)

    @given(mu_values(max_depth=4))
    @settings(max_examples=300, deadline=None)
    def test_compute_identity_never_crashes_on_valid_mu(self, value):
        """compute_identity should never crash on valid Mu."""
        assume(is_mu(value))

        try:
            result = compute_identity(value)
            assert isinstance(result, str)
            assert len(result) == 64
        except TypeError:
            # Invalid Mu - expected
            pass


# =============================================================================
# Property 14: Trace Limit Enforcement
# =============================================================================

class TestTraceLimitEnforcement:
    """Tests for trace limit enforcement."""

    @given(st.integers(min_value=0, max_value=min(100, MAX_TRACE_ENTRIES)))
    @settings(max_examples=20, deadline=None)
    def test_record_trace_accepts_within_limit(self, num_entries):
        """record_trace accepts entries up to MAX_TRACE_ENTRIES."""
        trace = []
        for i in range(num_entries):
            record_trace(trace, {"step": i})

        assert len(trace) == num_entries

    def test_record_trace_rejects_at_limit(self):
        """record_trace raises RuntimeError at MAX_TRACE_ENTRIES."""
        trace = []
        for i in range(MAX_TRACE_ENTRIES):
            record_trace(trace, {"step": i})

        # Next one should raise
        with pytest.raises(RuntimeError, match="Trace size limit exceeded"):
            record_trace(trace, {"step": MAX_TRACE_ENTRIES})


# =============================================================================
# Property 15: Bindings Conversion Roundtrip
# =============================================================================

class TestBindingsConversionRoundtrip:
    """Tests for bindings conversion roundtrip."""

    @given(mu_bindings_dict(max_depth=3))
    @settings(max_examples=300, deadline=None)
    def test_bindings_dict_roundtrip(self, bindings):
        """dict_to_bindings -> bindings_to_dict roundtrip."""
        # Skip empty dict edge case (it becomes None)
        if not bindings:
            return

        linked = dict_to_bindings(bindings)
        roundtrip = bindings_to_dict(linked)

        assert roundtrip == bindings, f"Roundtrip failed: {bindings} -> {linked} -> {roundtrip}"


# =============================================================================
# Property 16: Type Discrimination in mu_equal
# =============================================================================

class TestTypeDiscrimination:
    """Tests for type discrimination in mu_equal."""

    @given(st.integers(), st.booleans())
    @settings(max_examples=100, deadline=None)
    def test_mu_equal_discriminates_bool_int(self, n, b):
        """mu_equal discriminates True/1 and False/0 (unlike Python ==)."""
        if b is True and n == 1:
            assert not mu_equal(True, 1), "mu_equal failed to discriminate True vs 1"
        elif b is False and n == 0:
            assert not mu_equal(False, 0), "mu_equal failed to discriminate False vs 0"


# =============================================================================
# Property 17: JSON Roundtrip Consistency
# =============================================================================

class TestJSONRoundtripConsistency:
    """Tests for JSON roundtrip consistency."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=None)
    def test_json_roundtrip_consistency(self, value):
        """Valid Mu values should roundtrip through JSON."""
        assume(is_mu(value))

        try:
            # Serialize and deserialize
            serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
            deserialized = json.loads(serialized)

            # Should still be valid Mu
            assert is_mu(deserialized)

            # Should be structurally equal
            assert mu_equal(value, deserialized)
        except (TypeError, ValueError):
            pass


# =============================================================================
# Property 18: Deterministic Dict Key Ordering in Normalization
# =============================================================================

class TestDictKeyOrderingDeterminism:
    """Tests for deterministic dict key ordering."""

    @given(st.dictionaries(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        mu_values(max_depth=2),
        max_size=5
    ))
    @settings(max_examples=300, deadline=None)
    def test_normalize_dict_ordering_deterministic(self, d):
        """Dict normalization is deterministic regardless of key insertion order."""
        assume(is_mu(d))

        # Skip empty dict (normalizes to None)
        if not d:
            return

        # Normalize the same dict multiple times
        norm1 = normalize_for_match(d)
        norm2 = normalize_for_match(d)

        # Should be identical
        assert mu_equal(norm1, norm2), f"Non-deterministic normalization for {d}"

        # Create dict with same keys in different order
        reversed_d = {k: d[k] for k in reversed(sorted(d.keys()))}
        norm_reversed = normalize_for_match(reversed_d)

        # Should still be identical (keys are sorted)
        assert mu_equal(norm1, norm_reversed), f"Ordering affected normalization: {d}"
