"""
Kernel Bridge Fuzzer Tests

Property-based tests for kernel bridge functions:
- list_to_linked: Python list -> Mu linked list
- normalize_projection: Projection normalization

These functions bridge Python data to Mu structural representation.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from rcx_pi.selfhost.step_mu import list_to_linked, normalize_projection
from rcx_pi.selfhost.match_mu import (
    normalize_for_match,
    denormalize_from_match,
)
from rcx_pi.selfhost.mu_type import is_mu


# =============================================================================
# Test Data Strategies
# =============================================================================

# Valid Mu primitives
mu_primitive = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10000, max_value=10000),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=50),
)


@st.composite
def mu_value(draw, max_depth=2):
    """Generate valid Mu values up to given depth."""
    if max_depth <= 0:
        return draw(mu_primitive)

    return draw(st.one_of(
        mu_primitive,
        st.lists(mu_value(max_depth=max_depth - 1), max_size=3),
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            mu_value(max_depth=max_depth - 1),
            max_size=3
        ),
    ))


@st.composite
def projection_dict(draw, max_depth=2):
    """Generate valid projection dicts."""
    return {
        "pattern": draw(mu_value(max_depth=max_depth)),
        "body": draw(mu_value(max_depth=max_depth)),
    }


# =============================================================================
# list_to_linked Tests
# =============================================================================

class TestListToLinkedFuzzer:
    """Property-based tests for list_to_linked."""

    def test_empty_list_is_none(self):
        """Empty list converts to None."""
        result = list_to_linked([])
        assert result is None

    def test_single_element(self):
        """Single element list has None tail."""
        result = list_to_linked([42])
        assert result == {"head": 42, "tail": None}

    def test_two_elements(self):
        """Two elements produce nested linked list."""
        result = list_to_linked([1, 2])
        assert result == {"head": 1, "tail": {"head": 2, "tail": None}}

    @given(items=st.lists(mu_primitive, min_size=0, max_size=10))
    @settings(max_examples=100, deadline=5000)
    def test_length_preserved(self, items):
        """Length of linked list equals length of input list."""
        linked = list_to_linked(items)

        # Count elements in linked list
        count = 0
        current = linked
        while current is not None:
            assert isinstance(current, dict)
            assert "head" in current
            assert "tail" in current
            count += 1
            current = current["tail"]

        assert count == len(items)

    @given(items=st.lists(mu_primitive, min_size=1, max_size=10))
    @settings(max_examples=100, deadline=5000)
    def test_order_preserved(self, items):
        """Order of elements is preserved in linked list."""
        linked = list_to_linked(items)

        # Extract elements from linked list
        extracted = []
        current = linked
        while current is not None:
            extracted.append(current["head"])
            current = current["tail"]

        assert extracted == items

    @given(items=st.lists(mu_value(max_depth=1), min_size=0, max_size=5))
    @settings(max_examples=50, deadline=5000)
    def test_result_is_valid_mu(self, items):
        """Result is always valid Mu."""
        result = list_to_linked(items)
        assert is_mu(result)

    @given(items=st.lists(mu_primitive, min_size=0, max_size=10))
    @settings(max_examples=100, deadline=5000)
    def test_all_nodes_have_head_tail(self, items):
        """All non-None nodes have exactly head and tail keys."""
        linked = list_to_linked(items)

        current = linked
        while current is not None:
            assert isinstance(current, dict)
            assert set(current.keys()) == {"head", "tail"}
            current = current["tail"]

    def test_nested_list_elements(self):
        """List elements can themselves be lists."""
        items = [[1, 2], [3, 4]]
        result = list_to_linked(items)

        assert result["head"] == [1, 2]
        assert result["tail"]["head"] == [3, 4]
        assert result["tail"]["tail"] is None


# =============================================================================
# normalize_projection Tests
# =============================================================================

class TestNormalizeProjectionFuzzer:
    """Property-based tests for normalize_projection."""

    def test_simple_projection(self):
        """Simple projection normalizes both pattern and body."""
        proj = {"pattern": 1, "body": 2}
        result = normalize_projection(proj)

        assert "pattern" in result
        assert "body" in result
        # Both should be normalized (may be same value for primitives)
        assert result["pattern"] == normalize_for_match(1)
        assert result["body"] == normalize_for_match(2)

    @given(proj=projection_dict(max_depth=2))
    @settings(max_examples=100, deadline=5000)
    def test_has_pattern_and_body(self, proj):
        """Result always has pattern and body keys."""
        result = normalize_projection(proj)
        assert "pattern" in result
        assert "body" in result

    @given(proj=projection_dict(max_depth=2))
    @settings(max_examples=100, deadline=5000)
    def test_result_is_valid_mu(self, proj):
        """Result is always valid Mu."""
        result = normalize_projection(proj)
        assert is_mu(result)

    @given(proj=projection_dict(max_depth=2))
    @settings(max_examples=100, deadline=5000)
    def test_pattern_matches_normalize_for_match(self, proj):
        """Pattern equals normalize_for_match of original pattern."""
        result = normalize_projection(proj)
        expected_pattern = normalize_for_match(proj["pattern"])
        assert result["pattern"] == expected_pattern

    @given(proj=projection_dict(max_depth=2))
    @settings(max_examples=100, deadline=5000)
    def test_body_matches_normalize_for_match(self, proj):
        """Body equals normalize_for_match of original body."""
        result = normalize_projection(proj)
        expected_body = normalize_for_match(proj["body"])
        assert result["body"] == expected_body

    def test_preserves_var_sites(self):
        """Variable sites are preserved through normalization."""
        proj = {
            "pattern": {"var": "x"},
            "body": {"var": "x"}
        }
        result = normalize_projection(proj)

        # Var sites should be normalized but denormalizable back
        pattern_denorm = denormalize_from_match(result["pattern"])
        body_denorm = denormalize_from_match(result["body"])

        assert pattern_denorm == {"var": "x"}
        assert body_denorm == {"var": "x"}

    def test_list_pattern_normalized(self):
        """List patterns are converted to linked lists."""
        proj = {
            "pattern": [1, 2, 3],
            "body": "result"
        }
        result = normalize_projection(proj)

        # Pattern should be a linked list with type tag
        assert isinstance(result["pattern"], dict)
        assert result["pattern"].get("_type") == "list"
        assert "head" in result["pattern"]
        assert "tail" in result["pattern"]

    def test_dict_pattern_normalized(self):
        """Dict patterns are converted to kv-pair linked lists."""
        proj = {
            "pattern": {"a": 1, "b": 2},
            "body": "result"
        }
        result = normalize_projection(proj)

        # Pattern should be a linked list with dict type tag
        assert isinstance(result["pattern"], dict)
        assert result["pattern"].get("_type") == "dict"


# =============================================================================
# list_to_linked and normalize_projection Integration
# =============================================================================

class TestKernelBridgeIntegration:
    """Integration tests for kernel bridge functions."""

    def test_projection_list_to_linked(self):
        """Projections can be converted to linked list."""
        projs = [
            {"pattern": 1, "body": 2},
            {"pattern": 3, "body": 4},
        ]

        # Normalize each projection
        normalized = [normalize_projection(p) for p in projs]

        # Convert to linked list
        linked = list_to_linked(normalized)

        # Should be valid linked list
        assert linked is not None
        assert isinstance(linked, dict)
        assert "head" in linked
        assert "tail" in linked

        # First projection
        first = linked["head"]
        assert "pattern" in first
        assert "body" in first

        # Second projection
        second = linked["tail"]["head"]
        assert "pattern" in second
        assert "body" in second

    @given(projs=st.lists(projection_dict(max_depth=1), min_size=0, max_size=5))
    @settings(max_examples=50, deadline=5000)
    def test_projection_list_round_trip(self, projs):
        """Projections survive normalize -> list_to_linked."""
        # Normalize
        normalized = [normalize_projection(p) for p in projs]

        # Convert to linked list
        linked = list_to_linked(normalized)

        # Extract back to list
        extracted = []
        current = linked
        while current is not None:
            extracted.append(current["head"])
            current = current["tail"]

        # Should have same length
        assert len(extracted) == len(projs)

        # Each projection should have pattern and body
        for proj in extracted:
            assert "pattern" in proj
            assert "body" in proj


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestKernelBridgeEdgeCases:
    """Edge case tests for kernel bridge functions."""

    def test_list_with_none_elements(self):
        """List can contain None elements."""
        result = list_to_linked([None, None, None])
        assert result["head"] is None
        assert result["tail"]["head"] is None
        assert result["tail"]["tail"]["head"] is None
        assert result["tail"]["tail"]["tail"] is None

    def test_deeply_nested_elements(self):
        """List can contain deeply nested structures."""
        nested = {"a": {"b": {"c": 1}}}
        result = list_to_linked([nested])
        assert result["head"] == nested
        assert result["tail"] is None

    def test_normalize_with_empty_list_body(self):
        """Projection with empty list body normalizes correctly."""
        proj = {"pattern": "x", "body": []}
        result = normalize_projection(proj)
        # Empty list should become typed sentinel
        assert result["body"] == {"_type": "list"}

    def test_normalize_with_empty_dict_body(self):
        """Projection with empty dict body normalizes correctly."""
        proj = {"pattern": "x", "body": {}}
        result = normalize_projection(proj)
        # Empty dict should become typed sentinel
        assert result["body"] == {"_type": "dict"}

    def test_normalize_idempotent_for_primitives(self):
        """Normalizing primitives is idempotent."""
        for primitive in [None, True, False, 42, 3.14, "hello"]:
            proj = {"pattern": primitive, "body": primitive}
            result1 = normalize_projection(proj)
            # Normalizing the already-normalized projection
            proj2 = {"pattern": result1["pattern"], "body": result1["body"]}
            result2 = normalize_projection(proj2)
            # Should be the same
            assert result1 == result2
