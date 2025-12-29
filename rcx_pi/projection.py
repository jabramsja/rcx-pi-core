# rcx_pi/projection.py
"""
RCX-π structural projection + pattern layer.

This exposes the same marker / pattern encodings that the PureEvaluator
already knows how to interpret (via its rules), but as a reusable API.

Shapes (all are plain μ(...) motifs):

    CLOSURE_MARKER     = μ(μ(μ(μ(μ()))))
    ACTIVATION_MARKER  = μ(μ(μ(μ(μ(μ())))))
    PROJECTION_MARKER  = μ(μ(μ(μ(μ(μ(μ()))))))
    PATTERN_VAR_MARKER = μ(μ(μ(μ(μ(μ(μ(μ())))))))

Pattern variables are encoded as:

    var(id) = μ(PATTERN_VAR_MARKER, id)

Closures:

    projection   = μ(PROJECTION_MARKER, pattern, body)
    closure      = μ(CLOSURE_MARKER,   projection)
    activation   = μ(ACTIVATION_MARKER, closure, arg)

The evaluator is responsible for giving these structural nodes semantics.
"""

from __future__ import annotations

from rcx_pi.core.motif import Motif, μ, VOID


# ---------- markers (must match evaluator rules) ----------

CLOSURE_MARKER     = μ(μ(μ(μ(μ()))))              # 4-deep
ACTIVATION_MARKER  = μ(μ(μ(μ(μ(μ())))))           # 5-deep
PROJECTION_MARKER  = μ(μ(μ(μ(μ(μ(μ()))))))        # 6-deep
PATTERN_VAR_MARKER = μ(μ(μ(μ(μ(μ(μ(μ())))))))     # 7-deep


# ---------- pattern variables ----------

def var(id_motif: Motif) -> Motif:
    """
    Generic pattern variable constructor.

        id_motif = VOID      => "x"
        id_motif = μ(VOID)   => "y"
        etc.
    """
    return μ(PATTERN_VAR_MARKER, id_motif)


def var_x() -> Motif:
    """Pattern variable x (ID = VOID)."""
    return μ(PATTERN_VAR_MARKER, VOID)


def var_y() -> Motif:
    """Pattern variable y (ID = succ(VOID))."""
    return μ(PATTERN_VAR_MARKER, μ(VOID))


# ---------- projections & closures ----------

def make_projection(pattern: Motif, body: Motif) -> Motif:
    """
    Build a PROJECTION node:

        PROJECTION_MARKER, pattern, body
    """
    return μ(PROJECTION_MARKER, pattern, body)


def make_projection_closure(pattern: Motif, body: Motif) -> Motif:
    """
    Build a closure that captures a single projection:

        projection = μ(PROJECTION_MARKER, pattern, body)
        closure    = μ(CLOSURE_MARKER,   projection)
    """
    proj = make_projection(pattern, body)
    return μ(CLOSURE_MARKER, proj)


def closure_from_projection(projection: Motif) -> Motif:
    """
    Wrap an existing projection motif as a closure:

        closure = μ(CLOSURE_MARKER, projection)
    """
    return μ(CLOSURE_MARKER, projection)


def activate(func: Motif, arg: Motif) -> Motif:
    """
    Structural activation wrapper:

        ACTIVATE(func, arg) = μ(ACTIVATION_MARKER, func, arg)

    The evaluator's reduce(...) knows how to interpret this when `func`
    is a projection-style closure.
    """
    return μ(ACTIVATION_MARKER, func, arg)