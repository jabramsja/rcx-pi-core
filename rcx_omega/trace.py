"""
RCX-Ω: tracing utilities (staging)

This module adds observability around the frozen RCX-π evaluator
WITHOUT modifying rcx_pi internals.

Principle: Ω wraps; π remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.core.motif import Motif


@dataclass(frozen=True)
class TraceStep:
    i: int
    value: Motif


@dataclass(frozen=True)
class TraceResult:
    result: Motif
    steps: List[TraceStep]


def trace_reduce(
    ev: PureEvaluator,
    x: Motif,
    *,
    max_steps: int = 64,
    step_fn: Optional[Callable[[Motif], Motif]] = None,
) -> TraceResult:
    """
    Reduce `x` using `ev`, capturing intermediate motifs.

    We do NOT assume any internal evaluator step API exists.
    Instead, we repeatedly call `ev.reduce(...)` and detect convergence.

    If `step_fn` is provided, it is applied after each reduce pass
    (useful later for Ω transforms / projections).
    """
    steps: List[TraceStep] = []
    cur = x

    for i in range(max_steps):
        steps.append(TraceStep(i=i, value=cur))
        nxt = ev.reduce(cur)

        if step_fn is not None:
            nxt = step_fn(nxt)

        if nxt == cur:
            # Converged
            return TraceResult(result=cur, steps=steps)

        cur = nxt

    # Maxed out: return last state as result (still useful for debugging)
    steps.append(TraceStep(i=max_steps, value=cur))
    return TraceResult(result=cur, steps=steps)
