from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_world_trace_cli_runs_as_script_help():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "rcx_pi" / "worlds" / "world_trace_cli.py"

    r = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (r.stdout + "\n" + r.stderr)


def test_world_trace_cli_runs_as_module_help():
    repo_root = Path(__file__).resolve().parents[3]

    r = subprocess.run(
        [sys.executable, "-m", "rcx_pi.worlds.world_trace_cli", "--help"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (r.stdout + "\n" + r.stderr)
