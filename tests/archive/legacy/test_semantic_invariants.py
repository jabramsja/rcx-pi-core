import dataclasses
import inspect
import json
from typing import Any

from rcx_omega.core import parse_motif
from rcx_omega.trace import PureEvaluator, trace_reduce


def _to_primitive(x: Any) -> Any:
    """
    Convert TraceResult / TraceStep / Motif objects into JSON-stable primitives.
    Avoid repr() that may contain memory addresses.
    """
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, (list, tuple)):
        return [_to_primitive(v) for v in x]
    if isinstance(x, dict):
        # sort keys deterministically later via json.dumps(sort_keys=True)
        return {str(k): _to_primitive(v) for k, v in x.items()}

    # dataclass support
    if dataclasses.is_dataclass(x):
        return _to_primitive(dataclasses.asdict(x))

    # common attribute containers
    if hasattr(x, "__dict__"):
        d = {}
        for k, v in vars(x).items():
            if k.startswith("_"):
                continue
            d[str(k)] = _to_primitive(v)
        return d

    # last resort: stable string
    return str(x)


def _call_trace_reduce(evaluator: Any, motif: Any):
    """
    trace_reduce signature may vary slightly. We adapt by signature inspection.
    Expected typical shapes:
      - trace_reduce(evaluator, motif)
      - trace_reduce(motif, evaluator)
      - trace_reduce(motif)
    """
    sig = inspect.signature(trace_reduce)
    params = list(sig.parameters.values())

    # If it takes 2+ positional params, try by parameter names first.
    if len(params) >= 2:
        names = [p.name for p in params[:2]]
        if "evaluator" in names[0].lower() or "eval" in names[0].lower():
            return trace_reduce(evaluator, motif)
        if "evaluator" in names[1].lower() or "eval" in names[1].lower():
            return trace_reduce(motif, evaluator)
        # fallback: common ordering evaluator, motif
        try:
            return trace_reduce(evaluator, motif)
        except TypeError:
            return trace_reduce(motif, evaluator)

    # Single-arg variant
    return trace_reduce(motif)


def _semantic_trace_snapshot(expr: str) -> str:
    motif = parse_motif(expr)
    evaluator = PureEvaluator()

    tr = _call_trace_reduce(evaluator, motif)

    # Reduce to stable fields if present, else serialize whole object
    prim = _to_primitive(tr)
    # If it looks like a big dict, keep it; else wrap
    if not isinstance(prim, dict):
        prim = {"trace": prim}

    # Prefer stable subset if available
    keep = {}
    for k in (
        "input",
        "expr",
        "result",
        "summary",
        "schema_version",
        "schema",
        "version",
        "steps",
        "events",
        "trace",
    ):
        if k in prim:
            keep[k] = prim[k]
    if keep:
        prim = keep

    return (
        json.dumps(prim, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )


def test_semantic_trace_is_deterministic_for_canonical_expression():
    expr = "μ(μ())"
    a = _semantic_trace_snapshot(expr)
    b = _semantic_trace_snapshot(expr)
    assert a == b
