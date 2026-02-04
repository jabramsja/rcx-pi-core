"""
Security Boundary Fuzzer - Property-Based Tests for Security-Critical Functions

Tests the security boundaries that prevent domain data from forging kernel state.
These functions are CRITICAL for preventing state injection attacks.

Targets:
- validate_no_kernel_reserved_fields() - deep recursive validation
- KERNEL_RESERVED_FIELDS - field whitelist
- Depth guard (MAX_VALIDATION_DEPTH = 100)

Added 2026-01-29 after 7-agent steelman review identified this as a fuzzer gap.
"""

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from rcx_pi.selfhost.step_mu import (
    validate_no_kernel_reserved_fields,
    KERNEL_RESERVED_FIELDS,
)
from rcx_pi.selfhost.mu_type import is_mu


# =============================================================================
# Strategies for generating test inputs
# =============================================================================

# All kernel reserved fields
reserved_fields = st.sampled_from(list(KERNEL_RESERVED_FIELDS))

# Safe keys that don't start with underscore
safe_keys = st.text(min_size=1, max_size=10).filter(lambda k: not k.startswith("_"))

# Simple Mu values
simple_mu = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=20),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(safe_keys, children, max_size=3),
    ),
    max_leaves=10,
)


@st.composite
def nested_structure_with_reserved_field(draw, target_depth: int = 5):
    """Generate a nested structure with a reserved field at specified depth."""
    reserved = draw(reserved_fields)
    value = draw(simple_mu)

    # Build the malicious payload
    payload = {reserved: value}

    # Wrap it in nesting
    current = payload
    for _ in range(target_depth):
        wrapper_key = draw(safe_keys)
        current = {wrapper_key: current}

    return current, reserved


@st.composite
def deeply_nested_clean_structure(draw, depth: int = 50):
    """Generate a deeply nested structure WITHOUT reserved fields."""
    value = draw(simple_mu)
    current = value
    for _ in range(depth):
        key = draw(safe_keys)
        current = {key: current}
    return current


@st.composite
def structure_with_reserved_in_list(draw):
    """Generate a structure with reserved field inside a list."""
    reserved = draw(reserved_fields)
    value = draw(simple_mu)

    # Put reserved field in a dict inside a list
    malicious_dict = {reserved: value}
    wrapper = [malicious_dict, draw(simple_mu)]

    return wrapper, reserved


# =============================================================================
# Basic Validation Tests
# =============================================================================

class TestReservedFieldsBasic:
    """Basic tests for reserved field validation."""

    @given(value=simple_mu)
    @settings(deadline=5000)
    def test_clean_values_pass_validation(self, value):
        """Clean Mu values without reserved fields pass validation."""
        assume(is_mu(value))
        # Should not raise
        validate_no_kernel_reserved_fields(value, "test")

    @given(reserved=reserved_fields, value=simple_mu)
    @settings(deadline=5000)
    def test_top_level_reserved_field_rejected(self, reserved, value):
        """Reserved fields at top level are rejected."""
        malicious = {reserved: value}

        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")

    def test_all_24_reserved_fields_rejected(self):
        """All 24 reserved fields are rejected (12 kernel + 4 EngineNews + 4 Exhaustion + 4 Bridge)."""
        for field in KERNEL_RESERVED_FIELDS:
            malicious = {field: "attack"}
            with pytest.raises(ValueError, match="kernel-reserved field"):
                validate_no_kernel_reserved_fields(malicious, "test")

    def test_reserved_fields_count(self):
        """Verify exactly 22 reserved fields exist (12 kernel + 3 Recurrence + 3 Exhaustion + 4 Bridge).
        Gate 3: Entry points (detect_closure, detect_exhaustion) moved out of reserved fields.
        """
        assert len(KERNEL_RESERVED_FIELDS) == 22, (
            f"Expected 22 reserved fields, found {len(KERNEL_RESERVED_FIELDS)}"
        )


# =============================================================================
# Nested Structure Tests
# =============================================================================

class TestNestedReservedFields:
    """Tests for reserved fields at various nesting depths."""

    @given(data=nested_structure_with_reserved_field(target_depth=1))
    @settings(deadline=5000)
    def test_depth_1_reserved_field_rejected(self, data):
        """Reserved field at depth 1 is rejected."""
        malicious, reserved = data
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")

    @given(data=nested_structure_with_reserved_field(target_depth=5))
    @settings(deadline=5000)
    def test_depth_5_reserved_field_rejected(self, data):
        """Reserved field at depth 5 is rejected."""
        malicious, reserved = data
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")

    @given(data=nested_structure_with_reserved_field(target_depth=50))
    @settings(deadline=10000)
    def test_depth_50_reserved_field_rejected(self, data):
        """Reserved field at depth 50 is rejected."""
        malicious, reserved = data
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")

    @given(data=nested_structure_with_reserved_field(target_depth=99))
    @settings(max_examples=20, deadline=15000)
    def test_depth_99_reserved_field_rejected(self, data):
        """Reserved field at depth 99 (just under limit) is rejected."""
        malicious, reserved = data
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")


# =============================================================================
# Depth Guard Tests
# =============================================================================

class TestDepthGuard:
    """Tests for depth limit enforcement (fail-closed behavior)."""

    def test_depth_100_clean_accepted(self):
        """Clean structure at exactly depth 100 is accepted."""
        # Build structure at depth 100
        current = {"value": 42}
        for i in range(99):  # 99 more levels = 100 total
            current = {f"level_{i}": current}

        # Should not raise (clean structure at limit)
        validate_no_kernel_reserved_fields(current, "test")

    def test_depth_101_raises_regardless_of_content(self):
        """Depth 101 raises ValueError (fail-closed)."""
        # Build structure at depth 101
        current = {"value": 42}
        for i in range(100):  # 100 more levels = 101 total
            current = {f"level_{i}": current}

        # Should raise due to depth, not content
        with pytest.raises(ValueError, match="depth"):
            validate_no_kernel_reserved_fields(current, "test")

    @given(st.integers(min_value=101, max_value=150))
    @settings(max_examples=20, deadline=30000)
    def test_excessive_depth_always_rejected(self, depth):
        """Any depth > 100 is rejected (fail-closed)."""
        # Build structure at specified depth
        current = {"value": 42}
        for i in range(depth - 1):
            current = {f"level_{i}": current}

        with pytest.raises(ValueError, match="depth"):
            validate_no_kernel_reserved_fields(current, "test")

    @given(data=deeply_nested_clean_structure(depth=95))
    @settings(max_examples=20, deadline=15000)
    def test_deep_clean_structure_accepted(self, data):
        """Deep but clean structure under limit is accepted."""
        # Should not raise
        validate_no_kernel_reserved_fields(data, "test")


# =============================================================================
# List Traversal Tests
# =============================================================================

class TestListTraversal:
    """Tests for reserved field detection inside lists."""

    @given(data=structure_with_reserved_in_list())
    @settings(deadline=5000)
    def test_reserved_field_in_list_rejected(self, data):
        """Reserved field inside a list element is rejected."""
        malicious, reserved = data
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")

    def test_nested_list_with_reserved_field(self):
        """Reserved field in nested list structure is rejected."""
        malicious = [[[{"_mode": "attack"}]]]
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")

    def test_mixed_list_dict_nesting(self):
        """Reserved field in mixed list/dict nesting is rejected."""
        malicious = {"outer": [{"inner": {"_result": "pwned"}}]}
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(malicious, "test")


# =============================================================================
# Edge Cases and Adversarial Inputs
# =============================================================================

class TestEdgeCases:
    """Edge cases and adversarial inputs."""

    def test_empty_dict_accepted(self):
        """Empty dict is accepted."""
        validate_no_kernel_reserved_fields({}, "test")

    def test_empty_list_accepted(self):
        """Empty list is accepted."""
        validate_no_kernel_reserved_fields([], "test")

    def test_none_accepted(self):
        """None is accepted."""
        validate_no_kernel_reserved_fields(None, "test")

    def test_primitive_values_accepted(self):
        """Primitive values are accepted."""
        for value in [42, 3.14, "hello", True, False]:
            validate_no_kernel_reserved_fields(value, "test")

    def test_underscore_non_reserved_accepted(self):
        """Underscore-prefixed keys that aren't reserved are accepted."""
        # _custom is not in KERNEL_RESERVED_FIELDS
        valid = {"_custom": "value", "_user_data": 123}
        validate_no_kernel_reserved_fields(valid, "test")

    def test_similar_but_different_keys_accepted(self):
        """Keys similar to reserved but not exact matches are accepted."""
        # These look like reserved fields but aren't exact matches
        valid = {
            "mode": "not reserved",  # missing underscore
            "_Mode": "case sensitive",  # wrong case
            "_mode_extra": "has suffix",  # has extra chars
            "prefix_mode": "has prefix",  # different prefix
        }
        validate_no_kernel_reserved_fields(valid, "test")


# =============================================================================
# Unicode Homoglyph Tests (Security Edge Cases)
# =============================================================================

class TestUnicodeHomoglyphs:
    """Tests for Unicode homoglyph attacks on reserved field names."""

    def test_fullwidth_underscore_not_reserved(self):
        """Fullwidth underscore is different from ASCII underscore."""
        # ＿ (U+FF3F) looks like _ but is different
        homoglyph = {"＿mode": "attack"}  # fullwidth underscore
        # Should be accepted (not the same as _mode)
        validate_no_kernel_reserved_fields(homoglyph, "test")

    def test_cyrillic_o_not_reserved(self):
        """Cyrillic 'о' is different from ASCII 'o'."""
        # _mоde with Cyrillic о (U+043E) looks like _mode
        homoglyph = {"_mоde": "attack"}  # Cyrillic о
        # Should be accepted (not the same as _mode)
        validate_no_kernel_reserved_fields(homoglyph, "test")

    def test_real_reserved_fields_still_blocked(self):
        """Real reserved fields are still blocked after homoglyph tests."""
        # Ensure we didn't break real detection
        for field in ["_mode", "_phase", "_result", "_stall"]:
            malicious = {field: "attack"}
            with pytest.raises(ValueError, match="kernel-reserved field"):
                validate_no_kernel_reserved_fields(malicious, "test")
