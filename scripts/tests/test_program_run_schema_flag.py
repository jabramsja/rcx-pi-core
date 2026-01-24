from __future__ import annotations

import subprocess
from pathlib import Path


def test_program_run_schema_flag():
    repo_root = Path(__file__).resolve().parents[2]
    cli = repo_root / "rcx_pi" / "program_run_cli.py"
    assert cli.exists(), f"missing: {cli}"

    r = subprocess.run(
        ["python3", str(cli), "--schema"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = r.stdout.strip()
    assert (
        out
        == "rcx-program-run.v1 docs/program_run_schema.md docs/schemas/program_run_schema.json"
    )
