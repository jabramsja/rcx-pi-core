# rcx_pi/meta.py

"""
RCX-π META LAYER
================

Tiny structural self-awareness helpers built on top of the pure engine.

We do NOT rely on engine-side CLASSIFY/VALUE_TAG/etc anymore.
Instead:

  • classify_motif(m)       -> μ(TAG_HEADER, core_motif)
  • classification_label(m) -> "value" | "program" | "mixed" | "struct"

All classification is done by *structural inspection*:

  - "value"   = scalar Peano number or flat tuple-of-scalars, no program markers
  - "program" = has closure / projection / activation markers, no data numbers
  - "mixed"   = both data numbers and program markers present
  - "struct"  = none of the above (generic structural / nested numeric junk)
"""

from .core.motif import Motif, μ
from .utils.compression import compression
from .reduction.pattern_matching import (
    is_closure,
    is_proj,
    is_act,
)

# Single meta tag header: just a deep marker from the compression helper.
TAG_HEADER = compression.marker(25)


def strip_meta_tag(m: Motif) -> Motif:
    """
    Remove one or more layers of meta-tag of the form μ(TAG_HEADER, inner).
    If it's not tagged, return as-is.
    """
    cur = m
    while (
        isinstance(cur, Motif)
        and len(cur.structure) == 2
        and isinstance(cur.structure[0], Motif)
        and cur.structure[0].structurally_equal(TAG_HEADER)
    ):
        cur = cur.structure[1]
    return cur


# ---------- helpers to detect "program-ness" and "value-ness" ----------


def _has_program_marker(m: Motif) -> bool:
    """
    True if the motif contains any *well-formed* closure / activation / projection.

    This uses the shape-aware predicates from pattern_matching so that
    plain Peano numbers that happen to be k-deep are not misclassified
    as closures just because of depth.
    """
    if not isinstance(m, Motif):
        return False

    # Program-shaped at this node?
    if is_closure(m) or is_act(m) or is_proj(m):
        return True

    # Recurse into children
    return any(isinstance(c, Motif) and _has_program_marker(c)
               for c in m.structure)


def _contains_data_number(m: Motif, inside_prog: bool = False) -> bool:
    """
    True if the motif contains any Peano number that should be treated as *data*.

    Numbers that occur *inside* closures / projections / activations are treated
    as scaffolding, not data, so they don't count toward "value-ness".
    """
    if not isinstance(m, Motif):
        return False

    # If this node itself is a program form, recurse into its children
    # with inside_prog=True so their numbers are treated as scaffolding.
    if is_closure(m) or is_act(m) or is_proj(m):
        return any(
            isinstance(c, Motif) and _contains_data_number(c, inside_prog=True)
            for c in m.structure
        )

    # If this node is a pure Peano number and we're *not* inside a program,
    # it counts as a data value.
    if not inside_prog and (m.is_number_pure() or m.is_zero_pure()):
        return True

    # Otherwise recurse structurally, preserving the inside_prog flag.
    return any(
        isinstance(c, Motif) and _contains_data_number(c, inside_prog)
        for c in m.structure
    )


def _is_pure_data_value(m: Motif) -> bool:
    """
    'Pure data value' = either:
      - scalar Peano number, or
      - flat tuple of scalar Peano numbers,
    with NO program markers anywhere.

    Nested numeric structures like ((0,1),(2,0)) are *not* considered
    a single data value; they fall into 'struct'.
    """
    if not isinstance(m, Motif):
        return False

    # Any program markers at all -> not a pure data value
    if _has_program_marker(m):
        return False

    # Scalar number: Peano chain or zero
    if m.is_number_pure() or m.is_zero_pure():
        return True

    # Flat tuple of scalars: each direct child is a scalar Peano number
    if not m.structure:
        return False

    for c in m.structure:
        if not isinstance(c, Motif):
            return False
        # Child itself must be scalar, not composite
        if not (c.is_number_pure() or c.is_zero_pure()):
            return False

    return True


def _classify_core(m: Motif) -> str:
    """
    Core structural classification *without* any meta-tag wrapper.

    Returns one of: "value", "program", "mixed", "struct".

      has_prog       = contains any closure/projection/activation
      has_data       = contains any Peano *data* subtree (outside programs)
      is_pure_value  = scalar or flat tuple-of-scalars, no program markers

      value   = is_pure_value and not has_prog
      program = has_prog and not has_data
      mixed   = has_prog and has_data
      struct  = everything else
    """
    if not isinstance(m, Motif):
        return "struct"

    has_prog = _has_program_marker(m)
    has_data = _contains_data_number(m, inside_prog=False)
    is_pure_value = _is_pure_data_value(m)

    if is_pure_value and not has_prog:
        return "value"

    if has_prog and not has_data:
        return "program"

    if has_prog and has_data:
        return "mixed"

    return "struct"


# ---------- public API used by test_meta.py ----------


def classify_motif(m: Motif) -> Motif:
    """
    Wrap a motif with a structural meta-tag:

        input:  m
        output: μ(TAG_HEADER, core_motif)

    This is deliberately simple: we don't bake the label into the motif,
    we just tag it for "meta-space" and let classification_label()
    compute the label by structural inspection.
    """
    core = strip_meta_tag(m)
    return μ(TAG_HEADER, core)


def classification_label(tagged: Motif) -> str:
    """
    Inspect a (possibly tagged) motif and return a human-readable label:

        "value", "program", "mixed", "struct"
    """
    core = strip_meta_tag(tagged)
    return _classify_core(core)
