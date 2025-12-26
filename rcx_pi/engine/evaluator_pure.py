# rcx_pi/engine/evaluator_pure.py

from ..core.motif import Motif
from ..reduction.rules_pure import PureRules


class PureEvaluator:
    """
    Minimal evaluator for RCX-π
    Uses PureRules for single-step structural reduction.
    """

    def __init__(self, trace=False):
        self.rules = PureRules()
        self.trace = trace   # optional debug print-steps

    def step(self, m: Motif) -> Motif:
        """Apply one reduction step using PureRules."""
        r = self.rules.reduce(m)
        return r

    def reduce(self, m: Motif, limit=200) -> Motif:
        """Reduce `m` until normal form or iteration cap."""
        cur = m

        for i in range(limit):
            nxt = self.step(cur)

            # debugging view
            if self.trace:
                print(f"[{i}]  {cur}  -->  {nxt}")

            # no further progress -> normal form reached
            if nxt.structurally_equal(cur):
                return cur

            cur = nxt

        return cur   # stopped due to limit

    # -------------------------------------------------
    # Compatibility API so old scripts also work
    # -------------------------------------------------

    def evaluate(self, m: Motif, max_steps=200) -> Motif:
        """Alias for reduce()"""
        return self.reduce(m, limit=max_steps)