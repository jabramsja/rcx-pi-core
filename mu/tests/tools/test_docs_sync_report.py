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
