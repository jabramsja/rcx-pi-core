import json
import subprocess
import sys
from pathlib import Path


def test_trace_cli_reads_stdin_json():
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", "--stdin"],
        input="μ(μ(), μ(μ()))\n",
        capture_output=True,
        text=True,
        check=True,
    )
    obj = json.loads(p.stdout)
    assert "result" in obj
    assert "steps" in obj


def test_trace_cli_reads_file_json(tmp_path: Path):
    f = tmp_path / "motif.txt"
    f.write_text("μ(μ())\n", encoding="utf-8")

    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", "--file", str(f)],
        capture_output=True,
        text=True,
        check=True,
    )
    obj = json.loads(p.stdout)
    assert "result" in obj
    assert "stats" in obj
