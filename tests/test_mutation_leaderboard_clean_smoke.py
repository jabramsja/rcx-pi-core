from __future__ import annotations

import subprocess


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_mutation_leaderboard_clean_script_runs():
    # Smoke test: should exit 0 even if scores are None (e.g. runner skipping)
    p = _run(["bash", "scripts/mutation_leaderboard_clean.sh", "--seeds", "2", "--runner", "auto"])
    assert p.returncode == 0
    assert "== RCX: mutation sandbox leaderboard (clean) ==" in p.stdout
