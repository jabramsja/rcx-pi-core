"""
rcx_pi.meta

Structural meta-classifier for Motif trees.

The goal here is *not* to bake meta-information into Motif itself,
but to provide an **external, structural lens** that can:

  • tag motifs with a recognizable prefix (TAG_HEADER),
  • classify a motif into one of a few coarse "kinds":
        - "value"   : pure data value (Peano, simple tuple of values)
        - "program" : pure program / closure / pattern
        - "mixed"   : program+data entangled (activation, etc.)
        - "struct"  : generic structural motif, not a pure value/program

The tagging form is:

    tagged = μ(TAG_HEADER, core_motif)

where TAG_HEADER is a fixed Peano "tube" chosen to be
very unlikely to occur naturally in user-constructed motifs,
so we can recognize it reliably from the outside.

This is deliberately **external**: Motif itself stays oblivious.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

from rcx_pi import μ, VOID, UNIT
from rcx_pi.core.motif import Motif


MetaKind = Literal["value", "program", "mixed", "struct"]

__all__ = [
    "TAG_HEADER",
    "classify_motif",
    "classification_label",
    "strip_meta_tag",
    "MetaKind",
]

# ---------------------------------------------------------------------------
# Tag header construction
# ---------------------------------------------------------------------------

# We use a fairly deep Peano chain as the meta-header:
#   TAG_HEADER = succ^27(VOID)
#
# This is:
#   - recognizable,
#   - structurally inert,
#   - extremely unlikely to collide with "normal" user data.
#
# We build it explicitly so it is stable across runs.
_TAG_HEADER_DEPTH = 27


def _build_tag_header() -> Motif:
    m = VOID
    for _ in range(_TAG_HEADER_DEPTH):
        m = μ(m)
    return m


TAG_HEADER: Motif = _build_tag_header()

# ---------------------------------------------------------------------------
# Simple utilities: walking and helpers
# ---------------------------------------------------------------------------


def _is_pure_peano(m: Motif) -> bool:
    """
    True iff `m` is a pure Peano succ-chain: succ^n(0).
    """
    cur = m
    if not isinstance(cur, Motif):
        return False
    while cur.is_successor_pure():
        cur = cur.head()
    return cur.is_zero_pure()


def _contains_unit(m: Motif) -> bool:
    """
    True iff UNIT appears anywhere structurally inside `m`.
    """
    stack = [m]
    while stack:
        node = stack.pop()
        if node == UNIT:
            return True
        if isinstance(node, Motif):
            stack.extend(node.structure)
    return False


def _contains_void(m: Motif) -> bool:
    """
    True iff VOID appears anywhere structurally inside `m`.
    """
    stack = [m]
    while stack:
        node = stack.pop()
        if node.is_zero_pure():
            return True
        if isinstance(node, Motif):
            stack.extend(node.structure)
    return False


def _contains_data_number(m: Motif) -> bool:
    """
    True iff *some* sub-motif is a pure Peano number.
    """
    stack = [m]
    while stack:
        node = stack.pop()
        if isinstance(node, Motif) and _is_pure_peano(node):
            return True
        if isinstance(node, Motif):
            stack.extend(node.structure)
    return False


def _is_flat_tuple_of_values(m: Motif) -> bool:
    """
    Heuristic: treat μ(v1, v2, ..., vn) as a "value" tuple iff
    each vi is a pure Peano value.
    """
    if not isinstance(m, Motif):
        return False

    # degenerate case: single value
    if len(m.structure) == 1 and _is_pure_peano(m.structure[0]):
        return True

    if not m.structure:
        return False

    for child in m.structure:
        if not (isinstance(child, Motif) and _is_pure_peano(child)):
            return False
    return True


def _is_pure_data_value(m: Motif) -> bool:
    """
    "Pure value" means:

      • A pure Peano number, e.g. succ^n(0)
      • A *flat* tuple of pure values, e.g. μ(0, 1, 2)
        (All children are pure Peano.)

    Nested numeric structures like ((0,1),(2,0)) are not considered
    a single data value; they fall into "struct".
    """
    if _is_pure_peano(m):
        return True
    if _is_flat_tuple_of_values(m):
        return True
    return False


def _has_program_marker(m: Motif) -> bool:
    """
    Heuristic: detect "program-like" motifs.

    Since we don't want Motif to carry semantic tags internally, we
    use a few crude structural cues that are true for our RCX-π core
    "programs" but very unlikely for plain data:

      • Presence of UNIT in non-trivial positions.
      • Higher-arity nodes (arity >= 2) that combine VOID/UNIT with
        non-Peano subtrees.
    """
    stack = [m]
    while stack:
        node = stack.pop()
        if not isinstance(node, Motif):
            continue

        # UNIT anywhere is a program-ish smell (since our pure data examples
        # for numbers + tuples do not use UNIT).
        if node == UNIT:
            return True

        children = node.structure

        # Arity >= 2: if we mix "weird" and "value" shapes, treat as
        # program-ish
        if len(children) >= 2:
            has_value_like = any(
                isinstance(
                    ch,
                    Motif) and _is_pure_data_value(ch) for ch in children)
            has_nonvalue_like = any(
                isinstance(
                    ch,
                    Motif) and not _is_pure_data_value(ch) for ch in children)
            if has_value_like and has_nonvalue_like:
                return True

        stack.extend(children)

    return False


# ---------------------------------------------------------------------------
# Core classification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetaInfo:
    kind: MetaKind
    core: Motif


def _classify_core(m: Motif) -> MetaKind:
    """
    Internal classifier returning one of: "value", "program", "mixed", "struct".
    Heuristics are deliberately coarse but stable:

      • value
          Pure Peano or flat tuple of Peano values.
      • program
          Program-like (UNIT / VOID in "code-ish" positions)
          but NOT clearly mixed with overt data values.
      • mixed
          Program-like AND clearly entangled with value-like subtrees,
          e.g. activation(swap_closure, numeric_pair).
      • struct
          Everything else: general structural motifs.
    """
    # First: pure value?
    if _is_pure_data_value(m):
        return "value"

    # Program-ish markers present?
    has_program = _has_program_marker(m)
    has_value = _contains_data_number(m)

    if has_program and has_value:
        return "mixed"
    if has_program and not has_value:
        return "program"

    # Otherwise it's just "some structure" – neither pure program nor pure
    # value
    return "struct"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_motif(m: Motif) -> Motif:
    """
    Tag `m` with the meta-header:

        tagged = μ(TAG_HEADER, core_motif)

    where `core_motif` is the original motif.

    This is intentionally *lossless*: you can strip the tag via
    `strip_meta_tag` and recover `core_motif` exactly.
    """
    if not isinstance(m, Motif):
        raise TypeError("classify_motif expects a Motif")

    core_motif = m
    return μ(TAG_HEADER, core_motif)


def classification_label(m: Motif) -> MetaKind:
    """
    Structural classification label for `m`.

    If `m` is already tagged as μ(TAG_HEADER, core), we classify `core`.
    Otherwise, we classify `m` directly.
    """
    core = strip_meta_tag(m)
    return _classify_core(core)


def strip_meta_tag(m: Motif) -> Motif:
    """
    If `m` is of the form μ(TAG_HEADER, core), return `core`.
    Otherwise return `m` unchanged.
    """
    if not isinstance(m, Motif):
        raise TypeError("strip_meta_tag expects a Motif")

    if len(m.structure) == 2:
        head, tail = m.structure
        if isinstance(head, Motif) and head == TAG_HEADER:
            # tagged form: μ(TAG_HEADER, core)
            return tail

    return m
