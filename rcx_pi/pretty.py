# rcx_pi/pretty.py
"""
Pretty-print helpers for Motif.

This does NOT change Motif.__repr__ or any core behavior.
It just gives you a more compact, human-facing rendering.

Usage:

    from rcx_pi.pretty import pretty_motif
    from rcx_pi import μ, VOID, PureEvaluator

    m = μ(μ(VOID), μ(VOID))   # roughly (1,1)
    print(pretty_motif(m))

You can also control depth / width:

    pretty_motif(m, max_depth=4, max_width=3)
"""

from __future__ import annotations
from typing import Optional

from .core.motif import Motif, μ, VOID


def _motif_to_int(m: Motif) -> Optional[int]:
    """Best-effort Peano decoder: VOID = 0, succ^n(VOID) = n."""
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


def pretty_motif(
    m: Motif,
    max_depth: int = 4,
    max_width: int = 4,
) -> str:
    """
    Render a Motif in a compact, semi-structured way.

    - Peano numbers: `N:5`
    - Pairs/triples of numbers: `(2, 5)` or `(2, 5, 7)`
    - Deeper trees: truncated with `…` after `max_width` children
    - Nested levels beyond `max_depth`: shown as `…`
    """

    def rec(x: Motif, depth: int) -> str:
        if not isinstance(x, Motif):
            return repr(x)

        # depth limiter
        if depth > max_depth:
            return "…"

        # Peano number?
        n = _motif_to_int(x)
        if n is not None:
            return f"N:{n}"

        # structural node
        if not x.structure:
            # non-VOID empty structure should be rare
            if x.is_zero_pure():
                return "N:0"
            return "μ()"

        # treat up to max_width children
        items = []
        for i, child in enumerate(x.structure):
            if i >= max_width:
                items.append("…")
                break
            if isinstance(child, Motif):
                items.append(rec(child, depth + 1))
            else:
                items.append(repr(child))

        # if this is a "tuple-like" motif and children are all N:?
        # you get a nice `(a, b, c)` style for small arities
        if all(s.startswith("N:") for s in items) and len(items) <= 3:
            vals = ", ".join(s[2:] for s in items)  # strip "N:"
            return f"({vals})"

        inner = ", ".join(items)
        return f"μ[{inner}]"

    return rec(m, 0)