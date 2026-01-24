from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_schema() -> dict:
    root = _repo_root()
    p = root / "docs" / "schemas" / "rcx-trace-event.v1.json"
    assert p.exists(), f"Missing schema file: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def test_trace_event_schema_v1_accepts_canonical_event() -> None:
    try:
        import jsonschema  # type: ignore
    except Exception as e:  # pragma: no cover
        raise AssertionError(
            "Missing dependency: jsonschema. Install it (dev/test deps) to validate schemas."
        ) from e

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

    # Validate using Draft 2020-12
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(instance=ev, schema=schema)


def test_trace_event_schema_v1_rejects_extra_top_level_keys() -> None:
    try:
        import jsonschema  # type: ignore
    except Exception as e:  # pragma: no cover
        raise AssertionError(
            "Missing dependency: jsonschema. Install it (dev/test deps) to validate schemas."
        ) from e

    schema = _load_schema()
    bad = {"v": 1, "type": "trace.start", "i": 0, "extra": 123}

    jsonschema.Draft202012Validator.check_schema(schema)
    try:
        jsonschema.validate(instance=bad, schema=schema)
    except jsonschema.ValidationError:
        return
    raise AssertionError("Expected schema validation to fail for extra top-level keys.")
