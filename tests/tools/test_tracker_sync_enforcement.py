"""
Tests for tools/enforce_tracker_sync.sh.

These tests validate the fail-closed policy:
- If rcx_pi/selfhost/ or mu/ changes, STATUS.md or TASKS.md must also change.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "enforce_tracker_sync.sh"


@pytest.mark.skipif(os.name == "nt", reason="bash script test")
class TestTrackerSyncEnforcement:
    def run_script(self, *files: str) -> subprocess.CompletedProcess[str]:
        cmd = ["bash", str(SCRIPT), "--files", *files]
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_no_core_changes_passes(self):
        result = self.run_script("docs/core/BootstrapPrimitives.v0.md")
        assert result.returncode == 0
        assert "no core changes detected" in result.stdout.lower()

    def test_core_with_status_passes(self):
        result = self.run_script("rcx_pi/selfhost/step_mu.py", "STATUS.md")
        assert result.returncode == 0
        assert "tracker sync ok" in result.stdout.lower()

    def test_core_with_tasks_passes(self):
        result = self.run_script("mu/closures/recurrence.v1.json", "TASKS.md")
        assert result.returncode == 0
        assert "tracker sync ok" in result.stdout.lower()

    def test_core_without_trackers_fails(self):
        result = self.run_script("rcx_pi/selfhost/step_mu.py")
        assert result.returncode == 1
        assert "tracker sync violation" in result.stdout.lower()
        assert "status.md" in result.stdout.lower()
        assert "tasks.md" in result.stdout.lower()

    def test_core_plus_other_docs_still_fails(self):
        result = self.run_script("mu/closures/exhaustion.v1.json", "README.md", "docs/core/RCXKernel.v0.md")
        assert result.returncode == 1
        assert "tracker sync violation" in result.stdout.lower()

