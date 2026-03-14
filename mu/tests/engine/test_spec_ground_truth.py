"""
Spec-Level Ground Truth Tests

These tests verify EXPECTED OUTPUTS directly, not just parity between implementations.
They catch "both wrong in the same way" bugs that parity tests miss.

Each test has explicit expected results based on the RCX specification.
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.eval_seed import match, substitute, NO_MATCH


class TestMatchGroundTruth:
    """Ground truth tests for pattern matching."""

    def test_variable_binding_simple(self):
        """Variable pattern binds to any value - spec requirement."""
        pattern = {"var": "x"}
        value = 42

        bindings = match(pattern, value)

        # GROUND TRUTH: {"var": "x"} matching 42 must produce binding x=42
        assert bindings is not None, "Variable must match any value"
        assert bindings == {"x": 42}, f"Expected x=42, got {bindings}"

    def test_variable_binding_nested(self):
        """Variable in nested pattern binds to nested value."""
        pattern = {"a": {"var": "inner"}}
        value = {"a": {"nested": "value"}}

        bindings = match(pattern, value)

        # GROUND TRUTH: inner must bind to {"nested": "value"}
        assert bindings is not None
        assert bindings == {"inner": {"nested": "value"}}, f"Got {bindings}"

    def test_literal_equality_exact(self):
        """Literal patterns require exact equality."""
        pattern = {"type": "test", "value": 123}
        value = {"type": "test", "value": 123}

        bindings = match(pattern, value)

        # GROUND TRUTH: Exact match produces empty bindings (no variables)
        assert bindings is not None
        assert bindings == {}, f"Expected empty bindings, got {bindings}"

    def test_literal_mismatch_fails(self):
        """Mismatched literals must fail."""
        pattern = {"type": "test", "value": 123}
        value = {"type": "test", "value": 456}

        bindings = match(pattern, value)

        # GROUND TRUTH: Different literal values must not match
        assert bindings is NO_MATCH, "Mismatched literals must return None"

    def test_non_linear_same_value(self):
        """Non-linear pattern: same variable twice with same value succeeds."""
        pattern = {"left": {"var": "x"}, "right": {"var": "x"}}
        value = {"left": "same", "right": "same"}

        bindings = match(pattern, value)

        # GROUND TRUTH: x binds to "same" (both occurrences match)
        assert bindings is not None
        assert bindings == {"x": "same"}, f"Got {bindings}"

    def test_non_linear_different_value_fails(self):
        """Non-linear pattern: same variable with different values fails."""
        pattern = {"left": {"var": "x"}, "right": {"var": "x"}}
        value = {"left": "one", "right": "two"}

        bindings = match(pattern, value)

        # GROUND TRUTH: Non-linear mismatch must fail
        assert bindings is NO_MATCH, "Non-linear pattern with different values must fail"


class TestSubstituteGroundTruth:
    """Ground truth tests for substitution."""

    def test_simple_substitution(self):
        """Variable site replaced with bound value."""
        body = {"result": {"var": "x"}}
        bindings = {"x": 42}

        result = substitute(body, bindings)

        # GROUND TRUTH: {"var": "x"} replaced with 42
        assert result == {"result": 42}, f"Got {result}"

    def test_multiple_variables(self):
        """Multiple variables all substituted."""
        body = {"a": {"var": "x"}, "b": {"var": "y"}}
        bindings = {"x": 1, "y": 2}

        result = substitute(body, bindings)

        # GROUND TRUTH: Both variables replaced
        assert result == {"a": 1, "b": 2}, f"Got {result}"

    def test_nested_substitution(self):
        """Variables in nested structures substituted."""
        body = {"outer": {"inner": {"var": "x"}}}
        bindings = {"x": "deep"}

        result = substitute(body, bindings)

        # GROUND TRUTH: Nested variable replaced
        assert result == {"outer": {"inner": "deep"}}, f"Got {result}"

    def test_unbound_variable_raises(self):
        """Unbound variables raise KeyError (bootstrap behavior)."""
        body = {"known": {"var": "x"}, "unknown": {"var": "y"}}
        bindings = {"x": 1}

        # GROUND TRUTH: Bootstrap substitute raises on unbound variables
        # Note: The structural subst (subst_mu) stalls instead of raising
        with pytest.raises(KeyError, match="Unbound variable: y"):
            substitute(body, bindings)


class TestMatchSubstituteIntegration:
    """Integration tests: match then substitute (projection application)."""

    def test_projection_application_simple(self):
        """Apply a simple projection: match pattern, substitute body."""
        pattern = {"inc": {"var": "n"}}
        body = {"result": {"var": "n"}}  # Simplified - real would compute n+1
        value = {"inc": 5}

        # Match
        bindings = match(pattern, value)
        assert bindings == {"n": 5}, f"Match failed: {bindings}"

        # Substitute
        result = substitute(body, bindings)
        assert result == {"result": 5}, f"Substitute failed: {result}"

    def test_projection_no_match(self):
        """Projection doesn't apply when pattern doesn't match."""
        pattern = {"inc": {"var": "n"}}
        value = {"dec": 5}  # Different key

        bindings = match(pattern, value)

        # GROUND TRUTH: Wrong structure must not match
        assert bindings is NO_MATCH, "Pattern with wrong key must not match"


class TestNegativeCases:
    """
    Negative tests that MUST fail.

    These catch "always-pass" bugs - if these pass when they shouldn't,
    something is wrong with validation.
    """

    def test_match_type_mismatch_dict_vs_int(self):
        """Dict pattern cannot match integer."""
        pattern = {"key": "value"}
        value = 42

        bindings = match(pattern, value)

        assert bindings is NO_MATCH, "Dict pattern must not match integer"

    def test_match_type_mismatch_list_vs_dict(self):
        """List pattern cannot match dict."""
        pattern = [1, 2, 3]
        value = {"a": 1}

        bindings = match(pattern, value)

        assert bindings is NO_MATCH, "List pattern must not match dict"

    def test_match_extra_keys_in_value(self):
        """Pattern with fewer keys than value must fail (exact-key matching).

        The source path (_match_inner, _stage0_match) and compiled path
        (assert_key_profile) both enforce exact-key matching. The only
        exception is _type="list" on normalized list structures (Gate 3).
        """
        pattern = {"a": 1}
        value = {"a": 1, "b": 2}

        bindings = match(pattern, value)

        assert bindings is NO_MATCH, (
            "Extra keys in value must cause NO_MATCH (exact-key matching)")

    def test_match_missing_keys_in_value(self):
        """Pattern with more keys than value must fail."""
        pattern = {"a": 1, "b": 2}
        value = {"a": 1}

        bindings = match(pattern, value)

        assert bindings is NO_MATCH, "Pattern with missing keys must fail"
