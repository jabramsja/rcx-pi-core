import subprocess
from pathlib import Path

def test_world_trace_schema_flag():
    repo_root = Path(__file__).resolve().parents[2]
    cli = repo_root / "rcx_pi" / "worlds" / "world_trace_cli.py"

    r = subprocess.run(
        ["python3", str(cli), "--schema"],
        capture_output=True,
        text=True,
    )

    assert r.returncode == 0
    assert "rcx-world-trace.v1" in r.stdout
    assert "docs/world_trace_json_schema.md" in r.stdout
