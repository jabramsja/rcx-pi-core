"""
RCX-Ω Observer Lens (staging)

An Observer is a read-only structure that watches π evaluation
without mutating the π kernel.

Principle:
- π computes
- Ω observes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, List

from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.core.motif import Motif
from rcx_omega.trace import trace_reduce, TraceResult


class Observer(Protocol):
    """Read-only observer of evaluation."""
    def observe(self, trace: TraceResult) -> None: ...


@dataclass
class CollectingObserver:
    """Simple observer that records traces."""
    traces: List[TraceResult]

    def observe(self, trace: TraceResult) -> None:
        self.traces.append(trace)


def evaluate_with_lens(
    ev: PureEvaluator,
    x: Motif,
    *,
    observer: Observer,
    max_steps: int = 64,
) -> Motif:
    """
    Evaluate x under π, observed by Ω.

    Returns the π result unchanged.
    """
    tr = trace_reduce(ev, x, max_steps=max_steps)
    observer.observe(tr)
    return tr.result
