from __future__ import annotations

import json
from pathlib import Path

import pytest

EVENT_SCHEMA = Path("docs/schemas/rcx-trace-event.v1.json")
FIXTURE = Path("tests/fixtures/traces/minimal.v1.jsonl")


def _load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_trace_event_schema_file_exists():
    assert EVENT_SCHEMA.exists(), "Missing docs/schemas/rcx-trace-event.v1.json"


def test_trace_fixture_exists():
    assert FIXTURE.exists(), "Missing tests/fixtures/traces/minimal.v1.jsonl"


def test_trace_fixture_is_jsonl_one_event_per_line():
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    assert lines, "Fixture is empty"
    for ln in lines:
        obj = json.loads(ln)
        assert isinstance(obj, dict)


def test_trace_fixture_validates_against_schema_if_jsonschema_installed():
    try:
        import jsonschema  # type: ignore
    except Exception:
        pytest.skip("jsonschema not installed; skipping schema validation")
    schema = _load_json(EVENT_SCHEMA)
    for ln in FIXTURE.read_text(encoding="utf-8").splitlines():
        ev = json.loads(ln)
        jsonschema.validate(instance=ev, schema=schema)
