from __future__ import annotations

import subprocess
from pathlib import Path


def test_program_descriptor_schema_flag():
    repo_root = Path(__file__).resolve().parents[2]
    cli = repo_root / "rcx_pi" / "program_descriptor_cli.py"
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
        == "rcx-program-descriptor.v1 docs/program_descriptor_schema.md docs/schemas/program_descriptor_schema.json"
    )
