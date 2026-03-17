"""
Classify as Mu Projections - Phase 6b Self-Hosting

This module implements linked list classification using Mu projections.
It determines whether a head/tail linked list encodes a dict (all elements
are kv-pairs) or a list (general elements).

See mu/docs/core/SelfHosting.v0.md for design.

Pre-condition: Dict keys are strings (JSON constraint). The classification
patterns check structural shape but cannot verify Python types.
"""

from __future__ import annotations

from typing import Literal

from .mu_type import Mu
from .projection_loader import make_projection_loader

# =============================================================================
# Projection Loading (retained for test compatibility)
# =============================================================================

load_classify_projections, clear_projection_cache = make_projection_loader("classify.v1.json")

# =============================================================================
# Compiled Bundle Loading (Wave 3D-B — VM-backed production path)
# =============================================================================

from .stage0_vm import make_compiled_bundle_loader  # ANTICHEAT_OK: infra — bundle loader factory

_load_classify_bundle, _clear_classify_bundle = make_compiled_bundle_loader("classify_v1")


def classify_linked_list(value: Mu) -> Literal["dict", "list"]:
    """
    Classify a head/tail linked list as dict-encoding or list-encoding.

    For type-tagged structures (Phase 6c), simply returns the _type value.
    For legacy structures without _type, uses projection-based classification.

    Args:
        value: A head/tail linked list (or null for empty), optionally type-tagged.

    Returns:
        "dict" if type-tagged as dict or all elements are kv-pairs with string keys.
        "list" otherwise (including empty list, primitives, circular).
    """
    # Non-dict structures are not dict-encoded
    if not isinstance(value, dict):  # AST_OK: infra — type classification
        return "list"

    keys = set(value.keys())

    # Phase 6c: Type-tagged structures - use the _type directly
    if keys == {"_type", "head", "tail"}:  # AST_OK: key comparison
        _type = value.get("_type")
        # Security: Only accept string type tags from the whitelist
        # Non-string or unknown types are treated as invalid (return "list")
        if not isinstance(_type, str):  # AST_OK: infra — type classification
            return "list"
        if _type == "dict":
            return "dict"
        elif _type == "list":
            return "list"
        # Unknown string type - invalid, treat as list
        return "list"

    # Legacy: head/tail without type tag - use projection-based classification
    if keys != {"head", "tail"}:
        return "list"

    # Walk the list to check:
    # 1. No circular references (projections can't handle these)
    # 2. All kv-pair keys are strings (projections can't verify Python types)
    #
    # BOUNDARY SCAFFOLDING: This while loop is a pre-validation check before
    # projections run. It verifies preconditions that projections cannot check
    # (Python types, circular refs). This is boundary scaffolding analogous to
    # normalize_for_match/denormalize_from_match loops in match_mu.py.
    # See STATUS.md "Boundary Scaffolding vs Semantic Debt" for policy.
    visited: set[int] = set()
    current = value
    _max_classify_walk = 10000  # Defense-in-depth: cap iterations for acyclic lists
    _walk_count = 0
    while current is not None:  # BOUNDARY: pre-validation loop (off kernel path — called by classify_mu/apply_mu, not step_kernel_mu). Reclassified P7W4.
        _walk_count += 1
        if _walk_count > _max_classify_walk:
            # Deliberate cutoff: lists longer than 10000 nodes are treated as
            # "list" rather than walking to completion.  This bounds CPU time
            # for adversarial inputs while being well above any practical dict
            # size.  The boundary is 10000 (not 10001) because the check fires
            # after incrementing _walk_count, so node 10001 is never visited.
            return "list"
        if not isinstance(current, dict):  # AST_OK: infra — type classification
            break
        node_id = id(current)
        if node_id in visited:
            # Circular structure - not a valid dict encoding
            return "list"
        visited.add(node_id)
        if set(current.keys()) != {"head", "tail"}:
            break

        # Check if this element is a valid kv-pair with string key
        # This is the type check that projections cannot do
        #
        # KNOWN LIMITATION: A list like [[s, x]] normalizes identically to {s: x}
        # We cannot distinguish them after normalization. We favor dict interpretation
        # because dicts with None values are more common than lists of 2-element sublists.
        # See mu/docs/core/DebtCategories.v0.md for documentation of this design decision.
        head = current.get("head")
        if isinstance(head, dict):  # AST_OK: infra — type classification
            # Gate 3: Type-tagged structures are NOT kv-pairs
            # A kv-pair has exactly {head, tail} keys, not {head, tail, _type}
            if "_type" in head:
                # Type-tagged element means this is a list, not a dict
                return "list"
            # Could be a kv-pair: {"head": key, "tail": {"head": val, "tail": null}}
            if set(head.keys()) == {"head", "tail"}:
                key = head.get("head")
                if not isinstance(key, str):  # AST_OK: infra — type classification
                    # Key is not a string - not a valid dict encoding
                    return "list"
        # If head is not a dict, the projections will catch it as not-kv

        current = current.get("tail")

    # Wave 3D-B: VM-backed classification via stage0_vm_run_bounded
    from .stage0_vm import stage0_vm_run_bounded, Stage0VMError  # ANTICHEAT_OK: infra — bounded VM helper
    from .kernel import get_step_budget  # ANTICHEAT_OK: infra — step budget

    bundle = _load_classify_bundle()
    initial = {"classify": {"list": value}}
    budget = get_step_budget()

    try:
        outcome = stage0_vm_run_bounded(
            bundle, initial,
            max_steps=1000,
            terminal_field="mode",
            terminal_value="classify_done",
        )
    except Stage0VMError:
        # VM fault on malformed input (e.g., circular references inside element
        # values that bypass the pre-validation walk). Fail-closed to "list".
        budget.consume(1)
        return "list"

    # Budget accounting (parity with projection_runner)
    if outcome["status"] == "terminal":
        budget.consume(outcome["steps"])
    elif outcome["status"] == "stall":
        budget.consume(outcome["steps"] + 1)  # +1 for stall-detection probe
    else:  # exhaustion
        budget.consume(1000)

    # Extract result — fail-closed to "list"
    if outcome["status"] == "terminal":
        result_type = outcome["root"].get("type")
        if result_type == "dict":
            return "dict"

    return "list"
