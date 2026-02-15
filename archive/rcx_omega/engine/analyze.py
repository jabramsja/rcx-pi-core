"""
RCX-Ω analyzer (staging)

Pure structural analysis over π Motifs.
No mutation, no evaluation, no semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from rcx_pi.core.motif import Motif


@dataclass(frozen=True)
class MotifStats:
    nodes: int
    depth: int


def analyze_motif(x: Motif) -> MotifStats:
    """
    Compute basic structural metrics for a Motif:
    - total node count
    - maximum depth
    """

    def walk(m: Motif) -> Tuple[int, int]:
        # children live in m.structure (tuple)
        if not m.structure:
            return 1, 1

        child_stats = [walk(c) for c in m.structure]
        nodes = 1 + sum(n for n, _ in child_stats)
        depth = 1 + max(d for _, d in child_stats)
        return nodes, depth

    n, d = walk(x)
    return MotifStats(nodes=n, depth=d)
