"""
Substitute as Mu Projections - Phase 4b Self-Hosting

This module implements variable substitution using Mu projections instead of
Python recursion. It achieves parity with eval_seed.substitute() but uses
the kernel loop for iteration.

See mu/docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

import json

from .mu_type import Mu, assert_mu, MAX_MU_DEPTH
from .match_mu import (
    normalize_for_match,
    denormalize_from_match,
    dict_to_bindings,
    _check_empty_var_names,
)
from .projection_loader import make_projection_loader
from .projection_runner import make_projection_runner


# =============================================================================
# Projection Loading (v1 — retained for tests and legacy callers)
# =============================================================================

load_subst_projections, clear_projection_cache = make_projection_loader("subst.v1.json")

# =============================================================================
# Compiled Bundle Loading (v2 — VM-backed production path, Wave 3B)
# =============================================================================

_compiled_subst_v2_bundle_cache = None


def _load_compiled_subst_v2_bundle() -> dict:
    """Load and validate the compiled subst.v2 Stage0 VM bundle.

    Private to subst_mu.py — does NOT import from step_mu.py (circular dependency).
    Uses the same validation + provenance pattern as step_mu._load_compiled_subst_v2_bundle().
    """
    global _compiled_subst_v2_bundle_cache
    if _compiled_subst_v2_bundle_cache is not None:
        return _compiled_subst_v2_bundle_cache

    from .stage0_vm import validate_bundle  # ANTICHEAT_OK: infra — VM bundle validation
    from .seed_integrity import SEED_CHECKSUMS  # ANTICHEAT_OK: infra — N15 provenance

    from .seed_integrity import get_mu_dir  # ANTICHEAT_OK: infra — path resolution
    bundle_path = get_mu_dir() / "stage0" / "compiled" / "subst_v2.compiled.v1.json"
    if not bundle_path.exists():
        raise FileNotFoundError(f"Compiled subst.v2 bundle not found: {bundle_path}")

    with open(bundle_path, encoding="utf-8") as f:
        bundle = json.load(f)

    validate_bundle(bundle)

    # N15 provenance verification (inlined — cannot import from step_mu due to circular dep)
    source_seed = bundle.get("source_seed")
    source_digest = bundle.get("source_digest")
    if source_seed and source_digest:
        seed_filename = source_seed if source_seed.endswith(".json") else source_seed + ".json"
        if seed_filename in SEED_CHECKSUMS:
            expected = "sha256:" + SEED_CHECKSUMS[seed_filename]
            if source_digest != expected:  # AST_OK:infra — type guard
                raise ValueError(
                    f"SECURITY: Bundle provenance mismatch for '{seed_filename}'. "
                    f"Bundle claims source_digest={source_digest}, "
                    f"but SEED_CHECKSUMS says {expected}."
                )

    _compiled_subst_v2_bundle_cache = bundle
    return bundle


# =============================================================================
# Substitute Runner (v1 — retained for tests and legacy callers)
# =============================================================================

is_subst_done, is_subst_state, run_subst_projections = make_projection_runner("subst")

# v2 terminal detection (uses _mode instead of mode)
_is_subst_done_v2, _is_subst_state_v2, _ = make_projection_runner("subst", terminal_field="_mode")


def is_head_tail_structure(value: Mu) -> bool:
    """Check if value is a head/tail dict (including type-tagged variants).

    Recognizes both plain {"head", "tail"} and type-tagged {"_type", "head", "tail"}
    structures. Without this, type-tagged head/tail values would be incorrectly
    denormalized back to Python list/dict.

    isinstance at boundary is scaffolding: this is a type-dispatch guard
    at the host/Mu boundary, consistent with is_mu() and normalize_for_match().
    """
    if not isinstance(value, dict):  # AST_OK: boundary scaffolding — host type check
        return False
    keys = set(value.keys())  # AST_OK: boundary scaffolding — key set for structure dispatch
    if keys == {"head", "tail"}:  # AST_OK: key — structure dispatch
        return True
    if keys == {"_type", "head", "tail"}:  # AST_OK: key — structure dispatch
        return value["_type"] in ("list", "dict")  # Only valid type tags
    return False


def _substitute_direct(body: Mu, bindings: dict[str, Mu], _depth: int = 0) -> Mu:
    """Direct recursive substitution for head/tail body structures.

    Used by _reconcile_parity to preserve head/tail structures that would
    otherwise be incorrectly denormalized. Parity with eval_seed.substitute()
    for the head/tail subset of body shapes.

    This is a TEMPORARY parity fixup (wave4a D10). P7-d shadow mode is active;
    full cutover awaits evidence that the VM path matches all normalize→project→denormalize
    edge cases (see STATUS.md for cutover gate status).
    """
    if _depth > MAX_MU_DEPTH:
        raise TypeError(f"Max depth exceeded in _substitute_direct ({MAX_MU_DEPTH})")
    if body is None or isinstance(body, (bool, int, float, str)):  # AST_OK: boundary scaffolding — type dispatch
        return body
    if isinstance(body, dict):  # AST_OK: boundary scaffolding — type dispatch
        if len(body) == 1 and "var" in body and isinstance(body["var"], str):  # AST_OK: boundary scaffolding — var check
            name = body["var"]
            if name not in bindings:
                raise KeyError(f"Unbound variable: {name}")
            return bindings[name]
        return {k: _substitute_direct(v, bindings, _depth + 1) for k, v in body.items()}  # AST_OK: boundary scaffolding — parity fixup dict rebuild
    if isinstance(body, list):  # AST_OK: boundary scaffolding — type dispatch
        return [_substitute_direct(elem, bindings, _depth + 1) for elem in body]  # AST_OK: boundary scaffolding — parity fixup list rebuild
    return body


def _reconcile_parity(original_body: Mu, denormed: Mu,
                      bindings: dict[str, Mu], _depth: int = 0) -> Mu:
    """Reconcile denormalized result with original body for eval_seed parity.

    Fixes the nested head/tail parity gap (wave4a D10): denormalize_from_match
    converts ALL head/tail structures to Python lists/dicts, but eval_seed.substitute
    preserves head/tail structures that were in the original body or binding values.

    Walk original body and denormalized result in parallel:
    - At var sites: return raw binding value (not denormalized)
    - At head/tail body positions: use _substitute_direct (preserves structure)
    - At regular dict/list positions: recurse into children with denormalized values
    """
    if _depth > MAX_MU_DEPTH:
        return denormed
    # Var site: return raw binding value
    if isinstance(original_body, dict) and len(original_body) == 1 and "var" in original_body and isinstance(original_body["var"], str):  # AST_OK: boundary scaffolding — var check
        name = original_body["var"]
        if name not in bindings:
            raise KeyError(f"Unbound variable: {name}")
        return bindings[name]
    # Primitive/None: return denormalized value as-is
    if original_body is None or isinstance(original_body, (bool, int, float, str)):  # AST_OK: boundary scaffolding — type check
        return denormed
    # Head/tail structure: preserve via direct substitution
    if isinstance(original_body, dict) and is_head_tail_structure(original_body):  # AST_OK: boundary scaffolding — type check
        return _substitute_direct(original_body, bindings, _depth)
    # Regular dict: recurse into values
    if isinstance(original_body, dict) and isinstance(denormed, dict):  # AST_OK: boundary scaffolding — type check
        result = {}
        for k in denormed:
            if k in original_body:
                result[k] = _reconcile_parity(original_body[k], denormed[k], bindings, _depth + 1)
            else:
                result[k] = denormed[k]
        return result
    # Regular list: recurse into elements
    if isinstance(original_body, list) and isinstance(denormed, list):  # AST_OK: boundary scaffolding — type check
        n = min(len(original_body), len(denormed))
        return [_reconcile_parity(original_body[i], denormed[i], bindings, _depth + 1)  # AST_OK: boundary scaffolding — parity reconciliation list rebuild
                for i in range(n)]
    # Fallback (type mismatch between original and denormed)
    return denormed


def subst_mu(body: Mu, bindings: dict[str, Mu]) -> Mu:
    """
    Substitute variables in body with bound values using Mu projections.

    This is the parity function for eval_seed.substitute().

    Args:
        body: The body with possible {"var": "x"} sites.
        bindings: Dict mapping variable names to values.

    Returns:
        Body with variables replaced by their bound values.

    Raises:
        KeyError: If a variable in body is not in bindings.
    """
    assert_mu(body, "subst_mu.body")

    # Validate no empty variable names (parity with eval_seed.py)
    _check_empty_var_names(body, "body")

    # F-41: Validate binding names and values at entry (fail-closed)
    for k, v in bindings.items():  # AST_OK: boundary validation loop — entry guard
        if not isinstance(k, str) or not k:  # AST_OK: boundary scaffolding — type check
            raise ValueError(f"subst_mu: binding name must be non-empty string, got {k!r}")
        assert_mu(v, f"subst_mu.bindings[{k!r}]")

    # Normalize body to head/tail structure
    norm_body = normalize_for_match(body)

    # Convert bindings dict to linked list
    linked_bindings = dict_to_bindings(bindings)

    # Wave 3B: Load compiled subst.v2 bundle for VM-backed execution
    from .stage0_vm import stage0_vm_run, Stage0VMError  # ANTICHEAT_OK: infra — VM runner
    from .kernel import get_step_budget  # ANTICHEAT_OK: infra — step budget

    bundle = _load_compiled_subst_v2_bundle()

    # Wrap input in subst.v2 request format with _subst_ctx ABI envelope
    _subst_ctx = {"_input": None, "_remaining": None}
    initial = {
        "subst": {"body": norm_body, "bindings": linked_bindings},
        "_subst_ctx": _subst_ctx,
    }

    # Run via Stage0 VM (direct call, no projection_runner)
    budget = get_step_budget()
    try:
        vm_result = stage0_vm_run(bundle, initial, max_steps=1000)
        final_state = vm_result["root"]
        vm_steps = len(vm_result["steps"])

        if _is_subst_done_v2(final_state):
            # Successful completion: consume matched steps only
            budget.consume(vm_steps)
            is_stall = False
        else:
            # Genuine stall: +1 for the stall-detection attempt
            budget.consume(vm_steps + 1)
            is_stall = True
    except Stage0VMError as e:
        # Only catch run-step-limit exhaustion; re-raise real VM faults
        if "Run step limit exceeded" not in str(e):
            raise
        budget.consume(1000)
        is_stall = True
        final_state = initial  # return original on exhaustion

    # Extract result (v2 uses _result and _mode instead of result and mode)
    if is_stall:
        # Defensive fallback for incomplete bundles. Under correctly compiled
        # subst.v2, unbound variables always reach the done path via
        # lookup.exhausted -> subst.done (Delta 6). This stall-detection path
        # only activates if the compiled bundle is missing the lookup.exhausted
        # program or if a genuine non-variable stall occurs.
        if _is_subst_state_v2(final_state):
            phase = final_state.get("phase")
            if phase == "lookup":
                name = final_state.get("lookup_name")
                raise KeyError(f"Unbound variable: {name}")
        raise RuntimeError(f"Substitute stalled unexpectedly: {final_state}")

    if _is_subst_done_v2(final_state):
        result = final_state.get("_result")

        # Delta 6: v2 unbound-variable detection (error-as-value)
        # v2 lookup.exhausted produces _error result instead of stalling
        if isinstance(result, dict) and result.get("_error") == "unbound_variable":
            name = result.get("_name")
            raise KeyError(f"Unbound variable: {name}")

        # Wave4a D10 parity fix: handle head/tail structures correctly.
        if is_head_tail_structure(body):
            return _substitute_direct(body, bindings)
        denormed = denormalize_from_match(result)
        return _reconcile_parity(body, denormed, bindings)

    raise RuntimeError(f"Unexpected substitute state: {final_state}")
