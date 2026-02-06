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
    # Updated: Added execution_layer: META_CIRCULAR, fixed match.equal description
    # Updated: Fixed meta.doc path (docs/SelfHosting.v0.md -> docs/core/SelfHosting.v0.md)
    "match.v1.json": "9614ec7e802005dc3322dc7af474abf4f137a506efc57f52781157210e76e190",
    # Updated v1.2.0: added subst.typed.* projections for type-tagged structures (Phase 6c)
    # Updated: Added execution_layer: META_CIRCULAR
    # Updated: Fixed meta.doc path (docs/SelfHosting.v0.md -> docs/core/SelfHosting.v0.md)
    "subst.v1.json": "d8626f8ffddda711124205a761dd64d6781ebec53567e74a11f2ce8cf0ce75df",
    # Phase 6b: classification as Mu projections (v1.0.0 + nested_not_kv fix)
    # Updated: Added execution_layer: META_CIRCULAR
    # Updated: Fixed meta.doc path (docs/SelfHosting.v0.md -> docs/core/SelfHosting.v0.md)
    "classify.v1.json": "2008556c09105d0dc46f19e38382870a60ced7d88549dbd989f5d613d5db1968",
    # Phase 7a: meta-circular kernel projections (v1.0.1 - entry format output)
    # Updated: Added execution_layer: META_CIRCULAR
    "kernel.v1.json": "813cae10f2a7f19bd494e56e5c8cf2feaf92f32ae6988d626bca21ee01811daa",
    # Phase 7b: match with kernel context passthrough + match.fail (fixed var names)
    # Updated: Added execution_layer: META_CIRCULAR, fixed match.equal description
    "match.v2.json": "55a6b58a6c8fe31d4c3a8c704603d453fc04c1a757a45fcf7f6570afa1fe27b1",
    # Phase 7b: subst with kernel context passthrough
    # Updated: Added execution_layer: META_CIRCULAR
    "subst.v2.json": "e64695b966c497b22d710779ad7c1c9a2a5158734392714c10dffb77f6c39621",
    # mu/ folder reorganization: renamed from enginenews.v1/exhaust.v1 to recurrence.v1/exhaustion.v1
    # Legacy names (enginenews.v1, exhaust.v1) removed - mu/ is now canonical
    # Updated v1.2.0: HYBRID execution_layer (honest: production uses BOOTSTRAP, meta-circular proven)
    # Gate 3 (2026-02-06): Rewritten with normalized linked-list patterns for structural execution
    "recurrence.v1.json": "2b9974d8f53a7d5a87900658ea76727e52c01f1d5d6a8aba68b8747df9fe1dad",
    # exhaustion.v1.json = exhaust.v1.json with exhaustion.* projection IDs
    # Updated v1.2.0: HYBRID execution_layer (honest: production uses BOOTSTRAP, meta-circular proven)
    # Gate 3 (2026-02-06): Rewritten with normalized linked-list patterns for structural execution
    "exhaustion.v1.json": "2e407fd5774bd353b483eed51c153c4ec81ed7943447e97d7c18865f143de237",
    # RCX Engine: main program orchestrating recurrence + exhaustion
    # Updated: Added status: "design_only" marker
    # Updated: Fixed meta.doc path (docs/core/RCXEngine.v0.md -> docs/core/EngineNewsStructural.v0.md)
    "rcx_engine.v1.json": "dfc3c8fcd4545687b614b9ee8d80d687a29d72e36c69f148615061d0341b0456",
    # Step 7: Bootstrap-Structural Bridge (non-linear pattern support)
    "bootstrap_structural.v1.json": "edb9908eeaee4518b49f72bb17274aa490388555cebe9e363f5785d7e44014db",
    # Utilities: eval.v1.json - deep evaluation projections (BOOTSTRAP execution layer)
    # Updated: Fixed meta.doc path (docs/DeepStep.v0.md -> docs/core/EVAL_SEED.v0.md)
    "eval.v1.json": "22232b172f883271845d013d8e39b1b75555bd94899deb8276548c5f0d10f53e",
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
    # mu/ folder: recurrence.v1 (renamed from enginenews.v1)
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
    # Step 7: Bootstrap-Structural Bridge (non-linear pattern support)
    "bootstrap_structural.v1.json": [
        "bridge.var.check_existing",    # Entry: start lookup for variable
        "bridge.lookup.found_same",     # Found binding with same value (non-linear OK)
        "bridge.lookup.found_different",  # Found binding with different value -> NO_MATCH
        "bridge.lookup.not_found_yet",  # Name not at head, continue searching
        "bridge.lookup.not_found",      # Name not in bindings, add new
    ],
    # Utilities: eval.v1.json (legacy naming, BOOTSTRAP execution layer)
    "eval.v1.json": [
        "restart",              # ROOT_CHECK with changes -> restart traversal
        "unwrap",               # ROOT_CHECK without changes -> done
        "descend.dict",         # DESCEND into dict with head/tail structure
        "sibling.to_tail",      # SIBLING after head done -> move to tail
        "ascend.to_context",    # ASCEND -> pop context frame
        "ascend.to_root",       # ASCEND when context empty -> root_check
        "wrap",                 # Entry point - wrap raw value into state
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
    """Get the seeds directory path (DEPRECATED - use get_seed_path instead)."""
    import warnings
    warnings.warn(
        "get_seeds_dir() is deprecated. Use get_seed_path(seed_name) instead. "
        "mu/ is now the canonical location for seeds.",
        DeprecationWarning,
        stacklevel=2
    )
    return Path(__file__).parent.parent.parent / "seeds"


def get_mu_dir() -> Path:
    """Get the mu directory path (new organized structure)."""
    return Path(__file__).parent.parent.parent / "mu"


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

    # Map seed names to mu/ subfolders - this is the ONLY source of truth
    MU_SEED_LOCATIONS = {
        # Substrate seeds (the VM)
        "kernel.v1.json": "substrate",
        "match.v1.json": "substrate",
        "match.v2.json": "substrate",
        "subst.v1.json": "substrate",
        "subst.v2.json": "substrate",
        # Bridge seeds
        "bootstrap_structural.v1.json": "bridge",
        # Closure detection seeds
        "recurrence.v1.json": "closures",
        "exhaustion.v1.json": "closures",
        # Utilities
        "classify.v1.json": "utilities",
        "eval.v1.json": "utilities",
        # Programs
        "rcx_engine.v1.json": "programs",
    }

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
