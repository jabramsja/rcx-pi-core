from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_runner_omega_cli_is_skipped_for_world_like_mu_file(tmp_path: Path):
    # Looks like a "world" file (starts with '['), not a motif expression.
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n[b] -> lobe\n", encoding="utf-8")

    out = tmp_path / "sandbox_runs"
    p = _run(["bash", "scripts/mutation_sandbox.sh", str(w), "--out-dir", str(out), "--run", "--score", "--runner", "omega-cli", "--json"])
    assert p.returncode == 0

    obj = json.loads(p.stdout)
    run = obj["run"]
    assert run["runner"] == "omega-cli"

    b = run["baseline"]
    m = run["mutated"]
    assert b.get("skipped") is True
    assert m.get("skipped") is True
    assert b.get("json_ok") is False
    assert m.get("json_ok") is False

    # comparison still enabled, but no scores because no json
    assert obj["comparison"]["enabled"] is True
    assert obj["comparison"]["scores"]["baseline"] is None
    assert obj["comparison"]["scores"]["mutated"] is None
