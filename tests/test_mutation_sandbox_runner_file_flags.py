from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_mutation_sandbox_runner_none_still_works(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"
    p = _run(["bash", "scripts/mutation_sandbox.sh", str(w), "--out-dir", str(out), "--run", "--score", "--runner", "none", "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["run"]["runner"] == "none"
    assert obj["comparison"]["enabled"] is True


def test_mutation_sandbox_runner_trace_cli_does_not_crash(tmp_path: Path):
    # We don't assume the CLI can execute arbitrary tiny worlds; we only assert no crash.
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"
    p = _run(["bash", "scripts/mutation_sandbox.sh", str(w), "--out-dir", str(out), "--run", "--runner", "trace-cli", "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["run"]["runner"] == "trace-cli"
    assert Path(obj["paths"]["run_dir"]).is_dir()
