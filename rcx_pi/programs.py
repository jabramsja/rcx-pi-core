# rcx_pi/programs.py
"""
RCX-π structural programs and helpers.

All of these are *pure motifs* built from:
  - Motif / μ / VOID
  - PROJECTION / CLOSURE / ACTIVATION / VAR markers

Exposed:
  - num(n)                       : Peano number builder
  - activate(closure, arg)       : wrap as ACTIVATION motif

  - swap_xy_closure()            : (x, y)   -> (y, x)
  - dup_x_closure()              : (x, y)   -> (x, x)
  - rotate_xyz_closure()         : (x, y, z)-> (y, z, x)
  - swap_ends_xyz_closure()      : (x, y, z)-> (z, y, x)
"""

from .core.motif import Motif, μ, VOID
from .reduction.pattern_matching import (
    PROJECTION,
    CLOSURE,
    ACTIVATION,
    VAR,
)
# Program algebra tags & helpers
# ------------------------------
#
# We keep this extremely small and structural:
# - PROGRAM_TAG marks "this motif is a program block"
# - SEQ_TAG marks "sequence" of two program blocks
#
# Representation:
#   wrap_program(body) := μ(PROGRAM_TAG, body)
#   seq(p, q)          := μ(SEQ_TAG, wrap_program(p), wrap_program(q))

from rcx_pi.core.motif import Motif
from rcx_pi import μ, VOID

# A dedicated tag motif for "program block".
PROGRAM_TAG: Motif = μ(VOID)          # μ(μ())
# A dedicated tag motif for "sequence of programs".
SEQ_TAG: Motif = μ(VOID, VOID)        # μ(μ(), μ())

def wrap_program(body: Motif) -> Motif:
    """
    Wrap an arbitrary motif as a 'program block':
        P ↦ μ(PROGRAM_TAG, P)

    This lets the meta layer and pretty-printer recognize
    'this is intended as a program' without Python-side magic.
    """
    if not isinstance(body, Motif):
        raise TypeError(f"wrap_program expects Motif, got {type(body)}")
    return μ(PROGRAM_TAG, body)


def is_program_block(m: Motif) -> bool:
    """
    Returns True if m looks like μ(PROGRAM_TAG, body).
    """
    if not isinstance(m, Motif):
        return False
    if len(m.structure) != 2:
        return False
    tag, _ = m.structure
    return tag == PROGRAM_TAG


def unwrap_program(m: Motif) -> Motif:
    """
    Inverse of wrap_program, for motifs of the form μ(PROGRAM_TAG, body).
    """
    if not is_program_block(m):
        raise ValueError(f"Not a program block: {m!r}")
    return m.structure[1]


def seq(p: Motif, q: Motif) -> Motif:
    """
    Build a 'sequence' program structurally:
        seq(P, Q) := μ(SEQ_TAG, wrap_program(P), wrap_program(Q))

    Semantics (high level, not enforced here):
        given input x, seq(P, Q) should act like Q(P(x)).

    For now this is just a structural constructor; evaluation
    semantics can be layered in PureEvaluator later.
    """
    if not isinstance(p, Motif) or not isinstance(q, Motif):
        raise TypeError("seq expects Motif arguments")
    return μ(SEQ_TAG, wrap_program(p), wrap_program(q))
# ---------- basic helpers ----------

def num(n: int) -> Motif:
    """
    Build Peano n as nested successors over VOID:

        0 -> VOID
        1 -> succ(VOID)
        2 -> succ(succ(VOID))
        ...
    """
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def activate(closure: Motif, arg: Motif) -> Motif:
    """
    Structural application:

        closure(arg)  ~>  μ(ACTIVATION, closure, arg)

    The PureEvaluator + PureRules know how to reduce this.
    """
    return μ(ACTIVATION, closure, arg)


# ---------- tiny structural “programs” via projection ----------

def _triple_vars():
    """
    Convenience: three distinct pattern variables for triple-based programs.
    We only care that they are structurally distinct VAR-headed motifs.
    """
    vx = μ(VAR, VOID)           # x
    vy = μ(VAR, μ(VOID))        # y
    vz = μ(VAR, μ(μ(VOID)))     # z
    return vx, vy, vz


def swap_xy_closure() -> Motif:
    """
    Closure for (x, y) -> (y, x).

    Pattern: μ(vx, vy)
    Body:    μ(vy, vx)
    """
    vx = μ(VAR, VOID)           # x
    vy = μ(VAR, μ(VOID))        # y

    pattern = μ(vx, vy)
    body = μ(vy, vx)

    proj = μ(PROJECTION, pattern, body)
    return μ(CLOSURE, proj)


def dup_x_closure() -> Motif:
    """
    Closure for (x, y) -> (x, x).

    Pattern: μ(vx, vy)
    Body:    μ(vx, vx)
    """
    vx = μ(VAR, VOID)           # x
    vy = μ(VAR, μ(VOID))        # y (unused in body)

    pattern = μ(vx, vy)
    body = μ(vx, vx)

    proj = μ(PROJECTION, pattern, body)
    return μ(CLOSURE, proj)


def rotate_xyz_closure() -> Motif:
    """
    Closure for (x, y, z) -> (y, z, x).

    Pattern: μ(vx, vy, vz)
    Body:    μ(vy, vz, vx)
    """
    vx, vy, vz = _triple_vars()

    pattern = μ(vx, vy, vz)
    body = μ(vy, vz, vx)

    proj = μ(PROJECTION, pattern, body)
    return μ(CLOSURE, proj)


def swap_ends_xyz_closure() -> Motif:
    """
    Closure for (x, y, z) -> (z, y, x).

    Pattern: μ(vx, vy, vz)
    Body:    μ(vz, vy, vx)
    """
    vx, vy, vz = _triple_vars()

    pattern = μ(vx, vy, vz)
    body = μ(vz, vy, vx)

    proj = μ(PROJECTION, pattern, body)
    return μ(CLOSURE, proj)