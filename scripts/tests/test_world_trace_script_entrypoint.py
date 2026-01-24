from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_world_trace_script_entrypoint_help_smoke():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "world_trace.sh"

    r = subprocess.run(
        ["bash", str(script), "--help"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + "\n" + r.stderr
