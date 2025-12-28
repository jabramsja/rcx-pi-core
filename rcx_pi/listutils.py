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
from typing import Any, Optional

from rcx_pi.core.motif import Motif, μ, VOID


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
        if isinstance(item, int):
            item = num(item)
        elif not isinstance(item, Motif):
            raise TypeError(f"list_from_py: cannot embed {item!r} directly")
        m = CONS(item, m)
    return m


def py_from_list(m: Motif) -> Optional[list[Any]]:
    """
    Attempt to convert a motif list back to a Python list.

    Returns None if the structure is not a pure list.

    Numbers are decoded using a local Peano recognizer, everything
    else is returned as the raw Motif.
    """
    out: list[Any] = []
    cur: Motif = m

    while isinstance(cur, Motif) and len(cur.structure) == 2:
        h, t = cur.structure

        n = _motif_to_int_local(h)
        out.append(n if n is not None else h)

        cur = t  # type: ignore[assignment]

    return out if cur == VOID else None


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