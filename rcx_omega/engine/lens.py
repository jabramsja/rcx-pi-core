"""
RCX-Ω lens (staging)

A "lens" is a deterministic read-only wrapper that combines:
- tracing (Ω engine.trace)
- analysis (Ω engine.analyze)

π remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.core.motif import Motif

from rcx_omega.engine.trace import TraceResult, trace_reduce
from rcx_omega.engine.analyze import MotifStats, analyze_motif


@dataclass(frozen=True)
class TraceStats:
    input_stats: MotifStats
    result_stats: MotifStats


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
    return LensResult(
        trace=tr,
        stats=TraceStats(
            input_stats=analyze_motif(x),
            result_stats=analyze_motif(tr.result),
        ),
    )
