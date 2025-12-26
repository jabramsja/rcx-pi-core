# rcx_pi/programs.py
#
# Tiny RCX-π “standard library” of pure structural programs:
#   - swap (x, y) -> (y, x)
#   - dup  (x, y) -> (x, x)
#   - rotate (x, y, z) -> (y, z, x)
#
# All of this is pure μ-structure: no strings, no external env.

from .core.motif import Motif, μ, VOID, UNIT
from .reduction.pattern_matching import PROJECTION, CLOSURE, ACTIVATION


# ---------- local reconstruction of the pattern-var marker ----------

def depth_marker(depth: int) -> Motif:
    """
    Build a unary-depth marker:
        depth 0: VOID           = μ()
        depth 1: μ(VOID)
        depth 2: μ(μ(VOID))
        ...
    """
    m = VOID
    for _ in range(depth):
        m = μ(m)
    return m

# In pattern_matching.py, PATTERN_VAR_MARKER is defined as 7-deep.
# We recreate it structurally here so we don't need to import it.
PATTERN_VAR_MARKER = depth_marker(7)


# ---------- pattern variables (pure, no names) ----------

# We use unary-encoded IDs:
#   X_ID = 0 (VOID)
#   Y_ID = 1 (UNIT)
#   Z_ID = 2 (succ(UNIT))

X_ID = VOID          # 0
Y_ID = UNIT          # 1
Z_ID = UNIT.succ()   # 2

# Pattern-vars are motifs of the form μ(PATTERN_VAR_MARKER, id)
X = μ(PATTERN_VAR_MARKER, X_ID)
Y = μ(PATTERN_VAR_MARKER, Y_ID)
Z = μ(PATTERN_VAR_MARKER, Z_ID)


# ---------- helpers to build RCX-π constructs ----------

def make_projection(pattern: Motif, body: Motif) -> Motif:
    """Build PROJECTION(pattern, body)."""
    return μ(PROJECTION, pattern, body)


def make_closure(pattern: Motif, body: Motif) -> Motif:
    """Build CLOSURE(PROJECTION(pattern, body))."""
    return μ(CLOSURE, make_projection(pattern, body))


def activate(func: Motif, arg: Motif) -> Motif:
    """Build ACTIVATION(func, arg)."""
    return μ(ACTIVATION, func, arg)


# ---------- library “programs” (all pure structure) ----------

def swap_xy_closure() -> Motif:
    """
    (x, y) ↦ (y, x)

    pattern: μ(X, Y)
    body:    μ(Y, X)
    """
    pattern = μ(X, Y)
    body = μ(Y, X)
    return make_closure(pattern, body)


def dup_x_closure() -> Motif:
    """
    (x, y) ↦ (x, x)

    pattern: μ(X, Y)
    body:    μ(X, X)
    """
    pattern = μ(X, Y)
    body = μ(X, X)
    return make_closure(pattern, body)


def rotate_xyz_closure() -> Motif:
    """
    (x, y, z) ↦ (y, z, x)

    pattern: μ(X, Y, Z)
    body:    μ(Y, Z, X)
    """
    pattern = μ(X, Y, Z)
    body = μ(Y, Z, X)
    return make_closure(pattern, body)