from __future__ import annotations

from rcx_pi.cli_schema_run import run_schema_triplet


def test_rcx_cli_world_trace_schema_triplet_is_parseable():
    res = run_schema_triplet(
        ["python3", "-m", "rcx_pi.rcx_cli", "world", "trace", "--schema"],
        expected_tag="rcx-world-trace.v1",
    )
    assert res.trip.tag.endswith(".v1")
