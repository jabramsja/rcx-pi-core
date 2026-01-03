import json
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


def test_trace_cli_json_smoke():
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.trace_cli", "--json", "void"],
        capture_output=True,
        text=True,
        check=True,
    )
    obj = json.loads(p.stdout)
    assert obj["result"] is not None
    assert isinstance(obj["steps"], list)
    assert obj["steps"][0]["i"] == 0
