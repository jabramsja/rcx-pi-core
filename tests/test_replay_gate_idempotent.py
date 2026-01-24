from __future__ import annotations

import subprocess
from pathlib import Path


def _repo_root() -> Path:
    # tests/ -> repo root
    return Path(__file__).resolve().parents[1]


def _git_diff_tracked_names(cwd: Path) -> str:
    """
    Return tracked diffs, excluding build/install byproducts that can be touched during CI.
    """
    r = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--",
            ".",
            ":(exclude)rcx_pi_core.egg-info/PKG-INFO",
            ":(exclude)rcx_pi_core.egg-info/SOURCES.txt",
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return (r.stdout or "").strip()


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_replay_is_idempotent_for_tracked_files(tmp_path: Path) -> None:
    """
    Determinism gate (v1):
    Running replay on a fixed fixture must not change any tracked files.
    Output is allowed only to explicit --out (typically untracked temp paths).
    """
    root = _repo_root()

    before = _git_diff_tracked_names(root)
    assert before == "", f"Repo already has tracked diffs before test:\n{before}"

    trace = root / "tests" / "fixtures" / "traces" / "minimal.v1.jsonl"
    assert trace.exists(), f"Missing fixture: {trace}"

    out = tmp_path / "canon.jsonl"
    r = _run(
        [
            "python3",
            "-m",
            "rcx_pi.rcx_cli",
            "replay",
            "--trace",
            str(trace),
            "--out",
            str(out),
        ],
        root,
    )
    assert r.returncode == 0, (r.stdout or "") + "\n" + (r.stderr or "")

    after = _git_diff_tracked_names(root)
    assert after == "", f"Replay changed tracked files (forbidden):\n{after}"
