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
from pathlib import Path

from rcx_pi.selfhost.projection_loader import make_projection_loader
from rcx_pi.selfhost.seed_integrity import get_seeds_dir


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

    def test_second_load_returns_same_object(self):
        """Caching returns same list object on subsequent calls."""
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        first = load_fn()
        second = load_fn()
        assert first is second  # Same object, not just equal

    def test_clear_forces_reload(self):
        """Clear function forces next load to reload from disk."""
        load_fn, clear_fn = make_projection_loader("match.v1.json")
        clear_fn()
        first = load_fn()
        clear_fn()
        second = load_fn()
        # After clear, should be a new list (equal but not same object)
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
        assert load_subst() is subst_projs  # Still cached


class TestSeedLoading:
    """Test loading of various seed files."""

    @pytest.mark.parametrize("seed_file,expected_count", [
        ("match.v1.json", 7),
        ("match.v2.json", 8),
        ("subst.v1.json", 12),
        ("subst.v2.json", 12),
        ("classify.v1.json", 6),
        ("kernel.v1.json", 7),
        # Note: eval.v1.json excluded - not registered in seed_integrity checksums
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
        """Non-existent seed file raises error."""
        load_fn, clear_fn = make_projection_loader("nonexistent.json")
        clear_fn()
        with pytest.raises(FileNotFoundError):
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
