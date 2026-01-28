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
    # Phase 7a: meta-circular kernel projections (v1.0.1 - entry format output)
    "kernel.v1.json": "8d9eb8a05da580f8652c7f0453fbf19e88eb7c36057a7e885bdeb3348bf0e9f6",
    # Phase 7b: match with kernel context passthrough + match.fail (fixed var names)
    "match.v2.json": "1fbd00c6988505a8369cec8f25968453cf3405855dfdf053756bd22375f7acc2",
    # Phase 7b: subst with kernel context passthrough
    "subst.v2.json": "372fd6552208f432f945214c65d3c4ae8c62113cef7541c070c039f373202f22",
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
    "kernel.v1.json": [
        "kernel.wrap",      # Entry point (must be first for entry matching)
        "kernel.stall",     # Empty remaining list -> stall
        "kernel.try",       # Start matching first projection
        "kernel.match_success",  # Match succeeded -> start substitution
        "kernel.match_fail",     # Match failed -> try next projection
        "kernel.subst_success",  # Substitution complete -> return result
        "kernel.unwrap",    # Extract final result (must be last)
    ],
    # Phase 7b: match with context passthrough + match.fail catch-all
    "match.v2.json": [
        "match.done",
        "match.sibling",
        "match.equal",
        "match.var",
        "match.typed.descend",
        "match.dict.descend",
        "match.fail",       # Catch-all failure (must be before wrap)
        "match.wrap",       # Must be last (entry point)
    ],
    # Phase 7b: subst with context passthrough
    "subst.v2.json": [
        "subst.done",
        "subst.ascend",
        "subst.sibling",
        "subst.var",
        "subst.lookup.found",
        "subst.lookup.next",
        "subst.typed.descend",
        "subst.typed.sibling",
        "subst.typed.ascend",
        "subst.descend",
        "subst.primitive",
        "subst.wrap",       # Must be last (entry point)
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

    # Check wrap projection is last (catch-all) for match/subst/classify seeds
    # Kernel seeds have different structure: wrap is entry point, unwrap is exit
    if seed_name != "kernel.v1.json":
        wrap_id = [eid for eid in expected if eid.endswith(".wrap")]  # AST_OK: infra
        if wrap_id:
            wrap_id = wrap_id[0]
            if actual_ids[-1] != wrap_id:
                raise ValueError(
                    f"Seed {seed_name}: '{wrap_id}' must be last projection "
                    f"(catch-all), but last is '{actual_ids[-1]}'"
                )
    else:
        # Kernel seeds: wrap is first (entry), unwrap is last (exit)
        if actual_ids[0] != "kernel.wrap":
            raise ValueError(
                f"Seed {seed_name}: 'kernel.wrap' must be first projection "
                f"(entry point), but first is '{actual_ids[0]}'"
            )
        if actual_ids[-1] != "kernel.unwrap":
            raise ValueError(
                f"Seed {seed_name}: 'kernel.unwrap' must be last projection "
                f"(exit point), but last is '{actual_ids[-1]}'"
            )


# =============================================================================
# Public API
# =============================================================================


# BOOTSTRAP_PRIMITIVE: projection_loader
# This is the irreducible seed bootstrap primitive.
# Cannot be structural because projections must come from somewhere (JSON files).
# JSON parsing and schema validation are Python's job, not expressible as projections.
# See docs/core/BootstrapPrimitives.v0.md for full justification.
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

    See: docs/core/BootstrapPrimitives.v0.md
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
