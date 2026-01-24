from __future__ import annotations

import subprocess
from pathlib import Path
from rcx_pi.cli_schema_run import parse_schema_triplet_stdout, run_schema_triplet


def test_snapshot_schema_flag():
    repo_root = Path(__file__).resolve().parents[2]
    tool = repo_root / "scripts" / "snapshot_merge.py"
    assert tool.exists(), f"missing: {tool}"

    r = subprocess.run(
        ["python3", str(tool), "--schema", "A", "B", "--out", "OUT.json"],
        capture_output=True,
        text=True,
    )
    # --schema should exit early successfully (tool prints schema line)
    assert r.returncode == 0
    out = r.stdout.strip()
    assert (
        out
        == "rcx.snapshot.v1 docs/snapshot_json_schema.md docs/schemas/rcx.snapshot.v1.schema.json"
    )
