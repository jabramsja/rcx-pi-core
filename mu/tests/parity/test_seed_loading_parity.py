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

import functools
import re
import subprocess
from pathlib import Path

import pytest
from rcx_pi.selfhost.seed_integrity import (
    SEED_CHECKSUMS,
    EXPECTED_PROJECTION_IDS,
    MU_SEED_LOCATIONS,
)

# ── Locate JS source ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]
_JS_DIR = _REPO / "mu" / "host" / "js"


@functools.lru_cache(maxsize=1)
def _js_source() -> str:
    """Read all JS module files concatenated (monolith was split into modules)."""
    parts = []
    for f in sorted(_JS_DIR.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


def _extract_js_dict(source: str, const_name: str) -> dict[str, str]:
    """Extract a JS const object of 'key': 'value' pairs from source."""
    pattern = rf"const\s+{const_name}\s*=\s*\{{(.*?)\}};"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail(f"Could not find {const_name} in JS source")
    block = m.group(1)
    return dict(re.findall(r"'([^']+)':\s*'([^']+)'", block))


def _extract_js_list_dict(source: str, const_name: str) -> dict[str, list[str]]:
    """Extract a JS const object of 'key': [...] entries from source."""
    pattern = rf"const\s+{const_name}\s*=\s*\{{(.*?)\}};"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail(f"Could not find {const_name} in JS source")
    block = m.group(1)
    result = {}
    for seed_match in re.finditer(r"'([^']+\.json)':\s*\[(.*?)\]", block, re.DOTALL):
        seed_name = seed_match.group(1)
        ids_block = seed_match.group(2)
        ids = re.findall(r"'([^']+)'", ids_block)
        result[seed_name] = ids
    return result


def _extract_js_seed_checksums(source: str) -> dict[str, str]:
    return _extract_js_dict(source, "SEED_CHECKSUMS")


def _extract_js_projection_ids(source: str) -> dict[str, list[str]]:
    return _extract_js_list_dict(source, "EXPECTED_PROJECTION_IDS")


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
        """JS must load exactly 14 seeds (kernel + match/subst v2 + closures + bridge + programs + metabolization + metabolize_cycle + terminal_classify + evidence_walker)."""
        js_checksums = _extract_js_seed_checksums(_js_source())
        assert len(js_checksums) == 14, (
            f"JS seed count changed from 14 to {len(js_checksums)}. "
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


# ---------------------------------------------------------------------------
# F-46: Seed checksum verification fail-closed parity
# ---------------------------------------------------------------------------

class TestSeedChecksumFailClosed:
    """F-46: JS loadVerifiedSeed is fail-closed on unknown seeds (parity with Python)."""

    def test_js_rejects_unknown_seed_name(self):
        """loadVerifiedSeed with unregistered name must throw, not silently load."""
        js_script = (
            "const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');\n"
            "try {\n"
            "  loadVerifiedSeed('classify.v1.json', 'utilities');\n"
            "  process.stderr.write('FAIL: loaded unregistered seed');\n"
            "  process.exit(1);\n"
            "} catch(e) {\n"
            "  if (e.message.includes('Unknown seed') || e.message.includes('no checksum')) {\n"
            "    console.log('PASS');\n"
            "  } else {\n"
            "    process.stderr.write('WRONG ERROR: ' + e.message);\n"
            "    process.exit(1);\n"
            "  }\n"
            "}\n"
        )
        proc = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True, text=True,
            cwd=str(_REPO), timeout=10,
        )
        assert proc.returncode == 0, f"JS seed fail-closed test failed: {proc.stderr}"
        assert proc.stdout.strip() == "PASS"

    def test_python_rejects_unknown_seed_name(self):
        """Python verify_checksum rejects unknown seeds (regression lock)."""
        from rcx_pi.selfhost.seed_integrity import verify_checksum
        with pytest.raises(ValueError, match="Unknown seed"):
            verify_checksum("nonexistent_seed.v99.json", b"any content")


# ---------------------------------------------------------------------------
# N4: JS seed_loader.js CORE registries subset of cli/main.js registries
# ---------------------------------------------------------------------------

def _seed_loader_source() -> str:
    """Read seed_loader.js specifically (not concatenated rglob) to avoid comment shadowing."""
    path = _REPO / "mu" / "host" / "js" / "core" / "seed_loader.js"
    return path.read_text()


def _main_js_source() -> str:
    """Read cli/main.js specifically to avoid comment shadowing."""
    path = _REPO / "mu" / "host" / "js" / "cli" / "main.js"
    return path.read_text()


def _extract_js_core_seed_checksums() -> dict[str, str]:
    return _extract_js_dict(_seed_loader_source(), "CORE_SEED_CHECKSUMS")


def _extract_js_core_projection_ids() -> dict[str, list[str]]:
    return _extract_js_list_dict(_seed_loader_source(), "CORE_SEED_PROJECTION_IDS")


class TestJsSeedLoaderSubsetGate:
    """N4: seed_loader.js CORE registries must be a strict subset of cli/main.js registries."""

    def test_core_checksums_subset_of_main(self):
        """Every CORE_SEED_CHECKSUMS entry must exist in SEED_CHECKSUMS with same hash."""
        core = _extract_js_core_seed_checksums()
        main = _extract_js_dict(_main_js_source(), "SEED_CHECKSUMS")
        for seed, core_hash in core.items():
            assert seed in main, (
                f"seed_loader.js CORE_SEED_CHECKSUMS has '{seed}' not in cli/main.js SEED_CHECKSUMS"
            )
            assert main[seed] == core_hash, (
                f"Checksum mismatch for '{seed}': seed_loader={core_hash[:16]}... main={main[seed][:16]}..."
            )

    def test_core_projection_ids_subset_of_main(self):
        """Every CORE_SEED_PROJECTION_IDS entry must match cli/main.js exactly."""
        core = _extract_js_core_projection_ids()
        main = _extract_js_list_dict(_main_js_source(), "EXPECTED_PROJECTION_IDS")
        for seed, core_ids in core.items():
            assert seed in main, (
                f"seed_loader.js CORE_SEED_PROJECTION_IDS has '{seed}' not in cli/main.js"
            )
            assert main[seed] == core_ids, (
                f"Projection ID mismatch for '{seed}':\n"
                f"  seed_loader: {core_ids}\n  main: {main[seed]}"
            )

    def test_core_checksum_and_projection_id_keys_match(self):
        """CORE_SEED_CHECKSUMS and CORE_SEED_PROJECTION_IDS must have identical key sets."""
        core_checksums = _extract_js_core_seed_checksums()
        core_ids = _extract_js_core_projection_ids()
        assert set(core_checksums) == set(core_ids), (
            f"seed_loader.js registry asymmetry: "
            f"checksums={sorted(core_checksums)} ids={sorted(core_ids)}"
        )
