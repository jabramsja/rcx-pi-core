import json
import subprocess
import sys


def test_analyze_cli_pipe_smoke():
    # trace -> analyze pipe should work and emit the header
    trace = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", "void"],
        capture_output=True,
        text=True,
        check=True,
    )
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.analyze_cli"],
        input=trace.stdout,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "== Ω analyze ==" in p.stdout
    assert "converged:" in p.stdout
