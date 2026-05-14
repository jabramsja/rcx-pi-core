"""
Structural tests for projection_loader.py - Phase 6d Factory

Tests the projection loader factory to ensure:
1. Factory creates working loader/clear functions
2. Caching works correctly (load once, return cached)
3. Clear function resets cache
4. Invalid seed files are rejected
5. Loaded projections match expected structure
"""

import pytest

from rcx_pi.selfhost import projection_loader as projection_loader_module
from rcx_pi.selfhost import seed_integrity as seed_integrity_module
from rcx_pi.selfhost.projection_loader import make_projection_loader
from rcx_pi.selfhost.seed_integrity import (
    EXPECTED_PROJECTION_IDS,
    compute_checksum,
    get_seed_path,
    load_verified_seed,
)


class TestMakeProjectionLoader:
    """Test the factory function itself."""

    def test_returns_tuple_of_two_callables(self):
        """Factory returns (load, clear) tuple."""
        result = make_projection_loader("match.v1.json")
        assert isinstance(result, tuple)
        assert len(result) == 2
        load_fn, clear_fn = result
        assert callable(load_fn)
        assert callable(clear_fn)

    def test_load_returns_list(self):
        """Load function returns a list of projections."""
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()  # Ensure clean state
        projections = load_fn()
        assert isinstance(projections, list)
        assert len(projections) > 0

    def test_each_projection_has_required_fields(self):
        """Each projection has id, pattern, body."""
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        projections = load_fn()
        for proj in projections:
            assert isinstance(proj, dict)
            assert "id" in proj, f"Missing 'id' in projection: {proj}"
            assert "pattern" in proj, f"Missing 'pattern' in projection: {proj}"
            assert "body" in proj, f"Missing 'body' in projection: {proj}"


class TestCaching:
    """Test that caching works correctly."""

    def test_second_load_returns_equal_content(self):
        """Caching returns equal content on subsequent calls.

        Note: Returns defensive copy (not same object) to prevent cache mutation.
        (Adversary finding: cache mutation vulnerability)
        """
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        first = load_fn()
        second = load_fn()
        assert first == second  # Equal content
        assert first is not second  # But defensive copy (different object)

    def test_mutation_does_not_affect_cache(self):
        """Mutating returned list doesn't affect cached data.

        This is the security fix for the cache mutation vulnerability.
        (Adversary finding: cache mutation vulnerability)
        """
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        first = load_fn()
        original_len = len(first)

        # Mutate the returned list
        first.append({"pattern": "attack", "body": "payload"})
        assert len(first) == original_len + 1

        # Cache should be unaffected
        second = load_fn()
        assert len(second) == original_len  # Original length, not mutated

    def test_clear_forces_reload(self):
        """Clear function forces next load to reload from disk."""
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        first = load_fn()
        clear_fn()
        second = load_fn()
        # After clear, should be equal content (reloaded)
        assert first == second
        assert first is not second

    def test_separate_loaders_have_separate_caches(self):
        """Different loaders have independent caches."""
        load_match, clear_match = make_projection_loader("match.v1.json")
        load_subst, clear_subst = make_projection_loader("subst.v1.json")
        clear_match()
        clear_subst()

        match_projs = load_match()
        subst_projs = load_subst()

        # Different seeds have different projections
        assert match_projs != subst_projs

        # Clearing one doesn't affect the other
        clear_match()
        reloaded_subst = load_subst()
        assert reloaded_subst == subst_projs  # Still cached (equal content)


class TestSeedLoading:
    """Test loading of various seed files."""

    @pytest.mark.parametrize("seed_file,expected_count", [
        ("match.v1.json", 7),
        ("match.v2.json", 8),
        ("subst.v1.json", 12),
        ("subst.v2.json", 13),
        ("classify.v1.json", 6),
        ("kernel.v1.json", 7),
        ("eval.v1.json", 7),  # Now registered in seed_integrity checksums
    ])
    def test_seed_projection_counts(self, seed_file: str, expected_count: int):
        """Each seed file has expected number of projections."""
        load_fn, clear_fn = make_projection_loader(seed_file)
        clear_fn()
        projections = load_fn()
        assert len(projections) == expected_count, (
            f"{seed_file}: expected {expected_count}, got {len(projections)}"
        )

    def test_invalid_seed_file_raises(self):
        """Non-existent seed file raises error (ValueError from get_seed_path)."""
        load_fn, clear_fn = make_projection_loader("nonexistent.json")
        clear_fn()
        # get_seed_path() raises ValueError for unknown seed names
        with pytest.raises(ValueError, match="Unknown seed"):
            load_fn()


class TestProductionJsonBoundary:
    """Bind projection_loader.py tests to the current production JSON loader path."""

    @pytest.mark.parametrize(
        "seed_file",
        [
            "kernel.v1.json",
            "match.v2.json",
            "subst.v2.json",
            "bootstrap_structural.v1.json",
            "rcx_engine.v1.json",
        ],
    )
    def test_loader_matches_load_verified_seed_for_current_json_image(
        self, seed_file: str
    ):
        """make_projection_loader returns the production verified JSON projections."""
        expected_seed = load_verified_seed(get_seed_path(seed_file), verify=True)
        load_fn, clear_fn = make_projection_loader(seed_file)

        clear_fn()
        projections = load_fn()

        assert projections == expected_seed["projections"]
        assert [p["id"] for p in projections] == EXPECTED_PROJECTION_IDS[seed_file]

    def test_loader_rejects_malformed_registered_seed_after_checksum(
        self, tmp_path, monkeypatch
    ):
        """Projection loader fails closed through load_verified_seed structure checks."""
        malformed_seed = tmp_path / "kernel.v1.json"
        content = (
            '{"meta": {"version": "1.0", "name": "KERNEL_SEED", '
            '"description": "malformed projection control"}, '
            '"projections": [null]}'
        ).encode("utf-8")
        malformed_seed.write_bytes(content)
        monkeypatch.setattr(
            projection_loader_module,
            "get_seed_path",
            lambda _seed_file: malformed_seed,
        )
        monkeypatch.setitem(
            seed_integrity_module.SEED_CHECKSUMS,
            "kernel.v1.json",
            compute_checksum(content),
        )

        load_fn, clear_fn = projection_loader_module.make_projection_loader(
            "kernel.v1.json"
        )
        clear_fn()
        with pytest.raises(ValueError, match="projection 0 must be a dict"):
            load_fn()


class TestProjectionIntegrity:
    """Test that loaded projections have valid structure."""

    def test_match_projections_have_mode_patterns(self):
        """Match projections pattern on 'mode' field."""
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        projections = load_fn()

        # At least some projections should have mode in pattern
        mode_patterns = [
            p for p in projections
            if isinstance(p.get("pattern"), dict) and "mode" in p["pattern"]
        ]
        assert len(mode_patterns) > 0

    def test_kernel_projections_have_mode_patterns(self):
        """Kernel projections pattern on '_mode' field."""
        load_fn, clear_fn = make_projection_loader("kernel.v1.json")
        clear_fn()
        projections = load_fn()

        # kernel.wrap patterns on _step, others on _mode
        mode_patterns = [
            p for p in projections
            if isinstance(p.get("pattern"), dict) and (
                "_mode" in p["pattern"] or "_step" in p["pattern"]
            )
        ]
        assert len(mode_patterns) == len(projections)

    def test_projection_ids_are_unique(self):
        """All projection IDs in a seed are unique."""
        for seed_file in ["match.v1.json", "subst.v1.json", "kernel.v1.json"]:
            load_fn, clear_fn = make_projection_loader(seed_file)
            clear_fn()
            projections = load_fn()
            ids = [p["id"] for p in projections]
            assert len(ids) == len(set(ids)), f"Duplicate IDs in {seed_file}"

    def test_projection_ids_are_strings(self):
        """All projection IDs are strings."""
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        projections = load_fn()
        for proj in projections:
            assert isinstance(proj["id"], str)
