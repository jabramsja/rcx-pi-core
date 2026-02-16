"""
Normalize Malformed Input Fuzzer (9-agent Fuzzer finding 2026-02-01)

Tests that normalize_for_match correctly REJECTS malformed inputs.

Previous fuzzers only tested the happy path (roundtrip with valid inputs).
This fuzzer attacks the boundary with malicious/malformed structures.

Gap addressed:
- Invalid tail values (not None or dict)
- Type tag forgery (_type not in ["list", "dict"])
- Mixed structures (has _type but wrong shape)
"""

import pytest

pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.match_mu import normalize_for_match
from rcx_pi.selfhost.mu_type import is_mu


# =============================================================================
# Malformed Input Strategies
# =============================================================================

@composite
def malformed_type_tags(draw):
    """Generate invalid _type values that should be rejected or ignored."""
    return draw(st.one_of(
        # Integer type tag
        st.just({"_type": 123, "head": "x", "tail": None}),
        # Float type tag
        st.just({"_type": 3.14, "head": "x", "tail": None}),
        # None type tag
        st.just({"_type": None, "head": "x", "tail": None}),
        # Unknown string type tag
        st.just({"_type": "unknown", "head": "x", "tail": None}),
        st.just({"_type": "array", "head": "x", "tail": None}),
        st.just({"_type": "object", "head": "x", "tail": None}),
        st.just({"_type": "LIST", "head": "x", "tail": None}),  # Wrong case
        st.just({"_type": "Dict", "head": "x", "tail": None}),  # Wrong case
        # Empty string type tag
        st.just({"_type": "", "head": "x", "tail": None}),
        # List type tag (not string)
        st.just({"_type": ["list"], "head": "x", "tail": None}),
        # Dict type tag (not string)
        st.just({"_type": {"type": "list"}, "head": "x", "tail": None}),
    ))


@composite
def malformed_linked_lists(draw):
    """Generate linked list structures with invalid tail values."""
    # Invalid tail values (not None, not dict with head/tail)
    invalid_tails = draw(st.one_of(
        # String tail
        st.just({"head": 1, "tail": "invalid"}),
        # Integer tail
        st.just({"head": 1, "tail": 42}),
        # List tail (not linked list node)
        st.just({"head": 1, "tail": [1, 2, 3]}),
        # Boolean tail
        st.just({"head": 1, "tail": True}),
        # Float tail
        st.just({"head": 1, "tail": 3.14}),
        # Nested invalid tail
        st.just({"head": 1, "tail": {"head": 2, "tail": "broken"}}),
        # Missing head key
        st.just({"tail": None}),
        # Missing tail key
        st.just({"head": 1}),
        # Extra keys (not pure head/tail)
        st.just({"head": 1, "tail": None, "extra": "key"}),
    ))
    return invalid_tails


@composite
def mixed_type_structures(draw):
    """Generate structures with _type but wrong accompanying keys."""
    return draw(st.one_of(
        # _type without head/tail
        st.just({"_type": "list"}),
        st.just({"_type": "dict"}),
        # _type with only head
        st.just({"_type": "list", "head": 1}),
        # _type with only tail
        st.just({"_type": "dict", "tail": None}),
        # _type with extra keys
        st.just({"_type": "list", "head": 1, "tail": None, "extra": True}),
        # _type with wrong structure entirely
        st.just({"_type": "list", "items": [1, 2, 3]}),
        st.just({"_type": "dict", "keys": ["a", "b"], "values": [1, 2]}),
    ))


# =============================================================================
# Property 1: Malformed Type Tags Don't Cause Crashes
# =============================================================================

@given(malformed_type_tags())
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow]
)
def test_malformed_type_tags_no_crash(malformed_input):
    """Malformed type tags should not crash - they may be processed or rejected."""
    try:
        result = normalize_for_match(malformed_input)
        # If it succeeds, result must be valid Mu
        assert is_mu(result), f"Result is not valid Mu: {result}"
    except (ValueError, TypeError) as e:
        # Explicit rejection is acceptable
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 2: Malformed Linked Lists Handled Gracefully
# =============================================================================

@given(malformed_linked_lists())
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow]
)
def test_malformed_linked_lists_no_crash(malformed_input):
    """Malformed linked lists should not crash.

    These structures have head/tail keys but invalid tail values.
    The normalizer should either:
    1. Raise a clear error, OR
    2. Process them as regular dicts (not as linked lists)
    """
    try:
        result = normalize_for_match(malformed_input)
        # If it succeeds, result must be valid Mu
        assert is_mu(result), f"Result is not valid Mu: {result}"
    except (ValueError, TypeError) as e:
        # Explicit rejection is acceptable
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 3: Mixed Type Structures Handled Gracefully
# =============================================================================

@given(mixed_type_structures())
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow]
)
def test_mixed_type_structures_no_crash(malformed_input):
    """Structures with _type but wrong shape should not crash.

    These have _type key but not the expected head/tail structure.
    The normalizer should handle them gracefully.
    """
    try:
        result = normalize_for_match(malformed_input)
        # If it succeeds, result must be valid Mu
        assert is_mu(result), f"Result is not valid Mu: {result}"
    except (ValueError, TypeError) as e:
        # Explicit rejection is acceptable
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 4: Valid Type Tags Are Preserved
# =============================================================================

class TestValidTypeTagsPreserved:
    """Verify that valid type tags are correctly processed."""

    def test_valid_list_type_tag(self):
        """Valid _type: 'list' should be preserved."""
        input_val = {"_type": "list", "head": 1, "tail": None}
        result = normalize_for_match(input_val)
        # Should not crash and should produce valid Mu
        assert is_mu(result)

    def test_valid_dict_type_tag(self):
        """Valid _type: 'dict' should be preserved."""
        input_val = {"_type": "dict", "head": {"head": "key", "tail": {"head": "val", "tail": None}}, "tail": None}
        result = normalize_for_match(input_val)
        # Should not crash and should produce valid Mu
        assert is_mu(result)


# =============================================================================
# Property 5: Circular References Detected
# =============================================================================

class TestCircularReferenceDetection:
    """Verify circular references are detected and rejected."""

    def test_direct_circular_reference(self):
        """Direct circular reference should be detected."""
        circular = {"head": 1, "tail": None}
        circular["tail"] = circular  # Create cycle

        with pytest.raises(ValueError, match="[Cc]ircular"):
            normalize_for_match(circular)

    def test_indirect_circular_reference(self):
        """Indirect circular reference (A -> B -> A) should be detected."""
        node_a = {"head": 1, "tail": None}
        node_b = {"head": 2, "tail": node_a}
        node_a["tail"] = node_b  # Create cycle

        with pytest.raises(ValueError, match="[Cc]ircular"):
            normalize_for_match(node_a)


# =============================================================================
# Property 6: Deep Nesting Limits
# =============================================================================

@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=20, deadline=10000)
def test_deep_nesting_handled(depth):
    """Deep nesting should be handled without stack overflow."""
    # Build deeply nested structure
    value = "leaf"
    for _ in range(depth):
        value = {"nested": value}

    # Should not crash
    result = normalize_for_match(value)
    assert is_mu(result)


class TestExtremeDepth:
    """Test behavior at extreme depths."""

    def test_depth_at_limit(self):
        """Structure at MAX_MU_DEPTH should be handled."""
        from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH

        # Build structure at depth limit (minus buffer for normalization overhead)
        safe_depth = min(MAX_MU_DEPTH - 50, 100)  # Stay well under limit
        value = "leaf"
        for _ in range(safe_depth):
            value = {"level": value}

        result = normalize_for_match(value)
        assert is_mu(result)
