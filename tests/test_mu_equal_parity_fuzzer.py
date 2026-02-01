"""
Parity fuzzer for mu_equal usage in binding conflict detection.

This fuzzer verifies that the mu_equal-based binding conflict detection
(for non-linear patterns) behaves identically to the old json.dumps approach.

Non-linear patterns: when the same variable appears multiple times in a pattern,
all occurrences must bind to structurally equal values.

Example:
  pattern:  [{"var": "x"}, {"var": "x"}]
  input:    [1, 1]         -> matches (x=1 both times)
  input:    [1, 2]         -> NO_MATCH (x binds to different values)

This is CRITICAL for EngineNews closure detection (Rule 2.2◇) which relies
on detecting when state hasn't changed between cycles.
"""

import json
from hypothesis import given, strategies as st, settings

from rcx_pi.selfhost.eval_seed import match, NO_MATCH
from rcx_pi.selfhost.mu_type import mu_equal


# Strategy for generating valid Mu values
mu_scalar = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    st.text(min_size=0, max_size=20),
    st.booleans(),
    st.none(),
)


@st.composite
def mu_value(draw, max_depth=3):
    """Generate a valid Mu value with controlled depth."""
    if max_depth <= 0:
        return draw(mu_scalar)

    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        return draw(mu_scalar)
    elif choice == 1:
        # List (limited size for performance)
        return draw(st.lists(mu_value(max_depth=max_depth - 1), min_size=0, max_size=3))
    else:
        # Dict (limited size for performance)
        return draw(st.dictionaries(
            st.text(min_size=1, max_size=5, alphabet="abcdefghij"),
            mu_value(max_depth=max_depth - 1),
            min_size=0,
            max_size=3,
        ))


class TestNonLinearPatternParity:
    """Test that mu_equal correctly detects binding conflicts in non-linear patterns."""

    @given(value=mu_value(max_depth=2))
    @settings(max_examples=200, deadline=None)
    def test_same_value_binds_successfully(self, value):
        """Pattern [x, x] should match [v, v] for any value v."""
        pattern = [{"var": "x"}, {"var": "x"}]
        input_val = [value, value]

        result = match(pattern, input_val)

        # Should always match when both elements are identical
        assert result != NO_MATCH, f"Should match identical values: {value}"
        assert "x" in result
        assert mu_equal(result["x"], value)

    @given(val1=mu_value(max_depth=2), val2=mu_value(max_depth=2))
    @settings(max_examples=200, deadline=None)
    def test_different_values_conflict_correctly(self, val1, val2):
        """Pattern [x, x] should NO_MATCH for [v1, v2] when v1 != v2."""
        pattern = [{"var": "x"}, {"var": "x"}]
        input_val = [val1, val2]

        result = match(pattern, input_val)

        # Match iff values are mu_equal
        values_equal = mu_equal(val1, val2)

        if values_equal:
            assert result != NO_MATCH, f"Should match when values are equal: {val1}"
        else:
            assert result is NO_MATCH, f"Should NOT match different values: {val1} vs {val2}"

    @given(value=mu_value(max_depth=2))
    @settings(max_examples=100, deadline=None)
    def test_dict_non_linear_pattern(self, value):
        """Non-linear patterns in dicts: {"a": x, "b": x} matches {"a": v, "b": v}."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        input_val = {"a": value, "b": value}

        result = match(pattern, input_val)

        assert result != NO_MATCH, f"Should match identical values in dict: {value}"
        assert "x" in result
        assert mu_equal(result["x"], value)

    @given(val1=mu_value(max_depth=2), val2=mu_value(max_depth=2))
    @settings(max_examples=100, deadline=None)
    def test_dict_non_linear_conflict(self, val1, val2):
        """Dict pattern {"a": x, "b": x} conflicts when a != b."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        input_val = {"a": val1, "b": val2}

        result = match(pattern, input_val)
        values_equal = mu_equal(val1, val2)

        if values_equal:
            assert result != NO_MATCH
        else:
            assert result is NO_MATCH

    @given(value=mu_value(max_depth=2))
    @settings(max_examples=100, deadline=None)
    def test_nested_non_linear_pattern(self, value):
        """Nested non-linear: [[x], [x]] matches [[v], [v]]."""
        pattern = [[{"var": "x"}], [{"var": "x"}]]
        input_val = [[value], [value]]

        result = match(pattern, input_val)

        assert result != NO_MATCH
        assert "x" in result
        assert mu_equal(result["x"], value)


class TestMuEqualJsonDumpsParity:
    """Verify mu_equal produces same results as json.dumps comparison."""

    @given(val1=mu_value(max_depth=3), val2=mu_value(max_depth=3))
    @settings(max_examples=500, deadline=None)
    def test_mu_equal_matches_json_dumps(self, val1, val2):
        """mu_equal should produce same result as json.dumps comparison."""
        # The old approach
        json_equal = (
            json.dumps(val1, sort_keys=True) ==
            json.dumps(val2, sort_keys=True)
        )

        # The new approach
        mu_result = mu_equal(val1, val2)

        assert json_equal == mu_result, (
            f"Parity violation!\n"
            f"val1: {val1}\n"
            f"val2: {val2}\n"
            f"json.dumps equal: {json_equal}\n"
            f"mu_equal: {mu_result}"
        )


class TestEngineNewsClosureDetection:
    """Test patterns used by EngineNews for closure detection."""

    def test_state_unchanged_detection(self):
        """EngineNews Rule 2.2◇: detect when state hasn't changed."""
        # Pattern that detects "same state" (non-linear)
        # This is a simplified version of what EngineNews uses
        pattern = {"prev": {"var": "s"}, "curr": {"var": "s"}}

        # State unchanged - should match
        same_state = {"prev": {"a": 1, "b": 2}, "curr": {"a": 1, "b": 2}}
        result = match(pattern, same_state)
        assert result != NO_MATCH
        assert "s" in result

        # State changed - should NOT match
        diff_state = {"prev": {"a": 1, "b": 2}, "curr": {"a": 1, "b": 3}}
        result = match(pattern, diff_state)
        assert result is NO_MATCH

    def test_nested_state_comparison(self):
        """Deeply nested states must be compared correctly."""
        pattern = {"old": {"var": "state"}, "new": {"var": "state"}}

        # Deep nested identical states
        deep = {"x": {"y": {"z": [1, 2, 3]}}}
        input_same = {"old": deep, "new": {"x": {"y": {"z": [1, 2, 3]}}}}
        assert match(pattern, input_same) != NO_MATCH

        # Deep nested different states
        input_diff = {"old": deep, "new": {"x": {"y": {"z": [1, 2, 4]}}}}
        assert match(pattern, input_diff) is NO_MATCH

    def test_type_sensitive_comparison(self):
        """Different types must not match even if string repr is same."""
        pattern = [{"var": "x"}, {"var": "x"}]

        # 1 vs "1" - must NOT match
        assert match(pattern, [1, "1"]) is NO_MATCH

        # true vs 1 - must NOT match (json.dumps handles this)
        # Note: json.dumps(True) == "true", json.dumps(1) == "1"
        assert match(pattern, [True, 1]) is NO_MATCH

        # null vs "null" - must NOT match
        assert match(pattern, [None, "null"]) is NO_MATCH


class TestEdgeCases:
    """Edge cases that could trip up equality comparison."""

    def test_empty_structures(self):
        """Empty lists and dicts must work correctly."""
        pattern = [{"var": "x"}, {"var": "x"}]

        assert match(pattern, [[], []]) != NO_MATCH
        assert match(pattern, [{}, {}]) != NO_MATCH
        assert match(pattern, [[], {}]) is NO_MATCH

    def test_unicode_equality(self):
        """Unicode strings must compare correctly."""
        pattern = [{"var": "x"}, {"var": "x"}]

        assert match(pattern, ["café", "café"]) != NO_MATCH
        assert match(pattern, ["café", "cafe"]) is NO_MATCH
        assert match(pattern, ["日本語", "日本語"]) != NO_MATCH

    def test_float_edge_cases(self):
        """Float comparison edge cases."""
        pattern = [{"var": "x"}, {"var": "x"}]

        # Same float
        assert match(pattern, [3.14, 3.14]) != NO_MATCH

        # Float vs int with same value
        # json.dumps(1.0) == "1.0", json.dumps(1) == "1" -> different
        assert match(pattern, [1.0, 1]) is NO_MATCH

    def test_dict_key_order_irrelevant(self):
        """Dict comparison must be key-order independent."""
        pattern = [{"var": "x"}, {"var": "x"}]

        # Same content, different insertion order (via json.dumps sort_keys=True)
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}

        assert match(pattern, [d1, d2]) != NO_MATCH
