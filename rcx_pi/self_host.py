# rcx_pi/self_host.py
#
# Structural invariants for "self-hostable" RCX-π motifs.
#
# The point of this module is NOT to implement full self-hosting yet.
# Instead, it defines *filters* and *predicates* that say:
#
#   - "This motif is a pure Peano value."
#   - "This motif is structurally pure (no Python scalars)."
#   - "This motif is meta-tagged (has an external classifier tag)."
#   - "This motif would be allowed inside a future self-hosted core."
#
# That gives us a place where "self-hosting" has a *shape* in the codebase
# without over-claiming about what already works.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .core.motif import Motif


# ---------------------------------------------------------------------
# Basic structural helpers
# ---------------------------------------------------------------------


def _motif_to_int(m: Motif) -> Optional[int]:
    """
    Local, minimal copy of the Peano-decoder logic.

    We deliberately *do not* import motif_to_int from rcx_pi.__init__
    to avoid subtle import ordering / circular issues. This is the same
    structural rule: a pure Peano number is either:

        0:  VOID  (is_zero_pure())
        n:  nested successors over 0 (is_successor_pure() / head())

    Returns:
        int if m is a pure Peano number, otherwise None.
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

    if cur.is_zero_pure():
        return count
    return None


def is_pure_peano(m: Motif) -> bool:
    """
    True iff m is a pure Peano number structurally (no tags, no extras).

    This is the core "pure value" invariant for self-hosting: numbers are
    bare μ-chains over zero, nothing else.
    """
    return _motif_to_int(m) is not None


def is_structurally_pure(m: Motif) -> bool:
    """
    True iff the entire motif tree is built only out of Motif nodes.

    i.e. no Python ints, strings, dicts, etc. inside the structure.

    RCX-π already *should* maintain this, but this predicate makes that
    expectation explicit and testable.
    """
    if not isinstance(m, Motif):
        return False

    for child in m.structure:
        if not is_structurally_pure(child):
            return False
    return True


# ---------------------------------------------------------------------
# Meta-tag detection
# ---------------------------------------------------------------------

# In meta.py we tag motifs as:
#
#   tagged = μ(TAG_PEANO, original_motif)
#
# where TAG_PEANO is some large Peano number used only as a classifier
# marker. For self-hosting, we want to *exclude* such meta-tagged forms
# from the inner core.
#
# We don't need to know the exact tag values; we just treat "big" Peano
# heads as meta-tags.

TAG_MIN = 20  # heuristic: anything >= 20 is "probably a meta-tag"


def is_meta_tagged(m: Motif) -> bool:
    """
    True iff the motif looks like a meta-tagged wrapper:

        μ(TAG_PEANO, inner)

    where TAG_PEANO is a (structurally pure) Peano number >= TAG_MIN.
    """
    if not isinstance(m, Motif):
        return False

    if len(m.structure) != 2:
        return False

    tag, _inner = m.structure
    n = _motif_to_int(tag)
    return n is not None and n >= TAG_MIN


# ---------------------------------------------------------------------
# Self-hosting profile & invariants
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class SelfHostProfile:
    """
    Declarative knobs for what the "self-hostable" sub-language allows.

    For now this is intentionally minimal and conservative. In the
    future, we might extend this with more fine-grained restrictions
    (e.g. allowed closure shapes, maximum depth, etc.).
    """

    allow_meta_tagged: bool = False
    allow_mixed_struct: bool = True  # e.g. (value, value) pairs are OK


DEFAULT_PROFILE = SelfHostProfile()


def is_self_host_value(
        m: Motif,
        profile: SelfHostProfile = DEFAULT_PROFILE) -> bool:
    """
    A value that is allowed in the self-hosted core.

    For v1, this is simply "a pure Peano number" with no extra checks.
    """
    if not is_structurally_pure(m):
        return False
    if not is_pure_peano(m):
        return False
    if not profile.allow_meta_tagged and is_meta_tagged(m):
        return False
    return True


def is_self_host_struct(
        m: Motif,
        profile: SelfHostProfile = DEFAULT_PROFILE) -> bool:
    """
    A structurally pure motif that can live in the self-hosted core
    (values, closures, pairs, triples, etc.).

    This is intentionally *looser* than is_self_host_value: it just
    enforces "structural purity" and the meta-tag rule.
    """
    if not is_structurally_pure(m):
        return False
    if not profile.allow_meta_tagged and is_meta_tagged(m):
        return False
    return True


def is_self_host_safe(
        m: Motif,
        profile: SelfHostProfile = DEFAULT_PROFILE) -> bool:
    """
    Top-level guard: True iff m is structurally acceptable to hand off
    to a future self-hosting RCX-π kernel.

    Right now this is just an alias for is_self_host_struct, but it
    gives us a named concept to hang future constraints on.
    """
    return is_self_host_struct(m, profile=profile)
