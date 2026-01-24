from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping, Tuple, Union

TRACE_EVENT_V = 1
TRACE_EVENT_KEY_ORDER: Tuple[str, ...] = ("v", "type", "i", "t", "mu", "meta")

Json = Union[None, bool, int, float, str, List["Json"], Dict[str, "Json"]]


def _deep_sort_json(x: Any) -> Any:
    """
    Deterministically normalize nested JSON-ish structures:
    - dict: keys sorted lexicographically; values deep-sorted
    - list: values deep-sorted (order preserved)
    - primitives: unchanged
    """
    if isinstance(x, dict):
        out: Dict[str, Any] = {}
        for k in sorted(x.keys()):
            out[str(k)] = _deep_sort_json(x[k])
        return out
    if isinstance(x, list):
        return [_deep_sort_json(v) for v in x]
    return x


def canon_event(ev: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Canonicalize a single trace event to a deterministic dict.

    Required (v1):
    - v: const 1
    - type: non-empty string
    - i: integer >= 0

    Optional:
    - t: stable tag (string)
    - mu: optional payload (JSON-normalized if dict/list)
    - meta: optional metadata (deep-sorted for determinism)

    Rules:
    - Drop optional keys if value is None.
    - Ignore unknown keys (do not carry them forward).
    - Enforce stable top-level key order.
    """
    if not isinstance(ev, Mapping):
        raise TypeError(f"event must be a mapping, got {type(ev)}")

    v = ev.get("v", TRACE_EVENT_V)
    if v != TRACE_EVENT_V:
        raise ValueError(f"event.v must be {TRACE_EVENT_V}, got {v!r}")

    typ = ev.get("type")
    if not isinstance(typ, str) or not typ.strip():
        raise ValueError("event.type must be a non-empty string")

    i = ev.get("i")
    if not isinstance(i, int) or i < 0:
        raise ValueError("event.i must be an integer >= 0")

    t = ev.get("t", None)
    if t is not None and (not isinstance(t, str) or not t.strip()):
        raise ValueError("event.t must be a non-empty string when provided")

    mu = ev.get("mu", None)
    if isinstance(mu, (dict, list)):
        mu = _deep_sort_json(mu)

    meta = ev.get("meta", None)
    if meta is not None:
        if not isinstance(meta, Mapping):
            raise ValueError("event.meta must be an object/dict when provided")
        meta = _deep_sort_json(dict(meta))

    out: Dict[str, Any] = {}
    # Stable key order (dict insertion order)
    out["v"] = TRACE_EVENT_V
    out["type"] = typ
    out["i"] = i
    if t is not None:
        out["t"] = t
    if mu is not None:
        out["mu"] = mu
    if meta is not None:
        out["meta"] = meta
    return out


def canon_events(events: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """
    Canonicalize a sequence of events and enforce contiguous index ordering by `i`.
    We do NOT renumber; we assert correctness to catch drift early.
    """
    out: List[Dict[str, Any]] = [canon_event(ev) for ev in events]
    if out:
        expected = list(range(len(out)))
        got = [e["i"] for e in out]
        if got != expected:
            raise ValueError(
                f"event.i must be contiguous 0..n-1 in-order; got {got}, expected {expected}"
            )
    return out


def canon_event_json(ev: Mapping[str, Any]) -> str:
    """
    Serialize one canonical event as compact JSON with stable key order (top-level).
    """
    obj = canon_event(ev)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
