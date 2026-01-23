import shutil
import subprocess

import pytest


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return (p.stdout or "") + (p.stderr or "")


def _git_status_tracked_only() -> str:
    # Ignore untracked files (like this test itself before commit).
    return _run(["git", "status", "--porcelain=v1", "--untracked-files=no"]).strip()


def _git_diff_names() -> str:
    # Any tracked content changes will show up here.
    return _run(["git", "diff", "--name-only"]).strip()


@pytest.mark.skipif(shutil.which("dot") is None, reason="graphviz 'dot' not installed")
def test_build_orbit_artifacts_is_idempotent_for_tracked_files():
    # Baseline (tracked-only)
    before_status = _git_status_tracked_only()
    before_diff = _git_diff_names()
    assert before_diff == "", f"Repo already has tracked diffs before test:\n{before_diff}"

    # Run twice to catch churn
    _run(["bash", "scripts/build_orbit_artifacts.sh"])
    _run(["bash", "scripts/build_orbit_artifacts.sh"])

    # Tracked-only cleanliness must match baseline
    after_status = _git_status_tracked_only()
    after_diff = _git_diff_names()

    assert after_diff == "", f"Tracked files changed after build_orbit_artifacts.sh:\n{after_diff}"
    assert after_status == before_status, (
        "Tracked working tree status changed after build_orbit_artifacts.sh.\n"
        f"before:\n{before_status}\n\nafter:\n{after_status}"
    )
