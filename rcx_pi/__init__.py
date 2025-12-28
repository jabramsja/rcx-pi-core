# rcx_pi/__init__.py
"""
RCX-π public API surface — minimal, test-proof, docs-aligned.
"""

from .core.motif import Motif, μ, VOID, UNIT

# Evaluator selection ----------------------------------------------------------
try:
    from .engine.evaluator_pure import PureEvaluator
    _DefaultEvaluator = PureEvaluator
except ImportError:
    try:
        from .evaluator import Evaluator as _DefaultEvaluator  # fallback
    except ImportError:
        _DefaultEvaluator = None


def new_evaluator():
    if _DefaultEvaluator is None:
        raise RuntimeError("PureEvaluator not found. Expected at rcx_pi/engine/evaluator_pure.py")
    return _DefaultEvaluator()


# Numbers ----------------------------------------------------------------------
def num(n: int) -> Motif:
    if n < 0:
        raise ValueError("num only supports n>=0")
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def succ(m: Motif) -> Motif:
    return m.succ()


def pred(m: Motif):
    return m.head() if m.is_successor_pure() else None


def motif_to_int(m: Motif) -> int | None:
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
    va = motif_to_int(a)
    vb = motif_to_int(b)
    if va is None or vb is None:
        raise TypeError("add expects Peano numbers")
    return num(va + vb)


def zero() -> Motif:
    """Return the canonical zero motif (Peano 0)."""
    return VOID


# Lists ------------------------------------------------------------------------
from .listutils import (
    list_from_py,
    py_from_list,
    NIL,
    CONS,
    is_list_motif,
    head,
    tail,
)


# Pretty / Meta ----------------------------------------------------------------
from .pretty import pretty_motif
from .meta import classify_motif


# Programs ---------------------------------------------------------------------
from .programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    swap_ends_xyz_closure,
    reverse_list_closure,
    activate,
)


__all__ = [
    # core
    "Motif",
    "μ",
    "VOID",
    "UNIT",

    # evaluator
    "PureEvaluator",
    "new_evaluator",

    # numbers
    "num",
    "succ",
    "pred",
    "add",
    "motif_to_int",
    "zero",

    # lists
    "list_from_py",
    "py_from_list",
    "NIL",
    "CONS",
    "is_list_motif",
    "head",
    "tail",

    # pretty
    "pretty_motif",

    # meta
    "classify_motif",

    # programs
    "swap_xy_closure",
    "dup_x_closure",
    "rotate_xyz_closure",
    "swap_ends_xyz_closure",
    "reverse_list_closure",
    "activate",
]