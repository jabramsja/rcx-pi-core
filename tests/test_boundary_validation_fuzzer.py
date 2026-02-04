"""
Boundary Validation Fuzzer Tests

Property-based tests for boundary validation functions:
- assert_seed_pure (mu_type.py)
- validate_type_tag (match_mu.py)
- get_var_name (eval_seed.py)

These functions are security-critical boundary guards.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from rcx_pi.selfhost.mu_type import assert_seed_pure, assert_mu
from rcx_pi.selfhost.match_mu import validate_type_tag, VALID_TYPE_TAGS
from rcx_pi.selfhost.eval_seed import get_var_name, is_var


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
def valid_projection(draw):
    """Generate valid projection dicts."""
    return {
        "pattern": draw(mu_value(max_depth=1)),
        "body": draw(mu_value(max_depth=1)),
    }


# =============================================================================
# assert_seed_pure Tests
# =============================================================================

class TestAssertSeedPureFuzzer:
    """Property-based tests for assert_seed_pure."""

    @given(value=mu_value(max_depth=2))
    @settings(deadline=5000)
    def test_valid_mu_accepted(self, value):
        """All valid Mu values should be accepted."""
        # Should not raise
        assert_seed_pure(value, "test")

    @given(value=mu_value(max_depth=2))
    @settings(deadline=5000)
    def test_pure_mu_roundtrip(self, value):
        """assert_seed_pure is idempotent."""
        # First call should not raise
        assert_seed_pure(value, "test1")
        # Second call should also not raise (idempotent)
        assert_seed_pure(value, "test2")

    def test_lambda_rejected(self):
        """Lambda functions must be rejected."""
        seed = {"bad": lambda x: x}
        with pytest.raises(TypeError, match="must be a Mu"):
            assert_seed_pure(seed, "lambda_test")

    def test_function_rejected(self):
        """Regular functions must be rejected."""
        def my_func():
            pass
        seed = {"bad": my_func}
        with pytest.raises(TypeError, match="must be a Mu"):
            assert_seed_pure(seed, "func_test")

    def test_builtin_rejected(self):
        """Built-in functions must be rejected."""
        seed = {"bad": len}
        with pytest.raises(TypeError, match="must be a Mu"):
            assert_seed_pure(seed, "builtin_test")

    def test_nested_lambda_rejected(self):
        """Nested lambdas must be detected and rejected."""
        seed = {"level1": {"level2": {"bad": lambda: None}}}
        with pytest.raises(TypeError, match="must be a Mu"):
            assert_seed_pure(seed, "nested_lambda")

    def test_projection_with_lambda_rejected(self):
        """Projections containing lambdas must be rejected."""
        seed = {
            "projections": [
                {"pattern": {"var": "x"}, "body": lambda: None}
            ]
        }
        with pytest.raises(TypeError, match="must be a Mu"):
            assert_seed_pure(seed, "proj_lambda")

    @given(projections=st.lists(valid_projection(), min_size=0, max_size=3))
    @settings(deadline=5000)
    def test_valid_projections_accepted(self, projections):
        """Valid projection lists should be accepted."""
        seed = {"projections": projections}
        assert_seed_pure(seed, "projections_test")

    def test_projection_missing_pattern_rejected(self):
        """Projections without pattern must be rejected."""
        seed = {
            "seed": {
                "projections": [{"body": 1}]
            }
        }
        with pytest.raises(ValueError, match="missing 'pattern'"):
            assert_seed_pure(seed, "no_pattern")

    def test_projection_missing_body_rejected(self):
        """Projections without body must be rejected."""
        seed = {
            "seed": {
                "projections": [{"pattern": 1}]
            }
        }
        with pytest.raises(ValueError, match="missing 'body'"):
            assert_seed_pure(seed, "no_body")


# =============================================================================
# validate_type_tag Tests
# =============================================================================

class TestValidateTypeTagFuzzer:
    """Property-based tests for validate_type_tag."""

    def test_list_tag_valid(self):
        """'list' is a valid type tag."""
        validate_type_tag("list")  # Should not raise

    def test_dict_tag_valid(self):
        """'dict' is a valid type tag."""
        validate_type_tag("dict")  # Should not raise

    @given(tag=st.text(min_size=1, max_size=20).filter(lambda x: x not in VALID_TYPE_TAGS))
    @settings(deadline=5000)
    def test_invalid_tags_rejected(self, tag):
        """All tags not in whitelist must be rejected."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag(tag)

    def test_empty_string_rejected(self):
        """Empty string must be rejected."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("")

    def test_case_sensitive(self):
        """Type tags are case-sensitive."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("List")
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("DICT")

    @given(tag=st.sampled_from(["list", "dict"]))
    @settings(max_examples=20, deadline=5000)
    def test_valid_tags_whitelist(self, tag):
        """Valid tags should pass validation."""
        validate_type_tag(tag)  # Should not raise

    def test_unicode_homoglyph_rejected(self):
        """Unicode lookalikes must be rejected."""
        # 'l' with different unicode codepoint
        homoglyph_list = "lis\u0074"  # Regular 't' - this should pass actually
        # Try with Cyrillic 'а' instead of Latin 'a'
        homoglyph = "dict".replace("i", "\u0456")  # Cyrillic 'і'
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag(homoglyph)

    def test_injection_attempts_rejected(self):
        """SQL/code injection attempts must be rejected."""
        injections = [
            "list; DROP TABLE",
            "dict' OR '1'='1",
            "list\0dict",  # Null byte injection
            "list\ndict",  # Newline injection
        ]
        for injection in injections:
            with pytest.raises(ValueError, match="Invalid type tag"):
                validate_type_tag(injection)


# =============================================================================
# get_var_name Tests
# =============================================================================

class TestGetVarNameFuzzer:
    """Property-based tests for get_var_name."""

    @given(name=st.text(min_size=1, max_size=50))
    @settings(deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
    def test_valid_var_sites(self, name):
        """Valid variable sites should return their name."""
        var_site = {"var": name}
        if is_var(var_site):  # Filter for valid var sites
            result = get_var_name(var_site)
            assert result == name

    def test_empty_var_name_rejected(self):
        """Empty variable names must be rejected."""
        with pytest.raises(ValueError, match="empty"):
            get_var_name({"var": ""})

    def test_non_var_site_rejected(self):
        """Non-variable sites must be rejected."""
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name({"not_var": "x"})

    def test_extra_keys_rejected(self):
        """Variable sites with extra keys must be rejected."""
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name({"var": "x", "extra": "key"})

    def test_non_dict_rejected(self):
        """Non-dict values must be rejected."""
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name("x")
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name(42)
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name(["var", "x"])

    def test_non_string_var_value_rejected(self):
        """Variable names must be strings."""
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name({"var": 123})
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name({"var": None})
        with pytest.raises(ValueError, match="Not a variable site"):
            get_var_name({"var": ["x"]})

    @given(name=st.text(min_size=1, max_size=20))
    @settings(deadline=5000)
    def test_unicode_var_names_handled(self, name):
        """Unicode variable names should be handled correctly."""
        var_site = {"var": name}
        if is_var(var_site):
            result = get_var_name(var_site)
            assert result == name


# =============================================================================
# Integration: Boundary Guards Work Together
# =============================================================================

class TestBoundaryGuardIntegration:
    """Test that boundary guards work together correctly."""

    def test_seed_with_valid_var_sites(self):
        """Seeds with valid variable sites should pass all guards."""
        seed = {
            "projections": [
                {"pattern": {"var": "x"}, "body": {"var": "x"}},
                {"pattern": [1, {"var": "y"}], "body": {"var": "y"}},
            ]
        }
        # Should pass without raising
        assert_seed_pure(seed, "var_site_seed")

    def test_type_tagged_seed_valid(self):
        """Seeds using type tags should be valid."""
        seed = {
            "projections": [
                {
                    "pattern": {"_type": "list", "head": {"var": "h"}, "tail": {"var": "t"}},
                    "body": {"result": [{"var": "h"}, {"var": "t"}]}
                }
            ]
        }
        # Type tag should be valid
        validate_type_tag("list")
        # Seed should be pure
        assert_seed_pure(seed, "type_tagged_seed")

    @given(tag=st.sampled_from(["list", "dict"]))
    @settings(max_examples=20, deadline=5000)
    def test_type_tag_in_seed(self, tag):
        """Type-tagged structures in seeds should be valid."""
        seed = {
            "_type": tag,
            "head": "value",
            "tail": None
        }
        validate_type_tag(tag)
        assert_seed_pure(seed, "type_tagged_value")
