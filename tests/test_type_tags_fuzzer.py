"""
Property-Based Fuzzing for Phase 6c Type Tags Implementation using Hypothesis.

This test suite generates 1000+ random inputs to stress-test:
- Type tag injection resistance (security)
- List/dict discrimination after normalization
- Iterative roundtrip property
- Legacy compatibility (head/tail without _type)
- Circular reference detection

Run with: pytest tests/test_type_tags_fuzzer.py --hypothesis-show-statistics -v

Phase 6c: Property-based testing for type-tagged normalization.

Requires: pip install hypothesis
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
    is_dict_linked_list,
)
from rcx_pi.selfhost.classify_mu import classify_linked_list


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
def mu_values(draw, max_depth=5):
    """Generate valid Mu values recursively."""
    if max_depth <= 0:
        return draw(mu_primitives)

    strategies = [mu_primitives]

    # Add lists (limited size for performance)
    strategies.append(
        st.lists(
            st.deferred(lambda: mu_values(max_depth=max_depth-1)),
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
            st.deferred(lambda: mu_values(max_depth=max_depth-1)),
            max_size=4
        )
    )

    return draw(st.one_of(*strategies))


@composite
def malicious_type_tagged_structures(draw):
    """Generate structures with invalid _type tags (for injection testing)."""
    invalid_type = draw(st.one_of(
        st.just("malicious"),
        st.just("eval"),
        st.just("__import__"),
        st.just(""),
        st.just(123),  # Non-string type
        st.just(None),
        st.just(True),
        st.just([]),
        st.just({}),
    ))

    head = draw(mu_values(max_depth=2))
    tail = draw(st.one_of(st.none(), mu_values(max_depth=1)))

    return {"_type": invalid_type, "head": head, "tail": tail}


@composite
def legacy_head_tail_structures(draw):
    """Generate head/tail structures WITHOUT _type tags (for legacy testing)."""
    # Build a linked list without type tags
    length = draw(st.integers(min_value=0, max_value=5))
    tail = None
    for _ in range(length):
        head = draw(mu_values(max_depth=1))
        tail = {"head": head, "tail": tail}
    return tail


@composite
def ambiguous_list_dict_pairs(draw):
    """Generate pairs that test list/dict discrimination.

    Phase 6c must keep [["a", 1]] distinct from {"a": 1}.
    """
    key = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=("L",),
            min_codepoint=ord('a'),
            max_codepoint=ord('z')
        ),
        min_size=1,
        max_size=5
    ))
    value = draw(mu_values(max_depth=2))

    # Create both forms
    as_list = [[key, value]]
    as_dict = {key: value}

    return (as_list, as_dict)


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


# =============================================================================
# Property 1: Iterative Roundtrip (Phase 6c Critical Property)
# =============================================================================

class TestIterativeRoundtrip:
    """Tests for normalize(denormalize(normalize(x))) == normalize(x)."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=5000)
    def test_normalize_denormalize_normalize_idempotency(self, value):
        """normalize(denormalize(normalize(x))) == normalize(x).

        This is the CRITICAL property for Phase 6c iterative implementation.
        If normalization is correct, denormalizing then re-normalizing should
        produce the same result.
        """
        assume(is_mu(value))

        # Skip empty collections (normalize to None, can't distinguish [] vs {})
        if contains_empty_collection(value):
            return

        normalized_once = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized_once)
        normalized_twice = normalize_for_match(denormalized)

        assert mu_equal(normalized_once, normalized_twice), \
            f"Iterative roundtrip failed: {value} -> {normalized_once} -> {denormalized} -> {normalized_twice}"


# =============================================================================
# Property 2: Type Tag Preservation (Phase 6c Type Tagging)
# =============================================================================

class TestTypeTagPreservation:
    """Tests that type tags are correctly applied during normalization."""

    @given(st.lists(mu_values(max_depth=2), min_size=1, max_size=10))
    @settings(max_examples=500, deadline=5000)
    def test_lists_get_list_type_tag(self, value):
        """Non-empty lists normalize with _type='list' at root."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)

        # Non-empty list should have type tag at root
        assert isinstance(normalized, dict), f"Normalized list is not dict: {normalized}"
        assert "_type" in normalized, f"Normalized list missing _type: {normalized}"
        assert normalized["_type"] == "list", f"List has wrong type: {normalized['_type']}"

    @given(st.dictionaries(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
        mu_values(max_depth=2),
        min_size=1,
        max_size=10
    ))
    @settings(max_examples=500, deadline=5000)
    def test_dicts_get_dict_type_tag(self, value):
        """Non-empty dicts normalize with _type='dict' at root."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)

        # Non-empty dict should have type tag at root
        assert isinstance(normalized, dict), f"Normalized dict is not dict: {normalized}"
        assert "_type" in normalized, f"Normalized dict missing _type: {normalized}"
        assert normalized["_type"] == "dict", f"Dict has wrong type: {normalized['_type']}"

    @given(mu_values(max_depth=3))
    @settings(max_examples=300, deadline=5000)
    def test_primitives_have_no_type_tag(self, value):
        """Primitives (non-collection types) don't get type tags."""
        assume(is_mu(value))
        assume(not isinstance(value, (list, dict)))

        normalized = normalize_for_match(value)

        # Primitives should normalize to themselves (no type tag)
        if isinstance(normalized, dict):
            assert "_type" not in normalized or normalized.get("var") is not None, \
                f"Primitive got unexpected type tag: {value} -> {normalized}"


# =============================================================================
# Property 3: Type Tag Injection Resistance (Phase 6c Security)
# =============================================================================

class TestTypeTagInjectionResistance:
    """Tests that invalid _type values are rejected."""

    @given(malicious_type_tagged_structures())
    @settings(max_examples=300, deadline=5000)
    def test_denormalize_rejects_invalid_type_tags(self, malicious):
        """denormalize_from_match raises ValueError for invalid _type values."""
        # Only test if _type is a string (non-strings are handled differently)
        _type = malicious.get("_type")
        if not isinstance(_type, str):
            return

        if _type not in VALID_TYPE_TAGS:
            with pytest.raises(ValueError, match="Invalid type tag"):
                denormalize_from_match(malicious)

    @given(st.text(max_size=20))
    @settings(max_examples=200, deadline=5000)
    def test_validate_type_tag_whitelist(self, tag):
        """validate_type_tag only accepts whitelisted values."""
        if tag in VALID_TYPE_TAGS:
            validate_type_tag(tag)  # Should not raise
        else:
            with pytest.raises(ValueError, match="Invalid type tag"):
                validate_type_tag(tag)

    @given(malicious_type_tagged_structures())
    @settings(max_examples=200, deadline=5000)
    def test_is_dict_linked_list_rejects_invalid_types(self, malicious):
        """is_dict_linked_list returns False for invalid type tags."""
        result = is_dict_linked_list(malicious)

        # Invalid type tags should return False (not crash)
        assert isinstance(result, bool)

        _type = malicious.get("_type")
        if isinstance(_type, str) and _type not in VALID_TYPE_TAGS:
            assert result is False, f"Invalid type tag accepted: {_type}"

    @given(malicious_type_tagged_structures())
    @settings(max_examples=200, deadline=5000)
    def test_classify_linked_list_handles_invalid_types(self, malicious):
        """classify_linked_list returns 'list' for invalid type tags."""
        result = classify_linked_list(malicious)

        # Should always return a valid classification
        assert result in ["list", "dict"]

        _type = malicious.get("_type")
        # Non-string or unknown string types should return "list"
        if not isinstance(_type, str) or _type not in VALID_TYPE_TAGS:
            assert result == "list", f"Invalid type tag not rejected: {_type}"


# =============================================================================
# Property 4: Legacy Compatibility (Head/Tail Without _type)
# =============================================================================

class TestLegacyCompatibility:
    """Tests that legacy head/tail structures (no _type) still work."""

    @given(legacy_head_tail_structures())
    @settings(max_examples=300, deadline=5000)
    def test_legacy_structures_denormalize_without_crash(self, legacy):
        """Legacy head/tail structures denormalize without crashing."""
        assume(is_mu(legacy))

        try:
            result = denormalize_from_match(legacy)
            assert is_mu(result), f"Denormalized legacy is not Mu: {result}"
        except ValueError:
            # Circular reference or invalid structure - acceptable
            pass

    @given(legacy_head_tail_structures())
    @settings(max_examples=200, deadline=5000)
    def test_classify_handles_legacy_structures(self, legacy):
        """classify_linked_list handles legacy structures correctly."""
        assume(is_mu(legacy))

        try:
            result = classify_linked_list(legacy)
            assert result in ["list", "dict"], f"Invalid classification: {result}"
        except ValueError:
            # Circular reference - acceptable
            pass


# =============================================================================
# Property 5: List/Dict Discrimination (Phase 6c Critical Fix)
# =============================================================================

class TestListDictDiscrimination:
    """Tests that [["a", 1]] stays distinct from {"a": 1} after roundtrip.

    This is the PRIMARY BUG that Phase 6c fixes. Before type tags, these
    normalized to identical structures and couldn't be distinguished.
    """

    @given(ambiguous_list_dict_pairs())
    @settings(max_examples=500, deadline=5000)
    def test_list_vs_dict_roundtrip_discrimination(self, pair):
        """[["a", 1]] and {"a": 1} roundtrip to different values."""
        as_list, as_dict = pair

        # Skip if value contains empty collections (normalize to None, known limitation)
        if contains_empty_collection(as_list) or contains_empty_collection(as_dict):
            return

        # Normalize both
        norm_list = normalize_for_match(as_list)
        norm_dict = normalize_for_match(as_dict)

        # Phase 6c: Type tags make them distinguishable
        # Lists have _type="list", dicts have _type="dict"
        assert not mu_equal(norm_list, norm_dict), \
            f"List and dict normalized to same structure: list={norm_list}, dict={norm_dict}"

        # Denormalize both
        denorm_list = denormalize_from_match(norm_list)
        denorm_dict = denormalize_from_match(norm_dict)

        # They should roundtrip to their original forms
        assert denorm_list == as_list, f"List roundtrip failed: {as_list} -> {denorm_list}"
        assert denorm_dict == as_dict, f"Dict roundtrip failed: {as_dict} -> {denorm_dict}"

        # They should be different
        assert denorm_list != denorm_dict, \
            f"List and dict denormalized to same value: {denorm_list}"

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
           mu_values(max_depth=2))
    @settings(max_examples=300, deadline=5000)
    def test_nested_list_vs_dict_discrimination(self, key, value):
        """Nested structures maintain list/dict distinction."""
        # Skip if value contains empty collections (normalize to None, known limitation)
        if contains_empty_collection(value):
            return

        # Wrapper with both list and dict versions
        as_list = {"data": [[key, value]]}
        as_dict = {"data": {key: value}}

        # Roundtrip both
        list_rt = denormalize_from_match(normalize_for_match(as_list))
        dict_rt = denormalize_from_match(normalize_for_match(as_dict))

        # They should stay different
        assert list_rt == as_list, f"Nested list roundtrip failed"
        assert dict_rt == as_dict, f"Nested dict roundtrip failed"
        assert list_rt != dict_rt, f"Nested list/dict became identical"


# =============================================================================
# Property 6: Determinism
# =============================================================================

class TestNormalizationDeterminism:
    """Tests that normalization is deterministic."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=5000)
    def test_normalize_is_deterministic(self, value):
        """normalize_for_match produces same output every time."""
        assume(is_mu(value))

        norm1 = normalize_for_match(value)
        norm2 = normalize_for_match(value)
        norm3 = normalize_for_match(value)

        assert mu_equal(norm1, norm2), f"Normalization non-deterministic: {norm1} != {norm2}"
        assert mu_equal(norm2, norm3), f"Normalization non-deterministic: {norm2} != {norm3}"

    @given(mu_values(max_depth=4))
    @settings(max_examples=300, deadline=5000)
    def test_denormalize_is_deterministic(self, value):
        """denormalize_from_match produces same output every time."""
        assume(is_mu(value))

        denorm1 = denormalize_from_match(value)
        denorm2 = denormalize_from_match(value)
        denorm3 = denormalize_from_match(value)

        assert denorm1 == denorm2, f"Denormalization non-deterministic: {denorm1} != {denorm2}"
        assert denorm2 == denorm3, f"Denormalization non-deterministic: {denorm2} != {denorm3}"


# =============================================================================
# Property 7: Circular Reference Detection
# =============================================================================

class TestCircularReferenceDetection:
    """Tests that circular references are detected and raise ValueError."""

    def test_circular_list_in_normalize_raises(self):
        """Circular reference in list raises ValueError during normalization."""
        circular = [1, 2]
        circular.append(circular)  # Creates cycle

        with pytest.raises(ValueError, match="Circular reference"):
            normalize_for_match(circular)

    def test_circular_dict_in_normalize_raises(self):
        """Circular reference in dict raises ValueError during normalization."""
        circular = {"a": 1}
        circular["self"] = circular  # Creates cycle

        with pytest.raises(ValueError, match="Circular reference"):
            normalize_for_match(circular)

    def test_circular_in_denormalize_raises(self):
        """Circular reference in linked list raises ValueError during denormalization."""
        # Manually create circular linked list
        node1 = {"head": 1, "tail": None}
        node2 = {"head": 2, "tail": node1}
        node1["tail"] = node2  # Creates cycle

        with pytest.raises(ValueError, match="Circular reference"):
            denormalize_from_match(node1)


# =============================================================================
# Property 8: No Crash on Valid Inputs
# =============================================================================

class TestNoCrashOnValidInputs:
    """Tests that valid inputs don't cause unexpected crashes."""

    @given(mu_values(max_depth=4))
    @settings(max_examples=500, deadline=5000)
    def test_normalize_never_crashes_on_valid_mu(self, value):
        """normalize_for_match handles any valid Mu without unexpected crashes."""
        assume(is_mu(value))

        try:
            result = normalize_for_match(value)
            assert is_mu(result), f"Normalized result is not Mu: {result}"
        except ValueError as e:
            # Only circular reference errors are acceptable
            assert "Circular reference" in str(e), f"Unexpected ValueError: {e}"

    @given(mu_values(max_depth=4))
    @settings(max_examples=300, deadline=5000)
    def test_denormalize_never_crashes_on_valid_mu(self, value):
        """denormalize_from_match handles any valid Mu without unexpected crashes."""
        assume(is_mu(value))

        try:
            result = denormalize_from_match(value)
            assert is_mu(result), f"Denormalized result is not Mu: {result}"
        except ValueError as e:
            # Only circular reference or invalid type tag errors are acceptable
            assert "Circular reference" in str(e) or "Invalid type tag" in str(e), \
                f"Unexpected ValueError: {e}"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for specific edge cases."""

    def test_empty_list_vs_empty_dict(self):
        """Empty list and empty dict both normalize to None."""
        assert normalize_for_match([]) is None
        assert normalize_for_match({}) is None

    def test_single_element_list_has_type_tag(self):
        """Single-element list gets type tag."""
        normalized = normalize_for_match([42])
        assert isinstance(normalized, dict)
        assert normalized.get("_type") == "list"

    def test_single_kv_dict_has_type_tag(self):
        """Single key-value dict gets type tag."""
        normalized = normalize_for_match({"a": 1})
        assert isinstance(normalized, dict)
        assert normalized.get("_type") == "dict"

    def test_nested_empty_collections(self):
        """Nested empty collections normalize correctly."""
        value = {"outer": {"inner": []}}
        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)
        # Inner [] becomes None
        assert denormalized == {"outer": {"inner": None}}

    def test_mixed_valid_and_invalid_type_tags(self):
        """Structure with mix of valid and invalid type tags."""
        # Valid outer, invalid inner
        structure = {
            "_type": "dict",
            "head": {"head": "key", "tail": {"head": {"_type": "malicious", "head": 1, "tail": None}, "tail": None}},
            "tail": None
        }
        # Inner invalid type tag should be rejected during denormalization
        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(structure)
