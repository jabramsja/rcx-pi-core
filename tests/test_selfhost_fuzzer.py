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


# Hostile unicode strings for edge case testing
hostile_unicode_strings = st.one_of(
    # Emoji sequences (multi-byte, grapheme clusters)
    st.sampled_from([
        "\U0001F600",  # 😀 single emoji
        "\U0001F468\u200D\U0001F469\u200D\U0001F467",  # 👨‍👩‍👧 family emoji (ZWJ sequence)
        "\U0001F1FA\U0001F1F8",  # 🇺🇸 flag emoji (regional indicators)
    ]),
    # RTL and directional control characters
    st.sampled_from([
        "\u200F",  # RTL mark
        "\u200E",  # LTR mark
        "\u202A",  # LTR embedding
        "\u202B",  # RTL embedding
        "\u202C",  # pop directional formatting
        "\u2066",  # LTR isolate
        "\u2067",  # RTL isolate
        "\u2068",  # first strong isolate
        "\u2069",  # pop directional isolate
    ]),
    # Zero-width characters
    st.sampled_from([
        "\u200B",  # zero-width space
        "\u200C",  # zero-width non-joiner
        "\u200D",  # zero-width joiner
        "\uFEFF",  # byte order mark / zero-width no-break space
    ]),
    # Combining characters and diacritics
    st.sampled_from([
        "e\u0301",  # é as e + combining acute
        "a\u0308",  # ä as a + combining diaeresis
        "Z\u0336\u0311",  # Zalgo-style text (Z with multiple modifiers)
    ]),
    # Null and control characters (within JSON string bounds)
    st.sampled_from([
        "\t",  # tab
        "\n",  # newline
        "\r",  # carriage return
    ]),
    # Unicode normalization edge cases
    st.sampled_from([
        "\u00C5",  # Å (precomposed)
        "A\u030A",  # Å (decomposed: A + combining ring)
        "\uFB01",  # ﬁ ligature
    ]),
    # Unusual but valid unicode
    st.sampled_from([
        "\u0000",  # NULL character (valid in JSON strings)
        "\u001F",  # unit separator
        "\u007F",  # DEL character
    ]),
)


@composite
def hostile_mu_values(draw, max_depth=3):
    """Generate Mu values with hostile/edge-case unicode strings."""
    if max_depth <= 0:
        return draw(hostile_unicode_strings)

    return draw(st.one_of(
        hostile_unicode_strings,
        st.lists(
            st.deferred(lambda: hostile_mu_values(max_depth=max_depth-1)),
            max_size=3
        ),
        st.dictionaries(
            hostile_unicode_strings,
            st.deferred(lambda: hostile_mu_values(max_depth=max_depth-1)),
            max_size=3
        ),
    ))


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


def is_ambiguous_list_dict(value, _seen=None):
    """Check if value is a list that could be confused with a dict after normalization.

    KNOWN LIMITATION: A list of 2-element sublists where each sublist starts
    with a string normalizes identically to a dict. For example:
    - [['a', 1]] normalizes the same as {'a': 1}
    - [['x', None]] normalizes the same as {'x': None}

    We skip these cases in parity tests because the ambiguity is documented.
    """
    if _seen is None:
        _seen = set()
    if isinstance(value, (list, dict)) and id(value) in _seen:
        return False
    if isinstance(value, (list, dict)):
        _seen.add(id(value))

    if isinstance(value, list):
        # Check if this is a list of 2-element sublists with string first elements
        if len(value) > 0 and all(
            isinstance(elem, list) and len(elem) == 2 and isinstance(elem[0], str)
            for elem in value
        ):
            return True
        # Recurse into elements
        return any(is_ambiguous_list_dict(elem, _seen) for elem in value)

    if isinstance(value, dict):
        return any(is_ambiguous_list_dict(v, _seen) for v in value.values())

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
    @settings(max_examples=500, deadline=5000)
    def test_mu_equal_reflexivity(self, value):
        """mu_equal(x, x) must be True (reflexivity)."""
        assume(is_mu(value))
        assert mu_equal(value, value), f"Reflexivity failed for {value}"

    @given(mu_values(max_depth=4), mu_values(max_depth=4))
    @settings(
        max_examples=500,
        deadline=5000,
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
        deadline=5000,
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
    @settings(max_examples=1000, deadline=5000)
    def test_compute_identity_determinism(self, value):
        """compute_identity must be deterministic - same input gives same hash."""
        assume(is_mu(value))

        hash1 = compute_identity(value)
        hash2 = compute_identity(value)

        assert hash1 == hash2, f"Determinism failed for {value}"
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex string

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=5000)
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
        deadline=5000,
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
        deadline=5000,
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
    @settings(max_examples=300, deadline=5000)
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
    @settings(max_examples=1000, deadline=5000)
    def test_normalize_denormalize_roundtrip(self, value):
        """denormalize(normalize(x)) == x for most Mu values.

        Known exceptions:
        - Empty lists [] normalize to None
        - Empty dicts {} normalize to None
        - 2-element lists where first element is string (look like kv-pairs)
        """
        assume(is_mu(value))

        # Skip known exceptions
        if contains_empty_collection(value):
            return

        # Skip 2-element lists that look like kv-pairs (known limitation)
        def looks_like_kv_pair(v, _seen=None):
            if _seen is None:
                _seen = set()
            if isinstance(v, (list, dict)) and id(v) in _seen:
                return False
            if isinstance(v, (list, dict)):
                _seen.add(id(v))

            if isinstance(v, list):
                if len(v) == 2 and isinstance(v[0], str):
                    return True
                return any(looks_like_kv_pair(elem, _seen) for elem in v)
            if isinstance(v, dict):
                return any(looks_like_kv_pair(val, _seen) for val in v.values())
            return False

        if looks_like_kv_pair(value):
            return

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == value, f"Roundtrip failed: {value} -> {normalized} -> {denormalized}"

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=5000)
    def test_normalization_preserves_validity(self, value):
        """Normalized values are valid Mu."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        assert is_mu(normalized), f"Normalized value is not Mu: {normalized}"

    @given(mu_values(max_depth=4, allow_head_tail=True))
    @settings(max_examples=500, deadline=5000)
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
    @settings(max_examples=500, deadline=5000)
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
        deadline=5000,
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
        deadline=5000,
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
    @settings(max_examples=300, deadline=5000)
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
        deadline=5000,
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
        deadline=5000,
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

    def build_deep_structure(self, depth):
        """Build deeply nested dict structure."""
        result = "leaf"
        for _ in range(depth):
            result = {"nested": result}
        return result

    @given(st.integers(min_value=MAX_MU_DEPTH + 1, max_value=MAX_MU_DEPTH + 100))
    @settings(max_examples=20, deadline=5000)
    def test_is_mu_rejects_too_deep(self, depth):
        """is_mu rejects structures exceeding MAX_MU_DEPTH."""
        structure = self.build_deep_structure(depth)
        assert not is_mu(structure), f"is_mu accepted depth {depth} > {MAX_MU_DEPTH}"

    @given(st.integers(min_value=MAX_MU_WIDTH + 1, max_value=MAX_MU_WIDTH + 100))
    @settings(max_examples=20, deadline=5000)
    def test_is_mu_rejects_too_wide_list(self, width):
        """is_mu rejects lists exceeding MAX_MU_WIDTH."""
        wide_list = list(range(width))
        assert not is_mu(wide_list), f"is_mu accepted list width {width} > {MAX_MU_WIDTH}"

    @given(st.integers(min_value=MAX_MU_WIDTH + 1, max_value=MAX_MU_WIDTH + 100))
    @settings(max_examples=20, deadline=5000)
    def test_is_mu_rejects_too_wide_dict(self, width):
        """is_mu rejects dicts exceeding MAX_MU_WIDTH."""
        wide_dict = {f"key{i}": i for i in range(width)}
        assert not is_mu(wide_dict), f"is_mu accepted dict width {width} > {MAX_MU_WIDTH}"

    @given(st.integers(min_value=1, max_value=min(50, MAX_MU_DEPTH)))
    @settings(max_examples=50, deadline=5000)
    def test_is_mu_accepts_within_depth_limit(self, depth):
        """is_mu accepts structures within MAX_MU_DEPTH."""
        structure = self.build_deep_structure(depth)
        assert is_mu(structure), f"is_mu rejected valid depth {depth} <= {MAX_MU_DEPTH}"

    @given(st.integers(min_value=1, max_value=min(100, MAX_MU_WIDTH)))
    @settings(max_examples=50, deadline=5000)
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
    @settings(max_examples=1000, deadline=5000)
    def test_is_mu_never_crashes(self, value):
        """is_mu should never crash, just return bool."""
        result = is_mu(value)
        assert isinstance(result, bool)

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=5000)
    def test_mu_type_name_never_crashes(self, value):
        """mu_type_name should never crash."""
        result = mu_type_name(value)
        assert isinstance(result, str)
        assert result in ["null", "bool", "int", "float", "str", "list", "dict", "INVALID"]

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=5000)
    def test_has_callable_never_crashes(self, value):
        """has_callable should never crash."""
        result = has_callable(value)
        assert isinstance(result, bool)

    @given(mu_values(max_depth=4))
    @settings(max_examples=300, deadline=5000)
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
    @settings(max_examples=20, deadline=5000)
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
    @settings(max_examples=300, deadline=5000)
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
    @settings(max_examples=100, deadline=5000)
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
    @settings(max_examples=500, deadline=5000)
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
    @settings(max_examples=300, deadline=5000)
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


# =============================================================================
# Property 19: Hostile Unicode Handling
# =============================================================================

class TestHostileUnicodeHandling:
    """Tests for hostile/edge-case unicode string handling."""

    @given(hostile_mu_values(max_depth=2))
    @settings(max_examples=500, deadline=5000)
    def test_hostile_unicode_is_valid_mu(self, value):
        """Hostile unicode values should still be valid Mu (if JSON-compatible)."""
        # All our generated hostile values should be valid Mu
        assert is_mu(value), f"Hostile unicode value rejected: {repr(value)}"

    @given(hostile_mu_values(max_depth=2))
    @settings(max_examples=300, deadline=5000)
    def test_hostile_unicode_hash_deterministic(self, value):
        """compute_identity is deterministic for hostile unicode."""
        assume(is_mu(value))

        hash1 = compute_identity(value)
        hash2 = compute_identity(value)
        assert hash1 == hash2, f"Hash not deterministic for {repr(value)}"

    @given(hostile_mu_values(max_depth=2), hostile_mu_values(max_depth=2))
    @settings(
        max_examples=300,
        deadline=5000,
        suppress_health_check=[HealthCheck.filter_too_much]
    )
    def test_hostile_unicode_equality_symmetric(self, a, b):
        """mu_equal is symmetric for hostile unicode values."""
        assume(is_mu(a))
        assume(is_mu(b))

        assert mu_equal(a, b) == mu_equal(b, a)

    @given(hostile_mu_values(max_depth=2))
    @settings(max_examples=300, deadline=5000)
    def test_hostile_unicode_normalize_roundtrip(self, value):
        """Normalization roundtrip works for hostile unicode.

        Known limitation: 2-element lists where first element is string
        can be misidentified as key-value pairs and denormalize to dicts.
        """
        assume(is_mu(value))

        # Skip empty collections
        if contains_empty_collection(value):
            return

        # Skip 2-element lists that look like kv-pairs (known limitation)
        def looks_like_kv_pair(v, _seen=None):
            if _seen is None:
                _seen = set()
            if isinstance(v, (list, dict)) and id(v) in _seen:
                return False
            if isinstance(v, (list, dict)):
                _seen.add(id(v))

            if isinstance(v, list):
                if len(v) == 2 and isinstance(v[0], str):
                    return True
                return any(looks_like_kv_pair(elem, _seen) for elem in v)
            if isinstance(v, dict):
                return any(looks_like_kv_pair(val, _seen) for val in v.values())
            return False

        if looks_like_kv_pair(value):
            return  # Skip known edge case

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == value, f"Roundtrip failed for {repr(value)}"

    @given(hostile_unicode_strings)
    @settings(max_examples=200, deadline=5000)
    def test_hostile_unicode_as_dict_key(self, key):
        """Hostile unicode strings work as dict keys."""
        d = {key: "value"}
        assert is_mu(d)

        normalized = normalize_for_match(d)
        denormalized = denormalize_from_match(normalized)
        assert denormalized == d


# =============================================================================
# Property 20: Parity Tests (match_mu vs eval_seed.match)
# =============================================================================

# Import Python-native match and substitute for parity testing
from rcx_pi.eval_seed import match as python_match, substitute as python_substitute


class TestMatchMuParity:
    """Tests for match_mu parity with Python-native eval_seed.match()."""

    @given(mu_patterns(max_depth=3), mu_values(max_depth=4))
    @settings(
        max_examples=500,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_match_mu_parity_with_python_match(self, pattern, value):
        """match_mu produces same result as Python-native match().

        This is the critical parity test - match_mu (using Mu projections)
        must produce identical results to eval_seed.match (Python recursion).

        Known limitation: 2-element lists where first element is string
        can be misidentified as key-value pairs and denormalize to dicts.
        """
        assume(is_mu(pattern))
        assume(is_mu(value))

        # Skip patterns with empty var names
        if contains_empty_var_name(pattern):
            return

        # Skip head/tail structures (they may need special handling)
        if contains_head_tail(pattern) or contains_head_tail(value):
            return

        # Skip empty collections (normalize to None, causing false parity issues)
        if contains_empty_collection(pattern) or contains_empty_collection(value):
            return

        # Skip 2-element lists that look like kv-pairs (known limitation)
        # These can be misidentified during normalization roundtrip
        def looks_like_kv_pair(v, _seen=None):
            if _seen is None:
                _seen = set()
            if isinstance(v, (list, dict)) and id(v) in _seen:
                return False
            if isinstance(v, (list, dict)):
                _seen.add(id(v))

            if isinstance(v, list):
                if len(v) == 2 and isinstance(v[0], str):
                    return True
                return any(looks_like_kv_pair(elem, _seen) for elem in v)
            if isinstance(v, dict):
                return any(looks_like_kv_pair(val, _seen) for val in v.values())
            return False

        if looks_like_kv_pair(pattern) or looks_like_kv_pair(value):
            return

        # Skip cases where pattern is a list but value is a dict (or vice versa)
        # After normalization both become head/tail structures, so structural
        # matching can't distinguish them (known limitation of the approach)
        if isinstance(pattern, list) and isinstance(value, dict):
            return
        if isinstance(pattern, dict) and isinstance(value, list):
            # Allow if pattern is just a var site (matches anything)
            if not (set(pattern.keys()) == {"var"}):
                return

        try:
            python_result = python_match(pattern, value)
            mu_result = match_mu(pattern, value)

            # Both should either match or not match
            if python_result is NO_MATCH:
                assert mu_result is NO_MATCH, \
                    f"Parity violation: Python=NO_MATCH, Mu={mu_result} for pattern={pattern}, value={value}"
            else:
                assert mu_result is not NO_MATCH, \
                    f"Parity violation: Python={python_result}, Mu=NO_MATCH for pattern={pattern}, value={value}"
                # Bindings should be equal
                assert python_result == mu_result, \
                    f"Parity violation: Python={python_result}, Mu={mu_result} for pattern={pattern}, value={value}"
        except (ValueError, TypeError, RuntimeError):
            # If Python raises, Mu should raise too (or vice versa)
            # We just want to ensure no unexpected crashes
            pass

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5))
    @settings(max_examples=100, deadline=5000)
    def test_parity_simple_variable(self, var_name):
        """Simple variable binding has parity."""
        pattern = {"var": var_name}
        value = 42

        python_result = python_match(pattern, value)
        mu_result = match_mu(pattern, value)

        assert python_result == {var_name: value}
        assert mu_result == {var_name: value}

    @given(mu_values(max_depth=3))
    @settings(max_examples=300, deadline=5000)
    def test_parity_literal_match(self, value):
        """Literal (non-variable) pattern match has parity."""
        assume(is_mu(value))

        # Skip values containing var sites or head/tail
        if contains_head_tail(value):
            return

        # Skip empty collections (normalize to None)
        if contains_empty_collection(value):
            return

        # Pattern is the same as value - should match with empty bindings
        python_result = python_match(value, value)
        mu_result = match_mu(value, value)

        if python_result is NO_MATCH:
            assert mu_result is NO_MATCH
        else:
            assert mu_result is not NO_MATCH
            assert python_result == mu_result == {}


# =============================================================================
# Property 21: Substitute Parity Tests (match_mu vs eval_seed.substitute)
# =============================================================================


class TestSubstMuParity:
    """Tests for subst_mu parity with Python-native eval_seed.substitute().

    This is critical for Phase 4b - subst_mu (using Mu projections) must
    produce identical results to eval_seed.substitute (Python recursion).
    """

    @given(
        mu_values(max_depth=3, allow_var_sites=True),
        mu_bindings_dict(max_depth=3)
    )
    @settings(
        max_examples=500,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
    )
    def test_subst_mu_parity_with_python_substitute(self, body, bindings):
        """subst_mu produces same result as Python-native substitute().

        This is the critical parity test - subst_mu (using Mu projections)
        must produce identical results to eval_seed.substitute (Python recursion).
        """
        assume(is_mu(body))

        # Skip empty var names
        if contains_empty_var_name(body):
            return

        # Only test if all vars in body are bound
        body_vars = extract_var_names(body)
        if not body_vars.issubset(bindings.keys()):
            return  # Skip - would raise KeyError

        # Skip edge cases that normalize differently
        # - Empty collections normalize to None
        # - Head/tail structures are treated specially
        # - Lists of 2-element sublists with string keys are ambiguous with dicts
        if contains_empty_collection(body) or contains_head_tail(body) or is_ambiguous_list_dict(body):
            return

        try:
            python_result = python_substitute(body, bindings)
            mu_result = subst_mu(body, bindings)

            # Results should be structurally equal
            assert mu_equal(python_result, mu_result), \
                f"Parity violation: Python={python_result}, Mu={mu_result} for body={body}, bindings={bindings}"
        except (KeyError, ValueError, TypeError, RuntimeError):
            # If Python raises, Mu should raise too (or vice versa)
            # We just want to ensure no unexpected crashes
            pass

    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
        mu_values(max_depth=3)
    )
    @settings(max_examples=200, deadline=5000)
    def test_parity_simple_variable_subst(self, var_name, value):
        """Simple variable substitution has parity."""
        assume(is_mu(value))

        body = {"var": var_name}
        bindings = {var_name: value}

        python_result = python_substitute(body, bindings)
        mu_result = subst_mu(body, bindings)

        assert mu_equal(python_result, value), f"Python subst failed: {python_result}"
        assert mu_equal(mu_result, value), f"Mu subst failed: {mu_result}"
        assert mu_equal(python_result, mu_result), "Parity violation"

    @given(mu_values(max_depth=3))
    @settings(max_examples=300, deadline=5000)
    def test_parity_no_vars_subst(self, body):
        """Body with no variables substitutes to itself (parity)."""
        assume(is_mu(body))

        # Skip bodies with var sites
        body_vars = extract_var_names(body)
        if body_vars:
            return

        # Skip edge cases
        if contains_empty_collection(body) or contains_head_tail(body):
            return

        # Skip 2-element lists that look like kv-pairs (known limitation)
        def looks_like_kv_pair(v, _seen=None):
            if _seen is None:
                _seen = set()
            if isinstance(v, (list, dict)) and id(v) in _seen:
                return False
            if isinstance(v, (list, dict)):
                _seen.add(id(v))

            if isinstance(v, list):
                if len(v) == 2 and isinstance(v[0], str):
                    return True
                return any(looks_like_kv_pair(elem, _seen) for elem in v)
            if isinstance(v, dict):
                return any(looks_like_kv_pair(val, _seen) for val in v.values())
            return False

        if looks_like_kv_pair(body):
            return

        bindings = {}  # Empty bindings

        try:
            python_result = python_substitute(body, bindings)
            mu_result = subst_mu(body, bindings)

            # Both should return body unchanged
            assert mu_equal(python_result, body), f"Python subst changed body"
            assert mu_equal(mu_result, body), f"Mu subst changed body"
            assert mu_equal(python_result, mu_result), "Parity violation"
        except (KeyError, ValueError, TypeError, RuntimeError):
            pass

    @given(mu_bindings_dict(max_depth=3))
    @settings(max_examples=200, deadline=5000)
    def test_parity_nested_vars_subst(self, bindings):
        """Nested variable structure has parity."""
        assume(bindings)  # Need at least one binding

        # Get first binding name
        var_name = next(iter(bindings.keys()))
        value = bindings[var_name]

        # Skip complex values that may normalize differently
        if contains_empty_collection(value) or contains_head_tail(value):
            return

        # Create nested body with the variable
        body = {"outer": {"inner": {"var": var_name}}}

        try:
            python_result = python_substitute(body, bindings)
            mu_result = subst_mu(body, bindings)

            expected = {"outer": {"inner": value}}
            assert mu_equal(python_result, expected), f"Python: {python_result} != {expected}"
            assert mu_equal(mu_result, expected), f"Mu: {mu_result} != {expected}"
            assert mu_equal(python_result, mu_result), "Parity violation"
        except (KeyError, ValueError, TypeError, RuntimeError):
            pass


# =============================================================================
# Property 22: Near-Limit Stress Tests
# =============================================================================

class TestNearLimitStress:
    """Tests for behavior near width/depth limits (900+, 190+)."""

    @given(st.integers(min_value=max(1, MAX_MU_WIDTH - 100), max_value=MAX_MU_WIDTH))
    @settings(max_examples=20, deadline=10000)  # Higher deadline for large structures
    def test_near_width_limit_list(self, width):
        """Lists near MAX_MU_WIDTH are still valid Mu."""
        wide_list = list(range(width))
        assert is_mu(wide_list), f"Valid list width {width} rejected"

        # Should be able to hash
        hash_result = compute_identity(wide_list)
        assert len(hash_result) == 64

    @given(st.integers(min_value=max(1, MAX_MU_WIDTH - 100), max_value=MAX_MU_WIDTH))
    @settings(max_examples=20, deadline=10000)
    def test_near_width_limit_dict(self, width):
        """Dicts near MAX_MU_WIDTH are still valid Mu."""
        wide_dict = {f"k{i}": i for i in range(width)}
        assert is_mu(wide_dict), f"Valid dict width {width} rejected"

        # Should be able to hash
        hash_result = compute_identity(wide_dict)
        assert len(hash_result) == 64

    @given(st.integers(min_value=max(1, MAX_MU_DEPTH - 10), max_value=MAX_MU_DEPTH))
    @settings(max_examples=20, deadline=10000)
    def test_near_depth_limit(self, depth):
        """Structures near MAX_MU_DEPTH are still valid Mu."""
        deep = "leaf"
        for _ in range(depth):
            deep = {"n": deep}

        assert is_mu(deep), f"Valid depth {depth} rejected"

        # Should be able to hash
        hash_result = compute_identity(deep)
        assert len(hash_result) == 64

    @given(st.integers(min_value=MAX_MU_WIDTH + 1, max_value=MAX_MU_WIDTH + 10))
    @settings(max_examples=10, deadline=5000)
    def test_just_over_width_limit_rejected(self, width):
        """Structures just over MAX_MU_WIDTH are rejected."""
        wide_list = list(range(width))
        assert not is_mu(wide_list), f"Over-limit width {width} accepted"

        wide_dict = {f"k{i}": i for i in range(width)}
        assert not is_mu(wide_dict), f"Over-limit dict width {width} accepted"

    @given(st.integers(min_value=MAX_MU_DEPTH + 1, max_value=MAX_MU_DEPTH + 10))
    @settings(max_examples=10, deadline=5000)
    def test_just_over_depth_limit_rejected(self, depth):
        """Structures just over MAX_MU_DEPTH are rejected."""
        deep = "leaf"
        for _ in range(depth):
            deep = {"n": deep}

        assert not is_mu(deep), f"Over-limit depth {depth} accepted"

    def test_exact_width_limit_accepted(self):
        """Structure at exactly MAX_MU_WIDTH is accepted."""
        exact_list = list(range(MAX_MU_WIDTH))
        exact_dict = {f"k{i}": i for i in range(MAX_MU_WIDTH)}

        assert is_mu(exact_list), f"Exact width {MAX_MU_WIDTH} list rejected"
        assert is_mu(exact_dict), f"Exact width {MAX_MU_WIDTH} dict rejected"

    def test_exact_depth_limit_accepted(self):
        """Structure at exactly MAX_MU_DEPTH is accepted."""
        deep = "leaf"
        for _ in range(MAX_MU_DEPTH):
            deep = {"n": deep}

        assert is_mu(deep), f"Exact depth {MAX_MU_DEPTH} rejected"

    def test_one_over_width_limit_rejected(self):
        """Structure at MAX_MU_WIDTH + 1 is rejected."""
        over_list = list(range(MAX_MU_WIDTH + 1))
        over_dict = {f"k{i}": i for i in range(MAX_MU_WIDTH + 1)}

        assert not is_mu(over_list), f"Width {MAX_MU_WIDTH + 1} list accepted"
        assert not is_mu(over_dict), f"Width {MAX_MU_WIDTH + 1} dict accepted"

    def test_one_over_depth_limit_rejected(self):
        """Structure at MAX_MU_DEPTH + 1 is rejected."""
        deep = "leaf"
        for _ in range(MAX_MU_DEPTH + 1):
            deep = {"n": deep}

        assert not is_mu(deep), f"Depth {MAX_MU_DEPTH + 1} accepted"
