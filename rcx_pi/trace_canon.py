from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Mapping, Tuple, Union

TRACE_EVENT_V1 = 1
TRACE_EVENT_V2 = 2

# Feature flag: set RCX_TRACE_V2=1 to enable v2 observability events
RCX_TRACE_V2_ENABLED = os.environ.get("RCX_TRACE_V2", "0") == "1"
TRACE_EVENT_V = TRACE_EVENT_V1  # default for backwards compat
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

    v = ev.get("v", TRACE_EVENT_V1)
    if v not in (TRACE_EVENT_V1, TRACE_EVENT_V2):
        raise ValueError(f"event.v must be {TRACE_EVENT_V1} or {TRACE_EVENT_V2}, got {v!r}")

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
    out["v"] = v
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


def _motif_depth(m: Any) -> int:
    """Compute structural depth of a motif (for compact trace references)."""
    if not hasattr(m, "structure"):
        return 0
    if not m.structure:
        return 1
    return 1 + max(_motif_depth(c) for c in m.structure)


class TraceObserver:
    """
    Minimal observer for v2 trace events (stall/fix observability).
    Emits v2 events interleaved with v1 events, sharing contiguous indices.

    Feature flag: Set RCX_TRACE_V2=1 to enable event emission.
    When disabled (default), observer methods are no-ops.
    """

    def __init__(self, enabled: bool = None) -> None:
        self._events: List[Dict[str, Any]] = []
        self._index: int = 0
        # Use explicit enabled flag, or fall back to env var
        self._enabled = enabled if enabled is not None else RCX_TRACE_V2_ENABLED

    def _emit(self, event_type: str, t: str = None, mu: Any = None) -> None:
        if not self._enabled:
            return
        ev: Dict[str, Any] = {"v": TRACE_EVENT_V2, "type": event_type, "i": self._index}
        if t is not None:
            ev["t"] = t
        if mu is not None:
            ev["mu"] = mu
        self._events.append(ev)
        self._index += 1

    def stall(self, reason: str = "pattern_mismatch") -> None:
        """Emit reduction.stall event."""
        self._emit("reduction.stall", mu={"reason": reason})

    def normal(self) -> None:
        """Emit reduction.normal event."""
        self._emit("reduction.normal", mu={"reason": "no_rule_matched"})

    def applied(self, rule_id: str, before: Any, after: Any) -> None:
        """Emit reduction.applied event with rule_id and depth refs."""
        self._emit(
            "reduction.applied",
            t=rule_id,
            mu={
                "after_depth": _motif_depth(after),
                "before_depth": _motif_depth(before),
                "rule_id": rule_id,
            },
        )

    def get_events(self) -> List[Dict[str, Any]]:
        """Return collected events (canonicalized)."""
        return [canon_event(ev) for ev in self._events]

    def reset(self) -> None:
        """Reset observer state."""
        self._events = []
        self._index = 0
