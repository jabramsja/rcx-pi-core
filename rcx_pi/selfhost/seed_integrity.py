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
    # Step 5: EngineNews structural closure detection (Rule 2.2♢)
    # Updated Step 6 v0: Added tau_step output for Operator Exhaustion
    # Updated: Added execution_layer metadata (BOOTSTRAP - requires non-linear patterns)
    "enginenews.v1.json": "1ef120680a76bdeca0a949de8cc65ded011d0022a2bd2472474cc10e416c2762",
    # Step 6: Operator Exhaustion detection (Rule 3.1)
    # Updated: Added execution_layer metadata (BOOTSTRAP - requires non-linear patterns)
    "exhaust.v1.json": "28d211894bc74efda595977f8603041b867d6ebf116b61b73f87b0be523a56f4",
    # mu/ folder reorganization: renamed seeds with updated projection IDs
    # recurrence.v1.json = enginenews.v1.json with recurrence.* projection IDs
    "recurrence.v1.json": "1f1febacf5f54cb7a8dc48cd7a5830ec21093ef19a73cef0809e60853279d467",
    # exhaustion.v1.json = exhaust.v1.json with exhaustion.* projection IDs
    "exhaustion.v1.json": "8857132af750da7efbc5532bdb95ec4223d2acefdd5d911cfd00efd6ca393fa7",
    # RCX Engine: main program orchestrating recurrence + exhaustion
    "rcx_engine.v1.json": "d5a1478739f9d6371b072f2cb937e311bd7ba1879729556f10a1d2e641e0b94f",
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
    # Step 5: EngineNews structural closure detection (Rule 2.2♢)
    # init is entry point, unwrap is exit point (no .wrap catch-all)
    "enginenews.v1.json": [
        "enginenews.init",               # Entry: _detect_closure -> internal state
        "enginenews.end_of_trace",       # End of trace (null) -> no closure
        "enginenews.check_state_stall",  # Extract state from stall entry
        "enginenews.check_state_maxsteps",  # Extract state from max_steps entry
        "enginenews.check_state",        # Extract state from trace entry
        "enginenews.found_in_seen",      # State in seen-set -> closure!
        "enginenews.not_in_head",        # State not in head -> check tail
        "enginenews.not_found",          # State not in seen -> add and advance
        "enginenews.unwrap",             # Exit: extract final result
    ],
    # Step 6: Operator Exhaustion detection (Rule 3.1)
    # init_null is entry for no-tau case, do_freeze is terminal for exhaustion
    "exhaust.v1.json": [
        "exhaust.init_null",        # Entry: no tau_step -> continue
        "exhaust.init",             # Entry: tau_step set -> find tau entry
        "exhaust.find_match",       # Found step == tau_step (non-linear)
        "exhaust.find_continue",    # Not at tau_step yet, advance
        "exhaust.find_not_found",   # End of trace without finding tau
        "exhaust.scan_same",        # Same operator (non-linear), continue
        "exhaust.scan_different",   # Different operator -> not exhausted
        "exhaust.scan_end",         # End of trace, all same -> check frozen
        "exhaust.frozen_found",     # Operator in frozen list (non-linear)
        "exhaust.frozen_check_tail",  # Check next in frozen list
        "exhaust.do_freeze",        # Not frozen -> freeze it
    ],
    # mu/ folder reorganization: renamed seeds with updated projection IDs
    # recurrence.v1.json = enginenews.v1.json with recurrence.* projection IDs
    "recurrence.v1.json": [
        "recurrence.init",               # Entry: _detect_closure -> internal state
        "recurrence.end_of_trace",       # End of trace (null) -> no closure
        "recurrence.check_state_stall",  # Extract state from stall entry
        "recurrence.check_state_maxsteps",  # Extract state from max_steps entry
        "recurrence.check_state",        # Extract state from trace entry
        "recurrence.found_in_seen",      # State in seen-set -> closure!
        "recurrence.not_in_head",        # State not in head -> check tail
        "recurrence.not_found",          # State not in seen -> add and advance
        "recurrence.unwrap",             # Exit: extract final result
    ],
    # exhaustion.v1.json = exhaust.v1.json with exhaustion.* projection IDs
    "exhaustion.v1.json": [
        "exhaustion.init_null",        # Entry: no tau_step -> continue
        "exhaustion.init",             # Entry: tau_step set -> find tau entry
        "exhaustion.find_match",       # Found step == tau_step (non-linear)
        "exhaustion.find_continue",    # Not at tau_step yet, advance
        "exhaustion.find_not_found",   # End of trace without finding tau
        "exhaustion.scan_same",        # Same operator (non-linear), continue
        "exhaustion.scan_different",   # Different operator -> not exhausted
        "exhaustion.scan_end",         # End of trace, all same -> check frozen
        "exhaustion.frozen_found",     # Operator in frozen list (non-linear)
        "exhaustion.frozen_check_tail",  # Check next in frozen list
        "exhaustion.do_freeze",        # Not frozen -> freeze it
    ],
    # RCX Engine: main program orchestrating recurrence + exhaustion
    "rcx_engine.v1.json": [
        "engine.init",            # Entry: default config
        "engine.init_config",     # Entry: custom config
        "engine.trace_done",      # Trace complete -> recurrence
        "engine.recurrence_done", # Recurrence done -> exhaustion
        "engine.exhaustion_done", # Exhaustion done -> final result
        "engine.unwrap",          # Extract final result
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
    """Get the seeds directory path (legacy location)."""
    return Path(__file__).parent.parent.parent / "seeds"


def get_mu_dir() -> Path:
    """Get the mu directory path (new organized structure)."""
    return Path(__file__).parent.parent.parent / "mu"


def get_seed_path(seed_name: str) -> Path:
    """
    Get the path to a seed file, checking both legacy and new locations.

    Seed locations (new mu/ folder structure):
    - mu/substrate/  : kernel.v1, match.v1, match.v2, subst.v1, subst.v2
    - mu/closures/   : recurrence.v1, exhaustion.v1
    - mu/utilities/  : classify.v1, eval.v1
    - mu/programs/   : (future) rcx_engine.v1

    Legacy location (seeds/):
    - All seeds including enginenews.v1, exhaust.v1

    Args:
        seed_name: Name of seed file (e.g., "match.v2.json", "recurrence.v1.json")

    Returns:
        Path to the seed file (prefers mu/ if available, falls back to seeds/)
    """
    mu_dir = get_mu_dir()

    # Map seed names to mu/ subfolders
    MU_SEED_LOCATIONS = {
        # Substrate seeds (the VM)
        "kernel.v1.json": "substrate",
        "match.v1.json": "substrate",
        "match.v2.json": "substrate",
        "subst.v1.json": "substrate",
        "subst.v2.json": "substrate",
        # Closure detection seeds
        "recurrence.v1.json": "closures",
        "exhaustion.v1.json": "closures",
        # Utilities
        "classify.v1.json": "utilities",
        "eval.v1.json": "utilities",
        # Programs
        "rcx_engine.v1.json": "programs",
    }

    if seed_name in MU_SEED_LOCATIONS:
        mu_path = mu_dir / MU_SEED_LOCATIONS[seed_name] / seed_name
        if mu_path.exists():
            return mu_path

    # Fall back to legacy seeds/ folder
    legacy_path = get_seeds_dir() / seed_name
    if legacy_path.exists():
        return legacy_path

    # Return mu path even if it doesn't exist (for error messages)
    if seed_name in MU_SEED_LOCATIONS:
        return mu_dir / MU_SEED_LOCATIONS[seed_name] / seed_name
    return legacy_path


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
