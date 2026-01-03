"""
RCX-Ω: Motif <-> JSON object codec (staging, CANONICAL)

Encoding contract (minimal):
- VOID/UNIT are encoded as atoms ONLY when they are the canonical singletons
  (identity check), NOT when merely structurally equal.
    {"atom": "VOID"} / {"atom": "UNIT"}
- General motifs are encoded as μ nodes with children:
    {"μ": [<child1>, <child2>, ...]}

π fact:
- Motif children live in `Motif.structure` as a tuple.
- Motif equality is structural, so user-built μ(μ()) can be == UNIT.
  We must not collapse that into an atom unless it is literally the UNIT singleton.
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


def motif_to_json_obj(x: Motif, *, include_meta: bool = False) -> Dict[str, Any]:
    """
    Encode a π Motif as a JSON object.

    include_meta is accepted for forward-compatibility with Ω tooling/CLI.
    (Currently ignored; Ω may later include lightweight annotations.)
    """
    # Identity checks only: avoid collapsing arbitrary motifs that are structurally
    # equal to UNIT/VOID.
    if x is VOID:
        return {"atom": "VOID"}
    if x is UNIT:
        return {"atom": "UNIT"}

    kids = _children(x)
    return {"μ": [motif_to_json_obj(k, include_meta=include_meta) for k in kids]}


def json_obj_to_motif(obj: JsonObj) -> Motif:
    if not isinstance(obj, dict):
        raise ValueError(f"Invalid motif JSON object (expected dict): {obj!r}")

    if "atom" in obj:
        a = obj["atom"]
        if a == "VOID":
            return VOID
        if a == "UNIT":
            return UNIT
        raise ValueError(f"Unknown atom: {a!r}")

    if "μ" in obj:
        v = obj["μ"]
        if not isinstance(v, list):
            raise ValueError(f"Invalid μ payload (expected list): {v!r}")
        return μ(*[json_obj_to_motif(child) for child in v])

    raise ValueError(f"Invalid motif JSON object (expected 'μ' or 'atom'): {obj!r}")
