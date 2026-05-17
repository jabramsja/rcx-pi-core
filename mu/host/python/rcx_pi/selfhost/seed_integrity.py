"""
Seed Integrity Verification - Security foundation for self-hosting.

Validates all registered seed files across mu/ (substrate, closures,
bridge, programs, utilities) on load:
1. SHA256 checksum verification (detects tampering)
2. Structure validation (expected keys present)
3. Projection ID ordering verification (first-match-wins security)

See mu/docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# =============================================================================
# Canonical Seed Registry Manifest
# =============================================================================

SEED_REGISTRY_MANIFEST_NAME = "seed_registry_manifest.v1.json"
SEED_REGISTRY_MANIFEST_SCHEMA = "rcx.seed_registry_manifest.v1"
SEED_REGISTRY_MANIFEST_SHA256 = (
    "175ba95a371914f3d38bbe960ccd9300b44ea907d020164deb25947292bb7d29"
)

_MU_DIR = Path(__file__).resolve().parents[4]
_MANIFEST_PATH = _MU_DIR / SEED_REGISTRY_MANIFEST_NAME
_MANIFEST_BYTES = _MANIFEST_PATH.read_bytes()
_MANIFEST_ACTUAL_SHA256 = hashlib.sha256(_MANIFEST_BYTES).hexdigest()
if _MANIFEST_ACTUAL_SHA256 != SEED_REGISTRY_MANIFEST_SHA256:
    raise ValueError(
        f"Seed registry manifest integrity check failed for {_MANIFEST_PATH}:\n"
        f"  Expected: {SEED_REGISTRY_MANIFEST_SHA256}\n"
        f"  Got:      {_MANIFEST_ACTUAL_SHA256}"
    )

SEED_REGISTRY_MANIFEST = json.loads(
    _MANIFEST_BYTES.decode("utf-8"),
    parse_constant=int,
)
if not isinstance(SEED_REGISTRY_MANIFEST, dict):
    raise ValueError("Seed registry manifest must be a dict")
if SEED_REGISTRY_MANIFEST.get("schema") != SEED_REGISTRY_MANIFEST_SCHEMA:
    raise ValueError(
        "Seed registry manifest schema mismatch: "
        f"{SEED_REGISTRY_MANIFEST.get('schema')!r}"
    )
_MANIFEST_SEEDS = SEED_REGISTRY_MANIFEST.get("seeds")
if not isinstance(_MANIFEST_SEEDS, dict) or not _MANIFEST_SEEDS:
    raise ValueError("Seed registry manifest must contain non-empty seeds dict")

_VALID_MANIFEST_SUBDIRS = ("substrate", "closures", "bridge", "programs", "utilities")
_VALID_MANIFEST_STATUSES = ("production", "legacy-poc")
_REQUIRED_MANIFEST_RECORD_KEYS = (
    "subdir",
    "sha256",
    "projection_ids",
    "status",
    "dependencies",
    "js_cli_registered",
    "js_core_locked",
)
for _seed_name, _record in _MANIFEST_SEEDS.items():
    if not isinstance(_seed_name, str) or not _seed_name.endswith(".json"):
        raise ValueError(f"Seed registry manifest has invalid seed name: {_seed_name!r}")
    if not isinstance(_record, dict):
        raise ValueError(f"Seed registry manifest record for {_seed_name} must be a dict")
    _missing: list[str] = []
    for _required_key in _REQUIRED_MANIFEST_RECORD_KEYS:
        if _required_key not in _record:
            _missing.append(_required_key)
    if _missing:
        raise ValueError(
            f"Seed registry manifest record for {_seed_name} missing keys: {_missing}"
        )

    _subdir = _record["subdir"]
    if _subdir not in _VALID_MANIFEST_SUBDIRS:
        raise ValueError(
            f"Seed registry manifest record for {_seed_name} has invalid subdir: {_subdir!r}"
        )
    _checksum = _record["sha256"]
    if (
        not isinstance(_checksum, str)
        or len(_checksum) != 64
        or any(_char not in "0123456789abcdef" for _char in _checksum)
    ):
        raise ValueError(f"Seed registry manifest record for {_seed_name} has invalid sha256")
    _projection_ids = _record["projection_ids"]
    if not isinstance(_projection_ids, list) or not all(
        isinstance(_projection_id, str) for _projection_id in _projection_ids
    ):
        raise ValueError(
            f"Seed registry manifest record for {_seed_name} has invalid projection_ids"
        )
    _status = _record["status"]
    if _status not in _VALID_MANIFEST_STATUSES:
        raise ValueError(
            f"Seed registry manifest record for {_seed_name} has invalid status: {_status!r}"
        )
    _dependencies = _record["dependencies"]
    if not isinstance(_dependencies, list) or not all(
        isinstance(_dep, str) for _dep in _dependencies
    ):
        raise ValueError(
            f"Seed registry manifest record for {_seed_name} has invalid dependencies"
        )
    for _flag_name in ("js_cli_registered", "js_core_locked"):
        if not isinstance(_record[_flag_name], bool):
            raise ValueError(
                f"Seed registry manifest record for {_seed_name} has non-bool {_flag_name}"
            )

_REGISTERED_MANIFEST_SEEDS = set(_MANIFEST_SEEDS)
for _seed_name, _record in _MANIFEST_SEEDS.items():
    for _dep in _record["dependencies"]:
        if _dep not in _REGISTERED_MANIFEST_SEEDS:
            raise ValueError(
                f"Seed registry manifest record for {_seed_name} depends on unknown seed {_dep}"
            )

_SEED_REGISTRY_RECORDS: dict[str, dict[str, Any]] = SEED_REGISTRY_MANIFEST["seeds"]

# Compatibility views: static seed truth is manifest data, not host literals.
SEED_CHECKSUMS: dict[str, str] = {}
EXPECTED_PROJECTION_IDS: dict[str, list[str]] = {}
MU_SEED_LOCATIONS: dict[str, str] = {}
SEED_STATUS: dict[str, str] = {}
SEED_DEPENDENCIES: dict[str, list[str]] = {}
for _seed_name, _record in _SEED_REGISTRY_RECORDS.items():
    SEED_CHECKSUMS[_seed_name] = _record["sha256"]
    EXPECTED_PROJECTION_IDS[_seed_name] = list(_record["projection_ids"])
    MU_SEED_LOCATIONS[_seed_name] = _record["subdir"]
    SEED_STATUS[_seed_name] = _record["status"]
    if _record["dependencies"]:
        SEED_DEPENDENCIES[_seed_name] = list(_record["dependencies"])


def validate_seed_dependencies(loaded_seeds: set[str]) -> list[str]:
    """
    Validate that all execution-time dependencies are satisfied.

    Args:
        loaded_seeds: Set of seed names that are loaded/available.

    Returns:
        List of error messages (empty if all dependencies satisfied).
    """
    errors = []
    for seed_name in loaded_seeds:
        deps = SEED_DEPENDENCIES.get(seed_name, [])
        for dep in deps:
            if dep not in loaded_seeds:
                errors.append(
                    f"Seed {seed_name} requires {dep} but it is not loaded"
                )
    return errors


# =============================================================================
# Checksum Verification
# =============================================================================


def compute_checksum(content: bytes) -> str:
    """Compute SHA256 checksum of content."""
    return hashlib.sha256(content).hexdigest()


def verify_checksum(seed_name: str, content: bytes) -> None:
    """
    Verify seed content matches expected checksum.

    Args:
        seed_name: Name of seed file (e.g., "match.v1.json")
        content: Raw file content as bytes.

    Raises:
        ValueError: If checksum doesn't match.
    """
    if seed_name not in SEED_CHECKSUMS:
        raise ValueError(f"Unknown seed: {seed_name}")

    actual = compute_checksum(content)
    expected = SEED_CHECKSUMS[seed_name]

    if actual != expected:
        raise ValueError(
            f"Seed integrity check failed for {seed_name}:\n"
            f"  Expected: {expected}\n"
            f"  Got:      {actual}\n"
            f"  This may indicate file corruption or unauthorized modification."
        )


# =============================================================================
# Structure Validation
# =============================================================================


def validate_seed_structure(seed_name: str, seed: dict[str, Any]) -> None:
    """
    Validate seed has expected structure.

    Args:
        seed_name: Name of seed file.
        seed: Parsed seed dict.

    Raises:
        ValueError: If structure is invalid.
    """
    # Top-level must be a dict
    if not isinstance(seed, dict):
        raise ValueError(f"Seed {seed_name} must be a dict, got {type(seed).__name__}")

    # Must have meta and projections
    if "meta" not in seed:
        raise ValueError(f"Seed {seed_name} missing 'meta' key")
    if "projections" not in seed:
        raise ValueError(f"Seed {seed_name} missing 'projections' key")

    meta = seed["meta"]
    projections = seed["projections"]

    # Meta must be a dict (not list, string, etc.)
    if not isinstance(meta, dict):
        raise ValueError(f"Seed {seed_name} 'meta' must be a dict, got {type(meta).__name__}")

    # Projections must be a list
    if not isinstance(projections, list):
        raise ValueError(f"Seed {seed_name} 'projections' must be a list, got {type(projections).__name__}")

    # Meta must have required fields
    required_meta = {"version", "name", "description"}  # AST_OK: infra
    missing = required_meta - set(meta.keys())
    if missing:
        raise ValueError(f"Seed {seed_name} meta missing keys: {missing}")

    # Each projection must have id, pattern, body
    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):
            raise ValueError(f"Seed {seed_name} projection {i} must be a dict")

        required_proj = {"id", "pattern", "body"}  # AST_OK: infra
        missing = required_proj - set(proj.keys())
        if missing:
            raise ValueError(
                f"Seed {seed_name} projection {i} missing keys: {missing}"
            )


def validate_projection_ids(seed_name: str, seed: dict[str, Any]) -> None:
    """
    Validate expected projection IDs are present.

    Args:
        seed_name: Name of seed file.
        seed: Parsed seed dict.

    Raises:
        ValueError: If expected projections are missing or wrap isn't last.
    """
    if seed_name not in EXPECTED_PROJECTION_IDS:
        raise ValueError(
            f"Seed {seed_name} has no entry in EXPECTED_PROJECTION_IDS — "
            f"projection ordering is NOT validated. Register it for fail-closed security."
        )

    expected = EXPECTED_PROJECTION_IDS[seed_name]
    projections = seed.get("projections", [])
    actual_ids = [p.get("id") for p in projections]  # AST_OK: infra

    # Enforce exact ordered equality — projection order is security-critical
    # (first-match-wins means reordering changes routing semantics)
    if actual_ids != expected:
        missing = set(expected) - set(actual_ids)
        extra = set(actual_ids) - set(expected)
        if missing or extra:
            raise ValueError(
                f"Seed {seed_name} projection ID mismatch: "
                f"missing={missing or 'none'}, extra={extra or 'none'}"
            )
        # Same IDs but wrong order
        raise ValueError(
            f"Seed {seed_name} projection order mismatch "
            f"(order is security-critical): "
            f"expected {expected}, got {actual_ids}"
        )


# =============================================================================
# Public API
# =============================================================================


def load_verified_seed_image(
    seed_name: str,
    seed_bytes: bytes,
    verify: bool = True,
) -> dict[str, Any]:
    """
    Deterministically verify, parse, and validate a JSON seed image.

    Args:
        seed_name: Registered seed filename.
        seed_bytes: Raw seed JSON bytes.
        verify: If True, verify checksum and structure. Default True.

    Returns:
        Parsed seed dict.

    Raises:
        ValueError: If integrity check fails.
    """
    # Verify checksum
    if verify:
        verify_checksum(seed_name, seed_bytes)

    # Reject JSON's non-standard NaN/Infinity tokens and decimal/exponent number
    # literals without adding a semantic numeric layer to the loader.
    seed = json.loads(
        seed_bytes.decode("utf-8"),
        parse_float=int,
        parse_constant=int,
    )

    # Validate structure and projection IDs
    if verify:
        validate_seed_structure(seed_name, seed)
        validate_projection_ids(seed_name, seed)

    return seed


# BOOTSTRAP_PRIMITIVE: projection_loader
# This is the irreducible seed bootstrap primitive.
# Cannot be structural because projections must come from somewhere (JSON files).
# JSON parsing and schema validation are Python's job, not expressible as projections.
# See mu/docs/core/BootstrapPrimitives.v0.md for full justification.
def load_verified_seed(seed_path: Path, verify: bool = True) -> dict[str, Any]:
    """
    BOOTSTRAP PRIMITIVE: Load a seed file with integrity verification.

    This is the irreducible projection_loader primitive - analogous to
    ROM bootstrap or BIOS loading. Projections must come from somewhere,
    and JSON parsing cannot be expressed as a projection.

    Args:
        seed_path: Path to seed JSON file.
        verify: If True, verify checksum and structure. Default True.

    Returns:
        Parsed seed dict.

    Raises:
        FileNotFoundError: If seed file doesn't exist.
        ValueError: If integrity check fails.

    See: mu/docs/core/BootstrapPrimitives.v0.md
    """
    content = seed_path.read_bytes()
    return load_verified_seed_image(seed_path.name, content, verify=verify)


def get_mu_dir() -> Path:
    """Get the mu directory path (new organized structure)."""
    return _MU_DIR


def get_seed_path(seed_name: str) -> Path:
    """
    Get the path to a seed file from the canonical mu/ location.

    Seed locations (mu/ folder structure - CANONICAL):
    - mu/substrate/  : kernel.v1, match.v1, match.v2, subst.v1, subst.v2
    - mu/closures/   : recurrence.v1, exhaustion.v1
    - mu/bridge/     : bootstrap_structural.v1
    - mu/utilities/  : classify.v1, eval.v1
    - mu/programs/   : rcx_engine.v1

    Legacy seeds/ folder is DEPRECATED - do not use.

    Args:
        seed_name: Name of seed file (e.g., "match.v2.json", "recurrence.v1.json")

    Returns:
        Path to the seed file in mu/

    Raises:
        ValueError: If seed_name is not in the known location map.
    """
    mu_dir = get_mu_dir()

    if seed_name not in MU_SEED_LOCATIONS:
        raise ValueError(
            f"Unknown seed: {seed_name}. "
            f"Known seeds: {sorted(MU_SEED_LOCATIONS.keys())}"
        )

    return mu_dir / MU_SEED_LOCATIONS[seed_name] / seed_name


def verify_all_seeds() -> dict[str, bool]:
    """
    Verify all known seeds from mu/ (canonical location).

    Returns:
        Dict mapping seed name to verification success.
    """
    results = {}

    for seed_name in SEED_CHECKSUMS:
        try:
            seed_path = get_seed_path(seed_name)
            load_verified_seed(seed_path, verify=True)
            results[seed_name] = True
        except (FileNotFoundError, ValueError):
            results[seed_name] = False

    return results
