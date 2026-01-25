from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Iterable, List, Mapping, Tuple, Union

TRACE_EVENT_V1 = 1
TRACE_EVENT_V2 = 2

# Feature flag: set RCX_TRACE_V2=1 to enable v2 observability events
RCX_TRACE_V2_ENABLED = os.environ.get("RCX_TRACE_V2", "0") == "1"

# Feature flag: set RCX_EXECUTION_V0=1 to enable v0 execution semantics
RCX_EXECUTION_V0_ENABLED = os.environ.get("RCX_EXECUTION_V0", "0") == "1"

TRACE_EVENT_V = TRACE_EVENT_V1  # default for backwards compat
TRACE_EVENT_KEY_ORDER: Tuple[str, ...] = ("v", "type", "i", "t", "mu", "meta")

# Valid v2 event types
V2_OBSERVABILITY_TYPES = frozenset(["reduction.stall", "reduction.applied", "reduction.normal"])
V2_EXECUTION_TYPES = frozenset(["execution.stall", "execution.fix", "execution.fixed"])

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


def canon_jsonl(events: Iterable[Mapping[str, Any]]) -> str:
    """
    Serialize canonical events to JSONL (one event per line, newline-terminated).
    """
    canon = canon_events(events)
    lines = [
        json.dumps(e, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
        for e in canon
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def value_hash(mu: Any) -> str:
    """
    Compute deterministic hash of a value for trace references.
    Uses canonical JSON serialization to ensure determinism.
    Returns first 16 hex chars of SHA-256.
    """
    # Wrap in a minimal event structure for canonicalization
    canonical = json.dumps(
        _deep_sort_json(mu) if isinstance(mu, (dict, list)) else mu,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


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


# --- Execution Engine (v0) ---
# Feature flag: RCX_EXECUTION_V0=1


class ExecutionStatus:
    """Execution state for a value."""

    ACTIVE = "active"
    STALLED = "stalled"
    TERMINAL = "terminal"


class ExecutionEngine:
    """
    Minimal execution engine for Stall/Fix loop (v0).

    Tracks single value through stall/fix cycle:
    - ACTIVE: value is being reduced
    - STALLED: pattern match failed, awaiting fix
    - TERMINAL: value reached normal form

    Feature flag: RCX_EXECUTION_V0=1 must be set to enable.
    """

    def __init__(self, enabled: bool = None) -> None:
        self._enabled = enabled if enabled is not None else RCX_EXECUTION_V0_ENABLED
        self._events: List[Dict[str, Any]] = []
        self._index: int = 0
        self._status: str = ExecutionStatus.ACTIVE
        self._stall_reason: str = None
        self._current_value_hash: str = None

    def _emit(self, event_type: str, t: str = None, mu: Any = None) -> None:
        """Emit an execution event."""
        if not self._enabled:
            return
        ev: Dict[str, Any] = {"v": TRACE_EVENT_V2, "type": event_type, "i": self._index}
        if t is not None:
            ev["t"] = t
        if mu is not None:
            ev["mu"] = _deep_sort_json(mu) if isinstance(mu, (dict, list)) else mu
        self._events.append(ev)
        self._index += 1

    @property
    def status(self) -> str:
        """Current execution status."""
        return self._status

    @property
    def is_stalled(self) -> bool:
        """True if execution is stalled."""
        return self._status == ExecutionStatus.STALLED

    @property
    def current_value_hash(self) -> str | None:
        """Current value hash (for post-condition assertions)."""
        return self._current_value_hash

    def stall(self, pattern_id: str, value: Any) -> None:
        """
        Stall execution due to pattern mismatch.

        Precondition: status == ACTIVE
        Postcondition: status == STALLED
        """
        if not self._enabled:
            return
        if self._status != ExecutionStatus.ACTIVE:
            raise RuntimeError(f"Cannot stall: status is {self._status}, expected ACTIVE")

        self._current_value_hash = value_hash(value)
        self._stall_reason = pattern_id
        self._status = ExecutionStatus.STALLED

        self._emit(
            "execution.stall",
            mu={"pattern_id": pattern_id, "value_hash": self._current_value_hash},
        )

    def fix(self, rule_id: str, target_hash: str) -> bool:
        """
        Apply fix from trace event.

        Precondition: status == STALLED, target_hash matches current value
        Returns: True if fix was valid and applied

        Note: Actual transformation is done by caller; this just validates and records.
        """
        if not self._enabled:
            return True
        if self._status != ExecutionStatus.STALLED:
            raise RuntimeError(f"Cannot fix: status is {self._status}, expected STALLED")

        if target_hash != self._current_value_hash:
            raise RuntimeError(
                f"Fix target mismatch: expected {self._current_value_hash}, got {target_hash}"
            )

        return True

    def fixed(self, rule_id: str, before_hash: str, after_value: Any) -> None:
        """
        Confirm fix was applied, transition back to ACTIVE.

        Precondition: status == STALLED
        Postcondition: status == ACTIVE
        """
        if not self._enabled:
            return
        if self._status != ExecutionStatus.STALLED:
            raise RuntimeError(f"Cannot confirm fix: status is {self._status}, expected STALLED")

        after_hash = value_hash(after_value)
        self._emit(
            "execution.fixed",
            t=rule_id,
            mu={"after_hash": after_hash, "before_hash": before_hash},
        )

        self._status = ExecutionStatus.ACTIVE
        self._stall_reason = None
        self._current_value_hash = after_hash

    def terminate(self) -> None:
        """Mark execution as terminal (normal form reached)."""
        if not self._enabled:
            return
        self._status = ExecutionStatus.TERMINAL

    def get_events(self) -> List[Dict[str, Any]]:
        """Return collected execution events (canonicalized)."""
        return [canon_event(ev) for ev in self._events]

    def reset(self) -> None:
        """Reset execution state."""
        self._events = []
        self._index = 0
        self._status = ExecutionStatus.ACTIVE
        self._stall_reason = None
        self._current_value_hash = None

    # --- Consume API (consumes trace events during replay) ---

    def consume_stall(self, pattern_id: str, value_hash_from_trace: str) -> None:
        """
        Consume execution.stall event from trace.

        Precondition: status == ACTIVE
        Postcondition: status == STALLED, value_hash stored

        Unlike stall(), this takes a hash directly (no value to hash).
        Used for replay mode where we're consuming a recorded trace.
        """
        if not self._enabled:
            return
        if self._status != ExecutionStatus.ACTIVE:
            raise RuntimeError(f"Cannot replay stall: status is {self._status}, expected ACTIVE")

        self._current_value_hash = value_hash_from_trace
        self._stall_reason = pattern_id
        self._status = ExecutionStatus.STALLED

    def consume_fix(self, rule_id: str, target_hash: str) -> None:
        """
        Consume execution.fix event from trace.

        Precondition: status == STALLED, target_hash matches current value_hash

        Unlike fix(), this is a validation step for replay (no return value needed).
        """
        if not self._enabled:
            return
        if self._status != ExecutionStatus.STALLED:
            raise RuntimeError(f"Cannot replay fix: status is {self._status}, expected STALLED")

        if target_hash != self._current_value_hash:
            raise RuntimeError(
                f"Replay fix target mismatch: expected {self._current_value_hash}, got {target_hash}"
            )
        # Fix is validated; actual transformation would be applied by real execution

    def consume_fixed(self, rule_id: str, before_hash: str, after_hash: str) -> None:
        """
        Consume execution.fixed event from trace.

        Precondition: status == STALLED, before_hash matches current value_hash
        Postcondition: status == ACTIVE, value_hash updated to after_hash

        Unlike fixed(), this takes after_hash directly (no value to hash).
        """
        if not self._enabled:
            return
        if self._status != ExecutionStatus.STALLED:
            raise RuntimeError(f"Cannot replay fixed: status is {self._status}, expected STALLED")

        if before_hash != self._current_value_hash:
            raise RuntimeError(
                f"Replay fixed before_hash mismatch: expected {self._current_value_hash}, got {before_hash}"
            )

        self._status = ExecutionStatus.ACTIVE
        self._stall_reason = None
        self._current_value_hash = after_hash
