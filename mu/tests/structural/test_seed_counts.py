"""
Grounding tests for seed projection counts and integrity.

These tests verify that seed files have the expected structure.
If a seed file changes (projections added/removed), these tests
will fail, prompting a review of whether the change is intentional.

This prevents doc drift by making seed structure machine-verifiable.

NOTE: All seeds are now loaded from mu/ (canonical location).
The legacy seeds/ folder is deprecated.
"""

import json
from pathlib import Path

import pytest

from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed

ROOT = Path(__file__).parent.parent.parent
MU_DIR = ROOT / "mu"

# mu/ folder structure (canonical location for all seeds)
MU_SEEDS = {
    "substrate": ["kernel.v1.json", "match.v1.json", "match.v2.json", "subst.v1.json", "subst.v2.json"],
    "closures": ["recurrence.v1.json", "recurrence.v2.json", "exhaustion.v1.json", "fix.v1.json"],
    "programs": ["rcx_engine.v1.json", "hemispheres.v1.json", "paxos_demo.v1.json"],
    "utilities": ["classify.v1.json", "eval.v1.json"],
    "bridge": ["bootstrap_structural.v1.json"],
}

# All known seeds (flattened from MU_SEEDS)
ALL_SEEDS = [
    seed for seeds in MU_SEEDS.values() for seed in seeds
]

# Self-hosting seeds (follow naming conventions)
SELFHOST_SEEDS = [
    "match.v1.json", "subst.v1.json", "classify.v1.json", "kernel.v1.json",
    "match.v2.json", "subst.v2.json",
]

# Expected projection counts (update intentionally when seeds change)
EXPECTED_COUNTS = {
    "match.v1.json": 7,      # Phase 6c
    "subst.v1.json": 12,     # Phase 6a (includes lookup)
    "classify.v1.json": 6,   # Phase 6b
    "eval.v1.json": 7,       # deep_eval traversal (legacy naming)
    "kernel.v1.json": 7,     # Phase 7a (meta-circular kernel)
    "match.v2.json": 8,      # Phase 7b: 7 + match.fail
    "subst.v2.json": 12,     # Phase 7b: same count, added _subst_ctx
    # mu/closures/ seeds
    "recurrence.v1.json": 9,   # closure detection
    "recurrence.v2.json": 9,   # hash-accelerated closure detection
    "exhaustion.v1.json": 11,  # operator exhaustion
    "fix.v1.json": 6,          # structural fix (GAP-04-FIX, Rule 0.6) + idempotence guards
    # mu/programs/
    "rcx_engine.v1.json": 11,  # main program (+ fix dispatch + fix routing + trampoline loop)
    "hemispheres.v1.json": 12,  # native structural routing (5-way: null, inf, a, lobes, sink)
    "paxos_demo.v1.json": 6,   # consensus demo (+ engine-output healer)
    # mu/bridge/
    "bootstrap_structural.v1.json": 5,  # non-linear pattern support
}

# Expected namespace prefixes (self-hosting seeds only)
EXPECTED_PREFIXES = {
    "match.v1.json": "match.",
    "subst.v1.json": "subst.",
    "classify.v1.json": "classify.",
    "kernel.v1.json": "kernel.",
    "match.v2.json": "match.",
    "subst.v2.json": "subst.",
}


def load_seed(name: str) -> dict:
    """Load a seed file from mu/ via get_seed_path() and return parsed JSON."""
    seed_path = get_seed_path(name)
    return load_verified_seed(seed_path, verify=True)


def load_mu_seed(subfolder: str, name: str) -> dict:
    """Load a seed file from mu/<subfolder>/ and return parsed JSON."""
    seed_path = MU_DIR / subfolder / name
    with open(seed_path) as f:
        return json.load(f)


def get_projection_ids(seed: dict) -> list[str]:
    """Extract projection IDs from a seed."""
    return [p["id"] for p in seed.get("projections", [])]


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
    """Verify all expected seed files exist in mu/."""

    @pytest.mark.parametrize("seed_name", ALL_SEEDS)
    def test_seed_file_exists(self, seed_name):
        """Seed file must exist in mu/ directory."""
        seed_path = get_seed_path(seed_name)
        assert seed_path.exists(), f"Missing seed file: {seed_path}"

    @pytest.mark.parametrize("subfolder,seeds", list(MU_SEEDS.items()))
    def test_no_unexpected_seed_files(self, subfolder, seeds):
        """No seed files exist that aren't in MU_SEEDS.

        If you add a new seed, add it to MU_SEEDS at the top of this file.
        """
        subfolder_path = MU_DIR / subfolder
        if not subfolder_path.exists():
            pytest.skip(f"mu/{subfolder}/ does not exist")

        actual_seeds = set(p.name for p in subfolder_path.glob("*.json"))
        expected_seeds = set(seeds)

        unexpected = actual_seeds - expected_seeds
        assert not unexpected, (
            f"Unexpected seed files in mu/{subfolder}/: {unexpected}\n"
            f"Add them to MU_SEEDS in test_seed_counts.py"
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


# NOTE: Checksum verification tests are in tests/test_seed_integrity.py
# (TestChecksumsCurrent class) using SEED_CHECKSUMS from seed_integrity.py.
# This file focuses on projection count validation, not checksum enforcement.


class TestMuFolderStructure:
    """Verify mu/ folder structure seeds are correctly organized."""

    @pytest.mark.parametrize("subfolder,seeds", list(MU_SEEDS.items()))
    def test_mu_subfolder_exists(self, subfolder, seeds):
        """Each mu/ subfolder should exist."""
        subfolder_path = MU_DIR / subfolder
        assert subfolder_path.exists(), f"mu/{subfolder}/ should exist"

    @pytest.mark.parametrize("subfolder,seeds", list(MU_SEEDS.items()))
    def test_mu_seeds_present(self, subfolder, seeds):
        """Each expected seed in mu/<subfolder>/ should exist."""
        for seed_name in seeds:
            seed_path = MU_DIR / subfolder / seed_name
            assert seed_path.exists(), f"mu/{subfolder}/{seed_name} should exist"

    def test_recurrence_projection_count(self):
        """mu/closures/recurrence.v1.json has expected count."""
        seed = load_mu_seed("closures", "recurrence.v1.json")
        ids = get_projection_ids(seed)
        expected = EXPECTED_COUNTS["recurrence.v1.json"]
        assert len(ids) == expected, f"recurrence.v1.json: expected {expected}, found {len(ids)}"

    def test_exhaustion_projection_count(self):
        """mu/closures/exhaustion.v1.json has expected count."""
        seed = load_mu_seed("closures", "exhaustion.v1.json")
        ids = get_projection_ids(seed)
        expected = EXPECTED_COUNTS["exhaustion.v1.json"]
        assert len(ids) == expected, f"exhaustion.v1.json: expected {expected}, found {len(ids)}"

    def test_rcx_engine_projection_count(self):
        """mu/programs/rcx_engine.v1.json has expected count."""
        seed = load_mu_seed("programs", "rcx_engine.v1.json")
        ids = get_projection_ids(seed)
        expected = EXPECTED_COUNTS["rcx_engine.v1.json"]
        assert len(ids) == expected, f"rcx_engine.v1.json: expected {expected}, found {len(ids)}"

    def test_recurrence_ids_have_recurrence_prefix(self):
        """recurrence.v1.json projections use recurrence.* prefix."""
        seed = load_mu_seed("closures", "recurrence.v1.json")
        ids = get_projection_ids(seed)
        for proj_id in ids:
            assert proj_id.startswith("recurrence."), f"ID '{proj_id}' should start with 'recurrence.'"

    def test_exhaustion_ids_have_exhaustion_prefix(self):
        """exhaustion.v1.json projections use exhaustion.* prefix."""
        seed = load_mu_seed("closures", "exhaustion.v1.json")
        ids = get_projection_ids(seed)
        for proj_id in ids:
            assert proj_id.startswith("exhaustion."), f"ID '{proj_id}' should start with 'exhaustion.'"

    def test_rcx_engine_ids_have_engine_prefix(self):
        """rcx_engine.v1.json projections use engine.* prefix."""
        seed = load_mu_seed("programs", "rcx_engine.v1.json")
        ids = get_projection_ids(seed)
        for proj_id in ids:
            assert proj_id.startswith("engine."), f"ID '{proj_id}' should start with 'engine.'"

    def test_bootstrap_structural_ids_have_bridge_prefix(self):
        """bootstrap_structural.v1.json projections use bridge.* prefix."""
        seed = load_mu_seed("bridge", "bootstrap_structural.v1.json")
        ids = get_projection_ids(seed)
        for proj_id in ids:
            assert proj_id.startswith("bridge."), f"ID '{proj_id}' should start with 'bridge.'"
