from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_leaderboard_auto_uses_none_for_world_like_mu(tmp_path: Path):
    # world-like .mu (rules)
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n[b] -> lobe\n", encoding="utf-8")

    p = _run(["bash", "scripts/mutation_leaderboard_clean.sh", "--world", str(w), "--seeds", "1", "--runner", "auto"])
    assert p.returncode == 0
    assert "-- detected: world --" in p.stdout
    assert "-- runner: none" in p.stdout  # auto selection should pick none for world-like
