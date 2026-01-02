# rcx_pi/core/numbers.py
"""
Peano number helpers for RCX-π.

These are separated from rcx_pi.__init__ so that other modules
(api, pretty, tests) can import them without circular imports.
"""

from __future__ import annotations

from .motif import Motif, VOID


def num(n: int) -> Motif:
    """Build Peano number n as a pure successor chain."""
    if n < 0:
        raise ValueError("num only supports n>=0")
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def succ(m: Motif) -> Motif:
    """Successor of a Peano motif."""
    return m.succ()


def pred(m: Motif):
    """Predecessor of a Peano motif, or None for zero / non-successor."""
    return m.head() if m.is_successor_pure() else None


def motif_to_int(m: Motif) -> int | None:
    """
    Interpret a Motif as a Peano integer.

    Returns:
        int  if the motif is a pure successor chain
        None otherwise
    """
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


def add(a: Motif, b: Motif) -> Motif:
    """Peano addition via integer view + reconstruction."""
    va = motif_to_int(a)
    vb = motif_to_int(b)
    if va is None or vb is None:
        raise TypeError("add expects Peano numbers")
    return num(va + vb)


def zero() -> Motif:
    """Canonical zero alias used in tests and examples."""
    return VOID
