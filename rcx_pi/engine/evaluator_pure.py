# rcx_pi/engine/evaluator_pure.py

from ..core.motif import Motif
from ..reduction.rules_pure import PureRules


class PureEvaluator:
    """
    Minimal RCX-π evaluator.

    - Pure structural reduction
    - Optional step-by-step tracing
    """

    def __init__(self, trace: bool = False, max_steps: int = 200):
        self.rules = PureRules()
        self.trace = trace
        self.max_steps = max_steps

    def step(self, m: Motif) -> Motif:
        """Single reduction step."""
        return self.rules.reduce(m)

    def reduce(self, m: Motif, limit: int | None = None) -> Motif:
        """
        Reduce motif to (approximate) normal form.

        - Stops when a fixed point is reached (no more change), or
        - when the step limit is hit.
        """
        cur = m
        step_limit = limit if limit is not None else self.max_steps

        for i in range(step_limit):
            nxt = self.step(cur)

            if self.trace:
                print(f"[{i}] {cur}  -->  {nxt}")

            if nxt.structurally_equal(cur):
                # Normal-ish form
                return cur

            cur = nxt

        # Hit limit; return best effort
        return cur