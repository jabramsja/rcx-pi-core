"""
Seed loading parity guard.

Verifies that Python and JavaScript substrates load identical seed JSON
content (checksums) and projection IDs. These are hard invariants — if
the two substrates disagree on which seeds to load or their content,
cross-substrate parity breaks silently.

What this checker PROVES:
- Every JS-loaded seed has a matching Python checksum.
- Checksums are identical for all shared seeds.
- Projection ID lists match exactly (order-sensitive, first-match-wins).
- Python SEED_CHECKSUMS is a superset of JS SEED_CHECKSUMS (no JS-only seeds).
- MU_SEED_LOCATIONS covers every seed in SEED_CHECKSUMS.

What this checker does NOT prove:
- Semantic behavior parity (use test_js_parity_automated.py for that).
- Actual file content on disk (use seed_integrity.verify_all_checksums for that).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from rcx_pi.selfhost.seed_integrity import (
    SEED_CHECKSUMS,
    EXPECTED_PROJECTION_IDS,
    MU_SEED_LOCATIONS,
)

# ── Locate JS source ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]
_JS_PATH = _REPO / "mu" / "host" / "js" / "eval_step.js"


def _js_source() -> str:
    return _JS_PATH.read_text()


def _extract_js_seed_checksums(source: str) -> dict[str, str]:
    """Extract SEED_CHECKSUMS object from JS source."""
    pattern = r"const\s+SEED_CHECKSUMS\s*=\s*\{(.*?)\};"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail("Could not find SEED_CHECKSUMS in eval_step.js")
    block = m.group(1)
    # Extract 'name': 'hash' pairs
    pairs = re.findall(r"'([^']+)':\s*'([^']+)'", block)
    return dict(pairs)


def _extract_js_projection_ids(source: str) -> dict[str, list[str]]:
    """Extract EXPECTED_PROJECTION_IDS object from JS source."""
    pattern = r"const\s+EXPECTED_PROJECTION_IDS\s*=\s*\{(.*?)\};"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail("Could not find EXPECTED_PROJECTION_IDS in eval_step.js")
    block = m.group(1)
    result = {}
    # Find each seed entry: 'name.json': [...]
    for seed_match in re.finditer(r"'([^']+\.json)':\s*\[(.*?)\]", block, re.DOTALL):
        seed_name = seed_match.group(1)
        ids_block = seed_match.group(2)
        ids = re.findall(r"'([^']+)'", ids_block)
        result[seed_name] = ids
    return result


# ── Checksum parity ──────────────────────────────────────────────────────


class TestSeedChecksumParity:
    """Python and JS must agree on seed checksums."""

    def test_js_seeds_are_subset_of_python(self):
        """Every JS seed must exist in Python's SEED_CHECKSUMS."""
        js_checksums = _extract_js_seed_checksums(_js_source())
        js_only = set(js_checksums) - set(SEED_CHECKSUMS)
        assert not js_only, f"JS has seeds not in Python: {js_only}"

    def test_shared_checksums_match(self):
        """For every seed in both substrates, checksums must be identical."""
        js_checksums = _extract_js_seed_checksums(_js_source())
        mismatches = []
        for seed, js_hash in js_checksums.items():
            py_hash = SEED_CHECKSUMS.get(seed)
            if py_hash and py_hash != js_hash:
                mismatches.append(f"{seed}: py={py_hash[:12]}... js={js_hash[:12]}...")
        assert not mismatches, f"Checksum mismatches:\n" + "\n".join(mismatches)

    def test_js_loads_expected_seed_count(self):
        """JS must load exactly 11 seeds (kernel + match/subst v2 + closures + bridge + programs + metabolization)."""
        js_checksums = _extract_js_seed_checksums(_js_source())
        assert len(js_checksums) == 11, (
            f"JS seed count changed from 11 to {len(js_checksums)}. "
            f"Seeds: {sorted(js_checksums.keys())}"
        )

    def test_python_is_superset(self):
        """Python tracks more seeds than JS (v1 versions, utilities, demos)."""
        js_checksums = _extract_js_seed_checksums(_js_source())
        assert len(SEED_CHECKSUMS) > len(js_checksums), (
            "Python should track MORE seeds than JS (includes v1 versions, utilities)"
        )


# ── Projection ID parity ────────────────────────────────────────────────


class TestProjectionIdParity:
    """Projection IDs must match exactly between substrates (order matters)."""

    def test_js_projection_seeds_subset_of_python(self):
        """Every seed with JS projection IDs must also have Python projection IDs."""
        js_ids = _extract_js_projection_ids(_js_source())
        js_only = set(js_ids) - set(EXPECTED_PROJECTION_IDS)
        assert not js_only, f"JS has projection IDs for seeds not in Python: {js_only}"

    def test_projection_ids_match_exactly(self):
        """For shared seeds, projection ID lists must match (order-sensitive)."""
        js_ids = _extract_js_projection_ids(_js_source())
        mismatches = []
        for seed, js_list in js_ids.items():
            py_list = EXPECTED_PROJECTION_IDS.get(seed)
            if py_list is None:
                mismatches.append(f"{seed}: missing from Python")
                continue
            if py_list != js_list:
                mismatches.append(
                    f"{seed}:\n  py={py_list}\n  js={js_list}"
                )
        assert not mismatches, (
            f"Projection ID mismatches (order matters for first-match-wins):\n"
            + "\n".join(mismatches)
        )

    def test_projection_id_count_per_seed(self):
        """Projection count per seed must match between substrates."""
        js_ids = _extract_js_projection_ids(_js_source())
        for seed, js_list in js_ids.items():
            py_list = EXPECTED_PROJECTION_IDS.get(seed, [])
            assert len(py_list) == len(js_list), (
                f"{seed}: Python has {len(py_list)} projections, JS has {len(js_list)}"
            )


# ── Seed location coverage ──────────────────────────────────────────────


class TestSeedLocationCoverage:
    """MU_SEED_LOCATIONS must cover every seed in SEED_CHECKSUMS."""

    def test_every_checksum_seed_has_location(self):
        """Every seed in SEED_CHECKSUMS must have a location in MU_SEED_LOCATIONS."""
        missing = set(SEED_CHECKSUMS) - set(MU_SEED_LOCATIONS)
        assert not missing, f"Seeds without locations: {missing}"

    def test_no_orphan_locations(self):
        """Every seed in MU_SEED_LOCATIONS must be in SEED_CHECKSUMS."""
        orphans = set(MU_SEED_LOCATIONS) - set(SEED_CHECKSUMS)
        assert not orphans, f"Locations without checksums: {orphans}"

    def test_location_values_are_valid(self):
        """All location values must be valid mu/ subdirectories."""
        valid_dirs = {"substrate", "closures", "bridge", "programs", "utilities"}
        for seed, loc in MU_SEED_LOCATIONS.items():
            assert loc in valid_dirs, f"{seed} has invalid location '{loc}'"
