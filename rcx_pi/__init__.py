# rcx_pi/__init__.py
"""
RCX-π public API surface — stable, test-ready.
"""

# ---------------------------------------------------------------------------
# Core Motif types
# ---------------------------------------------------------------------------
from .core.motif import Motif, μ, VOID, UNIT

# ---------------------------------------------------------------------------
# Evaluator (primary: engine/evaluator_pure.py)
# ---------------------------------------------------------------------------
_DefaultEvaluator = None

try:
    from .engine.evaluator_pure import PureEvaluator
    _DefaultEvaluator = PureEvaluator
except Exception:
    pass

def new_evaluator():
    if _DefaultEvaluator is None:
        raise RuntimeError("PureEvaluator not found. Expected at rcx_pi/engine/evaluator_pure.py")
    return _DefaultEvaluator()

# expose clearly
PureEvaluator = _DefaultEvaluator


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------
def num(n: int) -> Motif:
    if n < 0: raise ValueError("num only supports n>=0")
    m = VOID
    for _ in range(n): m = m.succ()
    return m

def succ(m: Motif) -> Motif: return m.succ()
def pred(m: Motif): return m.head() if m.is_successor_pure() else None

def motif_to_int(m: Motif) -> int | None:
    if not isinstance(m, Motif): return None
    if m.is_zero_pure(): return 0
    n=0; cur=m
    while cur.is_successor_pure(): n+=1; cur=cur.head()
    return n if cur.is_zero_pure() else None

def add(a: Motif,b: Motif)->Motif:
    va,vb = motif_to_int(a),motif_to_int(b)
    if va is None or vb is None: raise TypeError("add expects Peano motifs")
    return num(va+vb)

def zero() -> Motif:
    return VOID


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------
from .listutils import (
    list_from_py, py_from_list, NIL, CONS, is_list_motif, head, tail
)

# ---------------------------------------------------------------------------
# Pretty + Meta
# ---------------------------------------------------------------------------
from .pretty import pretty_motif
from .meta   import classify_motif

# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------
from .programs import (
    swap_xy_closure, dup_x_closure, rotate_xyz_closure,
    swap_ends_xyz_closure, activate
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
    "Motif","μ","VOID","UNIT",
    "PureEvaluator","new_evaluator",

    # numbers
    "num","succ","pred","add","motif_to_int","zero",

    # lists
    "list_from_py","py_from_list","NIL","CONS","is_list_motif","head","tail",

    # ui
    "pretty_motif","classify_motif",

    # programs
    "swap_xy_closure","dup_x_closure","rotate_xyz_closure",
    "swap_ends_xyz_closure","activate",
]