from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    # Always exercise module-mode so the test doesn't depend on console_scripts install.
    cmd = [sys.executable, "-m", "rcx_pi.rcx_cli", *args]
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def test_rcx_cli_help_smoke():
    repo_root = Path(__file__).resolve().parents[2]
    r = _run(["--help"], repo_root)
    assert r.returncode == 0, r.stderr
    out = (r.stdout or "") + (r.stderr or "")
    assert "program describe" in out
    assert "program run" in out
    assert "world trace" in out
    assert "trace" in out  # alias


def test_rcx_cli_program_run_routes_and_emits_json():
    repo_root = Path(__file__).resolve().parents[2]
    r = _run(["program", "run", "succ-list", "[1,2,3]"], repo_root)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["schema"] == "rcx-program-run.v1"
    assert data["program"] == "succ-list"
    assert data["input"] == [1, 2, 3]
    assert data["output"] == [2, 3, 4]
    assert data.get("ok") is True


def test_rcx_cli_trace_alias_routes_and_emits_json():
    repo_root = Path(__file__).resolve().parents[2]
    r = _run(["trace", "pingpong", "ping", "--max-steps", "6"], repo_root)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["schema"] == "rcx-world-trace.v1"
    assert data["world"] == "pingpong"
    assert data["seed"] == "ping"
    assert data["max_steps"] == 6
    assert isinstance(data.get("trace"), list)
