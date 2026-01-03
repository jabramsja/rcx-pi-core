"""
RCX-Ω: Motif <-> JSON object codec (staging)

IMPORTANT:
- rcx_omega/tests currently import this module path:
    rcx_omega.utils.motif_codec

Encoding contract (minimal):
- VOID/UNIT are encoded as atoms:
    {"atom": "VOID"} / {"atom": "UNIT"}
- General motifs are encoded as μ nodes with children:
    {"μ": [<child1>, <child2>, ...]}

π fact:
- Motif children live in `Motif.structure` as a tuple.
"""

from __future__ import annotations

from typing import Any, Dict, List

from rcx_pi import μ, VOID, UNIT
from rcx_pi.core.motif import Motif

JsonObj = Any


def _children(x: Motif) -> List[Motif]:
    st = getattr(x, "structure", None)
    if st is None:
        return []
    if isinstance(st, tuple):
        return list(st)
    if isinstance(st, list):
        return st
    return []


def motif_to_json_obj(x: Motif) -> Dict[str, Any]:
    if x == VOID:
        return {"atom": "VOID"}
    if x == UNIT:
        return {"atom": "UNIT"}

    kids = _children(x)
    return {"μ": [motif_to_json_obj(k) for k in kids]}


def json_obj_to_motif(obj: JsonObj) -> Motif:
    if not isinstance(obj, dict):
        raise ValueError(f"Invalid motif JSON object (expected dict): {obj!r}")

    # atom form
    if "atom" in obj:
        a = obj["atom"]
        if a == "VOID":
            return VOID
        if a == "UNIT":
            return UNIT
        raise ValueError(f"Unknown atom: {a!r}")

    # μ form
    if "μ" in obj:
        v = obj["μ"]
        if not isinstance(v, list):
            raise ValueError(f"Invalid μ payload (expected list): {v!r}")
        return μ(*[json_obj_to_motif(child) for child in v])

    raise ValueError(f"Invalid motif JSON object (expected 'μ' or 'atom'): {obj!r}")
