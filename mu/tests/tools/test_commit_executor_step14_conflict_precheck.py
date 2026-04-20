"""Tests for commit_executor Step 14 CONFLICTING/DIRTY pre-check.

Before Step 14 invokes `gh pr checks --watch`, it queries `gh pr view`
to detect mergeable=CONFLICTING / mergeStateStatus=DIRTY. For such
PRs, GitHub Actions silently skips pull_request-triggered workflows
(2026-04-17 learning), so polling cannot succeed within the CI
timeout. Detecting and fail-fast eliminates the wasted 15-min poll
documented in the 2026-04-20 learning entry.

Covers:
1. CONFLICTING detection returns human-readable marker
2. DIRTY (mergeStateStatus) detection returns marker
3. MERGEABLE + CLEAN returns None (normal polling path)
4. gh error fails open (return None — pre-check is perf optimization)
5. Malformed JSON fails open
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


commit_mod = load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)


def _make_gh_result(*, returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh", "pr", "view"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


class TestCheckPrConflictState:
    def test_conflicting_mergeable_returns_marker(self, tmp_path):
        payload = '{"mergeable":"CONFLICTING","mergeStateStatus":"DIRTY"}'
        with patch.object(
            commit_mod.subprocess, "run",
            return_value=_make_gh_result(stdout=payload),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="123", log=None
            )
        assert result == "mergeable=CONFLICTING"

    def test_dirty_only_returns_marker(self, tmp_path):
        payload = '{"mergeable":"MERGEABLE","mergeStateStatus":"DIRTY"}'
        with patch.object(
            commit_mod.subprocess, "run",
            return_value=_make_gh_result(stdout=payload),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="456", log=None
            )
        assert result == "mergeStateStatus=DIRTY"

    def test_mergeable_clean_returns_none(self, tmp_path):
        payload = '{"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN"}'
        with patch.object(
            commit_mod.subprocess, "run",
            return_value=_make_gh_result(stdout=payload),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="789", log=None
            )
        assert result is None

    def test_mergeable_blocked_returns_none(self, tmp_path):
        payload = '{"mergeable":"MERGEABLE","mergeStateStatus":"BLOCKED"}'
        with patch.object(
            commit_mod.subprocess, "run",
            return_value=_make_gh_result(stdout=payload),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="790", log=None
            )
        assert result is None

    def test_gh_nonzero_exit_fails_open(self, tmp_path):
        with patch.object(
            commit_mod.subprocess, "run",
            return_value=_make_gh_result(returncode=1, stdout=""),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="791", log=None
            )
        assert result is None

    def test_gh_subprocess_error_fails_open(self, tmp_path):
        with patch.object(
            commit_mod.subprocess, "run",
            side_effect=subprocess.SubprocessError("gh not found"),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="792", log=None
            )
        assert result is None

    def test_malformed_json_fails_open(self, tmp_path):
        with patch.object(
            commit_mod.subprocess, "run",
            return_value=_make_gh_result(stdout="not valid json"),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="793", log=None
            )
        assert result is None

    def test_empty_stdout_fails_open(self, tmp_path):
        with patch.object(
            commit_mod.subprocess, "run",
            return_value=_make_gh_result(stdout=""),
        ):
            result = commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path, pr_number="794", log=None
            )
        assert result is None

    def test_log_callback_invoked_on_error(self, tmp_path):
        captured: list[str] = []
        with patch.object(
            commit_mod.subprocess, "run",
            side_effect=subprocess.SubprocessError("boom"),
        ):
            commit_mod._check_pr_conflict_state(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="795",
                log=captured.append,
            )
        assert captured, "expected log callback to record pre-check diagnostic"
        assert "Step 14 pre-check" in captured[0]
