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

import base64
from collections import Counter
import functools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from rcx_pi.selfhost.seed_integrity import (
    SEED_CHECKSUMS,
    SEED_DEPENDENCIES,
    SEED_REGISTRY_MANIFEST,
    SEED_BINARY_CHECKSUM_POLICY_ID,
    SEED_BINARY_MIGRATION_POLICY_ID,
    EXPECTED_PROJECTION_IDS,
    MU_SEED_LOCATIONS,
    compute_checksum,
    get_seed_path,
    load_verified_seed,
    load_verified_seed_image,
)
import mu.tools.util.seed_binary_migration as seed_binary_migration_tool
from mu.tools.util.seed_binary_migration import (
    SeedBinaryMigrationError,
    decode_seed_binary_projections,
    encode_seed_binary_projections,
    generate_seed_binary_migration_artifact,
    verify_seed_binary_migration_artifact,
)
from mu.tests.research.test_d010_h5_projection_loader_binary import (
    mu_decode_value,
    mu_encode,
)

# ── Locate JS source ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]


@functools.lru_cache(maxsize=1)
def _js_registry_snapshot() -> dict[str, dict[str, object]]:
    """Read JS registry views after manifest verification and derivation."""
    js_script = """
    const sl = require('./mu/host/js/core/seed_loader');
    console.log(JSON.stringify({
      SEED_REGISTRY_MANIFEST: sl.SEED_REGISTRY_MANIFEST,
      SEED_CHECKSUMS: sl.SEED_CHECKSUMS,
      EXPECTED_PROJECTION_IDS: sl.EXPECTED_PROJECTION_IDS,
      CORE_SEED_CHECKSUMS: sl.CORE_SEED_CHECKSUMS,
      CORE_SEED_PROJECTION_IDS: sl.CORE_SEED_PROJECTION_IDS,
      SEED_SUBDIRS: sl.SEED_SUBDIRS,
    }));
    """
    proc = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS registry probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_seed_checksums() -> dict[str, str]:
    return _js_registry_snapshot()["SEED_CHECKSUMS"]


def _js_projection_ids() -> dict[str, list[str]]:
    return _js_registry_snapshot()["EXPECTED_PROJECTION_IDS"]


def _python_load_verified_seed_result(seed_path: Path) -> dict[str, object]:
    try:
        seed = load_verified_seed(seed_path, verify=True)
    except Exception as exc:  # tests compare fail-closed behavior across substrates
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "ids": [proj["id"] for proj in seed["projections"]]}


def _js_load_verified_seed_result(seed_name: str, subdir: str) -> dict[str, object]:
    js_script = f"""
    const {{ loadVerifiedSeed }} = require('./mu/host/js/core/seed_loader');
    try {{
      const seed = loadVerifiedSeed({json.dumps(seed_name)}, {json.dumps(subdir)});
      console.log(JSON.stringify({{
        ok: true,
        ids: seed.projections.map(p => p.id),
      }}));
    }} catch (e) {{
      console.log(JSON.stringify({{
        ok: false,
        error: e.message,
      }}));
    }}
    """
    proc = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed loader probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_load_verified_seed_subdir_error(seed_name: str, subdir: str) -> dict[str, object]:
    js_script = f"""
    const {{ loadVerifiedSeed }} = require('./mu/host/js/core/seed_loader');
    try {{
      loadVerifiedSeed({json.dumps(seed_name)}, {json.dumps(subdir)});
      console.log(JSON.stringify({{ok: true}}));
    }} catch (e) {{
      console.log(JSON.stringify({{
        ok: false,
        error: e.message,
      }}));
    }}
    """
    proc = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed loader subdir probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _python_load_verified_seed_image_result(
    seed_name: str, seed_bytes: bytes, *, verify: bool
) -> dict[str, object]:
    try:
        seed = load_verified_seed_image(seed_name, seed_bytes, verify=verify)
    except Exception as exc:  # tests compare fail-closed behavior across substrates
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "ids": [proj["id"] for proj in seed["projections"]]}


def _python_load_verified_seed_binary_image_result(
    seed_name: str,
    seed_bytes: bytes,
    binary_bytes: bytes,
    expected_proof: dict[str, object],
) -> dict[str, object]:
    try:
        seed = load_verified_seed_image(
            seed_name,
            seed_bytes,
            verify=True,
            binary_image=binary_bytes,
            expected_binary_proof=expected_proof,
        )
    except Exception as exc:  # tests compare fail-closed behavior across substrates
        return {"ok": False, "error": str(exc), "name": type(exc).__name__}
    return {"ok": True, "ids": [proj["id"] for proj in seed["projections"]]}


def _js_load_verified_seed_image_result(
    seed_name: str,
    raw_json: str,
) -> dict[str, object]:
    js_script = f"""
    const {{
      loadVerifiedSeedImage,
      SEED_IMAGE_VERIFICATION_MODES,
    }} = require('./mu/host/js/core/seed_loader');
    const raw = Buffer.from({json.dumps(raw_json)}, 'utf8');
    try {{
      const seed = loadVerifiedSeedImage(
        {json.dumps(seed_name)},
        raw,
        SEED_IMAGE_VERIFICATION_MODES.CLI
      );
      console.log(JSON.stringify({{
        ok: true,
        ids: seed.projections.map(p => p.id),
      }}));
    }} catch (e) {{
      console.log(JSON.stringify({{
        ok: false,
        error: e.message,
      }}));
    }}
    """
    proc = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed image loader probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_load_verified_seed_image_bytes_result(
    seed_name: str,
    seed_bytes: bytes,
    *,
    forced_sha256: str | None = None,
) -> dict[str, object]:
    js_script = """
    const fs = require('fs');
    const {
      loadVerifiedSeedImage,
      SEED_IMAGE_VERIFICATION_MODES,
    } = require('./mu/host/js/core/seed_loader');
    const crypto = require('crypto');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const raw = Buffer.from(input.seedBytesBase64, 'base64');
    const originalCreateHash = crypto.createHash;
    if (input.forcedSha256 !== null) {
      crypto.createHash = function(...args) {
        const hash = originalCreateHash.apply(this, args);
        return {
          update(...updateArgs) {
            hash.update(...updateArgs);
            return this;
          },
          digest(encoding) {
            if (encoding === 'hex') {
              return input.forcedSha256;
            }
            return hash.digest(encoding);
          },
        };
      };
    }
    let result;
    try {
      const seed = loadVerifiedSeedImage(
        input.seedName,
        raw,
        SEED_IMAGE_VERIFICATION_MODES.CLI
      );
      result = {
        ok: true,
        ids: seed.projections.map(p => p.id),
      };
    } catch (e) {
      result = {
        ok: false,
        error: e.message,
      };
    } finally {
      crypto.createHash = originalCreateHash;
    }
    console.log(JSON.stringify(result));
    """
    payload = {
        "seedName": seed_name,
        "seedBytesBase64": base64.b64encode(seed_bytes).decode("ascii"),
        "forcedSha256": forced_sha256,
    }
    proc = subprocess.run(
        ["node", "-e", js_script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed image bytes probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_load_registered_seed_image_bytes_result(
    seed_name: str,
    seed_bytes: bytes,
) -> dict[str, object]:
    js_script = """
    const fs = require('fs');
    const {
      loadVerifiedSeedImage,
      SEED_IMAGE_VERIFICATION_MODES,
    } = require('./mu/host/js/core/seed_loader');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const raw = Buffer.from(input.seedBytesBase64, 'base64');
    try {
      const seed = loadVerifiedSeedImage(
        input.seedName,
        raw,
        SEED_IMAGE_VERIFICATION_MODES.CLI
      );
      console.log(JSON.stringify({
        ok: true,
        ids: seed.projections.map(p => p.id),
      }));
    } catch (e) {
      console.log(JSON.stringify({
        ok: false,
        error: e.message,
      }));
    }
    """
    payload = {
        "seedName": seed_name,
        "seedBytesBase64": base64.b64encode(seed_bytes).decode("ascii"),
    }
    proc = subprocess.run(
        ["node", "-e", js_script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS registered seed image probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_decode_mu_binary_value_result(binary_bytes: bytes) -> dict[str, object]:
    js_script = """
    const fs = require('fs');
    const { decodeMuBinaryValue } = require('./mu/host/js/core/seed_loader');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const raw = Buffer.from(input.binaryBytesBase64, 'base64');
    try {
      console.log(JSON.stringify({
        ok: true,
        value: decodeMuBinaryValue(raw),
      }));
    } catch (e) {
      console.log(JSON.stringify({
        ok: false,
        error: e.message,
        name: e.name,
      }));
    }
    """
    payload = {
        "binaryBytesBase64": base64.b64encode(binary_bytes).decode("ascii"),
    }
    proc = subprocess.run(
        ["node", "-e", js_script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS MuBinary decoder probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_decode_seed_binary_projections_result(binary_bytes: bytes) -> dict[str, object]:
    js_script = """
    const fs = require('fs');
    const {
      decodeSeedBinaryProjections,
    } = require('./mu/host/js/core/seed_loader');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const raw = Buffer.from(input.binaryBytesBase64, 'base64');
    try {
      console.log(JSON.stringify({
        ok: true,
        projections: decodeSeedBinaryProjections(raw),
      }));
    } catch (e) {
      console.log(JSON.stringify({
        ok: false,
        error: e.message,
        name: e.name,
      }));
    }
    """
    payload = {
        "binaryBytesBase64": base64.b64encode(binary_bytes).decode("ascii"),
    }
    proc = subprocess.run(
        ["node", "-e", js_script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed binary decoder probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_seed_binary_migration_proof_result(
    seed_name: str,
    seed_bytes: bytes,
    binary_bytes: bytes,
    expected_proof: dict[str, object] | None = None,
) -> dict[str, object]:
    js_script = """
    const fs = require('fs');
    const {
      buildSeedBinaryMigrationProof,
      verifySeedBinaryMigrationArtifact,
      SEED_IMAGE_VERIFICATION_MODES,
    } = require('./mu/host/js/core/seed_loader');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const seedBytes = Buffer.from(input.seedBytesBase64, 'base64');
    const binaryBytes = Buffer.from(input.binaryBytesBase64, 'base64');
    try {
      const proof = input.expectedProof === null
        ? buildSeedBinaryMigrationProof(
            input.seedName,
            seedBytes,
            binaryBytes,
            SEED_IMAGE_VERIFICATION_MODES.CLI
          )
        : verifySeedBinaryMigrationArtifact(
            input.seedName,
            seedBytes,
            binaryBytes,
            input.expectedProof,
            SEED_IMAGE_VERIFICATION_MODES.CLI
          );
      console.log(JSON.stringify({ok: true, proof}));
    } catch (e) {
      console.log(JSON.stringify({
        ok: false,
        error: e.message,
        name: e.name,
      }));
    }
    """
    payload = {
        "seedName": seed_name,
        "seedBytesBase64": base64.b64encode(seed_bytes).decode("ascii"),
        "binaryBytesBase64": base64.b64encode(binary_bytes).decode("ascii"),
        "expectedProof": expected_proof,
    }
    proc = subprocess.run(
        ["node", "-e", js_script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed binary proof probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_load_verified_seed_binary_image_result(
    seed_name: str,
    seed_bytes: bytes,
    binary_bytes: bytes,
    expected_proof: dict[str, object],
) -> dict[str, object]:
    js_script = """
    const fs = require('fs');
    const {
      loadVerifiedSeedImage,
      SEED_IMAGE_VERIFICATION_MODES,
    } = require('./mu/host/js/core/seed_loader');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const seedBytes = Buffer.from(input.seedBytesBase64, 'base64');
    const binaryBytes = Buffer.from(input.binaryBytesBase64, 'base64');
    try {
      const seed = loadVerifiedSeedImage(
        input.seedName,
        seedBytes,
        SEED_IMAGE_VERIFICATION_MODES.CLI,
        binaryBytes,
        input.expectedProof
      );
      console.log(JSON.stringify({
        ok: true,
        ids: seed.projections.map(p => p.id),
      }));
    } catch (e) {
      console.log(JSON.stringify({
        ok: false,
        error: e.message,
        name: e.name,
      }));
    }
    """
    payload = {
        "seedName": seed_name,
        "seedBytesBase64": base64.b64encode(seed_bytes).decode("ascii"),
        "binaryBytesBase64": base64.b64encode(binary_bytes).decode("ascii"),
        "expectedProof": expected_proof,
    }
    proc = subprocess.run(
        ["node", "-e", js_script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed binary image probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _js_seed_dependencies() -> dict[str, list[str]]:
    js_script = """
    const { SEED_DEPENDENCIES } = require('./mu/host/js/core/seed_loader');
    const nonArrayValues = {};
    for (const [seedName, deps] of Object.entries(SEED_DEPENDENCIES)) {
      if (!Array.isArray(deps)) {
        nonArrayValues[seedName] = Object.prototype.toString.call(deps);
      }
    }
    console.log(JSON.stringify({
      dependencies: SEED_DEPENDENCIES,
      nonArrayValues,
    }));
    """
    proc = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS seed dependency probe failed: {proc.stderr}"
    payload = json.loads(proc.stdout)
    non_array_values = payload["nonArrayValues"]
    assert non_array_values == {}, (
        "JS SEED_DEPENDENCIES has non-array values: "
        f"{non_array_values}"
    )
    dependencies = payload["dependencies"]
    assert isinstance(dependencies, dict), (
        "JS SEED_DEPENDENCIES export must serialize to an object"
    )
    return dependencies


def _python_seed_dependencies() -> dict[str, list[str]]:
    non_list_values = {
        seed_name: type(deps).__name__
        for seed_name, deps in SEED_DEPENDENCIES.items()
        if not isinstance(deps, list)
    }
    assert non_list_values == {}, (
        "Python SEED_DEPENDENCIES has non-list values: "
        f"{non_list_values}"
    )
    return SEED_DEPENDENCIES


def seed_dependency_map_snapshots() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return Python and JS SEED_DEPENDENCIES maps after shape validation."""
    return _python_seed_dependencies(), _js_seed_dependencies()


def _dependency_list_mismatch(seed_name: str, py_list: list[str], js_list: list[str]) -> str:
    py_counter = Counter(py_list)
    js_counter = Counter(js_list)
    missing_targets = sorted((py_counter - js_counter).elements())
    extra_targets = sorted((js_counter - py_counter).elements())
    details = [
        f"{seed_name}:",
        f"  py={py_list}",
        f"  js={js_list}",
    ]
    if missing_targets:
        details.append(f"  missing_js_targets={missing_targets}")
    if extra_targets:
        details.append(f"  extra_js_targets={extra_targets}")
    if py_counter == js_counter and py_list != js_list:
        details.append("  order_drift=true")
    return "\n".join(details)


def assert_seed_dependency_maps_match_exactly() -> None:
    """Assert Python and JS exported SEED_DEPENDENCIES maps are identical."""
    py_dependencies, js_dependencies = seed_dependency_map_snapshots()

    missing_js_keys = sorted(set(py_dependencies) - set(js_dependencies))
    extra_js_keys = sorted(set(js_dependencies) - set(py_dependencies))
    mismatches = []

    for seed_name in sorted(set(py_dependencies) & set(js_dependencies)):
        py_list = py_dependencies[seed_name]
        js_list = js_dependencies[seed_name]
        if py_list != js_list:
            mismatches.append(_dependency_list_mismatch(seed_name, py_list, js_list))

    errors = []
    if missing_js_keys:
        errors.append(f"missing_js_keys={missing_js_keys}")
    if extra_js_keys:
        errors.append(f"extra_js_keys={extra_js_keys}")
    if mismatches:
        errors.append("dependency_list_mismatches:\n" + "\n".join(mismatches))

    assert not errors, (
        "Python/JS SEED_DEPENDENCIES exported maps differ:\n"
        + "\n".join(errors)
    )


def _subdir_relative_to_mu(seed_dir: Path) -> str:
    return os.path.relpath(seed_dir, _REPO / "mu")


# ── Checksum parity ──────────────────────────────────────────────────────


class TestSeedChecksumParity:
    """Python and JS must agree on seed checksums."""

    def test_js_registry_views_are_manifest_derived(self):
        """JS registry exports must be derived from manifest registration flags."""
        snapshot = _js_registry_snapshot()
        records = snapshot["SEED_REGISTRY_MANIFEST"]["seeds"]

        assert snapshot["SEED_CHECKSUMS"] == {
            seed_name: record["sha256"]
            for seed_name, record in records.items()
            if record["js_cli_registered"]
        }
        assert snapshot["EXPECTED_PROJECTION_IDS"] == {
            seed_name: record["projection_ids"]
            for seed_name, record in records.items()
            if record["js_cli_registered"]
        }
        assert snapshot["CORE_SEED_CHECKSUMS"] == {
            seed_name: record["sha256"]
            for seed_name, record in records.items()
            if record["js_core_locked"]
        }
        assert snapshot["CORE_SEED_PROJECTION_IDS"] == {
            seed_name: record["projection_ids"]
            for seed_name, record in records.items()
            if record["js_core_locked"]
        }

    def test_js_seed_image_production_api_uses_closed_manifest_views(self):
        """Production JS seed-image calls must choose closed manifest modes."""
        source = (_REPO / "mu" / "host" / "js" / "core" / "seed_loader.js").read_text()
        main_source = (_REPO / "mu" / "host" / "js" / "cli" / "main.js").read_text()

        assert "function loadVerifiedSeedImage(" in source
        assert "verificationMode," in source
        assert "binaryImage = null" in source
        assert "expectedBinaryProof = null" in source
        assert "loadCliVerifiedSeedImage" not in source
        assert "loadVerifiedSeedImageForNegativeControl" not in source
        assert "SEED_IMAGE_VERIFICATION_MODES.CORE" in source
        assert "SEED_IMAGE_VERIFICATION_MODES.CLI" in source
        assert "TEST_ONLY_NEGATIVE_CONTROL" not in source
        assert "negativeControlView" not in source
        assert "SEED_IMAGE_VERIFICATION_VIEWS" in source

        mutation_probe = """
        'use strict';
        const sl = require('./mu/host/js/core/seed_loader');
        let mutationError = null;
        try {
          sl.SEED_CHECKSUMS['synthetic_control.v1.json'] = '0'.repeat(64);
          sl.EXPECTED_PROJECTION_IDS['synthetic_control.v1.json'] = [];
        } catch (e) {
          mutationError = e.name;
        }
        console.log(JSON.stringify({
          frozenChecksums: Object.isFrozen(sl.SEED_CHECKSUMS),
          frozenProjectionIds: Object.isFrozen(sl.EXPECTED_PROJECTION_IDS),
          hasSyntheticChecksum: Object.prototype.hasOwnProperty.call(
            sl.SEED_CHECKSUMS,
            'synthetic_control.v1.json'
          ),
          hasSyntheticProjectionIds: Object.prototype.hasOwnProperty.call(
            sl.EXPECTED_PROJECTION_IDS,
            'synthetic_control.v1.json'
          ),
          mutationError,
        }));
        """
        proc = subprocess.run(
            ["node", "-e", mutation_probe],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert proc.returncode == 0, proc.stderr
        probe = json.loads(proc.stdout)
        assert probe["frozenChecksums"] is True
        assert probe["frozenProjectionIds"] is True
        assert probe["hasSyntheticChecksum"] is False
        assert probe["hasSyntheticProjectionIds"] is False

        assert (
            "loadVerifiedSeedImage(seedName, raw, SEED_IMAGE_VERIFICATION_MODES.CLI)"
            in main_source
        )
        main_wrapper = main_source[
            main_source.index("function loadVerifiedSeed(seedName)"):
            main_source.index("// mu/ root is 3 levels up from cli/")
        ]
        assert "SEED_CHECKSUMS," not in main_wrapper
        assert "EXPECTED_PROJECTION_IDS," not in main_wrapper

    def test_js_seeds_are_subset_of_python(self):
        """Every JS seed must exist in Python's SEED_CHECKSUMS."""
        js_checksums = _js_seed_checksums()
        js_only = set(js_checksums) - set(SEED_CHECKSUMS)
        assert not js_only, f"JS has seeds not in Python: {js_only}"

    def test_shared_checksums_match(self):
        """For every seed in both substrates, checksums must be identical."""
        js_checksums = _js_seed_checksums()
        mismatches = []
        for seed, js_hash in js_checksums.items():
            py_hash = SEED_CHECKSUMS.get(seed)
            if py_hash and py_hash != js_hash:
                mismatches.append(f"{seed}: py={py_hash[:12]}... js={js_hash[:12]}...")
        assert not mismatches, f"Checksum mismatches:\n" + "\n".join(mismatches)

    def test_js_loads_expected_seed_count(self):
        """JS must register exactly 16 seeds including lazy/runtime structural seeds."""
        js_checksums = _js_seed_checksums()
        assert len(js_checksums) == 16, (
            f"JS seed count changed from 16 to {len(js_checksums)}. "
            f"Seeds: {sorted(js_checksums.keys())}"
        )

    def test_python_is_superset(self):
        """Python tracks more seeds than JS (v1 versions, utilities, demos)."""
        js_checksums = _js_seed_checksums()
        assert len(SEED_CHECKSUMS) > len(js_checksums), (
            "Python should track MORE seeds than JS (includes v1 versions, utilities)"
        )


# ── Projection ID parity ────────────────────────────────────────────────


class TestProjectionIdParity:
    """Projection IDs must match exactly between substrates (order matters)."""

    def test_js_projection_seeds_subset_of_python(self):
        """Every seed with JS projection IDs must also have Python projection IDs."""
        js_ids = _js_projection_ids()
        js_only = set(js_ids) - set(EXPECTED_PROJECTION_IDS)
        assert not js_only, f"JS has projection IDs for seeds not in Python: {js_only}"

    def test_projection_ids_match_exactly(self):
        """For shared seeds, projection ID lists must match (order-sensitive)."""
        js_ids = _js_projection_ids()
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
        js_ids = _js_projection_ids()
        for seed, js_list in js_ids.items():
            py_list = EXPECTED_PROJECTION_IDS.get(seed, [])
            assert len(py_list) == len(js_list), (
                f"{seed}: Python has {len(py_list)} projections, JS has {len(js_list)}"
            )


# ── Seed dependency parity ──────────────────────────────────────────────


class TestSeedDependencyParity:
    """SEED_DEPENDENCIES maps must match exactly between Python and JS."""

    def test_seed_dependency_maps_match_exactly(self):
        assert_seed_dependency_maps_match_exactly()


class TestProjectionLoaderBinaryDecoderParity:
    """JS sidecar TLV decoder must mechanically match the D010 research codec."""

    def test_js_binary_decoder_exports_sidecar_without_production_default_flip(self):
        """Binary decoding remains a sidecar and the JSON production paths stay default."""
        source = (_REPO / "mu" / "host" / "js" / "core" / "seed_loader.js").read_text()

        assert "decodeMuBinaryValue" in source
        assert "decodeSeedBinaryProjections" in source
        assert "function loadVerifiedSeedImage(" in source
        assert "binaryImage = null" in source
        assert "expectedBinaryProof = null" in source

        json_boundary = source[
            source.index("function loadVerifiedSeedImage"):
            source.index("/**\n * Load and verify a seed file.")
        ]
        path_wrapper = source[
            source.index("function loadVerifiedSeed(seedName, subdir)"):
            source.index("function getSeedChecksum")
        ]

        assert "if (hasBinaryImage)" in json_boundary
        assert "decodeSeedBinaryProjections(" not in path_wrapper
        assert "loadVerifiedSeedImage(" in path_wrapper
        assert "SEED_IMAGE_VERIFICATION_MODES.CORE" in path_wrapper

    @pytest.mark.parametrize(
        ("binary_bytes", "expected"),
        [
            (bytes([0x00]), None),
            (bytes([0x01]), True),
            (bytes([0x02]), False),
            (bytes([0x03]) + (42).to_bytes(8, "big", signed=True), 42),
            (bytes([0x03]) + (-1).to_bytes(8, "big", signed=True), -1),
            (bytes([0x03]) + (2**53).to_bytes(8, "big", signed=True), 2**53),
            (bytes([0x03]) + (-(2**53)).to_bytes(8, "big", signed=True), -(2**53)),
            (bytes([0x05, 0x00, 0x00, 0x00, 0x05]) + b"hello", "hello"),
            (bytes([0x06, 0x00, 0x00, 0x00, 0x00]), []),
            (bytes([0x07, 0x00, 0x00, 0x00, 0x00]), {}),
        ],
    )
    def test_js_mu_binary_golden_values_match_python_research_decoder(
        self,
        binary_bytes,
        expected,
    ):
        """Hand-built TLV values decode identically in Python research and JS."""
        assert mu_decode_value(binary_bytes) == expected

        js_result = _js_decode_mu_binary_value_result(binary_bytes)

        assert js_result == {"ok": True, "value": expected}

    def test_js_seed_binary_projection_decoder_matches_python_research_codec(self):
        """A D010-style projection image decodes to the current JSON projection data."""
        seed_name = "rcx_engine.v1.json"
        seed = load_verified_seed_image(
            seed_name,
            get_seed_path(seed_name).read_bytes(),
            verify=True,
        )
        minimal_projections = [
            {
                "id": projection["id"],
                "pattern": projection["pattern"],
                "body": projection["body"],
            }
            for projection in seed["projections"]
        ]
        binary_image = mu_encode(minimal_projections)

        assert mu_decode_value(binary_image) == minimal_projections
        js_result = _js_decode_seed_binary_projections_result(binary_image)

        assert js_result == {"ok": True, "projections": minimal_projections}

    def test_js_seed_binary_projection_decoder_accepts_d010_large_int_fixture(self):
        """The JS sidecar accepts D010's exact ±2**53 INT64 research fixture."""
        large_int = 2**53
        projections = [
            {
                "id": "large.int.control",
                "pattern": {"n": large_int},
                "body": {"neg": -large_int},
            },
        ]
        binary_image = mu_encode(projections)

        assert mu_decode_value(binary_image) == projections
        js_result = _js_decode_seed_binary_projections_result(binary_image)

        assert js_result == {"ok": True, "projections": projections}

    def test_js_mu_binary_decoder_rejects_int64_values_that_would_round_in_js(self):
        """Non-exact INT64 materialization remains outside this sidecar proof."""
        non_exact = 2**53 + 1
        binary_value = bytes([0x03]) + non_exact.to_bytes(8, "big", signed=True)

        assert mu_decode_value(binary_value) == non_exact
        js_result = _js_decode_mu_binary_value_result(binary_value)

        assert js_result["ok"] is False
        assert js_result["name"] == "MuBinaryDecodeError"
        assert "cannot be represented exactly" in str(js_result["error"])

    def test_js_mu_binary_decoder_rejects_malformed_utf8_string_with_mu_taxonomy(
        self,
    ):
        """Malformed binary string payloads must not leak host TypeError."""
        malformed_string = bytes([0x05, 0x00, 0x00, 0x00, 0x01, 0xFF])

        js_result = _js_decode_mu_binary_value_result(malformed_string)

        assert js_result["ok"] is False
        assert js_result["name"] == "MuBinaryDecodeError"
        assert "Malformed UTF-8 string at offset 0" in str(js_result["error"])

    def test_js_seed_binary_projection_decoder_preserves_proto_string_keys(self):
        """Mu dict keys named __proto__ are data, not JavaScript prototype edits."""
        projections = [
            {
                "id": "proto.null.control",
                "pattern": {"__proto__": None, "safe": 1},
                "body": {},
            },
        ]
        binary_image = mu_encode(projections)

        assert mu_decode_value(binary_image) == projections
        js_result = _js_decode_seed_binary_projections_result(binary_image)

        assert js_result == {"ok": True, "projections": projections}

    def test_js_seed_binary_projection_decoder_rejects_non_projection_image(self):
        """Binary seed projection sidecar must fail closed on wrong top-level shape."""
        js_result = _js_decode_seed_binary_projections_result(bytes([0x00]))

        assert js_result["ok"] is False
        assert js_result["name"] == "MuBinaryDecodeError"
        assert "projections array" in str(js_result["error"])

    @pytest.mark.parametrize("float_value", [2.5, 2.0])
    def test_js_seed_binary_projection_decoder_rejects_float64_seed_numerics(
        self,
        float_value,
    ):
        """The sidecar rejects FLOAT64 seed numerics even when JS sees an integer."""
        binary_image = mu_encode(
            [
                {
                    "id": "float.policy.control",
                    "pattern": {"n": float_value},
                    "body": {"ok": True},
                },
            ]
        )

        assert mu_decode_value(binary_image)[0]["pattern"] == {"n": float_value}
        js_result = _js_decode_seed_binary_projections_result(binary_image)

        assert js_result["ok"] is False
        assert js_result["name"] == "MuBinaryDecodeError"
        assert "FLOAT64 numeric data" in str(js_result["error"])

    def test_js_mu_binary_decoder_rejects_trailing_data_and_non_string_dict_key(self):
        """Negative controls lock parser failure modes without exercising Mu semantics."""
        trailing = _js_decode_mu_binary_value_result(bytes([0x00, 0x00]))
        non_string_key = _js_decode_mu_binary_value_result(
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])
            + bytes([0x03]) + (42).to_bytes(8, "big", signed=True)
            + bytes([0x05, 0x00, 0x00, 0x00, 0x03]) + b"val"
        )

        assert trailing["ok"] is False
        assert trailing["name"] == "MuBinaryDecodeError"
        assert "Trailing data" in str(trailing["error"])
        assert non_string_key["ok"] is False
        assert non_string_key["name"] == "MuBinaryDecodeError"
        assert "Dict key must decode to string" in str(non_string_key["error"])


class TestProjectionLoaderSeedMigrationIntegrityChain:
    """Generated seed binary artifacts must bind back to JSON source truth."""

    @staticmethod
    def _minimal_projections(seed: dict[str, object]) -> list[dict[str, object]]:
        return [
            {
                "id": projection["id"],
                "pattern": projection["pattern"],
                "body": projection["body"],
            }
            for projection in seed["projections"]
        ]

    @staticmethod
    def encode_projection_with_duplicate_body(
        projection: dict[str, object],
        duplicate_count: int,
    ) -> bytes:
        pairs = [
            ("id", projection["id"]),
            ("pattern", projection["pattern"]),
            ("body", projection["body"]),
        ]
        pairs.extend(("body", projection["body"]) for _ in range(duplicate_count))
        parts = [bytes([0x07]) + len(pairs).to_bytes(4, "big")]
        for key, value in pairs:
            parts.append(mu_encode(key))
            parts.append(mu_encode(value))
        return b"".join(parts)

    @classmethod
    def _duplicate_key_sidecar(
        cls,
        projections: list[dict[str, object]],
    ) -> bytes:
        parts = [bytes([0x06]) + len(projections).to_bytes(4, "big")]
        for index, projection in enumerate(projections):
            if index == 0:
                parts.append(
                    cls.encode_projection_with_duplicate_body(
                        projection,
                        1,
                    )
                )
            else:
                parts.append(mu_encode(projection))
        return b"".join(parts)

    @staticmethod
    def _reordered_projection_key_sidecar(
        projections: list[dict[str, object]],
    ) -> bytes:
        return encode_seed_binary_projections(
            [
                {
                    "body": projection["body"],
                    "pattern": projection["pattern"],
                    "id": projection["id"],
                }
                for projection in projections
            ]
        )

    def test_generated_artifact_is_smaller_stable_and_cross_substrate_verified(self):
        """Python generation and JS sidecar verification produce the same proof chain."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
        minimal_projections = self._minimal_projections(seed)

        binary_one, proof_one = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )
        binary_two, proof_two = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )

        assert binary_one == binary_two
        assert proof_one == proof_two
        assert len(binary_one) < len(seed_bytes)
        assert proof_one["binary_is_smaller"] is True
        assert proof_one["migration_policy_id"] == SEED_BINARY_MIGRATION_POLICY_ID
        assert proof_one["checksum_policy_id"] == SEED_BINARY_CHECKSUM_POLICY_ID
        assert proof_one["json_sha256"] == compute_checksum(seed_bytes)
        assert proof_one["binary_sha256"] == compute_checksum(binary_one)
        assert proof_one["projection_ids"] == EXPECTED_PROJECTION_IDS[seed_name]
        assert proof_one["projection_count"] == len(minimal_projections)
        assert len(proof_one["proof_chain_sha256"]) == 64

        assert decode_seed_binary_projections(binary_one) == minimal_projections
        js_decode = _js_decode_seed_binary_projections_result(binary_one)
        assert js_decode == {"ok": True, "projections": minimal_projections}

        js_build = _js_seed_binary_migration_proof_result(
            seed_name,
            seed_bytes,
            binary_one,
        )
        js_verify = _js_seed_binary_migration_proof_result(
            seed_name,
            seed_bytes,
            binary_one,
            proof_one,
        )
        assert js_build == {"ok": True, "proof": proof_one}
        assert js_verify == {"ok": True, "proof": proof_one}

    def test_integrity_chain_rejects_duplicate_key_sidecar(self, tmp_path):
        """Validation must reject non-generated duplicate-key sidecars."""
        seed_name = "rcx_engine.v1.json"
        seed_path = get_seed_path(seed_name)
        seed_bytes = seed_path.read_bytes()
        seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
        minimal_projections = self._minimal_projections(seed)
        generated_binary, proof = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )
        duplicate_binary = self._duplicate_key_sidecar(minimal_projections)

        assert generated_binary != duplicate_binary
        assert len(duplicate_binary) < len(seed_bytes)
        with pytest.raises(SeedBinaryMigrationError, match="Duplicate dict key"):
            decode_seed_binary_projections(duplicate_binary)

        with pytest.raises(SeedBinaryMigrationError, match="Duplicate dict key"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                duplicate_binary,
                proof,
            )

        js_build = _js_seed_binary_migration_proof_result(
            seed_name,
            seed_bytes,
            duplicate_binary,
        )
        assert js_build["ok"] is False
        assert js_build["name"] == "MuBinaryDecodeError"
        assert "Duplicate dict key" in str(js_build["error"])

        binary_path = tmp_path / "duplicate-key.mub"
        proof_path = tmp_path / "proof.json"
        binary_path.write_bytes(duplicate_binary)
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
        validate = subprocess.run(
            [
                sys.executable,
                str(_REPO / "mu" / "tools" / "util" / "seed_binary_migration.py"),
                "validate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_path),
                "--binary",
                str(binary_path),
                "--proof",
                str(proof_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert validate.returncode == 1
        assert "Duplicate dict key" in validate.stderr

    def test_integrity_chain_rejects_noncanonical_projection_key_order(self):
        """Python and JS proof paths must reject non-generated projection ordering."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
        minimal_projections = self._minimal_projections(seed)
        _, proof = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )
        reordered_binary = self._reordered_projection_key_sidecar(minimal_projections)

        assert reordered_binary != encode_seed_binary_projections(minimal_projections)
        with pytest.raises(SeedBinaryMigrationError, match="non-canonical key order"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                reordered_binary,
                proof,
            )

        js_build = _js_seed_binary_migration_proof_result(
            seed_name,
            seed_bytes,
            reordered_binary,
        )
        assert js_build["ok"] is False
        assert js_build["name"] == "MuBinaryDecodeError"
        assert "non-canonical key order" in str(js_build["error"])

    def test_integrity_chain_rejects_checksum_trailing_id_and_source_mismatch(self):
        """Stored proof validation fails closed for each migration identity break."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
        minimal_projections = self._minimal_projections(seed)
        binary_image, proof = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )

        with pytest.raises(ValueError, match="integrity check failed"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes + b" ",
                binary_image,
                proof,
            )

        with pytest.raises(SeedBinaryMigrationError, match="Trailing data"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                binary_image + b"\x00",
                proof,
            )

        with pytest.raises(SeedBinaryMigrationError, match="Unknown tag"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                b"\xff",
                proof,
            )

        id_mismatch = json.loads(json.dumps(minimal_projections))
        id_mismatch[0]["id"] = "migration.id.mismatch"
        with pytest.raises(SeedBinaryMigrationError, match="projection ID mismatch"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                mu_encode(id_mismatch),
                proof,
            )

        source_mismatch = json.loads(json.dumps(minimal_projections))
        source_mismatch[0]["body"] = {"migration": "mismatch"}
        with pytest.raises(SeedBinaryMigrationError, match="source/binary mismatch"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                mu_encode(source_mismatch),
                proof,
            )

        wrong_proof = dict(proof)
        wrong_proof["binary_sha256"] = "0" * 64
        with pytest.raises(SeedBinaryMigrationError, match="binary_sha256"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                binary_image,
                wrong_proof,
            )

        for key, bad_value in {
            "binary_is_smaller": False,
            "binary_size": 999999,
            "json_size": 1,
            "projection_count": 999,
        }.items():
            tampered_proof = dict(proof)
            tampered_proof[key] = bad_value
            with pytest.raises(SeedBinaryMigrationError, match=key):
                verify_seed_binary_migration_artifact(
                    seed_name,
                    seed_bytes,
                    binary_image,
                    tampered_proof,
                )

            js_verify = _js_seed_binary_migration_proof_result(
                seed_name,
                seed_bytes,
                binary_image,
                tampered_proof,
            )
            assert js_verify["ok"] is False
            assert key in str(js_verify["error"])

        bool_as_number_proof = dict(proof)
        bool_as_number_proof["binary_is_smaller"] = 1
        with pytest.raises(SeedBinaryMigrationError, match="binary_is_smaller"):
            verify_seed_binary_migration_artifact(
                seed_name,
                seed_bytes,
                binary_image,
                bool_as_number_proof,
            )
        js_verify = _js_seed_binary_migration_proof_result(
            seed_name,
            seed_bytes,
            binary_image,
            bool_as_number_proof,
        )
        assert js_verify["ok"] is False
        assert "binary_is_smaller" in str(js_verify["error"])

    def test_non_exact_integer_policy_remains_fail_closed(self, monkeypatch):
        """Migration does not expand the current exact-number seed policy."""
        seed_name = "nonexact_int_control.v1.json"
        seed_bytes = (
            b'{"meta":{"version":"1.0","name":"NONEXACT","description":"x"},'
            b'"projections":[{"id":"nonexact","pattern":{"n":9007199254740993},'
            b'"body":{}}]}'
        )
        monkeypatch.setitem(SEED_CHECKSUMS, seed_name, compute_checksum(seed_bytes))
        monkeypatch.setitem(EXPECTED_PROJECTION_IDS, seed_name, ["nonexact"])
        monkeypatch.setitem(
            SEED_REGISTRY_MANIFEST["seeds"],
            seed_name,
            {
                "subdir": "utilities",
                "sha256": compute_checksum(seed_bytes),
                "projection_ids": ["nonexact"],
                "status": "production",
                "dependencies": [],
                "js_cli_registered": True,
                "js_core_locked": False,
            },
        )

        with pytest.raises(SeedBinaryMigrationError, match="outside exact JS integer"):
            generate_seed_binary_migration_artifact(seed_name, seed_bytes)

    def test_seed_binary_migration_rejects_seed_outside_js_registry(self, tmp_path):
        """The migration artifact boundary must be verifiable by the JS CLI view."""
        seed_name = "classify.v1.json"
        seed_path = get_seed_path(seed_name)
        binary_path = tmp_path / "classify.v1.mub"
        proof_path = tmp_path / "classify.v1.mub.proof.json"
        tool = _REPO / "mu" / "tools" / "util" / "seed_binary_migration.py"

        assert seed_name in SEED_CHECKSUMS
        assert seed_name not in _js_seed_checksums()

        with pytest.raises(SeedBinaryMigrationError, match="JS CLI verification registry"):
            generate_seed_binary_migration_artifact(seed_name, seed_path.read_bytes())

        generate = subprocess.run(
            [
                sys.executable,
                str(tool),
                "generate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_path),
                "--binary-out",
                str(binary_path),
                "--proof-out",
                str(proof_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert generate.returncode == 1
        assert "JS CLI verification registry" in generate.stderr
        assert not binary_path.exists()
        assert not proof_path.exists()

        binary_path.write_bytes(b"\x00")
        proof_path.write_text("{}", encoding="utf-8")
        validate = subprocess.run(
            [
                sys.executable,
                str(tool),
                "validate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_path),
                "--binary",
                str(binary_path),
                "--proof",
                str(proof_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert validate.returncode == 1
        assert "JS CLI verification registry" in validate.stderr

    def test_seed_binary_migration_tool_generate_validate_round_trip(self, tmp_path):
        """The bounded mu/tools CLI delegates generation and validation to policy code."""
        seed_name = "rcx_engine.v1.json"
        seed_path = get_seed_path(seed_name)
        binary_path = tmp_path / "rcx_engine.v1.mub"
        proof_path = tmp_path / "rcx_engine.v1.mub.proof.json"
        tool = _REPO / "mu" / "tools" / "util" / "seed_binary_migration.py"

        generate = subprocess.run(
            [
                sys.executable,
                str(tool),
                "generate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_path),
                "--binary-out",
                str(binary_path),
                "--proof-out",
                str(proof_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert generate.returncode == 0, generate.stderr
        generated_proof = json.loads(generate.stdout)
        assert binary_path.is_file()
        assert proof_path.is_file()
        assert json.loads(proof_path.read_text()) == generated_proof

        validate = subprocess.run(
            [
                sys.executable,
                str(tool),
                "validate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_path),
                "--binary",
                str(binary_path),
                "--proof",
                str(proof_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert validate.returncode == 0, validate.stderr
        assert json.loads(validate.stdout) == generated_proof

        tampered_proof = dict(generated_proof)
        tampered_proof["binary_size"] = 999999
        proof_path.write_text(json.dumps(tampered_proof), encoding="utf-8")
        validate_tampered = subprocess.run(
            [
                sys.executable,
                str(tool),
                "validate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_path),
                "--binary",
                str(binary_path),
                "--proof",
                str(proof_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert validate_tampered.returncode == 1
        assert "binary_size" in validate_tampered.stderr

        bool_as_number_proof = dict(generated_proof)
        bool_as_number_proof["binary_is_smaller"] = 1
        proof_path.write_text(json.dumps(bool_as_number_proof), encoding="utf-8")
        validate_bool_as_number = subprocess.run(
            [
                sys.executable,
                str(tool),
                "validate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_path),
                "--binary",
                str(binary_path),
                "--proof",
                str(proof_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert validate_bool_as_number.returncode == 1
        assert "binary_is_smaller" in validate_bool_as_number.stderr

    def test_seed_binary_migration_tool_generate_rejects_path_overlap_and_partial_outputs(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Generate must not overwrite inputs or leave sidecar halves on output failure."""
        seed_name = "rcx_engine.v1.json"
        seed_source = get_seed_path(seed_name)
        seed_copy = tmp_path / seed_name
        seed_copy.write_bytes(seed_source.read_bytes())
        seed_copy_sha = compute_checksum(seed_copy.read_bytes())
        tool = _REPO / "mu" / "tools" / "util" / "seed_binary_migration.py"

        input_overlap_proof = tmp_path / "input-overlap.proof.json"
        input_overlap = subprocess.run(
            [
                sys.executable,
                str(tool),
                "generate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_copy),
                "--binary-out",
                str(seed_copy),
                "--proof-out",
                str(input_overlap_proof),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert input_overlap.returncode == 1
        assert "must be distinct" in input_overlap.stderr
        assert compute_checksum(seed_copy.read_bytes()) == seed_copy_sha
        assert not input_overlap_proof.exists()

        same_output = tmp_path / "same-output"
        output_overlap = subprocess.run(
            [
                sys.executable,
                str(tool),
                "generate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_copy),
                "--binary-out",
                str(same_output),
                "--proof-out",
                str(same_output),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert output_overlap.returncode == 1
        assert "must be distinct" in output_overlap.stderr
        assert not same_output.exists()

        binary_path = tmp_path / "partial.mub"
        proof_dir = tmp_path / "proof-dir"
        proof_dir.mkdir()
        proof_write_failure = subprocess.run(
            [
                sys.executable,
                str(tool),
                "generate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_copy),
                "--binary-out",
                str(binary_path),
                "--proof-out",
                str(proof_dir),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=10,
        )
        assert proof_write_failure.returncode == 1
        assert "proof-out must be a file path" in proof_write_failure.stderr
        assert not binary_path.exists()

        rollback_binary = tmp_path / "rollback.mub"
        rollback_proof = tmp_path / "rollback.proof.json"
        old_binary = b"OLD_BINARY"
        old_proof = '{"old": true}\n'
        rollback_binary.write_bytes(old_binary)
        rollback_proof.write_text(old_proof, encoding="utf-8")
        replace_targets: list[Path] = []
        original_replace = Path.replace

        def fail_second_replace(self: Path, target: object) -> Path:
            target_path = Path(target)
            replace_targets.append(target_path)
            if len(replace_targets) == 2:
                raise RuntimeError("forced second replace failure")
            return original_replace(self, target)

        monkeypatch.setattr(Path, "replace", fail_second_replace)
        late_publish_failure = seed_binary_migration_tool.main(
            [
                "generate",
                "--seed-name",
                seed_name,
                "--json-seed",
                str(seed_copy),
                "--binary-out",
                str(rollback_binary),
                "--proof-out",
                str(rollback_proof),
            ]
        )
        assert late_publish_failure == 1
        assert replace_targets[:2] == [rollback_binary, rollback_proof]
        assert rollback_binary.read_bytes() == old_binary
        assert rollback_proof.read_text(encoding="utf-8") == old_proof
        assert not list(tmp_path.glob(".rollback.mub.*.tmp"))
        assert not list(tmp_path.glob(".rollback.proof.json.*.tmp"))


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

    def test_js_seed_subdirs_are_manifest_derived(self):
        """JS path-loader subdir view must be derived from the verified manifest."""
        snapshot = _js_registry_snapshot()
        records = snapshot["SEED_REGISTRY_MANIFEST"]["seeds"]

        assert snapshot["SEED_SUBDIRS"] == {
            seed_name: record["subdir"]
            for seed_name, record in records.items()
        }

    def test_js_path_loader_rejects_caller_subdir_drift(self):
        """JS path loader must not trust caller-supplied subdir authority."""
        result = _js_load_verified_seed_subdir_error(
            "rcx_engine.v1.json", "utilities"
        )

        assert result["ok"] is False
        assert "subdir mismatch" in str(result["error"])

    def test_js_cli_seed_reads_resolve_subdir_from_manifest(self):
        """JS CLI seed path loading must not duplicate per-seed subdir maps."""
        source = (_REPO / "mu" / "host" / "js" / "cli" / "main.js").read_text()

        assert "getSeedSubdir(seedName)" in source
        assert "substrateDir" not in source
        assert "closuresDir" not in source
        assert "bridgeDir" not in source
        assert "programsDir" not in source
        assert "loadVerifiedSeed(path.join" not in source


class TestProductionLoaderBoundaryParity:
    """Python and JS production loaders must agree on accept/reject boundaries."""

    def test_valid_rcx_engine_seed_loads_same_projection_ids(self):
        """Both substrates load the current rcx_engine JSON seed through production loaders."""
        py_result = _python_load_verified_seed_result(get_seed_path("rcx_engine.v1.json"))
        js_result = _js_load_verified_seed_result("rcx_engine.v1.json", "programs")

        expected_ids = EXPECTED_PROJECTION_IDS["rcx_engine.v1.json"]
        assert py_result == {"ok": True, "ids": expected_ids}
        assert js_result == {"ok": True, "ids": expected_ids}

    def test_canonical_seed_corpus_loads_integer_images_in_both_boundaries(self):
        """All JS-registered canonical corpus seed images load through production views."""
        canonical_subdirs = {"substrate", "closures", "bridge", "programs"}
        js_registered = set(_js_seed_checksums())
        seed_names = sorted(
            seed_name
            for seed_name, subdir in MU_SEED_LOCATIONS.items()
            if subdir in canonical_subdirs and seed_name in js_registered
        )
        assert seed_names

        for seed_name in seed_names:
            seed_path = get_seed_path(seed_name)
            seed_bytes = seed_path.read_bytes()
            expected_ids = EXPECTED_PROJECTION_IDS[seed_name]

            py_result = _python_load_verified_seed_image_result(
                seed_name, seed_bytes, verify=True
            )
            js_result = _js_load_registered_seed_image_bytes_result(seed_name, seed_bytes)

            assert py_result == {"ok": True, "ids": expected_ids}
            assert js_result == {"ok": True, "ids": expected_ids}

    def test_opt_in_smaller_seed_image_pilot_preserves_json_rollback(self):
        """The smaller image pilot stays explicit while Python fails closed."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        expected_ids = EXPECTED_PROJECTION_IDS[seed_name]
        binary_image, proof = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )

        py_binary = _python_load_verified_seed_binary_image_result(
            seed_name,
            seed_bytes,
            binary_image,
            proof,
        )
        js_binary = _js_load_verified_seed_binary_image_result(
            seed_name,
            seed_bytes,
            binary_image,
            proof,
        )
        py_json = _python_load_verified_seed_image_result(
            seed_name,
            seed_bytes,
            verify=True,
        )
        js_json = _js_load_registered_seed_image_bytes_result(seed_name, seed_bytes)

        assert py_binary["ok"] is False
        assert py_binary["name"] == "SeedBinaryMigrationError"
        assert "Mu-native sidecar adapter" in str(py_binary["error"])
        assert js_binary == {"ok": True, "ids": expected_ids}
        assert py_json == {"ok": True, "ids": expected_ids}
        assert js_json == {"ok": True, "ids": expected_ids}

    def test_opt_in_smaller_seed_image_tamper_rejects_with_json_rollback_intact(self):
        """Sidecar failure must not change the default JSON seed loading path."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = get_seed_path(seed_name).read_bytes()
        expected_ids = EXPECTED_PROJECTION_IDS[seed_name]
        binary_image, proof = generate_seed_binary_migration_artifact(
            seed_name,
            seed_bytes,
        )
        tampered_binary = binary_image + b"\x00"

        py_binary = _python_load_verified_seed_binary_image_result(
            seed_name,
            seed_bytes,
            tampered_binary,
            proof,
        )
        js_binary = _js_load_verified_seed_binary_image_result(
            seed_name,
            seed_bytes,
            tampered_binary,
            proof,
        )
        py_json = _python_load_verified_seed_image_result(
            seed_name,
            seed_bytes,
            verify=True,
        )
        js_json = _js_load_registered_seed_image_bytes_result(seed_name, seed_bytes)

        assert py_binary["ok"] is False
        assert py_binary["name"] == "SeedBinaryMigrationError"
        assert "Mu-native sidecar adapter" in str(py_binary["error"])
        assert js_binary["ok"] is False
        assert "Trailing data" in str(js_binary["error"])
        assert py_json == {"ok": True, "ids": expected_ids}
        assert js_json == {"ok": True, "ids": expected_ids}

    def test_tampered_known_seed_fails_closed_in_both_byte_boundaries(self):
        """The same tampered known seed image is rejected before parse on both substrates."""
        seed_name = "rcx_engine.v1.json"
        seed_bytes = (
            b'{"meta": {"version": "1.0", "name": "RCX_ENGINE", '
            b'"description": "tampered"}, "projections": [null]}'
        )

        py_result = _python_load_verified_seed_image_result(
            seed_name, seed_bytes, verify=True
        )
        js_result = _js_load_registered_seed_image_bytes_result(seed_name, seed_bytes)

        assert py_result["ok"] is False
        assert "integrity check failed" in str(py_result["error"])
        assert js_result["ok"] is False
        assert "checksum mismatch" in str(js_result["error"])

    def test_unknown_malformed_projection_seed_fails_closed_in_both_loaders(
        self, tmp_path
    ):
        """The same unknown malformed projection image is not accepted by either loader."""
        seed_name = "malformed_projection_control.v1.json"
        seed_path = tmp_path / seed_name
        seed_path.write_text(
            '{"meta": {"version": "1.0", "name": "MALFORMED", '
            '"description": "projection type control"}, "projections": [null]}'
        )

        py_result = _python_load_verified_seed_result(seed_path)
        js_result = _js_load_verified_seed_result(
            seed_name, _subdir_relative_to_mu(tmp_path)
        )

        assert py_result["ok"] is False
        assert "Unknown seed" in str(py_result["error"])
        assert js_result["ok"] is False
        assert "Unknown seed" in str(js_result["error"])

    def test_non_finite_seed_image_fails_closed_in_both_byte_boundaries(self):
        """Both seed image boundaries reject non-finite numeric JSON."""
        raw_json = (
            '{"meta": {"version": "1.0", "name": "NAN", "description": "x"}, '
            '"projections": [{"id": "x", "pattern": NaN, "body": {}}]}'
        )

        py_result = _python_load_verified_seed_image_result(
            "nonfinite_control.v1.json", raw_json.encode("utf-8"), verify=False
        )
        js_result = _js_load_verified_seed_image_result(
            "nonfinite_control.v1.json",
            raw_json,
        )

        assert py_result["ok"] is False
        assert "NaN" in str(py_result["error"])
        assert js_result["ok"] is False
        assert (
            "Unexpected token" in str(js_result["error"])
            or "not valid JSON" in str(js_result["error"])
        )

    def test_finite_non_integer_seed_image_fails_closed_in_both_byte_boundaries(self):
        """Both seed image boundaries reject finite non-integer JSON numerics."""
        raw_json = (
            '{"meta": {"version": "1.0", "name": "DECIMAL", "description": "x"}, '
            '"projections": [{"id": "x", "pattern": 2.5, "body": {}}]}'
        )

        py_result = _python_load_verified_seed_image_result(
            "decimal_control.v1.json", raw_json.encode("utf-8"), verify=False
        )
        js_result = _js_load_verified_seed_image_result(
            "decimal_control.v1.json",
            raw_json,
        )

        assert py_result["ok"] is False
        assert "2.5" in str(py_result["error"])
        assert js_result["ok"] is False
        assert "non-integer JSON numeric literal 2.5" in str(js_result["error"])

    def test_js_seed_image_boundary_rejects_projection_order_mismatch(self):
        """Production JS byte boundary rejects checksum-valid projection order drift."""
        seed_name = "rcx_engine.v1.json"
        seed = json.loads(get_seed_path(seed_name).read_text())
        expected_ids = EXPECTED_PROJECTION_IDS[seed_name]
        assert len(seed["projections"]) > 1

        first, second, *rest = seed["projections"]
        seed["projections"] = [second, first, *rest]
        actual_ids = [projection["id"] for projection in seed["projections"]]
        assert actual_ids != expected_ids
        assert Counter(actual_ids) == Counter(expected_ids)

        seed_bytes = json.dumps(seed, separators=(",", ":")).encode("utf-8")
        js_result = _js_load_verified_seed_image_bytes_result(
            seed_name,
            seed_bytes,
            forced_sha256=_js_seed_checksums()[seed_name],
        )

        assert js_result["ok"] is False
        assert "Seed projection IDs mismatch" in str(js_result["error"])
        assert actual_ids[0] in str(js_result["error"])
        assert expected_ids[0] in str(js_result["error"])

    def test_control_seed_image_missing_meta_fails_closed_in_both_boundaries(
        self, monkeypatch
    ):
        """Malformed seed image controls reject missing top-level metadata."""
        seed_name = "missing_meta_control.v1.json"
        seed_bytes = json.dumps(
            {
                "projections": [
                    {"id": "missing.meta", "pattern": {}, "body": {}},
                ],
            }
        ).encode("utf-8")
        monkeypatch.setitem(SEED_CHECKSUMS, seed_name, compute_checksum(seed_bytes))
        monkeypatch.setitem(EXPECTED_PROJECTION_IDS, seed_name, ["missing.meta"])

        py_result = _python_load_verified_seed_image_result(
            seed_name, seed_bytes, verify=True
        )
        js_result = _js_load_verified_seed_image_bytes_result(
            seed_name,
            seed_bytes,
        )

        assert py_result["ok"] is False
        assert "missing 'meta'" in str(py_result["error"])
        assert js_result["ok"] is False
        assert "missing 'meta'" in str(js_result["error"])

    def test_control_seed_image_missing_projection_body_fails_closed_in_both_boundaries(
        self, monkeypatch
    ):
        """Malformed projection controls must retain id/pattern/body structure."""
        seed_name = "missing_projection_body_control.v1.json"
        seed_bytes = json.dumps(
            {
                "meta": {
                    "version": "1.0",
                    "name": "MISSING_BODY",
                    "description": "projection body control",
                },
                "projections": [
                    {"id": "missing.body", "pattern": {}},
                ],
            }
        ).encode("utf-8")
        monkeypatch.setitem(SEED_CHECKSUMS, seed_name, compute_checksum(seed_bytes))
        monkeypatch.setitem(EXPECTED_PROJECTION_IDS, seed_name, ["missing.body"])

        py_result = _python_load_verified_seed_image_result(
            seed_name, seed_bytes, verify=True
        )
        js_result = _js_load_verified_seed_image_bytes_result(
            seed_name,
            seed_bytes,
        )

        assert py_result["ok"] is False
        assert "missing keys" in str(py_result["error"])
        assert js_result["ok"] is False
        assert "missing key 'body'" in str(js_result["error"])

    def test_control_invalid_utf8_seed_image_fails_closed_in_both_boundaries(
        self, monkeypatch
    ):
        """JS must not replace invalid UTF-8 that Python rejects during decoding."""
        seed_name = "invalid_utf8_control.v1.json"
        seed_bytes = (
            b'{"meta": {"version": "1.0", "name": "'
            + bytes([0xFF])
            + b'", "description": "x"}, "projections": []}'
        )
        monkeypatch.setitem(SEED_CHECKSUMS, seed_name, compute_checksum(seed_bytes))
        monkeypatch.setitem(EXPECTED_PROJECTION_IDS, seed_name, [])

        py_result = _python_load_verified_seed_image_result(
            seed_name, seed_bytes, verify=True
        )
        js_result = _js_load_verified_seed_image_bytes_result(
            seed_name,
            seed_bytes,
        )

        assert py_result["ok"] is False
        assert "utf-8" in str(py_result["error"]).lower()
        assert js_result["ok"] is False
        assert "utf-8" in str(js_result["error"]).lower()


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

def _extract_js_core_seed_checksums() -> dict[str, str]:
    return _js_registry_snapshot()["CORE_SEED_CHECKSUMS"]


def _extract_js_core_projection_ids() -> dict[str, list[str]]:
    return _js_registry_snapshot()["CORE_SEED_PROJECTION_IDS"]


class TestJsSeedLoaderSubsetGate:
    """N4: seed_loader.js CORE registries must be a strict subset of cli/main.js registries."""

    def test_core_checksums_subset_of_main(self):
        """Every CORE_SEED_CHECKSUMS entry must exist in SEED_CHECKSUMS with same hash."""
        core = _extract_js_core_seed_checksums()
        main = _js_seed_checksums()
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
        main = _js_projection_ids()
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
