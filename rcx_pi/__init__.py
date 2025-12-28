"""
RCX-π public API surface.

This keeps the real engine in submodules, and exposes a small, friendly set
of entry points for demos, REPLs, and examples.
"""

from .core.motif import Motif, μ, VOID, UNIT
from .engine.evaluator_pure import PureEvaluator
from .programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    swap_ends_xyz_closure,
    activate,
)

# ---------------------------------------------------------------------------
# Convenience: Peano <-> int bridge
# ---------------------------------------------------------------------------

def num(n: int) -> "Motif":
    """
    Build Peano n as nested successors over VOID, e.g.

        num(0) = μ()
        num(3) = μ(μ(μ()))
    """
    if n < 0:
        raise ValueError("num(n) only supports n >= 0 for now")

    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def motif_to_int(m: "Motif") -> int | None:
    """
    If m is a pure Peano motif (built from VOID via succ),
    return its integer value, else None.
    """
    if not isinstance(m, Motif):
        return None

    if m.is_zero_pure():
        return 0

    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()

    return count if cur.is_zero_pure() else None


# ---------------------------------------------------------------------------
# Meta & pretty-print helpers
# ---------------------------------------------------------------------------

from .meta import classify_motif
from .pretty import pretty_motif

__all__ = [
    # core
    "Motif",
    "μ",
    "VOID",
    "UNIT",
    "PureEvaluator",

    # basic programs
    "swap_xy_closure",
    "dup_x_closure",
    "rotate_xyz_closure",
    "swap_ends_xyz_closure",
    "activate",

    # helpers
    "num",
    "motif_to_int",

    # meta / pretty
    "classify_motif",
    "pretty_motif",
]