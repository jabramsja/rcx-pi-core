"""
RCX-Ω: trace analysis (staging)

Given a TraceResult, compute a simple classification:
- fixedpoint (converged)
- maxed (hit max-steps, no detected cycle)
- cycle (repeat detected in trace steps)

This is intentionally conservative and string-based. We do NOT depend
on Motif hashing or internal evaluator APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from rcx_omega.trace import TraceResult


@dataclass(frozen=True)
class TraceAnalysis:
    kind: str  # "fixedpoint" | "cycle" | "maxed"
    period: Optional[int] = None
    cycle_start: Optional[int] = None
    note: str = ""


def analyze_trace(tr: TraceResult) -> TraceAnalysis:
    if tr.converged:
        return TraceAnalysis(kind="fixedpoint", note="nxt == cur detected")

    # If we didn't converge, try to detect a cycle inside the recorded steps.
    # Use string representations for robustness.
    seen: Dict[str, int] = {}
    values = [str(s.value) for s in tr.steps]

    for i, v in enumerate(values):
        if v in seen:
            start = seen[v]
            period = i - start
            if period > 0:
                return TraceAnalysis(
                    kind="cycle",
                    period=period,
                    cycle_start=start,
                    note="repeat detected in trace steps",
                )
        else:
            seen[v] = i

    # No cycle detected. If trace_reduce hit max, label maxed.
    if tr.maxed:
        return TraceAnalysis(kind="maxed", note="max_steps reached; no cycle detected")

    # Should be rare (defensive)
    return TraceAnalysis(kind="maxed", note="non-converged trace; treating as maxed")
