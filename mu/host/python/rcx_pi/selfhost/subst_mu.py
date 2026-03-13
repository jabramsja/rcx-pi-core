"""
Substitute as Mu Projections - Phase 4b Self-Hosting

This module implements variable substitution using Mu projections instead of
Python recursion. It achieves parity with eval_seed.substitute() but uses
the kernel loop for iteration.

See mu/docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

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
# Projection Loading (consolidated via factory)
# =============================================================================

load_subst_projections, clear_projection_cache = make_projection_loader("subst.v1.json")

# =============================================================================
# Substitute Runner (consolidated via factory)
# =============================================================================

is_subst_done, is_subst_state, run_subst_projections = make_projection_runner("subst")


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

    This is a TEMPORARY parity fixup (wave4a D10). P7-d will replace the
    normalize→project→denormalize mechanism entirely.
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

    # Load projections
    projections = load_subst_projections()

    # Wrap input in subst request format
    initial = {"subst": {"body": norm_body, "bindings": linked_bindings}}

    # Run projections (bindings are embedded in initial state)
    final_state, steps, is_stall = run_subst_projections(projections, initial)

    # Extract result
    if is_stall:
        # Check if we stalled on a lookup (unbound variable)
        # Phase 6a: lookup stalls when lookup_bindings is null
        if is_subst_state(final_state):
            phase = final_state.get("phase")
            if phase == "lookup":
                # Stalled in lookup phase = unbound variable
                name = final_state.get("lookup_name")
                raise KeyError(f"Unbound variable: {name}")
            # Legacy check for old lookup marker format (shouldn't happen now)
            focus = final_state.get("focus")
            if isinstance(focus, dict) and "lookup" in focus:
                name = focus["lookup"]
                raise KeyError(f"Unbound variable: {name}")
        raise RuntimeError(f"Substitute stalled unexpectedly: {final_state}")

    if is_subst_done(final_state):
        result = final_state.get("result")
        # Wave4a D10 parity fix: handle head/tail structures correctly.
        if is_head_tail_structure(body):
            # Root head/tail: use direct substitution (preserves structure +
            # handles nested Python types that denormalize_from_match can't).
            return _substitute_direct(body, bindings)
        # Non-head/tail root: denormalize, then reconcile to preserve nested
        # head/tail structures and raw binding values.
        denormed = denormalize_from_match(result)
        return _reconcile_parity(body, denormed, bindings)

    raise RuntimeError(f"Unexpected substitute state: {final_state}")
