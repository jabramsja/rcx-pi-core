from __future__ import annotations

import subprocess

from rcx_pi.cli_schema import parse_schema_triplet


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip() != ""]
    assert len(lines) == 1, (
        f"expected exactly 1 non-empty stdout line, got {len(lines)}: {lines!r}"
    )
    return lines[0]


def test_rcx_program_descriptor_schema_triplet_is_parseable():
    line = _run(["rcx-program-descriptor", "--schema"])
    trip = parse_schema_triplet(line)
    assert trip.tag == "rcx-program-descriptor.v1"


def test_rcx_program_run_schema_triplet_is_parseable():
    line = _run(["rcx-program-run", "--schema"])
    trip = parse_schema_triplet(line)
    assert trip.tag == "rcx-program-run.v1"


def test_rcx_world_trace_schema_triplet_is_parseable():
    line = _run(["rcx-world-trace", "--schema"])
    trip = parse_schema_triplet(line)
    assert trip.tag == "rcx-world-trace.v1"
