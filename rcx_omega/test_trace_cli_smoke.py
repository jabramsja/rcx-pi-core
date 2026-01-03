import subprocess
import sys


def test_trace_cli_void_smoke():
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.trace_cli", "void"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "result:" in p.stdout
    assert "steps:" in p.stdout
