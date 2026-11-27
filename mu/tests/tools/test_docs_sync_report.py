"""
Smoke tests for tools/docs_sync_report.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


from tests.repo_root import REPO_ROOT
SCRIPT = REPO_ROOT / "tools" / "docs" / "docs_sync_report.py"
REAL_TOOLS = (REPO_ROOT / "mu" / "tools").resolve()


def _fixture_env(home: Path) -> dict[str, str]:
    """Child env that selects no inherited repository, index or git config."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.pop("PYTHONPATH", None)
    env.pop("XDG_CONFIG_HOME", None)
    env["HOME"] = str(home)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _git(root: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        env=env,
        capture_output=True,
        timeout=30,
        check=True,
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_report(root: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    """Run the real CLI in a fresh child, as check_docs_consistency.sh does."""
    return subprocess.run(
        [sys.executable, str(root / "tools" / "docs" / "docs_sync_report.py"), *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _ignored_copies_fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A work tree laid out like a lane: ``tools`` links to this repo's mu/tools.

    The Codex import-sync mirrors (.agents/, .codex/) are ignored through
    .git/info/exclude, as in the lanes, and one docs/ subfolder is ignored
    through .gitignore. Each ignored file would be a violation if walked.
    """
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    env = _fixture_env(home)
    _git(root, env, "init", "-q")
    (root / "tools").symlink_to(REAL_TOOLS, target_is_directory=True)
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("/.agents/\n/.codex/\n")
    _write(root / ".gitignore", "/docs/ghost/\n")
    _write(root / "README.md", "# fixture\n")
    _write(root / "gone.md", "# tracked, then deleted from the work tree\n")
    _git(root, env, "add", "--", ".gitignore", "README.md", "gone.md")
    (root / "gone.md").unlink()
    _write(root / ".agents" / "skills" / "x" / "SKILL.md", "## NOW\nmirror copy\n")
    _write(root / ".codex" / "AGENTS.md", "## NEXT\nmirror copy\n")
    _write(root / "docs" / "ghost" / "only.md", "# ignored docs subfolder\n")
    # Untracked and not ignored, but exempt: still classified, and skipped.
    _write(root / ".scratch" / "copy" / "TASKS.md", "## NOW\nscratch copy\n")
    return root, env


def test_docs_sync_report_check_passes_with_only_git_ignored_copies(tmp_path):
    """Ignored import-sync copies alone must not fail --check (the R13 stop)."""
    root, env = _ignored_copies_fixture(tmp_path)

    result = _run_report(root, env, "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Unclassified markdown files: 0" in result.stdout
    assert "Unregistered docs subfolders: 0" in result.stdout
    assert "Tracker section placement violations: 0" in result.stdout


def test_docs_sync_report_still_reports_untracked_unignored_markdown(tmp_path):
    """Untracked, non-ignored markdown stays in scope for every check."""
    root, env = _ignored_copies_fixture(tmp_path)
    _write(root / "stray" / "notes.md", "## NEXT\nuntracked, not ignored\n")
    _write(root / "docs" / "fresh" / "new.md", "# untracked docs subfolder\n")

    result = _run_report(root, env, "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "unclassified_markdown": ["docs/fresh/new.md", "stray/notes.md"],
        "unregistered_docs_subfolders": ["fresh"],
        "tracker_section_violations": [{"path": "stray/notes.md", "section": "NEXT"}],
    }

    check = _run_report(root, env, "--check")
    assert check.returncode == 1, check.stdout + check.stderr
    assert "  - stray/notes.md" in check.stdout


def test_docs_sync_report_fails_closed_without_a_git_listing(tmp_path):
    """Outside a git work tree the report refuses instead of walking the filesystem."""
    root = tmp_path / "norepo"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    (root / "tools").symlink_to(REAL_TOOLS, target_is_directory=True)
    _write(root / "stray.md", "# would be unclassified\n")
    env = _fixture_env(home)
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path.resolve())

    for args in (("--check",), ("--json",)):
        result = _run_report(root, env, *args)
        assert result.returncode == 2, result.stdout + result.stderr
        assert result.stdout == ""
        assert "docs_sync_report: cannot list git-visible markdown" in result.stderr


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
