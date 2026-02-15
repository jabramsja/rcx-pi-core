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
import warnings
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
    # Updated: Fixed meta.doc path (docs/SelfHosting.v0.md -> mu/docs/core/SelfHosting.v0.md)
    "match.v1.json": "33c7bc60d2c4468f224d85c7d0e6c385a898f61585001370b6511c30307f2c9c",
    # Updated v1.2.0: added subst.typed.* projections for type-tagged structures (Phase 6c)
    # Updated: Added execution_layer: META_CIRCULAR
    # Updated: Fixed meta.doc path (docs/SelfHosting.v0.md -> mu/docs/core/SelfHosting.v0.md)
    "subst.v1.json": "929db9a6d60b28d53c5e184da7db8c7c668d2f9a65068e8cb0e2629083ffd51f",
    # Phase 6b: classification as Mu projections (v1.0.0 + nested_not_kv fix)
    # Updated: Added execution_layer: META_CIRCULAR
    # Updated: Fixed meta.doc path (docs/SelfHosting.v0.md -> mu/docs/core/SelfHosting.v0.md)
    "classify.v1.json": "8ecd4fccca243c49129c0d65c8fef5797f19a36499e17038625fca3051108b79",
    # Phase 7a: meta-circular kernel projections (v1.0.1 - entry format output)
    # Updated: Added execution_layer: META_CIRCULAR
    "kernel.v1.json": "8a4471648c8d77d4d5beedf3491c04b8154e282bbfbf52a958f8c5bcc5d94c4f",
    # Phase 7b: match with kernel context passthrough + match.fail (fixed var names)
    # Updated: Added execution_layer: META_CIRCULAR, fixed match.equal description
    "match.v2.json": "cd89ce2bef9668b2e0bb190ad8a615a53bd699d4a0ad3ff9d6c1429db5e3594d",
    # Phase 7b: subst with kernel context passthrough
    # Updated: Added execution_layer: META_CIRCULAR
    "subst.v2.json": "0b735c52da437a6eae1478dc4c992269bff8978c7e9084d15ffcba6c06e3037f",
    # mu/ folder reorganization: renamed from enginenews.v1/exhaust.v1 to recurrence.v1/exhaustion.v1
    # Legacy names (enginenews.v1, exhaust.v1) removed - mu/ is now canonical
    # Updated v1.2.0: META_CIRCULAR execution_layer (Gate 4 cutover complete)
    # Gate 3 (2026-02-06): Rewritten with normalized linked-list patterns for structural execution
    # Gate 4 (2026-02-07): runtime cutover to step_kernel_mu bridge path
    # v1.2.0 + PROOF_OF_CONCEPT marker (superseded by recurrence.v2.json)
    "recurrence.v1.json": "ad9944b340e22df187fe567875d2c75483d4201b1b5c0147e1e8ec63e0bbacd0",
    # exhaustion.v1.json = exhaust.v1.json with exhaustion.* projection IDs
    # Updated v1.2.0: META_CIRCULAR execution_layer (Gate 4 cutover complete)
    # Gate 3 (2026-02-06): Rewritten with normalized linked-list patterns for structural execution
    # Gate 4 (2026-02-07): runtime cutover to step_kernel_mu bridge path
    "exhaustion.v1.json": "2497881e19015db553a834c9d1f287c7774c2607effc224ed460b4b8051dffe0",
    # RCX Engine: structural specification for pipeline orchestration (7 projections)
    # Status: structural_specification — host loop services boundary stalls (hash_trace, sub-algorithms)
    "rcx_engine.v1.json": "1e32fcb989d18015be45ee7dd6d7b85a9ecfa8509d44562f04b7029c23ec684f",
    # Step 7: Bootstrap-Structural Bridge (non-linear pattern support)
    "bootstrap_structural.v1.json": "dfaa1ea9de000e344fee1e61be9666e2876091fa64aff524857265929a261964",
    # Utilities: eval.v1.json - deep evaluation projections (BOOTSTRAP execution layer)
    # Updated: Fixed meta.doc path (docs/DeepStep.v0.md -> mu/docs/core/EVAL_SEED.v0.md)
    "eval.v1.json": "4c88e312002601f56fa5c3604f7938bc3651cf2718f1e672274a454b14e8bd78",
    # Hemispheres v1: native structural routing (APPLICATION execution layer)
    "hemispheres.v1.json": "e7f4735c36450f58fdebf137ba2933695b31eac813d1eb4a8e84db3380438ab5",
    # Paxos demo: livelock simulation + healer (APPLICATION execution layer)
    "paxos_demo.v1.json": "56f534439b0b93df1802b3fb2e41fb0d0919b934c6667d9ab413678f6971ef6d",
    # Recurrence v2: hash-accelerated closure detection (META_CIRCULAR)
    "recurrence.v2.json": "f8bc7fc7f43f5423b0ecf0e78fd4b2d99699456ecff1e113d4c8e7167b213fa9",
    # Fix v1: structural fix routine for GAP-04-FIX (Rule 0.6, APPLICATION)
    "fix.v1.json": "d961abcf1b9ba39c2eebcf049ae3351b51082a09c41deb0d71efef9eedadca34",
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
    # recurrence.v2.json = hash-accelerated closure detection
    "recurrence.v2.json": [
        "recurrence.init",               # Entry: _detect_closure -> internal state
        "recurrence.end_of_trace",       # End of trace (null) -> no closure
        "recurrence.check_state_stall",  # Extract state+hash from stall entry
        "recurrence.check_state_maxsteps",  # Extract state+hash from max_steps entry
        "recurrence.check_state",        # Extract state+hash from trace entry
        "recurrence.hash_match",         # Hash in seen-set (non-linear) -> closure!
        "recurrence.hash_no_match",      # Hash not in head -> check tail
        "recurrence.not_found",          # Hash not in seen -> add {hash,state} and advance
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
        "engine.init",                      # Entry: default config
        "engine.init_config",               # Entry: custom config (+ trampoline re-entry)
        "engine.trace_done",                # Trace complete -> request boundary hash
        "engine.hash_done_fix",             # Stall detected -> dispatch fix.v1.json (Rule 0.6)
        "engine.hash_done",                 # Non-stall -> start recurrence
        "engine.fix_done_applied",          # Fix applied -> recurrence with fixed result
        "engine.fix_done_none",             # Fix not applicable -> recurrence with original
        "engine.recurrence_done",           # Recurrence done -> exhaustion
        "engine.exhaustion_done_freeze",    # action=freeze -> trampoline re-entry (TRANSITIONAL)
        "engine.exhaustion_done_terminal",  # Non-freeze -> final result
        "engine.unwrap",                    # Extract final result
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
    # Paxos demo: consensus demonstration
    "paxos_demo.v1.json": [
        "paxos.init",
        "paxos.vote_a",
        "paxos.reject_b",
        "paxos.reject_a",
        "healer.detect_deadlock",
        "healer.detect_deadlock_engine",
    ],
    # Hemispheres v1: native structural routing (APPLICATION execution layer)
    "hemispheres.v1.json": [
        "hemisphere.init",                  # Entry: decompose engine_result
        "hemisphere.classify.exhaustion",   # Exhaustion detected -> sink
        "hemisphere.classify.null",         # Value is null -> r_null
        "hemisphere.classify.closure",      # Closure detected -> r_a
        "hemisphere.classify.stall",        # Stall detected -> r_inf
        "hemisphere.classify.default",      # Default -> lobes
        "hemisphere.add.r_null",            # Prepend entry to r_null
        "hemisphere.add.r_inf",             # Prepend entry to r_inf
        "hemisphere.add.r_a",               # Prepend entry to r_a
        "hemisphere.add.lobes",             # Prepend entry to lobes
        "hemisphere.add.sink",              # Prepend entry to sink
        "hemisphere.unwrap",                # Extract final result
    ],
    # Fix v1: structural fix routine for GAP-04-FIX (Rule 0.6)
    "fix.v1.json": [
        "fix.init",              # Entry: decompose apply_fix request
        "fix.edge_add_guard",    # I3 idempotence: already has fix edge
        "fix.edge_add",          # Add one edge to graph with edges
        "fix.vertex_add_guard",  # I3 idempotence: already has fix vertex
        "fix.vertex_add",        # Add one vertex to graph with vertices
        "fix.pass_through",      # Fallback: no perturbation possible
    ],
}


# Map seed names to mu/ subfolders — the ONLY source of truth for seed locations.
# Module-level so it's created once (not per call).
MU_SEED_LOCATIONS: dict[str, str] = {
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
    "recurrence.v2.json": "closures",
    "exhaustion.v1.json": "closures",
    "fix.v1.json": "closures",
    # Utilities
    "classify.v1.json": "utilities",
    "eval.v1.json": "utilities",
    # Programs
    "rcx_engine.v1.json": "programs",
    "hemispheres.v1.json": "programs",
    "paxos_demo.v1.json": "programs",
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
        warnings.warn(
            f"Seed {seed_name} has no entry in EXPECTED_PROJECTION_IDS — "
            f"projection ordering is NOT validated. Register it for fail-closed security.",
            stacklevel=2,
        )
        return

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
