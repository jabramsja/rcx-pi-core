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


# ---------------------------------------------------------------------------
# LOCAL TEST FIXTURE — NOT production code.
#
# _is_kernel_internal_state was removed from rcx_pi/selfhost/eval_seed.py
# after the caller-trust model replaced shape-based trust.  Zero production
# callers remain.  This copy exists ONLY so the 3-layer check logic can be
# regression-tested without re-importing a deleted function.  Changes here
# do NOT affect production behavior.
# ---------------------------------------------------------------------------
_VALID_MU_TYPES = (type(None), bool, int, float, str, list, dict)
_KNOWN_KERNEL_MODES = frozenset({
    'kernel', 'done', 'error', 'match_done', 'subst_done', 'engine',
})
_KERNEL_CONTEXT_KEYS = frozenset({'_match_ctx', '_subst_ctx', '_kernel_ctx'})


def _is_kernel_internal_state(value):
    """Three-layer kernel state check (test fixture, not production code)."""
    if not isinstance(value, dict):
        return False
    mode = value.get('_mode')
    if mode is not None:
        if not isinstance(mode, str) or mode not in _KNOWN_KERNEL_MODES:
            return False
    else:
        if not any(k in value for k in _KERNEL_CONTEXT_KEYS):
            return False
    for v in value.values():
        if not isinstance(v, _VALID_MU_TYPES):
            return False
    return True


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
        # GROUNDING: Verify _type was actually preserved
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("_type") == "list", f"_type not preserved: {result}"

    def test_normalize_preserves_valid_dict_type(self):
        """Normalization should preserve valid _type: 'dict'."""
        value = {
            "_type": "dict",
            "head": {"head": "key", "tail": {"head": "value", "tail": None}},
            "tail": None,
        }
        result = normalize_for_match(value)
        assert result is not None
        # GROUNDING: Verify _type was actually preserved
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("_type") == "dict", f"_type not preserved: {result}"

    def test_denormalize_rejects_malicious_type_tag(self):
        """denormalize_from_match should reject unknown _type values."""
        # Construct a normalized structure with malicious type tag
        malicious = {"_type": "malicious", "head": 1, "tail": None}

        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious)

    def test_denormalize_handles_numeric_type_tag_safely(self):
        """Numeric type tags should either raise or be treated as regular dict (no crash)."""
        malicious = {"_type": 123, "head": 1, "tail": None}

        # Either raise (rejecting invalid tag) or handle gracefully as regular dict
        try:
            result = denormalize_from_match(malicious)
            # If it doesn't raise, verify it's returned as a regular dict (not interpreted as list)
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        except (ValueError, TypeError):
            pass  # Rejection is also acceptable

    def test_denormalize_handles_null_type_tag_safely(self):
        """Null type tags should either raise or be treated as regular dict (no crash)."""
        malicious = {"_type": None, "head": 1, "tail": None}

        # Either raise (rejecting invalid tag) or handle gracefully as regular dict
        try:
            result = denormalize_from_match(malicious)
            # If it doesn't raise, verify it's returned as a regular dict (not interpreted as list)
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        except (ValueError, TypeError):
            pass  # Rejection is also acceptable

    def test_kernel_mode_injection_blocked(self):
        """Cannot inject kernel state via _mode key."""
        # Try to forge kernel state
        forged = {"_mode": "done", "_result": "pwned"}

        # Normalization should not preserve kernel-internal keys
        result = normalize_for_match(forged)

        # The structure should be normalized as a regular dict
        # _mode and _result are just regular keys, not special
        assert result is not None
        # GROUNDING: Verify it's normalized as dict (head/tail structure), not treated specially
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        # Should have _type: dict since it's a dict being normalized
        assert result.get("_type") == "dict", f"Should be type dict: {result}"


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
        # GROUNDING: Verify correct types - outer is list, inner is dict
        assert isinstance(result, list), f"Outer should be list, got {type(result)}"
        assert len(result) == 1, f"List should have 1 element, got {len(result)}"
        assert isinstance(result[0], dict), f"Inner should be dict, got {type(result[0])}"

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


class TestKernelInternalStateBypass:
    """Grounding tests for _is_kernel_internal_state bypass vulnerability.

    Phase 8b Round 6 security fix: Attack vector was {"match": {}, "bomb": ...}
    which would bypass depth validation because 'match' triggered kernel state detection.

    The fix: Only underscore-prefixed fields (_mode, _phase, etc.) trigger bypass.
    """

    def test_match_field_does_not_trigger_bypass(self):
        """'match' field should NOT trigger kernel internal state detection.

        GROUNDING: Proves the bypass vulnerability is closed.
        Before fix: {"match": ...} would trigger bypass, skipping validation.
        After fix: Only _mode, _phase, etc. trigger bypass.
        """


        # Attack vector: domain data with 'match' field
        attack = {"match": {}, "data": "anything"}

        # CRITICAL: This MUST return False - match is NOT a kernel field
        assert _is_kernel_internal_state(attack) is False, (
            "SECURITY BUG: 'match' field should NOT trigger kernel state bypass! "
            "Attack vector: {'match': {}, 'bomb': <depth 500>} would skip validation."
        )

    def test_subst_field_does_not_trigger_bypass(self):
        """'subst' field should NOT trigger kernel internal state detection.

        GROUNDING: Same as match - 'subst' is generic domain data.
        """


        # Attack vector: domain data with 'subst' field
        attack = {"subst": {}, "data": "anything"}

        # CRITICAL: This MUST return False
        assert _is_kernel_internal_state(attack) is False, (
            "SECURITY BUG: 'subst' field should NOT trigger kernel state bypass!"
        )

    def test_reserved_mode_field_with_known_mode_triggers_detection(self):
        """_mode with known kernel mode string SHOULD trigger detection.

        GROUNDING: Verifies legitimate kernel states are detected.
        Phase 8c tightening: _mode must be a KNOWN kernel mode string
        (from seed files), not just any string.
        """


        # Real kernel state uses known mode "kernel"
        kernel_state = {"_mode": "kernel", "_input": 42}

        assert _is_kernel_internal_state(kernel_state) is True, (
            "_mode with known kernel mode should trigger detection"
        )

    def test_reserved_mode_field_with_unknown_mode_blocked(self):
        """_mode with unknown mode string should NOT trigger detection.

        GROUNDING (Phase 8c): Tighter security - arbitrary mode strings
        no longer bypass validation. Only seed-defined modes are trusted.
        """


        # _mode: "match" is NOT a known kernel mode (kernel.v1 uses "kernel", not "match")
        assert _is_kernel_internal_state({"_mode": "match", "_phase": "init"}) is False
        assert _is_kernel_internal_state({"_mode": "arbitrary"}) is False

    def test_phase_field_alone_does_not_trigger_detection(self):
        """_phase alone should NOT trigger detection (tighter Phase 8c check).

        GROUNDING: Phase 8c requires either known _mode or context key.
        _phase alone is insufficient — prevents forgery with just _phase.
        """


        kernel_state = {"_phase": "execute"}

        assert _is_kernel_internal_state(kernel_state) is False, (
            "_phase alone should NOT trigger detection (Phase 8c tightening)"
        )

    def test_combined_attack_blocked(self):
        """Combined attack vector with both match and payload should NOT bypass.

        GROUNDING: Full attack scenario test.
        """


        # Attacker tries: {"match": {}, "deeply": {"nested": {"bomb": ...}}}
        # This should NOT be detected as kernel state
        attack = {
            "match": {"pattern": "foo"},
            "deeply_nested": {"level2": {"level3": "payload"}}
        }

        assert _is_kernel_internal_state(attack) is False, (
            "Combined attack should NOT bypass validation!"
        )


class TestKernelBypassIntegration:
    """Integration tests proving the bypass fix works end-to-end.

    Round 7 Grounding: These tests verify the fix at the kernel entry point,
    not just at the _is_kernel_internal_state() function level.
    """

    def test_domain_data_with_match_field_goes_through_depth_validation(self):
        """
        GROUNDING: Proves the fix closes the bypass end-to-end.

        Before fix: {"match": {}, "bomb": <depth 500>} bypassed validation
        After fix: validate_no_kernel_reserved_fields() is called even with "match" field
        """
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        # Build a deeply nested structure with "match" field at top level
        # This should go through depth validation now
        bomb = {"value": 42}
        for i in range(305):  # Exceeds MAX_MU_DEPTH=300
            bomb = {f"level_{i}": bomb}

        attack = {"match": {}, "bomb": bomb}

        # CRITICAL: This MUST raise ValueError due to depth validation
        # If it doesn't raise, the bypass could still be present
        with pytest.raises(ValueError, match="depth"):
            validate_no_kernel_reserved_fields(attack, "test")

    def test_nested_underscore_mode_field_rejected(self):
        """
        GROUNDING: Proves nested kernel bypass triggers are still caught.

        Attack: Smuggle _mode field inside nested structure.
        """
        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        # Nested _mode field (should be detected by deep validation)
        attack = {
            "outer": {
                "inner": {
                    "_mode": "done",  # Smuggled kernel field
                    "_result": "pwned"
                }
            }
        }

        # Test at validation layer - should catch nested _mode
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(attack, "test")

    def test_validation_order_correct(self):
        """
        GROUNDING: Proves validation runs BEFORE bypass detection can apply.

        Security model: Order matters.
        1. validate_no_kernel_reserved_fields() - checks ALL domain data
        2. _is_kernel_internal_state() - bypass for KNOWN kernel states only

        If reversed: Domain data could forge kernel state before validation.
        """

        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        # Forged kernel state (has _mode, but is domain input - MUST be rejected)
        forged_kernel_state = {"_mode": "done", "_result": "pwned", "_stall": False}

        # _is_kernel_internal_state would return True (has _mode)
        assert _is_kernel_internal_state(forged_kernel_state) is True

        # BUT at boundary: validate_no_kernel_reserved_fields should reject forged state
        # Even though _is_kernel_internal_state would return True
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(forged_kernel_state, "domain input")

    def test_round6_regression_attack_blocked_end_to_end(self):
        """
        REGRESSION TEST: The exact Round 6 attack vector is blocked.

        Attack: {"match": {}, "subst": {}, "nested": <depth bomb>}
        This used to bypass validation because 'match' was in kernel_fields.
        """

        from rcx_pi.selfhost.step_mu import validate_no_kernel_reserved_fields

        # Build depth bomb
        bomb = {"payload": "deep"}
        for i in range(305):  # Exceeds MAX_MU_DEPTH=300
            bomb = {f"level_{i}": bomb}

        # The exact Round 6 attack - generic fields that WERE in kernel_fields
        attack = {"match": {}, "subst": {}, "bomb": bomb}

        # Step 1: _is_kernel_internal_state should return False (no underscore fields)
        assert _is_kernel_internal_state(attack) is False, (
            "REGRESSION: 'match'/'subst' should NOT trigger kernel detection"
        )

        # Step 2: Depth validation should catch the bomb
        with pytest.raises(ValueError, match="depth"):
            validate_no_kernel_reserved_fields(attack, "test")


class TestStepKernelMuIntegration:
    """End-to-end tests that call step_kernel_mu with attack payloads.

    Round 8 Critical Fix: Previous tests only tested validate_no_kernel_reserved_fields()
    directly. These tests verify the kernel entry point ACTUALLY calls validation.

    If someone removes the validation call from step_kernel_mu(), these tests will fail.
    """

    def test_step_kernel_mu_rejects_top_level_reserved_fields(self):
        """
        GROUNDED: Kernel entry point rejects reserved fields in domain input.

        This tests the ACTUAL kernel execution path, not just the validation function.
        """
        from rcx_pi.selfhost.step_mu import step_kernel_mu

        # Attack payloads with kernel-reserved fields at top level
        attacks = [
            {"_mode": "done", "_result": "pwned", "_stall": False},
            {"data": "innocent", "_kernel_ctx": {"evil": "payload"}},
            {"_phase": "match", "value": 42},
            {"_step": {"pattern": "x"}, "_projs": []},
        ]

        for attack in attacks:
            with pytest.raises(ValueError, match="kernel-reserved field"):
                step_kernel_mu([], attack)

    def test_step_kernel_mu_rejects_nested_reserved_fields(self):
        """
        GROUNDED: Kernel entry rejects reserved fields at ANY depth.

        Tests deep validation is called from kernel entry point.
        """
        from rcx_pi.selfhost.step_mu import step_kernel_mu

        # Nested attacks - reserved fields hidden in structure
        attacks = [
            {"outer": {"_mode": "done"}},  # Depth 1
            {"level1": {"level2": {"_result": "pwned"}}},  # Depth 2
            {"list_wrapper": [{"_phase": "inject"}]},  # In list
        ]

        for attack in attacks:
            with pytest.raises(ValueError, match="kernel-reserved field"):
                step_kernel_mu([], attack)

    def test_step_kernel_mu_accepts_valid_domain_data(self):
        """
        GROUNDED: Kernel accepts valid domain data (positive test).

        Proves both rejection AND acceptance paths work.
        """
        from rcx_pi.selfhost.step_mu import step_kernel_mu

        # Valid domain data (no reserved fields)
        valid_inputs = [
            {"x": 42},
            {"nested": {"y": [1, 2, 3]}},
            {"mode": "not_reserved"},  # "mode" without underscore is OK
            {"phase": "also_ok", "result": "not_reserved_either"},
        ]

        # Minimal projection that matches anything
        projs = [{"pattern": {"var": "x"}, "body": {"matched": {"var": "x"}}}]

        for valid_input in valid_inputs:
            # Should not raise - domain data is clean
            result = step_kernel_mu(projs, valid_input)
            # Result should be valid (either matched or original)
            assert isinstance(result, dict), f"Expected dict result: {result}"

    def test_step_kernel_mu_rejects_depth_bomb_with_generic_field(self):
        """
        GROUNDED: Round 6 regression test at kernel entry point.

        The specific attack: {"match": {}, "bomb": <depth 500>}
        Previously bypassed validation, now should be caught.
        assert_mu catches the depth bomb before validate_no_kernel_reserved_fields.
        """
        from rcx_pi.selfhost.step_mu import step_kernel_mu

        # Build depth bomb exceeding MAX_MU_DEPTH=300
        bomb = {"value": 42}
        for i in range(305):
            bomb = {f"level_{i}": bomb}

        # Round 6 attack vector
        attack = {"match": {}, "bomb": bomb}

        # Kernel entry catches depth violation — assert_mu rejects before validation
        with pytest.raises(TypeError, match="must be a Mu"):
            step_kernel_mu([], attack)
