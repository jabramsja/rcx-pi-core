"""
Seed registry cross-validation: mechanical consistency between registries.

seed_integrity.py maintains parallel registries (SEED_CHECKSUMS,
EXPECTED_PROJECTION_IDS, MU_SEED_LOCATIONS, SEED_STATUS, SEED_DEPENDENCIES).
This test ensures they stay consistent with each other.

Existing parity tests (test_seed_loading_parity.py) verify CHECKSUMS↔LOCATIONS
bidirectional coverage. This test covers the remaining cross-registry gaps:
- EXPECTED_PROJECTION_IDS ↔ SEED_CHECKSUMS consistency
- SEED_STATUS ↔ SEED_CHECKSUMS consistency
- SEED_DEPENDENCIES referential integrity and acyclicity
- Path resolution for all registered seeds

Usage:
    PYTHONHASHSEED=0 pytest tests/engine/test_seed_registry_consistency.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rcx_pi.selfhost.seed_integrity import (
    SEED_CHECKSUMS,
    EXPECTED_PROJECTION_IDS,
    MU_SEED_LOCATIONS,
    SEED_STATUS,
    SEED_DEPENDENCIES,
    get_seed_path,
)


class TestProjectionIdsVsChecksums:
    """Every seed with projection IDs must have a checksum and vice versa."""

    def test_all_projection_id_seeds_have_checksums(self):
        """Every seed in EXPECTED_PROJECTION_IDS must be in SEED_CHECKSUMS."""
        missing = set(EXPECTED_PROJECTION_IDS) - set(SEED_CHECKSUMS)
        assert not missing, (
            f"Seeds with projection IDs but no checksum: {sorted(missing)}"
        )

    def test_all_checksum_seeds_have_projection_ids(self):
        """Every seed in SEED_CHECKSUMS must be in EXPECTED_PROJECTION_IDS."""
        missing = set(SEED_CHECKSUMS) - set(EXPECTED_PROJECTION_IDS)
        assert not missing, (
            f"Seeds with checksum but no projection IDs: {sorted(missing)}"
        )


class TestSeedStatusVsChecksums:
    """SEED_STATUS keys must be a subset of SEED_CHECKSUMS."""

    def test_all_status_seeds_have_checksums(self):
        """Every seed in SEED_STATUS must be in SEED_CHECKSUMS."""
        orphans = set(SEED_STATUS) - set(SEED_CHECKSUMS)
        assert not orphans, (
            f"Seeds with status but no checksum: {sorted(orphans)}"
        )

    def test_status_values_valid(self):
        """SEED_STATUS values must be from allowed set."""
        allowed = {"production", "legacy-poc"}
        for seed, status in SEED_STATUS.items():
            assert status in allowed, (
                f"Seed {seed} has invalid status '{status}', "
                f"allowed: {sorted(allowed)}"
            )


class TestSeedDependencies:
    """SEED_DEPENDENCIES referential integrity and structure."""

    def test_dependency_keys_have_checksums(self):
        """Every seed with dependencies must be in SEED_CHECKSUMS."""
        orphans = set(SEED_DEPENDENCIES) - set(SEED_CHECKSUMS)
        assert not orphans, (
            f"Seeds with dependencies but no checksum: {sorted(orphans)}"
        )

    def test_dependency_targets_have_checksums(self):
        """Every dependency target must be a registered seed."""
        for seed, deps in SEED_DEPENDENCIES.items():
            for dep in deps:
                assert dep in SEED_CHECKSUMS, (
                    f"Seed {seed} depends on {dep} which is not registered"
                )

    def test_no_self_dependencies(self):
        """No seed depends on itself."""
        for seed, deps in SEED_DEPENDENCIES.items():
            assert seed not in deps, (
                f"Seed {seed} has self-dependency"
            )

    def test_no_circular_dependencies(self):
        """Dependency graph is acyclic (DAG)."""
        visited = set()
        path = set()

        def has_cycle(node):
            if node in path:
                return True
            if node in visited:
                return False
            visited.add(node)
            path.add(node)
            for dep in SEED_DEPENDENCIES.get(node, []):
                if has_cycle(dep):
                    return True
            path.discard(node)
            return False

        for seed in SEED_DEPENDENCIES:
            assert not has_cycle(seed), (
                f"Circular dependency detected involving {seed}"
            )


class TestPathResolution:
    """get_seed_path() succeeds for every registered seed."""

    @pytest.mark.parametrize("seed_name", sorted(SEED_CHECKSUMS.keys()))
    def test_seed_path_exists(self, seed_name):
        """Seed file exists on disk at the path constructed from registry."""
        path = get_seed_path(seed_name)
        assert path.exists(), (
            f"Seed {seed_name} path does not exist: {path}"
        )

    @pytest.mark.parametrize("seed_name", sorted(SEED_CHECKSUMS.keys()))
    def test_seed_path_is_json(self, seed_name):
        """Seed path ends in .json."""
        path = get_seed_path(seed_name)
        assert path.suffix == ".json", (
            f"Seed {seed_name} path is not .json: {path}"
        )


class TestRegistryCompleteness:
    """All three main registries cover the same seed set."""

    def test_three_registry_key_alignment(self):
        """CHECKSUMS, PROJECTION_IDS, and LOCATIONS must cover the same seeds."""
        checksums_set = set(SEED_CHECKSUMS)
        proj_ids_set = set(EXPECTED_PROJECTION_IDS)
        locations_set = set(MU_SEED_LOCATIONS)

        # Report all gaps at once
        gaps = []
        only_checksums = checksums_set - proj_ids_set - locations_set
        if only_checksums:
            gaps.append(f"Only in CHECKSUMS: {sorted(only_checksums)}")

        only_proj_ids = proj_ids_set - checksums_set
        if only_proj_ids:
            gaps.append(f"Only in PROJECTION_IDS: {sorted(only_proj_ids)}")

        only_locations = locations_set - checksums_set
        if only_locations:
            gaps.append(f"Only in LOCATIONS: {sorted(only_locations)}")

        in_checksums_not_locations = checksums_set - locations_set
        if in_checksums_not_locations:
            gaps.append(
                f"In CHECKSUMS but not LOCATIONS: {sorted(in_checksums_not_locations)}"
            )

        in_checksums_not_proj_ids = checksums_set - proj_ids_set
        if in_checksums_not_proj_ids:
            gaps.append(
                f"In CHECKSUMS but not PROJECTION_IDS: {sorted(in_checksums_not_proj_ids)}"
            )

        assert not gaps, "Registry alignment gaps:\n" + "\n".join(gaps)
