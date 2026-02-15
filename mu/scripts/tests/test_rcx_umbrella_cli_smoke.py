import json
import subprocess
import sys
from rcx_pi.cli_schema_run import parse_schema_triplet_stdout, run_schema_triplet

PYTHON = sys.executable


def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def test_rcx_program_describe_schema():
    r = run([PYTHON, "-m", "rcx_pi.rcx_cli", "program", "describe", "--schema"])
    assert "rcx-program-descriptor.v1" in r.stdout


def test_rcx_program_run_schema():
    r = run([PYTHON, "-m", "rcx_pi.rcx_cli", "program", "run", "--schema"])
    assert "rcx-program-run.v1" in r.stdout


def test_rcx_world_trace_schema():
    r = run([PYTHON, "-m", "rcx_pi.rcx_cli", "world", "trace", "--schema"])
    assert "rcx-world-trace.v1" in r.stdout


def test_rcx_program_run_executes():
    r = run([PYTHON, "-m", "rcx_pi.rcx_cli", "program", "run", "succ-list", "[1,2,3]"])
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload["output"] == [2, 3, 4]


def test_rcx_world_trace_executes():
    r = run(
        [
            PYTHON,
            "-m",
            "rcx_pi.rcx_cli",
            "trace",
            "pingpong",
            "ping",
            "--max-steps",
            "4",
        ]
    )
    payload = json.loads(r.stdout)
    assert payload["schema"] == "rcx-world-trace.v1"
    assert payload["world"] == "pingpong"
