# rcx_pi/programs.py
#
# Small library of "RCX-π programs":
#   - numeric constructor: num(n)
#   - pair/triple construction
#   - higher-level closures built from PROJECTION/CLOSURE/VAR

from .core.motif import Motif, μ, VOID
from .reduction.pattern_matching import PROJECTION, CLOSURE, VAR


# ---------- numeric helpers ----------

def num(n: int) -> Motif:
    """Build Peano number n as nested successors over VOID."""
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


# ---------- basic structural constructors ----------

def make_pair(a: Motif, b: Motif) -> Motif:
    """μ(a, b)"""
    return μ(a, b)


def make_triple(a: Motif, b: Motif, c: Motif) -> Motif:
    """μ(a, b, c)"""
    return μ(a, b, c)


# ---------- pattern variables ----------

def pattern_var(var_id: int) -> Motif:
    """
    Create a pattern variable motif.

    We distinguish variables structurally by using different Peano IDs
    as the second field: μ(VAR, num(var_id)).
    PatternMatcher keys by repr(), so distinct structure = distinct var.
    """
    return μ(VAR, num(var_id))


# ---------- projection-built closures ----------

def swap_xy_closure() -> Motif:
    """
    Closure that swaps a pair:

        input motif shape:  μ(x, y)
        output motif:       μ(y, x)

    Encoded as:

        μ(CLOSURE,
          μ(PROJECTION,
            μ(x, y),
            μ(y, x)))
    """
    x = pattern_var(1)
    y = pattern_var(2)

    pattern = μ(x, y)
    body    = μ(y, x)

    projection = μ(PROJECTION, pattern, body)
    return μ(CLOSURE, projection)


def dup_x_closure() -> Motif:
    """
    Closure that duplicates the first element of a pair:

        input:  μ(x, y)
        output: μ(x, x)
    """
    x = pattern_var(1)
    y = pattern_var(2)

    pattern = μ(x, y)
    body    = μ(x, x)

    projection = μ(PROJECTION, pattern, body)
    return μ(CLOSURE, projection)


def rotate_xyz_closure() -> Motif:
    """
    Closure that rotates a triple left:

        input:  μ(x, y, z)
        output: μ(y, z, x)
    """
    x = pattern_var(1)
    y = pattern_var(2)
    z = pattern_var(3)

    pattern = μ(x, y, z)
    body    = μ(y, z, x)

    projection = μ(PROJECTION, pattern, body)
    return μ(CLOSURE, projection)