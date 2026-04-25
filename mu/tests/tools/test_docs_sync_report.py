"""
Smoke tests for tools/docs_sync_report.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


from tests.repo_root import REPO_ROOT
SCRIPT = REPO_ROOT / "tools" / "docs" / "docs_sync_report.py"


def test_docs_sync_report_json_output_has_expected_keys():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert "unclassified_markdown" in payload
    assert "unregistered_docs_subfolders" in payload
    assert "tracker_section_violations" in payload


def test_docs_sync_report_check_mode_passes_in_repo_state():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_sync_report_ignores_tracker_sections_in_exempt_paths():
    scratch_tasks = REPO_ROOT / ".scratch" / "pytest_docs_sync_exempt" / "TASKS.md"
    scratch_tasks.parent.mkdir(parents=True, exist_ok=True)
    scratch_tasks.write_text("## NOW\nscratch copy\n", encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    finally:
        scratch_tasks.unlink(missing_ok=True)
        scratch_tasks.parent.rmdir()

    payload = json.loads(result.stdout)
    assert {
        "path": ".scratch/pytest_docs_sync_exempt/TASKS.md",
        "section": "NOW",
    } not in payload["tracker_section_violations"]
