"""
Seed Integrity Verification - Security foundation for self-hosting.

This module validates seed files (match.v1.json, subst.v1.json) on load:
1. SHA256 checksum verification (detects tampering)
2. Structure validation (expected keys present)
3. Projection ID verification (expected projections present)

See docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# =============================================================================
# Known Good Checksums
# =============================================================================

# SHA256 checksums of canonical seed files.
# Update these when seeds are intentionally modified.
SEED_CHECKSUMS: dict[str, str] = {
    # Updated v1.1.0: added match.typed.descend for type-tagged head/tail structures
    "match.v1.json": "e60a3f3184038147f6a065d025d8458e7a161acc8d9dde1ce6719771500bca8c",
    # Updated v1.2.0: added subst.typed.* projections for type-tagged structures (Phase 6c)
    "subst.v1.json": "ff2acb1450b30a078a7cd2bdd42443b07e28075569a8b095f65165e23eb69893",
    # Phase 6b: classification as Mu projections (v1.0.0 + nested_not_kv fix)
    "classify.v1.json": "3216e28b2f28b8f9d2dfd2693dfecad2c2ba94783151bb4b8f920d29aa8e5cf1",
}

# Expected projection IDs for each seed.
# These must be present for the seed to be valid.
EXPECTED_PROJECTION_IDS: dict[str, list[str]] = {
    "match.v1.json": [
        "match.done",
        "match.sibling",
        "match.equal",
        "match.var",
        "match.typed.descend",  # Type-tagged head/tail (Phase 6c)
        "match.dict.descend",
        "match.wrap",  # Must be last (catch-all)
    ],
    "subst.v1.json": [
        "subst.done",
        "subst.ascend",
        "subst.sibling",
        "subst.var",
        "subst.lookup.found",   # Phase 6a: structural lookup
        "subst.lookup.next",    # Phase 6a: structural lookup
        "subst.typed.descend",  # Phase 6c: type-tagged structures
        "subst.typed.sibling",  # Phase 6c: type-tagged structures
        "subst.typed.ascend",   # Phase 6c: type-tagged structures
        "subst.descend",
        "subst.primitive",
        "subst.wrap",  # Must be last (catch-all)
    ],
    "classify.v1.json": [
        "classify.done",
        "classify.nested_not_kv",  # Reject head/tail in key position
        "classify.kv_continue",
        "classify.not_kv",
        "classify.empty",
        "classify.wrap",  # Must be last (catch-all)
    ],
}


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
    # Must have meta and projections
    if "meta" not in seed:
        raise ValueError(f"Seed {seed_name} missing 'meta' key")
    if "projections" not in seed:
        raise ValueError(f"Seed {seed_name} missing 'projections' key")

    meta = seed["meta"]
    projections = seed["projections"]

    # Meta must have required fields
    required_meta = {"version", "name", "description"}  # AST_OK: infra
    missing = required_meta - set(meta.keys())
    if missing:
        raise ValueError(f"Seed {seed_name} meta missing keys: {missing}")

    # Projections must be a list
    if not isinstance(projections, list):
        raise ValueError(f"Seed {seed_name} 'projections' must be a list")

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
        # Unknown seed - skip projection ID check
        return

    expected = EXPECTED_PROJECTION_IDS[seed_name]
    projections = seed.get("projections", [])
    actual_ids = [p.get("id") for p in projections]  # AST_OK: infra

    # Check all expected IDs are present
    missing = set(expected) - set(actual_ids)
    if missing:
        raise ValueError(
            f"Seed {seed_name} missing expected projection IDs: {missing}"
        )

    # Check wrap projection is last (it's the catch-all entry point)
    wrap_id = [eid for eid in expected if eid.endswith(".wrap")]  # AST_OK: infra
    if wrap_id:
        wrap_id = wrap_id[0]
        if actual_ids[-1] != wrap_id:
            raise ValueError(
                f"Seed {seed_name}: '{wrap_id}' must be last projection "
                f"(catch-all), but last is '{actual_ids[-1]}'"
            )


# =============================================================================
# Public API
# =============================================================================


def load_verified_seed(seed_path: Path, verify: bool = True) -> dict[str, Any]:
    """
    Load a seed file with integrity verification.

    Args:
        seed_path: Path to seed JSON file.
        verify: If True, verify checksum and structure. Default True.

    Returns:
        Parsed seed dict.

    Raises:
        FileNotFoundError: If seed file doesn't exist.
        ValueError: If integrity check fails.
    """
    seed_name = seed_path.name

    # Read raw content for checksum
    content = seed_path.read_bytes()

    # Verify checksum
    if verify:
        verify_checksum(seed_name, content)

    # Parse JSON
    seed = json.loads(content.decode("utf-8"))

    # Validate structure and projection IDs
    if verify:
        validate_seed_structure(seed_name, seed)
        validate_projection_ids(seed_name, seed)

    return seed


def get_seeds_dir() -> Path:
    """Get the seeds directory path."""
    return Path(__file__).parent.parent.parent / "seeds"


def verify_all_seeds() -> dict[str, bool]:
    """
    Verify all known seeds.

    Returns:
        Dict mapping seed name to verification success.
    """
    results = {}
    seeds_dir = get_seeds_dir()

    for seed_name in SEED_CHECKSUMS:
        seed_path = seeds_dir / seed_name
        try:
            load_verified_seed(seed_path, verify=True)
            results[seed_name] = True
        except (FileNotFoundError, ValueError):
            results[seed_name] = False

    return results
