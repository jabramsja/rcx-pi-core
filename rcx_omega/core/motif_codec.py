"""
RCX-Ω: Motif <-> JSON object codec (staging)

Goal:
- Provide a stable, explicit JSON-ish representation of π Motifs
  WITHOUT modifying rcx_pi internals.

Canonical π fact (discovered via introspection):
- Motif children live in `Motif.structure` as a tuple.

Encoding (minimal + explicit):
- VOID -> {"VOID": []}
- UNIT -> {"UNIT": []}
- μ(...) -> {"μ": [<child1>, <child2>, ...]}

This is intentionally conservative. As Ω grows, we can add richer atoms,
metadata, or alternative forms, but this base should stay stable.
"""

from __future__ import annotations

from typing import Any, Dict, List

from rcx_pi import μ, VOID, UNIT
from rcx_pi.core.motif import Motif


JsonObj = Any  # nested dict/list/str/int etc. (we keep it loose for staging)


def _motif_children(x: Motif) -> List[Motif]:
    """
    Canonical child discovery for π Motif: use `x.structure`.

    In π, `structure` is a tuple of Motif children (possibly empty).
    """
    st = getattr(x, "structure", None)
    if st is None:
        return []
    if isinstance(st, tuple):
        return list(st)
    if isinstance(st, list):
        return st
    # If someone mutates π later (they shouldn't), fail safe:
    return []


def motif_to_json_obj(x: Motif) -> Dict[str, Any]:
    """
    Encode a π Motif into a JSON-friendly object.

    This returns a dict with a single key.
    """
    if x == VOID:
        return {"VOID": []}
    if x == UNIT:
        return {"UNIT": []}

    kids = _motif_children(x)
    return {"μ": [motif_to_json_obj(k) for k in kids]}


def json_obj_to_motif(obj: JsonObj) -> Motif:
    """
    Decode a JSON object produced by `motif_to_json_obj` back into a π Motif.
    """
    if not isinstance(obj, dict) or len(obj) != 1:
        raise ValueError(f"Invalid motif JSON object (expected 1-key dict): {obj!r}")

    (k, v), = obj.items()

    if k == "VOID":
        return VOID
    if k == "UNIT":
        return UNIT
    if k == "μ":
        if not isinstance(v, list):
            raise ValueError(f"Invalid μ payload (expected list): {v!r}")
        return μ(*[json_obj_to_motif(child) for child in v])

    raise ValueError(f"Unknown motif tag: {k!r}")
