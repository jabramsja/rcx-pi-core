"""
RCX-Ω: Motif codec (staging)

Goal:
- JSON-ish encoding of π Motifs as {"μ": [...]}
- Preserve μ arity exactly (μ(μ()) must show one child)
- NO π mutation. Ω only reflects.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from rcx_pi.core.motif import Motif


def _as_seq(v: Any) -> List[Any] | None:
    if isinstance(v, (list, tuple)):
        return list(v)
    return None


def _try_attr_or_method(obj: Any, name: str) -> Any:
    if not hasattr(obj, name):
        return None
    v = getattr(obj, name)
    # If it's a zero-arg method, call it.
    if callable(v):
        try:
            return v()
        except TypeError:
            return None
    return v


def motif_children(m: Motif) -> List[Any]:
    """
    Discover Motif children in a slots-safe, API-tolerant way.

    Priority:
    1) Known attribute/method names
    2) Iteration protocol
    3) __slots__ inspection (best-effort)
    """
    # 1) Known/common names (attr OR method)
    for name in ("children", "args", "items", "xs", "elts", "_children", "_args", "_items", "_xs"):
        v = _try_attr_or_method(m, name)
        seq = _as_seq(v)
        if seq is not None:
            return seq

    # 2) If Motif is iterable (common for tree nodes), use that.
    try:
        it = list(m)  # type: ignore[arg-type]
        # Guard: if it iterates characters or nonsense, ignore.
        if all(isinstance(x, Motif) for x in it) or it == []:
            return it
    except Exception:
        pass

    # 3) Slots inspection: scan slot values for a list/tuple that looks like children.
    slots = getattr(type(m), "__slots__", ())
    if isinstance(slots, str):
        slots = (slots,)
    for s in slots:
        try:
            v = getattr(m, s)
        except Exception:
            continue
        seq = _as_seq(v)
        if seq is None:
            continue
        # Heuristic: children are often Motifs (or empty)
        if seq == [] or all(isinstance(x, Motif) for x in seq):
            return seq

    return []


def motif_to_json_obj(x: Any) -> Any:
    # JSON primitives
    if x is None or isinstance(x, (bool, int, float, str)):
        return x

    # Lists / tuples
    if isinstance(x, (list, tuple)):
        return [motif_to_json_obj(v) for v in x]

    # Dicts
    if isinstance(x, dict):
        return {str(k): motif_to_json_obj(v) for k, v in x.items()}

    # π Motif
    if isinstance(x, Motif):
        kids = motif_children(x)
        return {"μ": [motif_to_json_obj(c) for c in kids]}

    # Fallback (debug only)
    return {"$repr": repr(x)}
