import json
import subprocess
import sys


def test_trace_cli_json_includes_stats():
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", "void"],
        capture_output=True,
        text=True,
        check=True,
    )
    obj = json.loads(p.stdout)
    assert "stats" in obj
    assert "input" in obj["stats"]
    assert "result" in obj["stats"]
    assert obj["stats"]["input"]["nodes"] == 1
    assert obj["stats"]["result"]["nodes"] == 1
