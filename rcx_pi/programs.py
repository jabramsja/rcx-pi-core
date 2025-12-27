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