from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_mutation_sandbox_does_not_crash_when_world_score_returns_rc1(tmp_path: Path):
    # Create a trace-shaped JSON with 4 steps
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps([{"state": 1}, {"state": 2}, {"state": 3}, {"state": 4}]), encoding="utf-8")

    # Confirm world_score can return rc=1 with max-steps=3
    p = _run(["bash", "scripts/world_score.sh", str(trace), "--json", "--max-steps", "3"])
    assert p.returncode == 1

    # Now run mutation_sandbox in a mode that won't produce json, but we at least ensure the script still runs.
    # The real regression we care about: mutation_sandbox internal code no longer has a NameError on rc=1 path.
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n[b] -> lobe\n[c] -> sink\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"

    p2 = _run(["bash", "scripts/mutation_sandbox.sh", str(w), "--out-dir", str(out), "--run", "--score", "--runner", "none", "--max-steps", "3", "--json"])
    assert p2.returncode == 0
    obj = json.loads(p2.stdout)
    assert obj["comparison"]["enabled"] is True
