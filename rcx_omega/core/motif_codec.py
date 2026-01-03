"""
RCX-Ω: Motif codec (staging)

Purpose:
- Provide a stable JSON-ish representation of π Motifs
- WITHOUT mutating π
- While preserving μ arity exactly (μ(μ()) -> one child)

This codec is reflective, not speculative.
"""

from __future__ import annotations

from typing import Any, Dict, List

from rcx_pi.core.motif import Motif


def motif_to_json_obj(x: Any) -> Any:
    """
    Convert a π motif (or nested structure) to a JSON-serializable object.
    Motifs become {"μ": [...]} trees.
    """

    # JSON primitives
    if x is None or isinstance(x, (bool, int, float, str)):
        return x

    # Lists / tuples
    if isinstance(x, (list, tuple)):
        return [motif_to_json_obj(v) for v in x]

    # Dicts
    if isinstance(x, dict):
        return {str(k): motif_to_json_obj(v) for k, v in x.items()}

    # π Motif (authoritative path)
    if isinstance(x, Motif):
        # Motif stores children internally; this is the ONLY correct source
        return {
            "μ": [motif_to_json_obj(c) for c in x.items]
        }

    # Fallback (debug only)
    return {"$repr": repr(x)}
