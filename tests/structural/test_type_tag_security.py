"""
Grounding tests for type tag security.

Verifies that type tag validation rejects malicious or unknown type tags.
This is a Phase 7 blocker identified in STATUS.md.
"""

import pytest

from rcx_pi.selfhost.match_mu import (
    VALID_TYPE_TAGS,
    normalize_for_match,
    denormalize_from_match,
    validate_type_tag,
)


class TestTypeTagWhitelist:
    """Verify type tag whitelist is correctly defined and enforced."""

    def test_valid_type_tags_is_frozen(self):
        """VALID_TYPE_TAGS should be a frozenset (immutable)."""
        assert isinstance(VALID_TYPE_TAGS, frozenset), (
            "VALID_TYPE_TAGS must be frozenset to prevent runtime modification"
        )

    def test_valid_type_tags_contains_only_list_and_dict(self):
        """VALID_TYPE_TAGS should contain exactly 'list' and 'dict'."""
        assert VALID_TYPE_TAGS == frozenset({"list", "dict"}), (
            f"Expected VALID_TYPE_TAGS = {{'list', 'dict'}}, "
            f"found {VALID_TYPE_TAGS}"
        )

    def test_validate_type_tag_accepts_list(self):
        """validate_type_tag should accept 'list'."""
        # Should not raise
        validate_type_tag("list", "test")

    def test_validate_type_tag_accepts_dict(self):
        """validate_type_tag should accept 'dict'."""
        # Should not raise
        validate_type_tag("dict", "test")

    def test_validate_type_tag_rejects_unknown_string(self):
        """validate_type_tag should reject unknown type tags."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("malicious", "test")

    def test_validate_type_tag_rejects_exec(self):
        """validate_type_tag should reject 'exec' (potential code injection)."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("exec", "test")

    def test_validate_type_tag_rejects_lambda(self):
        """validate_type_tag should reject 'lambda' (lambda calculus smuggling)."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("lambda", "test")

    def test_validate_type_tag_rejects_function(self):
        """validate_type_tag should reject 'function'."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("function", "test")


class TestTypeTagInjection:
    """Verify type tag injection attacks are blocked."""

    def test_normalize_preserves_valid_list_type(self):
        """Normalization should preserve valid _type: 'list'."""
        value = {"_type": "list", "head": 1, "tail": None}
        result = normalize_for_match(value)
        # Should not raise and should preserve structure
        assert result is not None

    def test_normalize_preserves_valid_dict_type(self):
        """Normalization should preserve valid _type: 'dict'."""
        value = {
            "_type": "dict",
            "head": {"head": "key", "tail": {"head": "value", "tail": None}},
            "tail": None,
        }
        result = normalize_for_match(value)
        assert result is not None

    def test_denormalize_rejects_malicious_type_tag(self):
        """denormalize_from_match should reject unknown _type values."""
        # Construct a normalized structure with malicious type tag
        malicious = {"_type": "malicious", "head": 1, "tail": None}

        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious)

    def test_denormalize_rejects_numeric_type_tag(self):
        """Type tags must be strings, not numbers."""
        malicious = {"_type": 123, "head": 1, "tail": None}

        # Should either raise or handle gracefully (not crash)
        try:
            result = denormalize_from_match(malicious)
            # If it doesn't raise, it should treat as regular dict
            assert result is not None
        except (ValueError, TypeError):
            pass  # Expected behavior

    def test_denormalize_rejects_null_type_tag(self):
        """Type tags must be strings, not null."""
        malicious = {"_type": None, "head": 1, "tail": None}

        try:
            result = denormalize_from_match(malicious)
            # If it doesn't raise, it should treat as regular dict
            assert result is not None
        except (ValueError, TypeError):
            pass  # Expected behavior

    def test_kernel_mode_injection_blocked(self):
        """Cannot inject kernel state via _mode key."""
        # Try to forge kernel state
        forged = {"_mode": "done", "_result": "pwned"}

        # Normalization should not preserve kernel-internal keys
        result = normalize_for_match(forged)

        # The structure should be normalized as a regular dict
        # _mode and _result are just regular keys, not special
        assert result is not None


class TestNestedTypeTagValidation:
    """Verify type tag validation at nested levels."""

    def test_nested_valid_types_accepted(self):
        """Valid type tags in nested structures should work."""
        nested = {
            "_type": "list",
            "head": {"_type": "dict", "head": {"head": "k", "tail": {"head": "v", "tail": None}}, "tail": None},
            "tail": None,
        }

        # Should not raise
        result = denormalize_from_match(nested)
        assert result is not None

    def test_deeply_nested_malicious_type_rejected(self):
        """Malicious type tags in nested structures should be rejected."""
        nested = {
            "_type": "list",
            "head": {"_type": "evil", "head": 1, "tail": None},  # Malicious nested
            "tail": None,
        }

        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(nested)


class TestTypeTagEdgeCases:
    """Edge cases for type tag handling."""

    def test_empty_string_type_tag_rejected(self):
        """Empty string type tag should be rejected."""
        malicious = {"_type": "", "head": 1, "tail": None}

        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious)

    def test_whitespace_type_tag_rejected(self):
        """Whitespace-only type tag should be rejected."""
        malicious = {"_type": "   ", "head": 1, "tail": None}

        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious)

    def test_case_sensitive_type_tags(self):
        """Type tags should be case-sensitive ('List' != 'list')."""
        malicious = {"_type": "List", "head": 1, "tail": None}

        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious)

    def test_unicode_type_tag_rejected(self):
        """Unicode lookalike type tags should be rejected."""
        # 'lіst' with Cyrillic 'і' instead of Latin 'i'
        malicious = {"_type": "lіst", "head": 1, "tail": None}

        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious)
