from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_clean_print_requires_summary_file(tmp_path: Path):
    summary = tmp_path / "summary.txt"
    work = tmp_path / "work.log"

    # Command does nothing and does not create summary -> should fail
    p = _run(
        [
            "bash",
            "scripts/clean_print.sh",
            "--summary",
            str(summary),
            "--work",
            str(work),
            "--",
            "bash",
            "-lc",
            "true",
        ]
    )
    assert p.returncode == 1
