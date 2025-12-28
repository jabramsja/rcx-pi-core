# rcx_pi/pretty.py
"""
Pretty-printer for Motif structures in RCX-π.
Now includes readable list formatting: [1,2,3]
"""

from __future__ import annotations
from typing import Optional
from rcx_pi.core.motif import Motif
from rcx_pi import motif_to_int
from rcx_pi.listutils import is_list_motif, py_from_list


def pretty_motif(m: Motif, *, depth=0, max_depth=10) -> str:
    """Human-oriented view of motifs.

    Numbers → N:3
    Lists → [1,2,3]
    VOID → ∅
    UNIT → •
    General → μ(a,b,c)
    """

    # --- recursion stop ---
    if depth > max_depth:
        return "…"

    # Numbers ---------------------------------------------------------
    n = motif_to_int(m)
    if n is not None:
        return f"N:{n}"

    # List formatting -------------------------------------------------
    if is_list_motif(m):
        lst = py_from_list(m)
        inner = ", ".join(str(x) for x in lst)
        return f"[{inner}]"

    # VOID / UNIT simplified -----------------------------------------
    from rcx_pi.core.motif import VOID, UNIT
    if m == VOID:
        return "∅"
    if m == UNIT:
        return "•"

    # Generic Motif --------------------------------------------------
    items = []
    for child in m.structure:
        if isinstance(child, Motif):
            items.append(pretty_motif(child, depth=depth+1))
        else:
            items.append(repr(child))

    return f"μ({', '.join(items)})"