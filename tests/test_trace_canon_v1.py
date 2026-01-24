from __future__ import annotations

import json
import pytest

from rcx_pi.trace_canon import canon_event, canon_event_json, canon_events


def test_canon_event_minimal_keeps_required_fields_and_order():
    ev = {"type": "trace.start", "i": 0, "v": 1}
    out = canon_event(ev)

    # Required fields exist
    assert out["v"] == 1
    assert out["type"] == "trace.start"
    assert out["i"] == 0

    # Stable insertion order of keys (v1)
    assert list(out.keys()) == ["v", "type", "i"]


def test_canon_event_drops_none_optionals_and_ignores_unknown_keys():
    ev = {
        "v": 1,
        "type": "x",
        "i": 0,
        "t": None,
        "mu": None,
        "meta": None,
        "lol_nope": "ignored",
    }
    out = canon_event(ev)
    assert "t" not in out
    assert "mu" not in out
    assert "meta" not in out
    assert "lol_nope" not in out
    assert list(out.keys()) == ["v", "type", "i"]


def test_canon_event_meta_is_deep_sorted():
    ev = {
        "v": 1,
        "type": "x",
        "i": 0,
        "meta": {"b": 2, "a": {"d": 4, "c": 3}},
    }
    out = canon_event(ev)
    assert list(out["meta"].keys()) == ["a", "b"]
    assert list(out["meta"]["a"].keys()) == ["c", "d"]


def test_canon_event_json_is_deterministic_across_input_key_permutations():
    ev1 = {"v": 1, "type": "x", "i": 0, "meta": {"b": 2, "a": 1}}
    ev2 = {"meta": {"a": 1, "b": 2}, "i": 0, "type": "x", "v": 1}

    j1 = canon_event_json(ev1)
    j2 = canon_event_json(ev2)
    assert j1 == j2

    # Also ensure it's valid JSON
    obj = json.loads(j1)
    assert obj["meta"] == {"a": 1, "b": 2}


def test_canon_events_enforces_contiguous_i():
    ok = [{"v": 1, "type": "a", "i": 0}, {"v": 1, "type": "b", "i": 1}]
    out = canon_events(ok)
    assert [e["i"] for e in out] == [0, 1]

    bad = [{"v": 1, "type": "a", "i": 0}, {"v": 1, "type": "b", "i": 2}]
    with pytest.raises(ValueError):
        canon_events(bad)


def test_canon_event_rejects_invalid_required_fields():
    # v=3 is invalid (only v1 and v2 supported)
    with pytest.raises(ValueError):
        canon_event({"v": 3, "type": "x", "i": 0})
    with pytest.raises(ValueError):
        canon_event({"v": 1, "type": "", "i": 0})
    with pytest.raises(ValueError):
        canon_event({"v": 1, "type": "x", "i": -1})


def test_canon_event_accepts_v2():
    """v2 events are valid (for observability/execution events)."""
    ev = {"v": 2, "type": "execution.stall", "i": 0}
    out = canon_event(ev)
    assert out["v"] == 2
    assert out["type"] == "execution.stall"
