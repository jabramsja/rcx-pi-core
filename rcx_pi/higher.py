# rcx_pi/higher.py
"""
Higher-level helpers on top of pure RCX-π Peano numbers.

These are convenience utilities that stay strictly at the Motif level,
but use Python control flow to *compose* structural operations.

They are stepping stones toward fully structural closures.
"""

from __future__ import annotations
from typing import Iterable, Optional

from .core.motif import Motif
from .engine.evaluator_pure import PureEvaluator
from . import μ, VOID  # rcx_pi/__init__.py exposes these


# ---------- local Peano helpers (no utils dependency) ----------


def num(n: int) -> Motif:
    """Build Peano n as nested successors over VOID."""
    if n < 0:
        raise ValueError("num(n) only defined for n >= 0")
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def motif_to_int(m: Motif) -> Optional[int]:
    """Convert pure Peano motif to int; return None if not pure."""
    if not isinstance(m, Motif):
        return None

    if m.is_zero_pure():
        return 0

    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()

    if cur.is_zero_pure():
        return count
    return None


# ---------- higher-level helpers ----------


def peano_list(ints: Iterable[int]) -> Motif:
    """
    Encode a Python iterable of ints into a Motif "tuple" μ(a, b, c, ...).

    This is just a structural convenience, not a canonical list encoding.
    """
    motifs = [num(i) for i in ints]
    return μ(*motifs)


def peano_factorial(n_val: int, ev: Optional[PureEvaluator] = None) -> Motif:
    """
    Compute n! using Motif.mult and the pure evaluator.

    This uses:
        acc = 1
        for k in 2..n:
            acc = ev.reduce(acc.mult(k))

    It stays entirely in motif-space, but control structure is Python.
    """
    if n_val < 0:
        raise ValueError("factorial undefined for negative n")

    if ev is None:
        ev = PureEvaluator()

    # 0! = 1
    acc = num(1)
    for k in range(2, n_val + 1):
        acc = ev.reduce(acc.mult(num(k)))
    return acc


def peano_sum(ints: Iterable[int], ev: Optional[PureEvaluator] = None) -> Motif:
    """
    Sum a list of Python ints as Peano motifs.

    Equivalent to fold(add, 0, ints).
    """
    if ev is None:
        ev = PureEvaluator()

    acc = num(0)
    for i in ints:
        acc = ev.reduce(acc.add(num(i)))
    return acc


def peano_map_increment(
    ints: Iterable[int],
    delta: int = 1,
    ev: Optional[PureEvaluator] = None,
) -> Motif:
    """
    Map (+delta) over a list of ints and return a "tuple" motif μ(...).

    Example:
        map_increment([2,5,7], 1) -> μ(N:3, N:6, N:8) as motif.
    """
    if delta < 0:
        # keeping it honest: no subtraction primitive yet
        raise ValueError("negative delta not supported in pure Peano helpers")

    if ev is None:
        ev = PureEvaluator()

    out = []
    for i in ints:
        base = num(i)
        inc = num(delta)
        res = ev.reduce(base.add(inc))
        out.append(res)

    return μ(*out)
