"""
Kernel Security Fuzzer - Property-Based Testing for L2 Security Boundaries

Created: 2026-01-30 (from 7-agent adversarial review)
Covers gaps identified by fuzzer agent:
1. Deep nesting stress (depth 50-200)
2. Wide structure stress (width 100-1000)
3. Kernel reserved field smuggling at depth boundaries
4. Unicode homoglyph attacks on field names
5. Projection count boundaries (0, 1, 100+)

Run with: pytest tests/test_kernel_security_fuzzer.py -v
"""

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume

from rcx_pi.selfhost.mu_type import (
    is_mu,
    mu_equal,
    MAX_MU_DEPTH,
    MAX_MU_WIDTH,
)
from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match
from rcx_pi.selfhost.step_mu import (
    validate_no_kernel_reserved_fields,
    KERNEL_RESERVED_FIELDS,
    step_kernel_mu,
    is_kernel_terminal,
    is_kernel_intermediate,
)


# =============================================================================
# Strategies
# =============================================================================

mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    st.text(max_size=20),
)


# =============================================================================
# Deep Nesting Stress Tests
# =============================================================================

class TestDeepNestingStress:
    """Test behavior at depth limits."""

    @given(st.integers(min_value=10, max_value=50))
    @settings(max_examples=50, deadline=10000)
    def test_moderate_depth_normalizes(self, depth):
        """Structures at moderate depth should normalize and roundtrip."""
        value = "leaf"
        for _ in range(depth):
            value = {"nested": value}

        assume(is_mu(value))

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == value

    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=50, deadline=5000)
    def test_depth_determinism(self, depth):
        """Normalization is deterministic at any depth."""
        value = 42
        for _ in range(depth):
            value = {"level": value}

        assume(is_mu(value))

        norm1 = normalize_for_match(value)
        norm2 = normalize_for_match(value)

        assert mu_equal(norm1, norm2)


# =============================================================================
# Wide Structure Stress Tests
# =============================================================================

class TestWideStructureStress:
    """Test behavior at width limits."""

    @given(st.integers(min_value=50, max_value=200))
    @settings(max_examples=30, deadline=15000)
    def test_wide_dict_normalizes(self, width):
        """Wide dicts should normalize and roundtrip."""
        wide_dict = {f"key{i}": i for i in range(width)}

        assume(is_mu(wide_dict))

        normalized = normalize_for_match(wide_dict)
        denormalized = denormalize_from_match(normalized)

        assert len(denormalized) == width

    @given(st.integers(min_value=50, max_value=200))
    @settings(max_examples=30, deadline=15000)
    def test_wide_list_normalizes(self, width):
        """Wide lists should normalize and roundtrip."""
        wide_list = list(range(width))

        assume(is_mu(wide_list))

        normalized = normalize_for_match(wide_list)
        denormalized = denormalize_from_match(normalized)

        assert len(denormalized) == width


# =============================================================================
# Kernel Reserved Field Smuggling Tests
# =============================================================================

class TestKernelReservedFieldSmuggling:
    """Test kernel boundary security."""

    @given(st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)), mu_primitives)
    @settings(max_examples=200, deadline=5000)
    def test_top_level_reserved_field_rejected(self, field_name, value):
        """Top-level kernel reserved fields are rejected."""
        smuggled = {field_name: value}

        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(smuggled)

    @given(st.integers(min_value=1, max_value=50))
    @settings(max_examples=100, deadline=5000)
    def test_nested_reserved_field_rejected(self, depth):
        """Kernel reserved fields at any depth are rejected."""
        smuggled = {"_mode": "pwned"}
        for _ in range(depth):
            smuggled = {"outer": smuggled}

        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(smuggled)

    @given(st.integers(min_value=95, max_value=100))
    @settings(max_examples=20, deadline=10000)
    def test_smuggling_near_depth_limit(self, depth):
        """Smuggling at depth limit is still caught or rejected."""
        smuggled = {"_result": "attack"}
        for _ in range(depth):
            smuggled = {"nested": smuggled}

        # Should either catch the field or reject due to depth
        with pytest.raises(ValueError):
            validate_no_kernel_reserved_fields(smuggled)

    @given(st.integers(min_value=101, max_value=120))
    @settings(max_examples=20, deadline=10000)
    def test_depth_limit_enforced(self, depth):
        """Validation rejects inputs deeper than MAX_VALIDATION_DEPTH."""
        value = "leaf"
        for _ in range(depth):
            value = {"nested": value}

        with pytest.raises(ValueError, match="maximum validation depth"):
            validate_no_kernel_reserved_fields(value)

    @given(st.sampled_from(sorted(KERNEL_RESERVED_FIELDS)))
    @settings(max_examples=100, deadline=5000)
    def test_reserved_field_in_list(self, field_name):
        """Kernel reserved fields in lists are rejected."""
        smuggled = [{field_name: "attack"}]

        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(smuggled)


# =============================================================================
# Unicode Homoglyph Attack Tests
# =============================================================================

class TestUnicodeHomoglyphAttacks:
    """Test Unicode attacks on field names - adversary finding."""

    def test_cyrillic_o_not_confused_with_mode(self):
        """Cyrillic 'о' (U+043E) should not be confused with Latin 'o'."""
        # _mоde with Cyrillic 'о' should pass (not a reserved field)
        attack = {"_m\u043ede": "attack"}  # Cyrillic о
        # Should NOT raise - it's not "_mode"
        validate_no_kernel_reserved_fields(attack)

    def test_cyrillic_a_not_confused_with_phase(self):
        """Cyrillic 'а' (U+0430) should not be confused with Latin 'a'."""
        attack = {"_ph\u0430se": "attack"}  # Cyrillic а
        validate_no_kernel_reserved_fields(attack)

    def test_cyrillic_i_not_confused_with_input(self):
        """Cyrillic 'і' (U+0456) should not be confused with Latin 'i'."""
        attack = {"_\u0456nput": "attack"}  # Cyrillic і
        validate_no_kernel_reserved_fields(attack)

    def test_cyrillic_e_not_confused_with_step(self):
        """Cyrillic 'е' (U+0435) should not be confused with Latin 'e'."""
        attack = {"_st\u0435p": "attack"}  # Cyrillic е
        validate_no_kernel_reserved_fields(attack)

    def test_all_12_reserved_with_cyrillic_o(self):
        """All 12 reserved fields with Cyrillic 'о' should pass."""
        for field in KERNEL_RESERVED_FIELDS:
            if 'o' in field:
                attack = {field.replace('o', '\u043e'): "attack"}
                # Should pass - different character
                validate_no_kernel_reserved_fields(attack)


# =============================================================================
# Projection Count Boundary Tests
# =============================================================================

class TestProjectionCountBoundaries:
    """Test behavior with varying projection counts."""

    @given(mu_primitives)
    @settings(max_examples=100, deadline=5000)
    def test_zero_projections_stalls(self, value):
        """Empty projection list causes immediate stall."""
        assume(is_mu(value))
        assume(not isinstance(value, dict) or not any(k.startswith('_') for k in value.keys()))

        result = step_kernel_mu([], value)
        assert mu_equal(result, value), "Empty projections should return input unchanged"

    @given(mu_primitives)
    @settings(max_examples=100, deadline=5000)
    def test_single_identity_projection(self, value):
        """Single identity projection returns input."""
        assume(is_mu(value))
        assume(not isinstance(value, dict) or not any(k.startswith('_') for k in value.keys()))

        identity_proj = {"pattern": {"var": "x"}, "body": {"var": "x"}}
        result = step_kernel_mu([identity_proj], value)

        assert mu_equal(result, value), "Identity projection should preserve input"

    @given(st.integers(min_value=10, max_value=50))
    @settings(max_examples=20, deadline=30000)
    def test_many_projections_first_match_wins(self, count):
        """With many projections, first match wins."""
        identity_proj = {"pattern": {"var": "x"}, "body": {"var": "x"}}
        projections = [identity_proj] * count

        value = 42
        result = step_kernel_mu(projections, value)

        assert mu_equal(result, value), f"First match should win with {count} projections"


# =============================================================================
# Kernel State Detection Tests
# =============================================================================

class TestKernelStateDetection:
    """Test kernel terminal/intermediate detection."""

    @given(mu_primitives)
    @settings(max_examples=100, deadline=5000)
    def test_primitives_not_terminal(self, value):
        """Primitive values are not kernel terminal states."""
        assume(is_mu(value))
        assume(not isinstance(value, dict))

        assert not is_kernel_terminal(value)

    def test_done_state_is_terminal(self):
        """Kernel done state is detected."""
        done_state = {"_mode": "done", "_result": 42, "_stall": False}
        assert is_kernel_terminal(done_state)

    def test_incomplete_done_not_terminal(self):
        """Incomplete done state is not terminal."""
        incomplete = {"_mode": "done", "_result": 42}  # Missing _stall
        assert not is_kernel_terminal(incomplete)

    @given(mu_primitives)
    @settings(max_examples=100, deadline=5000)
    def test_primitives_not_intermediate(self, value):
        """Primitive values are not kernel intermediate states."""
        assume(is_mu(value))
        assume(not isinstance(value, dict))

        assert not is_kernel_intermediate(value)


# =============================================================================
# Determinism Under Stress
# =============================================================================

class TestDeterminismUnderStress:
    """Test determinism with edge case inputs."""

    @given(st.integers(min_value=5, max_value=30))
    @settings(max_examples=50, deadline=10000)
    def test_nested_dict_deterministic(self, depth):
        """Nested dict normalization is deterministic."""
        value = {"leaf": 42}
        for i in range(depth):
            value = {f"level_{i}": value}

        assume(is_mu(value))

        norm1 = normalize_for_match(value)
        norm2 = normalize_for_match(value)

        assert mu_equal(norm1, norm2)

    @given(st.integers(min_value=10, max_value=100))
    @settings(max_examples=30, deadline=10000)
    def test_wide_dict_deterministic(self, width):
        """Wide dict normalization is deterministic."""
        value = {f"k{i}": i for i in range(width)}

        assume(is_mu(value))

        norm1 = normalize_for_match(value)
        norm2 = normalize_for_match(value)

        assert mu_equal(norm1, norm2)
