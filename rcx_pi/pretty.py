# rcx_pi/pretty.py
"""
Pretty-print helpers for Motif.

This does NOT change Motif.__repr__ or any core behavior.
It just gives you a more compact, human-facing rendering.

Usage:

    from rcx_pi.pretty import pretty_motif
    from rcx_pi import μ, VOID, PureEvaluator, num

    m = μ(num(1), num(1))   # roughly (1, 1)
    print(pretty_motif(m))

You can also control depth / width via keyword arguments.
"""

from __future__ import annotations

from typing import Optional

from rcx_pi import μ, VOID, UNIT, motif_to_int, num
from rcx_pi.core.motif import Motif

# Optional: integrate with rcx_pi.meta if available, so we can collapse the
# big TAG_HEADER prefix into a tiny textual label.
try:  # pragma: no cover - meta is optional at import time
    from rcx_pi.meta import TAG_HEADER, classification_label, strip_meta_tag
except Exception:  # pragma: no cover
    TAG_HEADER = None
    classification_label = None
    strip_meta_tag = None  # type: ignore[assignment]


def _is_tag_header(m: Motif) -> bool:
    """Return True if *m* looks like the meta TAG_HEADER.

    We first try direct equality with TAG_HEADER (if imported).
    If that fails or TAG_HEADER is unavailable, we fall back to a structural
    heuristic: a long (>20) pure Peano successor chain starting at VOID.
    """
    if not isinstance(m, Motif):
        return False

    if TAG_HEADER is not None and m == TAG_HEADER:
        return True

    # Fallback heuristic: long Peano chain
    depth = 0
    cur = m
    while isinstance(cur, Motif) and cur.is_successor_pure():
        depth += 1
        cur = cur.head()
    if isinstance(cur, Motif) and cur.is_zero_pure() and depth >= 20:
        return True
    return False


def _is_pure_peano(m: Motif) -> bool:
    """Return True if *m* is a pure Peano succ^n(0) chain."""
    cur = m
    if not isinstance(cur, Motif):
        return False
    while cur.is_successor_pure():
        cur = cur.head()
    return cur.is_zero_pure()


def pretty_motif(
    m: Motif,
    *,
    max_depth: int = 6,
    max_width: int = 6,
    show_meta: bool = True,
) -> str:
    """Render a Motif into a compact, human-oriented string.

    Conventions
    -----------
    * Peano numbers are rendered as ``N:5``.
    * The empty constructor (VOID) is rendered as ``∅``.
    * UNIT is rendered as ``•``.
    * Small tuples of numeric motifs are rendered as ``(a, b, c)``.
    * General motifs are rendered as ``μ[child1, child2, ...]``.
    * If ``show_meta`` is True and the motif looks like
      ``μ(TAG_HEADER, payload)``, we show ``<kind> payload`` instead,
      where ``kind`` is the structural meta classification label
      (\"value\", \"program\", \"mixed\", or \"struct\") if
      :mod:`rcx_pi.meta` is available.

    Parameters
    ----------
    m:
        Motif to pretty-print.
    max_depth:
        Max recursion depth; deeper nodes are rendered as ``…``.
    max_width:
        Max number of children to display per node; extra children collapsed
        into ``…``.
    show_meta:
        Whether to recognize and collapse TAG_HEADER-style meta tags.
    """

    def rec(node: Motif, depth: int) -> str:
        # Depth guard
        if depth > max_depth:
            return "…"

        # Non-motif: fallback to repr
        if not isinstance(node, Motif):
            return repr(node)

        # 1) Recognize meta-tagged motifs: μ(TAG_HEADER, core)
        if (
            show_meta
            and isinstance(node, Motif)
            and len(node.structure) == 2
            and isinstance(node.structure[0], Motif)
            and _is_tag_header(node.structure[0])
        ):
            _header, core = node.structure
            # Derive label from rcx_pi.meta if available
            if classification_label is not None:
                label = classification_label(core)
            else:
                label = "meta"
            inner = rec(core, depth + 1)
            return f"<{label}> {inner}"

        # 2) Pure Peano number?
        n = motif_to_int(node)
        if n is not None:
            return f"N:{n}"

        # 3) Special atoms
        if node.is_zero_pure():
            return "∅"
        if node == UNIT:
            return "•"

        # 4) General structural motif
        children = list(node.structure)
        if not children:
            # Should not normally happen (VOID already handled),
            # but keep a minimal fallback.
            return "μ[]"

        items: list[str] = []
        for idx, child in enumerate(children):
            if idx >= max_width:
                items.append("…")
                break
            if isinstance(child, Motif):
                items.append(rec(child, depth + 1))
            else:
                items.append(repr(child))

        # If the children all look like "N:x" and arity is small,
        # display as a tuple: (x, y, z)
        if items and all(s.startswith("N:") for s in items if s != "…") and len(items) <= 3:
            vals = ", ".join(s[2:] for s in items)
            return f"({vals})"

        inner = ", ".join(items)
        return f"μ[{inner}]"

    return rec(m, 0)