"""
Classify as Mu Projections - Phase 6b Self-Hosting

This module implements linked list classification using Mu projections.
It determines whether a head/tail linked list encodes a dict (all elements
are kv-pairs) or a list (general elements).

See docs/core/SelfHosting.v0.md for design.

Pre-condition: Dict keys are strings (JSON constraint). The classification
patterns check structural shape but cannot verify Python types.
"""

from __future__ import annotations

from typing import Literal

from .mu_type import Mu, mu_equal
from .eval_seed import step
from .kernel import get_step_budget
from .projection_loader import make_projection_loader
from .projection_runner import make_projection_runner


# =============================================================================
# Projection Loading (consolidated via factory)
# =============================================================================

load_classify_projections, clear_projection_cache = make_projection_loader("classify.v1.json")

# =============================================================================
# Classify Runner (consolidated via factory)
# =============================================================================

is_classify_done, is_classify_state, run_classify_projections = make_projection_runner("classify")


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
    if not isinstance(value, dict):
        return "list"

    keys = set(value.keys())

    # Phase 6c: Type-tagged structures - use the _type directly
    if keys == {"_type", "head", "tail"}:  # AST_OK: key comparison
        _type = value.get("_type")
        # Security: Only accept string type tags from the whitelist
        # Non-string or unknown types are treated as invalid (return "list")
        if not isinstance(_type, str):
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
    visited: set[int] = set()
    current = value
    while current is not None:
        if not isinstance(current, dict):
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
        # See docs/core/DebtCategories.v0.md for documentation of this design decision.
        head = current.get("head")
        if isinstance(head, dict):
            # Could be a kv-pair: {"head": key, "tail": {"head": val, "tail": null}}
            if set(head.keys()) == {"head", "tail"}:
                key = head.get("head")
                if not isinstance(key, str):
                    # Key is not a string - not a valid dict encoding
                    return "list"
        # If head is not a dict, the projections will catch it as not-kv

        current = current.get("tail")

    # Load projections for structural validation
    projections = load_classify_projections()

    # Wrap input in classify request format
    initial = {"classify": {"list": value}}

    # Run projections
    final_state, steps, is_stall = run_classify_projections(projections, initial)

    # Extract result
    if is_stall:
        # Stall means no projection matched = treat as list
        return "list"

    if is_classify_done(final_state):
        result_type = final_state.get("type")
        if result_type == "dict":
            return "dict"

    return "list"
