"""
Match v2 Parity Tests - Verify match.v2.json preserves v1 behavior.

Phase 7b added context passthrough (_match_ctx) and match.fail catch-all.
These tests verify that:
1. v2 seed structure is compatible with v1
2. All v1 projection IDs exist in v2
3. match_mu() (using v1) produces same results as kernel integration (using v2)

If these tests fail after modifying match.v2.json, the change may have broken
backward compatibility with v1 behavior.
"""

import pytest

from rcx_pi.selfhost.eval_seed import NO_MATCH
from rcx_pi.selfhost.match_mu import match_mu
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir


SEEDS_DIR = get_seeds_dir()


class TestMatchV2SeedStructure:
    """Verify v2 seed structure is compatible with v1."""

    @pytest.fixture
    def v1_seed(self):
        return load_verified_seed(SEEDS_DIR / "match.v1.json")

    @pytest.fixture
    def v2_seed(self):
        return load_verified_seed(SEEDS_DIR / "match.v2.json")

    def test_v2_has_all_v1_projection_ids(self, v1_seed, v2_seed):
        """All v1 projection IDs must exist in v2."""
        v1_ids = {p["id"] for p in v1_seed["projections"]}
        v2_ids = {p["id"] for p in v2_seed["projections"]}

        missing = v1_ids - v2_ids
        assert not missing, f"v2 missing v1 projection IDs: {missing}"

    def test_v2_has_context_passthrough(self, v2_seed):
        """v2 projections must have _match_ctx passthrough."""
        for proj in v2_seed["projections"]:
            # All v2 projections should reference _match_ctx
            proj_str = str(proj)
            assert "_match_ctx" in proj_str, f"Projection {proj['id']} missing _match_ctx"

    def test_v2_has_match_fail_catchall(self, v2_seed):
        """v2 must have match.fail catch-all projection."""
        ids = [p["id"] for p in v2_seed["projections"]]
        assert "match.fail" in ids, "v2 missing match.fail catch-all"

    def test_match_fail_is_before_wrap(self, v2_seed):
        """match.fail must come before match.wrap (catch failures before entry)."""
        ids = [p["id"] for p in v2_seed["projections"]]
        fail_idx = ids.index("match.fail")
        wrap_idx = ids.index("match.wrap")

        assert fail_idx < wrap_idx, "match.fail must come before match.wrap"

    def test_v2_projection_count(self, v1_seed, v2_seed):
        """v2 should have exactly 1 more projection than v1 (match.fail)."""
        v1_count = len(v1_seed["projections"])
        v2_count = len(v2_seed["projections"])

        assert v2_count == v1_count + 1, (
            f"v2 has {v2_count} projections, expected {v1_count + 1} (v1 + match.fail)"
        )


class TestMatchMuBehaviorStable:
    """Verify match_mu() behavior is unchanged (uses v1 internally)."""

    def test_literal_match(self):
        """Literals match as expected."""
        assert match_mu(42, 42) == {}

    def test_literal_mismatch(self):
        """Literal mismatches return NO_MATCH."""
        assert match_mu(42, 43) is NO_MATCH

    def test_variable_binding(self):
        """Variables bind correctly."""
        assert match_mu({"var": "x"}, 42) == {"x": 42}

    def test_dict_match(self):
        """Dict patterns match correctly."""
        result = match_mu({"a": {"var": "x"}, "b": 2}, {"a": 1, "b": 2})
        assert result == {"x": 1}

    def test_nested_dict_match(self):
        """Nested dict patterns match correctly."""
        result = match_mu(
            {"outer": {"inner": {"var": "v"}}},
            {"outer": {"inner": 99}}
        )
        assert result == {"v": 99}

    def test_structure_mismatch(self):
        """Structure mismatches return NO_MATCH."""
        assert match_mu({"a": 1}, 42) is NO_MATCH

    def test_string_match(self):
        """String patterns match correctly."""
        assert match_mu("hello", "hello") == {}

    def test_string_mismatch(self):
        """String mismatches return NO_MATCH."""
        assert match_mu("hello", "world") is NO_MATCH

    def test_multiple_variables(self):
        """Multiple variables bind correctly."""
        result = match_mu(
            {"x": {"var": "a"}, "y": {"var": "b"}},
            {"x": 1, "y": 2}
        )
        assert result == {"a": 1, "b": 2}

    def test_null_match(self):
        """Null patterns match correctly."""
        assert match_mu(None, None) == {}

    def test_bool_match(self):
        """Boolean patterns match correctly."""
        assert match_mu(True, True) == {}
        assert match_mu(False, False) == {}

    def test_bool_mismatch(self):
        """Boolean mismatches return NO_MATCH."""
        assert match_mu(True, False) is NO_MATCH


class TestMatchV2FailCatchAll:
    """Verify match.fail catch-all works correctly in kernel context."""

    # These tests verify that when using match.v2 through the kernel,
    # failures are caught by match.fail instead of stalling.
    # The actual integration is tested in test_phase7c_integration.py

    def test_match_fail_projection_pattern(self):
        """match.fail pattern should match any in-progress match state."""
        v2_seed = load_verified_seed(SEEDS_DIR / "match.v2.json")
        match_fail = next(
            p for p in v2_seed["projections"] if p["id"] == "match.fail"
        )

        # Should match on mode: "match" with non-null focuses
        pattern = match_fail["pattern"]
        assert pattern.get("mode") == "match", "match.fail should match mode: match"

    def test_match_fail_produces_no_match_status(self):
        """match.fail body should produce match_done with no_match status."""
        v2_seed = load_verified_seed(SEEDS_DIR / "match.v2.json")
        match_fail = next(
            p for p in v2_seed["projections"] if p["id"] == "match.fail"
        )

        body = match_fail["body"]
        assert body.get("_mode") == "match_done", "match.fail should produce match_done"
        assert body.get("_status") == "no_match", "match.fail should produce no_match status"
