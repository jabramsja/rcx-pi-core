import json
import subprocess
import sys


def test_omega_analyze_cli_pipe_smoke():
    # omega -> analyze pipe should work and emit the header (or at least not crash)
    omega = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", "μ(μ())"],
        capture_output=True,
        text=True,
        check=True,
    )

    # sanity: omega output is json and has result
    obj = json.loads(omega.stdout)
    assert "result" in obj

    analyze = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.analyze_cli"],
        input=omega.stdout,
        capture_output=True,
        text=True,
        check=True,
    )

    # analyze should accept summary payloads and still emit the header
    assert "== Ω analyze ==" in analyze.stdout
    assert "analyze: summary" in analyze.stdout
