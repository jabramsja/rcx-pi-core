# rcx_pi/listutils.py
"""
Minimal list/sequence utilities for RCX-π.

Design:
-------
* Lists are pure motifs:
      NIL()         -> VOID
      CONS(h, t)    -> μ(h, t)

* A motif is treated as a list iff it is a chain of μ(h, t) nodes
  ending in VOID.

We deliberately avoid importing ``rcx_pi`` at module import time
to prevent circular-import issues. Any bridges to the public API
(e.g. num / motif_to_int) are done locally or reimplemented here.
"""

from __future__ import annotations
from typing import Any

from rcx_pi.core.motif import Motif, μ, VOID, UNIT


# ---------------------------------------------------------------------------
# Core constructors
# ---------------------------------------------------------------------------


def NIL() -> Motif:
    """Empty list sentinel."""
    return VOID


def CONS(h: Motif, t: Motif) -> Motif:
    """Cons cell: μ(h, t)."""
    return μ(h, t)


# ---------------------------------------------------------------------------
# Local Peano helper to avoid rcx_pi import at module import time
# ---------------------------------------------------------------------------


def _motif_to_int_local(m: Motif) -> int | None:
    """Local Peano decoder: succ^n(VOID) -> n, else None."""
    if not isinstance(m, Motif):
        return None
    if m.is_zero_pure():
        return 0
    n = 0
    cur = m
    while cur.is_successor_pure():
        n += 1
        cur = cur.head()
    return n if cur.is_zero_pure() else None


# ---------------------------------------------------------------------------
# Python list <-> Motif list bridges
# ---------------------------------------------------------------------------


def list_from_py(seq: list[Any]) -> Motif:
    """
    Build a motif list from a Python list.

    Example:
        list_from_py([1, 2, 3])  →
            CONS(num(1), CONS(num(2), CONS(num(3), NIL())))
    """
    m = NIL()

    # Import num lazily, at call time, to avoid circular imports.
    from rcx_pi import num  # type: ignore

    for item in reversed(seq):
        # 1) ints → Peano numbers
        if isinstance(item, int):
            elem = num(item)

        # 2) already a Motif → use as-is (lists, numbers, closures, etc)
        elif isinstance(item, Motif):
            elem = item

        # 3) anything else (e.g. "x", "y") → box in a Motif with meta["py"]
        else:
            # Use a non-Peano shape so motif_to_int(elem) returns None.
            box = μ(UNIT, VOID)
            meta = getattr(box, "meta", None)
            if not isinstance(meta, dict):
                box.meta = {}
            box.meta["py"] = item
            elem = box

        m = CONS(elem, m)

    return m


def py_from_list(m: Motif) -> list[Any]:
    """
    Convert a motif list back to a Python list.

    Integers encoded as Peano numbers (VOID, succ(...)) are mapped back
    to Python ints via motif_to_int. Any element that is a Motif with
    meta["py"] is unboxed to that Python value. Everything else is
    returned as-is.
    """
    from rcx_pi import motif_to_int  # type: ignore

    out: list[Any] = []
    cur = m

    while cur != VOID:
        h = head(cur)
        cur = tail(cur)

        # Try Peano int
        n = motif_to_int(h)
        if n is not None:
            out.append(n)
            continue

        # Try boxed Python value
        meta = getattr(h, "meta", None)
        if isinstance(meta, dict) and "py" in meta:
            out.append(meta["py"])
            continue

        # Fallback: return motif itself
        out.append(h)

    return out


# ---------------------------------------------------------------------------
# List recognizers and accessors
# ---------------------------------------------------------------------------


def is_list_motif(m: Motif) -> bool:
    """Return True if m structurally looks like a list."""
    cur: Motif = m
    while isinstance(cur, Motif) and len(cur.structure) == 2:
        _, t = cur.structure
        cur = t  # type: ignore[assignment]
    return cur == VOID


def head(m: Motif) -> Motif:
    """Return first element of a CONS pair."""
    if not isinstance(m, Motif) or len(m.structure) != 2:
        raise TypeError("head: motif is not a CONS pair")
    return m.structure[0]


def tail(m: Motif) -> Motif:
    """Return tail of a CONS pair."""
    if not isinstance(m, Motif) or len(m.structure) != 2:
        raise TypeError("tail: motif is not a CONS pair")
    return m.structure[1]
