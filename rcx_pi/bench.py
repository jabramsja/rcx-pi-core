# rcx_pi/bench.py
"""
Tiny benchmarking helper for RCX-π reductions.

This is intentionally simple and does not depend on any external libs.

Usage:

    from rcx_pi.bench import benchmark_reduce
    from rcx_pi import μ, VOID, PureEvaluator

    def build_expr():
        # build a motif you want to reduce repeatedly
        ...

    stats = benchmark_reduce(build_expr, repeats=20)
    print(stats)

You can also use the CLI helper in bench_rcx.py
"""

from __future__ import annotations
import time
from typing import Callable, Dict, Any

from .core.motif import Motif
from .engine.evaluator_pure import PureEvaluator


def benchmark_reduce(
    builder: Callable[[], Motif],
    repeats: int = 10,
) -> Dict[str, Any]:
    """
    Run `repeats` reductions of `builder()` using PureEvaluator.

    Returns a small stats dict:
        {
            "repeats": N,
            "min_s": ...,
            "max_s": ...,
            "avg_s": ...,
            "total_s": ...,
        }
    """
    if repeats <= 0:
        raise ValueError("repeats must be > 0")

    ev = PureEvaluator()
    times = []

    for _ in range(repeats):
        expr = builder()
        t0 = time.perf_counter()
        _ = ev.reduce(expr)
        t1 = time.perf_counter()
        times.append(t1 - t0)

    total = sum(times)
    return {
        "repeats": repeats,
        "min_s": min(times),
        "max_s": max(times),
        "avg_s": total / repeats,
        "total_s": total,
    }