"""
RCX-Ω lens (staging)

A "lens" is a deterministic read-only wrapper that combines:
- tracing
- analysis
- step-wise deltas

π remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.core.motif import Motif

from rcx_omega.engine.trace import TraceResult, trace_reduce
from rcx_omega.engine.analyze import MotifStats, analyze_motif


@dataclass(frozen=True)
class StepDelta:
    i: int
    nodes: int
    depth: int
    delta_nodes: int
    delta_depth: int


@dataclass(frozen=True)
class TraceStats:
    input_stats: MotifStats
    result_stats: MotifStats
    deltas: List[StepDelta]


@dataclass(frozen=True)
class LensResult:
    trace: TraceResult
    stats: TraceStats


def trace_reduce_with_stats(
    ev: PureEvaluator,
    x: Motif,
    *,
    max_steps: int = 64,
) -> LensResult:
    tr = trace_reduce(ev, x, max_steps=max_steps)

    # analyze all steps
    step_stats: List[MotifStats] = [
        analyze_motif(s.value) for s in tr.steps
    ]

    deltas: List[StepDelta] = []
    prev: Optional[MotifStats] = None

    for i, st in enumerate(step_stats):
        if prev is None:
            deltas.append(
                StepDelta(
                    i=i,
                    nodes=st.nodes,
                    depth=st.depth,
                    delta_nodes=0,
                    delta_depth=0,
                )
            )
        else:
            deltas.append(
                StepDelta(
                    i=i,
                    nodes=st.nodes,
                    depth=st.depth,
                    delta_nodes=st.nodes - prev.nodes,
                    delta_depth=st.depth - prev.depth,
                )
            )
        prev = st

    return LensResult(
        trace=tr,
        stats=TraceStats(
            input_stats=analyze_motif(x),
            result_stats=analyze_motif(tr.result),
            deltas=deltas,
        ),
    )
