"""
Denormalize Type Confusion Fuzzer (9-agent Fuzzer finding 2026-02-01)

Tests that denormalize_from_match correctly handles type confusion attacks.

Previous fuzzers only tested the happy path (roundtrip with valid linked lists).
This fuzzer attacks with malformed/malicious structures that could cause
type confusion during denormalization.

Gap addressed:
- Non-string type tags
- Unknown type tags
- Malformed kv-pair structures
- Mixed valid/invalid nested structures
"""

import pytest

pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.match_mu import denormalize_from_match
from rcx_pi.selfhost.mu_type import is_mu


# =============================================================================
# Type Confusion Strategies
# =============================================================================

@composite
def non_string_type_tags(draw):
    """Generate structures with non-string _type values."""
    type_val = draw(st.one_of(
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
        st.lists(st.text(max_size=10), max_size=3),
        st.dictionaries(st.text(max_size=5), st.integers(), max_size=3),
    ))

    return {"_type": type_val, "head": "value", "tail": None}


@composite
def unknown_type_tags(draw):
    """Generate structures with unknown string _type values."""
    unknown_types = draw(st.one_of(
        st.just("array"),
        st.just("object"),
        st.just("set"),
        st.just("tuple"),
        st.just("vector"),
        st.just("map"),
        st.just("LIST"),  # Wrong case
        st.just("DICT"),  # Wrong case
        st.just("List"),
        st.just("Dict"),
        st.just(""),
        st.just(" list"),  # Leading space
        st.just("list "),  # Trailing space
        st.text(min_size=1, max_size=20),  # Random strings
    ))

    return {"_type": unknown_types, "head": "value", "tail": None}


@composite
def malformed_kv_pairs(draw):
    """Generate structures that look like kv-pairs but are malformed."""
    return draw(st.one_of(
        # Missing inner tail
        st.just({"head": {"head": "key"}, "tail": None}),
        # Wrong inner structure
        st.just({"head": {"key": "val"}, "tail": None}),
        # Extra keys in inner
        st.just({"head": {"head": "key", "tail": "val", "extra": True}, "tail": None}),
        # Inner is primitive
        st.just({"head": "not_a_kv_pair", "tail": None}),
        # Inner is list
        st.just({"head": ["key", "val"], "tail": None}),
        # Inner tail is not proper structure
        st.just({"head": {"head": "key", "tail": "value_not_wrapped"}, "tail": None}),
        # Nested null kv-pair
        st.just({"head": {"head": None, "tail": {"head": "val", "tail": None}}, "tail": None}),
    ))


@composite
def mixed_valid_invalid_structures(draw):
    """Generate structures that mix valid and invalid elements."""
    # Valid list element followed by invalid
    valid_then_invalid = {
        "head": 1,
        "tail": {
            "head": {"broken": "structure"},  # Not a proper element
            "tail": None
        }
    }

    # Type-tagged with invalid nested content
    typed_with_bad_nested = {
        "_type": "list",
        "head": {"_type": 999, "head": "x", "tail": None},  # Invalid nested type
        "tail": None
    }

    return draw(st.one_of(
        st.just(valid_then_invalid),
        st.just(typed_with_bad_nested),
        st.just({
            "head": 1,
            "tail": {
                "head": 2,
                "tail": "not_a_node"  # Invalid tail in middle
            }
        }),
    ))


# =============================================================================
# Property 1: Non-String Type Tags Don't Cause Crashes
# =============================================================================

@given(non_string_type_tags())
@settings(
    max_examples=100,
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow]
)
def test_non_string_type_tags_no_crash(malformed_input):
    """Non-string type tags should not crash denormalization.

    The denormalizer should either:
    1. Ignore the invalid type tag and process as generic structure, OR
    2. Raise a clear error
    """
    try:
        result = denormalize_from_match(malformed_input)
        # If it succeeds, result must be valid Mu
        assert is_mu(result), f"Result is not valid Mu: {result}"
    except (ValueError, TypeError) as e:
        # Explicit rejection is acceptable
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 2: Unknown Type Tags Don't Cause Crashes
# =============================================================================

@given(unknown_type_tags())
@settings(
    max_examples=100,
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow]
)
def test_unknown_type_tags_no_crash(malformed_input):
    """Unknown string type tags should not crash denormalization.

    Only "list" and "dict" are valid type tags. Unknown values should:
    1. Be treated as generic structures, OR
    2. Raise a clear error
    """
    try:
        result = denormalize_from_match(malformed_input)
        # If it succeeds, result must be valid Mu
        assert is_mu(result), f"Result is not valid Mu: {result}"
    except (ValueError, TypeError) as e:
        # Explicit rejection is acceptable
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 3: Malformed KV-Pairs Don't Cause Crashes
# =============================================================================

@given(malformed_kv_pairs())
@settings(
    max_examples=100,
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow]
)
def test_malformed_kv_pairs_no_crash(malformed_input):
    """Malformed kv-pair structures should not crash denormalization.

    KV-pairs should have structure: {"head": key, "tail": {"head": val, "tail": null}}
    Malformed structures should be handled gracefully.
    """
    try:
        result = denormalize_from_match(malformed_input)
        # If it succeeds, result must be valid Mu
        assert is_mu(result), f"Result is not valid Mu: {result}"
    except (ValueError, TypeError) as e:
        # Explicit rejection is acceptable
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 4: Mixed Valid/Invalid Structures Don't Cause Crashes
# =============================================================================

@given(mixed_valid_invalid_structures())
@settings(
    max_examples=50,
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow]
)
def test_mixed_valid_invalid_no_crash(malformed_input):
    """Structures mixing valid and invalid elements should not crash."""
    try:
        result = denormalize_from_match(malformed_input)
        # If it succeeds, result must be valid Mu
        assert is_mu(result), f"Result is not valid Mu: {result}"
    except (ValueError, TypeError) as e:
        # Explicit rejection is acceptable
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 5: Valid Type Tags Produce Correct Types
# =============================================================================

class TestValidTypeTagBehavior:
    """Verify valid type tags produce the expected Python types."""

    def test_list_type_tag_produces_list(self):
        """_type: 'list' should denormalize to Python list."""
        # Simple list: [1, 2]
        linked_list = {
            "_type": "list",
            "head": 1,
            "tail": {
                "_type": "list",
                "head": 2,
                "tail": None
            }
        }
        result = denormalize_from_match(linked_list)
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    def test_dict_type_tag_produces_dict(self):
        """_type: 'dict' should denormalize to Python dict."""
        # Simple dict: {"key": "value"}
        linked_dict = {
            "_type": "dict",
            "head": {
                "head": "key",
                "tail": {
                    "head": "value",
                    "tail": None
                }
            },
            "tail": None
        }
        result = denormalize_from_match(linked_dict)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    def test_empty_list_type_tag(self):
        """Empty _type: 'list' should denormalize to empty list."""
        empty_list = {"_type": "list"}
        result = denormalize_from_match(empty_list)
        assert result == [], f"Expected [], got {result}"

    def test_empty_dict_type_tag(self):
        """Empty _type: 'dict' should denormalize to empty dict."""
        empty_dict = {"_type": "dict"}
        result = denormalize_from_match(empty_dict)
        assert result == {}, f"Expected {{}}, got {result}"


# =============================================================================
# Property 6: Deeply Nested Type Tags
# =============================================================================

@given(st.integers(min_value=1, max_value=20))
@settings(max_examples=20, deadline=10000)
def test_deeply_nested_type_tags(depth):
    """Deeply nested structures with type tags should be handled."""
    # Build nested list structure
    value = None
    for i in range(depth):
        value = {"_type": "list", "head": i, "tail": value}

    result = denormalize_from_match(value)
    assert is_mu(result)
    # Should be a list of integers
    assert isinstance(result, list)


# =============================================================================
# Property 7: Type Tag Whitelist Enforcement
# =============================================================================

class TestTypeTagWhitelist:
    """Verify only whitelisted type tags are honored."""

    VALID_TAGS = ["list", "dict"]
    INVALID_TAGS = ["array", "set", "tuple", "vector", "map", "LIST", "DICT", ""]

    def test_valid_tags_accepted(self):
        """Valid type tags should be processed correctly."""
        for tag in self.VALID_TAGS:
            structure = {"_type": tag}
            result = denormalize_from_match(structure)
            # Should produce empty list or dict
            assert result == [] or result == {}

    def test_invalid_tags_handled(self):
        """Invalid type tags should be handled gracefully (not crash)."""
        for tag in self.INVALID_TAGS:
            structure = {"_type": tag, "head": "x", "tail": None}
            try:
                result = denormalize_from_match(structure)
                # If it succeeds, result must be valid Mu
                assert is_mu(result)
            except (ValueError, TypeError):
                # Explicit rejection is also acceptable
                pass


# =============================================================================
# Property 8: Circular Reference Detection in Denormalize
# =============================================================================

class TestDenormalizeCircularDetection:
    """Verify circular references are detected during denormalization."""

    def test_circular_linked_list(self):
        """Circular linked list should be detected."""
        circular = {"head": 1, "tail": None}
        circular["tail"] = circular

        with pytest.raises(ValueError, match="[Cc]ircular"):
            denormalize_from_match(circular)

    def test_circular_in_element(self):
        """Circular reference in list element should be detected.

        Note: The error may be caught at different levels:
        - ValueError with 'circular' in denormalize
        - TypeError during Mu validation (circular dict can't be serialized)
        """
        element = {"inner": None}
        element["inner"] = element

        structure = {"head": element, "tail": None}

        # Circular reference should cause either ValueError or TypeError
        with pytest.raises((ValueError, TypeError)):
            denormalize_from_match(structure)
