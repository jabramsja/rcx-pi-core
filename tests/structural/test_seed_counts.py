"""
Grounding tests for seed projection counts.

These tests verify that seed files have the expected structure.
If a seed file changes (projections added/removed), these tests
will fail, prompting a review of whether the change is intentional.

This prevents doc drift by making seed structure machine-verifiable.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
SEEDS_DIR = ROOT / "seeds"


def load_seed(name: str) -> dict:
    """Load a seed file and return parsed JSON."""
    seed_path = SEEDS_DIR / name
    with open(seed_path) as f:
        return json.load(f)


def get_projection_ids(seed: dict) -> list[str]:
    """Extract projection IDs from a seed."""
    return [p["id"] for p in seed.get("projections", [])]


class TestSeedProjectionCounts:
    """Verify seed projection counts are stable."""

    def test_match_seed_projection_count(self):
        """Match seed has expected number of projections.

        If this test fails after adding/removing a projection,
        update the expected count intentionally.
        """
        seed = load_seed("match.v1.json")
        ids = get_projection_ids(seed)

        # Current count as of Phase 6c
        expected = 7
        actual = len(ids)

        assert actual == expected, (
            f"match.v1.json: expected {expected} projections, found {actual}.\n"
            f"Projection IDs: {ids}\n"
            f"If intentional, update this test."
        )

    def test_subst_seed_projection_count(self):
        """Subst seed has expected number of projections."""
        seed = load_seed("subst.v1.json")
        ids = get_projection_ids(seed)

        # Current count as of Phase 6a (includes lookup projections)
        expected = 12
        actual = len(ids)

        assert actual == expected, (
            f"subst.v1.json: expected {expected} projections, found {actual}.\n"
            f"Projection IDs: {ids}\n"
            f"If intentional, update this test."
        )

    def test_classify_seed_projection_count(self):
        """Classify seed has expected number of projections."""
        seed = load_seed("classify.v1.json")
        ids = get_projection_ids(seed)

        # Current count as of Phase 6b
        expected = 6
        actual = len(ids)

        assert actual == expected, (
            f"classify.v1.json: expected {expected} projections, found {actual}.\n"
            f"Projection IDs: {ids}\n"
            f"If intentional, update this test."
        )


class TestSeedProjectionNaming:
    """Verify projection ID conventions are followed."""

    @pytest.mark.parametrize("seed_name,prefix", [
        ("match.v1.json", "match."),
        ("subst.v1.json", "subst."),
        ("classify.v1.json", "classify."),
    ])
    def test_projection_ids_have_correct_prefix(self, seed_name, prefix):
        """All projection IDs should start with seed namespace."""
        seed = load_seed(seed_name)
        ids = get_projection_ids(seed)

        for proj_id in ids:
            assert proj_id.startswith(prefix), (
                f"{seed_name}: projection '{proj_id}' should start with '{prefix}'"
            )

    @pytest.mark.parametrize("seed_name", [
        "match.v1.json",
        "subst.v1.json",
        "classify.v1.json",
    ])
    def test_wrap_projection_is_last(self, seed_name):
        """Wrap projection must be last (catch-all entry point)."""
        seed = load_seed(seed_name)
        ids = get_projection_ids(seed)

        assert ids, f"{seed_name}: no projections found"

        last_id = ids[-1]
        assert last_id.endswith(".wrap"), (
            f"{seed_name}: last projection should be .wrap, found '{last_id}'"
        )


class TestSeedSchema:
    """Verify projection schema requirements."""

    @pytest.mark.parametrize("seed_name", [
        "match.v1.json",
        "subst.v1.json",
        "classify.v1.json",
    ])
    def test_all_projections_have_required_fields(self, seed_name):
        """Each projection must have id, pattern, body."""
        seed = load_seed(seed_name)

        for i, proj in enumerate(seed.get("projections", [])):
            proj_id = proj.get("id", f"<projection {i}>")

            assert "id" in proj, f"{seed_name} {proj_id}: missing 'id'"
            assert "pattern" in proj, f"{seed_name} {proj_id}: missing 'pattern'"
            assert "body" in proj, f"{seed_name} {proj_id}: missing 'body'"

    @pytest.mark.parametrize("seed_name", [
        "match.v1.json",
        "subst.v1.json",
        "classify.v1.json",
    ])
    def test_seed_has_meta_section(self, seed_name):
        """Each seed must have a meta section with version."""
        seed = load_seed(seed_name)

        assert "meta" in seed, f"{seed_name}: missing 'meta' section"
        assert "version" in seed["meta"], f"{seed_name}: missing 'meta.version'"
        assert "name" in seed["meta"], f"{seed_name}: missing 'meta.name'"

    @pytest.mark.parametrize("seed_name", [
        "match.v1.json",
        "subst.v1.json",
        "classify.v1.json",
    ])
    def test_no_duplicate_projection_ids(self, seed_name):
        """Each projection ID must be unique within the seed."""
        seed = load_seed(seed_name)
        ids = get_projection_ids(seed)

        seen = set()
        duplicates = []
        for proj_id in ids:
            if proj_id in seen:
                duplicates.append(proj_id)
            seen.add(proj_id)

        assert not duplicates, (
            f"{seed_name}: duplicate projection IDs: {duplicates}"
        )
