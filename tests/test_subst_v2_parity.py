"""
Subst v2 Parity Tests - Verify subst.v2.json preserves v1 behavior.

Phase 7b added context passthrough (_subst_ctx) to all substitution projections.
These tests verify that:
1. v2 seed structure is compatible with v1
2. All v1 projection IDs exist in v2
3. subst_mu() (using v1) behavior is unchanged

If these tests fail after modifying subst.v2.json, the change may have broken
backward compatibility with v1 behavior.
"""

import pytest

from rcx_pi.selfhost.subst_mu import subst_mu
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir


SEEDS_DIR = get_seeds_dir()


class TestSubstV2SeedStructure:
    """Verify v2 seed structure is compatible with v1."""

    @pytest.fixture
    def v1_seed(self):
        return load_verified_seed(SEEDS_DIR / "subst.v1.json")

    @pytest.fixture
    def v2_seed(self):
        return load_verified_seed(SEEDS_DIR / "subst.v2.json")

    def test_v2_has_all_v1_projection_ids(self, v1_seed, v2_seed):
        """All v1 projection IDs must exist in v2."""
        v1_ids = {p["id"] for p in v1_seed["projections"]}
        v2_ids = {p["id"] for p in v2_seed["projections"]}

        missing = v1_ids - v2_ids
        assert not missing, f"v2 missing v1 projection IDs: {missing}"

    def test_v2_has_context_passthrough(self, v2_seed):
        """v2 projections must have _subst_ctx passthrough."""
        for proj in v2_seed["projections"]:
            # All v2 projections should reference _subst_ctx
            proj_str = str(proj)
            assert "_subst_ctx" in proj_str, f"Projection {proj['id']} missing _subst_ctx"

    def test_v2_projection_count(self, v1_seed, v2_seed):
        """v2 should have same projection count as v1 (context is additive only)."""
        v1_count = len(v1_seed["projections"])
        v2_count = len(v2_seed["projections"])

        assert v2_count == v1_count, (
            f"v2 has {v2_count} projections, expected {v1_count} (same as v1)"
        )

    def test_v2_wrap_is_last(self, v2_seed):
        """subst.wrap must be last projection (entry point)."""
        ids = [p["id"] for p in v2_seed["projections"]]
        assert ids[-1] == "subst.wrap", f"Last projection should be subst.wrap, got {ids[-1]}"

    def test_v2_done_is_first(self, v2_seed):
        """subst.done must be first projection (exit point)."""
        ids = [p["id"] for p in v2_seed["projections"]]
        assert ids[0] == "subst.done", f"First projection should be subst.done, got {ids[0]}"


class TestSubstMuBehaviorStable:
    """Verify subst_mu() behavior is unchanged (uses v1 internally)."""

    def test_literal_passthrough(self):
        """Literals pass through unchanged."""
        assert subst_mu(42, {}) == 42

    def test_string_passthrough(self):
        """Strings pass through unchanged."""
        assert subst_mu("hello", {}) == "hello"

    def test_variable_substitution(self):
        """Variables are substituted correctly."""
        assert subst_mu({"var": "x"}, {"x": 42}) == 42

    def test_dict_substitution(self):
        """Dict values are substituted correctly."""
        result = subst_mu({"a": {"var": "x"}, "b": 2}, {"x": 1})
        assert result == {"a": 1, "b": 2}

    def test_nested_substitution(self):
        """Nested structures are substituted correctly."""
        result = subst_mu(
            {"outer": {"inner": {"var": "v"}}},
            {"v": 99}
        )
        assert result == {"outer": {"inner": 99}}

    def test_multiple_variables(self):
        """Multiple variables are substituted correctly."""
        result = subst_mu(
            {"x": {"var": "a"}, "y": {"var": "b"}},
            {"a": 1, "b": 2}
        )
        assert result == {"x": 1, "y": 2}

    def test_no_substitution_needed(self):
        """Body without variables passes through unchanged."""
        result = subst_mu({"a": 1, "b": {"c": 2}}, {"unused": 99})
        assert result == {"a": 1, "b": {"c": 2}}

    def test_null_passthrough(self):
        """Null passes through unchanged."""
        assert subst_mu(None, {}) is None

    def test_bool_passthrough(self):
        """Booleans pass through unchanged."""
        assert subst_mu(True, {}) is True
        assert subst_mu(False, {}) is False

    def test_variable_to_dict(self):
        """Variable can be substituted with dict value."""
        result = subst_mu(
            {"result": {"var": "data"}},
            {"data": {"nested": {"value": 123}}}
        )
        assert result == {"result": {"nested": {"value": 123}}}

    def test_deeply_nested(self):
        """Deeply nested structures work correctly."""
        result = subst_mu(
            {"a": {"b": {"c": {"d": {"var": "x"}}}}},
            {"x": "deep"}
        )
        assert result == {"a": {"b": {"c": {"d": "deep"}}}}


class TestSubstV2ContextDesign:
    """Verify _subst_ctx design is correct."""

    def test_context_is_variable_bound(self):
        """_subst_ctx should be bound via variable pattern."""
        v2_seed = load_verified_seed(SEEDS_DIR / "subst.v2.json")

        for proj in v2_seed["projections"]:
            pattern = proj["pattern"]
            body = proj["body"]

            # Context should be bound in pattern
            ctx_pattern = pattern.get("_subst_ctx")
            assert ctx_pattern == {"var": "ctx"}, (
                f"Projection {proj['id']} should bind _subst_ctx to 'ctx'"
            )

            # Context should be passed through in body
            ctx_body = body.get("_subst_ctx")
            assert ctx_body == {"var": "ctx"}, (
                f"Projection {proj['id']} should pass _subst_ctx unchanged"
            )

    def test_done_preserves_context(self):
        """subst.done should preserve context in output."""
        v2_seed = load_verified_seed(SEEDS_DIR / "subst.v2.json")
        done_proj = next(p for p in v2_seed["projections"] if p["id"] == "subst.done")

        body = done_proj["body"]
        assert "_subst_ctx" in body, "subst.done must preserve _subst_ctx"
        assert body["_subst_ctx"] == {"var": "ctx"}, "subst.done must pass through context"
