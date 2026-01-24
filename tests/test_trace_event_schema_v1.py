from __future__ import annotations

import json
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_schema() -> dict:
    root = _repo_root()
    p = root / "docs" / "schemas" / "rcx-trace-event.v1.json"
    assert p.exists(), f"Missing schema file: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def test_trace_event_schema_v1_accepts_canonical_event() -> None:
    jsonschema = pytest.importorskip("jsonschema")

    from rcx_pi.trace_canon import canon_event

    schema = _load_schema()
    ev = canon_event(
        {
            "v": 1,
            "type": "trace.start",
            "i": 0,
            "t": "smoke",
            "mu": {"b": 2, "a": 1},
            "meta": {"z": 9, "y": 8},
        }
    )

    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=ev, schema=schema)


def test_trace_event_schema_v1_rejects_extra_top_level_keys() -> None:
    jsonschema = pytest.importorskip("jsonschema")

    schema = _load_schema()
    bad = {"v": 1, "type": "trace.start", "i": 0, "extra": 123}

    jsonschema.Draft202012Validator.check_schema(schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
