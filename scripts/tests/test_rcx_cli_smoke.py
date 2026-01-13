from __future__ import annotations

import subprocess
import sys


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "rcx_pi.rcx_cli", *args],
        capture_output=True,
        text=True,
    )


def test_rcx_cli_program_describe_schema():
    r = _run(["program", "describe", "--schema"])
    assert r.returncode == 0
    assert "rcx-program-descriptor.v1" in r.stdout


def test_rcx_cli_program_run_schema():
    r = _run(["program", "run", "--schema"])
    assert r.returncode == 0
    assert "rcx-program-run.v1" in r.stdout


def test_rcx_cli_world_trace_schema():
    r = _run(["world", "trace", "--schema"])
    assert r.returncode == 0
    assert "rcx-world-trace.v1" in r.stdout


def test_rcx_cli_trace_alias_schema():
    r1 = _run(["world", "trace", "--schema"])
    r2 = _run(["trace", "--schema"])
    assert r1.returncode == 0
    assert r2.returncode == 0
    assert r1.stdout.strip() == r2.stdout.strip()
