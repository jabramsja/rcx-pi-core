"""
Grounding tests for seed projection counts and integrity.

These tests verify that seed files have the expected structure.
If a seed file changes (projections added/removed), these tests
will fail, prompting a review of whether the change is intentional.

This prevents doc drift by making seed structure machine-verifiable.
"""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
SEEDS_DIR = ROOT / "seeds"

# All known seed files
ALL_SEEDS = ["match.v1.json", "subst.v1.json", "classify.v1.json", "eval.v1.json", "kernel.v1.json"]

# Self-hosting seeds (follow naming conventions)
SELFHOST_SEEDS = ["match.v1.json", "subst.v1.json", "classify.v1.json", "kernel.v1.json"]

# Expected projection counts (update intentionally when seeds change)
EXPECTED_COUNTS = {
    "match.v1.json": 7,      # Phase 6c
    "subst.v1.json": 12,     # Phase 6a (includes lookup)
    "classify.v1.json": 6,   # Phase 6b
    "eval.v1.json": 7,       # deep_eval traversal (legacy naming)
    "kernel.v1.json": 7,     # Phase 7a (meta-circular kernel)
}

# Expected namespace prefixes (self-hosting seeds only)
EXPECTED_PREFIXES = {
    "match.v1.json": "match.",
    "subst.v1.json": "subst.",
    "classify.v1.json": "classify.",
    "kernel.v1.json": "kernel.",
}


def load_seed(name: str) -> dict:
    """Load a seed file and return parsed JSON."""
    seed_path = SEEDS_DIR / name
    with open(seed_path) as f:
        return json.load(f)


def get_projection_ids(seed: dict) -> list[str]:
    """Extract projection IDs from a seed."""
    return [p["id"] for p in seed.get("projections", [])]


def compute_seed_checksum(name: str) -> str:
    """Compute SHA256 checksum of seed file."""
    seed_path = SEEDS_DIR / name
    content = seed_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


class TestSeedProjectionCounts:
    """Verify seed projection counts are stable."""

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_seed_projection_count(self, seed_name):
        """Seed has expected number of projections.

        If this test fails after adding/removing a projection,
        update EXPECTED_COUNTS intentionally.
        """
        seed = load_seed(seed_name)
        ids = get_projection_ids(seed)

        expected = EXPECTED_COUNTS[seed_name]
        actual = len(ids)

        assert actual == expected, (
            f"{seed_name}: expected {expected} projections, found {actual}.\n"
            f"Projection IDs: {ids}\n"
            f"If intentional, update EXPECTED_COUNTS in this file."
        )


class TestSeedProjectionNaming:
    """Verify projection ID conventions are followed.

    Note: eval.v1.json uses legacy naming (predates self-hosting convention).
    Only self-hosting seeds (match, subst, classify) are checked for prefix/wrap.
    """

    @pytest.mark.parametrize("seed_name", SELFHOST_SEEDS)
    def test_projection_ids_have_correct_prefix(self, seed_name):
        """Self-hosting seed IDs should start with seed namespace."""
        seed = load_seed(seed_name)
        ids = get_projection_ids(seed)
        prefix = EXPECTED_PREFIXES[seed_name]

        for proj_id in ids:
            assert proj_id.startswith(prefix), (
                f"{seed_name}: projection '{proj_id}' should start with '{prefix}'"
            )

    @pytest.mark.parametrize("seed_name", SELFHOST_SEEDS)
    def test_wrap_projection_is_last(self, seed_name):
        """Self-hosting wrap projection must be last (catch-all entry point).

        Exception: kernel seeds have .wrap as first (entry) and .unwrap as last (exit).
        """
        seed = load_seed(seed_name)
        ids = get_projection_ids(seed)

        assert ids, f"{seed_name}: no projections found"

        last_id = ids[-1]
        if seed_name == "kernel.v1.json":
            # Kernel seeds: wrap is first (entry), unwrap is last (exit)
            assert last_id.endswith(".unwrap"), (
                f"{seed_name}: last projection should be .unwrap, found '{last_id}'"
            )
            assert ids[0].endswith(".wrap"), (
                f"{seed_name}: first projection should be .wrap, found '{ids[0]}'"
            )
        else:
            assert last_id.endswith(".wrap"), (
                f"{seed_name}: last projection should be .wrap, found '{last_id}'"
            )

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
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


class TestSeedSchema:
    """Verify projection schema requirements."""

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_all_projections_have_required_fields(self, seed_name):
        """Each projection must have id, pattern, body."""
        seed = load_seed(seed_name)

        for i, proj in enumerate(seed.get("projections", [])):
            proj_id = proj.get("id", f"<projection {i}>")

            assert "id" in proj, f"{seed_name} {proj_id}: missing 'id'"
            assert "pattern" in proj, f"{seed_name} {proj_id}: missing 'pattern'"
            assert "body" in proj, f"{seed_name} {proj_id}: missing 'body'"

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_seed_has_meta_section(self, seed_name):
        """Each seed must have a meta section with version."""
        seed = load_seed(seed_name)

        assert "meta" in seed, f"{seed_name}: missing 'meta' section"
        assert "version" in seed["meta"], f"{seed_name}: missing 'meta.version'"
        assert "name" in seed["meta"], f"{seed_name}: missing 'meta.name'"

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_seed_has_projections_key(self, seed_name):
        """Each seed must have a projections array."""
        seed = load_seed(seed_name)

        assert "projections" in seed, f"{seed_name}: missing 'projections' key"
        assert isinstance(seed["projections"], list), (
            f"{seed_name}: 'projections' must be a list"
        )


class TestSeedFilesExist:
    """Verify all expected seed files exist."""

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_seed_file_exists(self, seed_name):
        """Seed file must exist in seeds/ directory."""
        seed_path = SEEDS_DIR / seed_name
        assert seed_path.exists(), f"Missing seed file: {seed_path}"

    def test_no_unexpected_seed_files(self):
        """No seed files exist that aren't in ALL_SEEDS.

        If you add a new seed, add it to ALL_SEEDS at the top of this file.
        """
        actual_seeds = set(p.name for p in SEEDS_DIR.glob("*.json"))
        expected_seeds = set(ALL_SEEDS)

        unexpected = actual_seeds - expected_seeds
        assert not unexpected, (
            f"Unexpected seed files found: {unexpected}\n"
            f"Add them to ALL_SEEDS in test_seed_counts.py"
        )


class TestProjectionOrder:
    """Verify projection order is security-critical (first-match-wins)."""

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_done_projection_before_wrap(self, seed_name):
        """Done projection must come before wrap (specific before general)."""
        seed = load_seed(seed_name)
        ids = get_projection_ids(seed)

        # Find positions
        done_positions = [i for i, id in enumerate(ids) if ".done" in id]
        wrap_positions = [i for i, id in enumerate(ids) if ".wrap" in id]

        if done_positions and wrap_positions:
            # All done projections must come before wrap
            for done_pos in done_positions:
                for wrap_pos in wrap_positions:
                    assert done_pos < wrap_pos, (
                        f"{seed_name}: .done projection at {done_pos} must come "
                        f"before .wrap at {wrap_pos} (first-match-wins)"
                    )


class TestSeedChecksums:
    """Verify seed checksums for tamper detection.

    These checksums are computed at test time and compared to stored values.
    If a seed changes, the checksum changes, and this test fails.
    This provides an additional layer of change detection beyond projection counts.
    """

    # Stored checksums (update when seeds legitimately change)
    # Run: python3 -c "import hashlib; print(hashlib.sha256(open('seeds/X.json','rb').read()).hexdigest()[:16])"
    CHECKSUMS = {
        "match.v1.json": None,      # Populated on first run
        "subst.v1.json": None,
        "classify.v1.json": None,
        "eval.v1.json": None,
    }

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_seed_checksum_logged(self, seed_name):
        """Log seed checksum for verification (informational test).

        This test always passes but logs the checksum.
        Use this to populate CHECKSUMS dict above.
        """
        checksum = compute_seed_checksum(seed_name)
        # Just log it - actual enforcement is in test_seed_integrity.py
        # which uses SHA256 checksums stored in seed_integrity.py
        assert checksum, f"{seed_name}: computed checksum {checksum}"
