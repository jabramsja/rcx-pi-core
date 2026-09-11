"""Public CLI regressions using only disposable repositories and directories."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import errno
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

import pytest

from tests.repo_root import REPO_ROOT


CLI = REPO_ROOT / "mu" / "tools" / "executors" / "workingrcx_fleet_census.py"


@contextmanager
def _fixture_git_env(**extra_env):
    """Isolate runner config while allowing explicit fixture HOME/XDG/PATH overrides."""
    with tempfile.TemporaryDirectory(prefix="census-fixture-git-") as directory:
        home = Path(directory) / "home"
        home.mkdir()
        bindir = Path(directory) / "bin"
        bindir.mkdir()
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home),
                   GIT_OPTIONAL_LOCKS="0", PYTHONDONTWRITEBYTECODE="1")
        env.update(extra_env)
        real_git = shutil.which("git", path=env["PATH"])
        assert real_git
        wrapper = bindir / "git"
        # The production CLI drops GIT_* overrides before probing effective config.
        # Apply system-config isolation at exec; fixture global/includes stay real.
        wrapper.write_text(f'#!/bin/sh\nGIT_CONFIG_NOSYSTEM=1 exec {shlex.quote(real_git)} "$@"\n')
        wrapper.chmod(0o700)
        env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
        yield env


def _git(root: Path, *args: str) -> str:
    with _fixture_git_env() as env:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-c", "init.defaultBranch=main",
             "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
             "-c", "user.name=Census Fixture", "-c", "user.email=census@example.invalid",
             "-C", str(root), *args],
            env=env, capture_output=True, check=True,
        )
    return os.fsdecode(result.stdout).removesuffix("\n")


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "tracked.txt").write_text("committed fixture\n")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "-qm", "fixture")
    return path


def _cli(fleet: Path, anchor: Path, output: Path, **extra_env) -> tuple[subprocess.CompletedProcess, dict]:
    with _fixture_git_env(**extra_env) as env:
        result = subprocess.run(
            [sys.executable, str(CLI), "--fleet-root", str(fleet),
             "--anchor-repo", str(anchor), "--output", str(output)],
            env=env, capture_output=True,
        )
    report = json.loads(output.read_text(encoding="ascii"))
    assert report["entry_count"] == len(report["entries"])
    assert all(row["classification"] == "UNCLASSIFIED" for row in report["entries"])
    return result, report


def _rows(report: dict) -> dict[str, dict]:
    return {row["path"]: row for row in report["entries"]}


def _snapshot(root: Path) -> dict:
    """Check both bytes and mtimes, including Git indexes, refs and directory entries."""
    result = {}
    for path in [root, *root.rglob("*")]:
        info = path.lstat()
        payload = None
        if stat.S_ISREG(info.st_mode):
            payload = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_symlink():
            payload = os.readlink(path)
        result[str(path.relative_to(root))] = (info.st_mode, info.st_mtime_ns, payload)
    return result


def test_cli_unions_both_sources_counts_dirty_entries_and_preserves_targets(tmp_path):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    linked = fleet / "wOrKiNgRcX-linked"
    _git(anchor, "worktree", "add", "--detach", str(linked), "HEAD")
    outside = tmp_path / "outside" / "registered-without-prefix"
    outside.parent.mkdir()
    _git(anchor, "worktree", "add", "--detach", str(outside), "HEAD")
    dirty = _repo(fleet / "WorkingRCX-dirty")
    (dirty / "tracked.txt").write_text("PRIVATE_CONTENT_MUST_NOT_APPEAR\n")
    (dirty / "PRIVATE_UNTRACKED_DIRECTORY").mkdir()
    (dirty / "PRIVATE_UNTRACKED_DIRECTORY" / "one").write_text("one")
    (dirty / "PRIVATE_UNTRACKED_DIRECTORY" / "two").write_text("two")
    (fleet / "unrelated" / "WorkingRCX-nested").mkdir(parents=True)
    # A configured fsmonitor must not execute during this read-only census.
    monitor = tmp_path / "fsmonitor"
    marker = tmp_path / "fsmonitor-ran"
    monitor.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
    monitor.chmod(0o700)
    _git(dirty, "config", "core.fsmonitor", str(monitor))
    before_fleet, before_outside = _snapshot(fleet), _snapshot(outside.parent)
    output = tmp_path / "census.json"

    result, report = _cli(
        fleet, anchor, output,
        GIT_DIR=str(dirty / ".git"), GIT_WORK_TREE=str(dirty),
        GIT_INDEX_FILE=str(tmp_path / "wrong-index"), GIT_OPTIONAL_LOCKS="1",
    )

    assert result.returncode == 0, result.stderr
    assert report["coverage_complete"] is True
    rows = _rows(report)
    assert set(rows) == {str(path) for path in (anchor, linked, outside, dirty)}
    assert rows[str(anchor)]["sources"] == ["fleet_root", "anchor_worktrees"]
    assert rows[str(linked)]["sources"] == ["fleet_root", "anchor_worktrees"]
    assert rows[str(outside)]["sources"] == ["anchor_worktrees"]
    assert rows[str(dirty)]["sources"] == ["fleet_root"]
    assert rows[str(dirty)]["registration_status"] == "not_registered"
    assert rows[str(anchor)]["repository_kind"] == "standalone_repository"
    assert rows[str(linked)]["repository_kind"] == "linked_worktree"
    assert rows[str(linked)]["git"]["branch_status"] == "detached"
    assert rows[str(anchor)]["git"]["branch"] == "refs/heads/main"
    assert rows[str(linked)]["git"]["HEAD"] == rows[str(anchor)]["git"]["HEAD"]
    assert rows[str(linked)]["git"]["common_dir"] == str(anchor / ".git")
    assert rows[str(dirty)]["git"]["dirty_status"] == "dirty"
    assert rows[str(dirty)]["git"]["dirty_counts"] == {
        "entries": 2, "tracked": 1, "untracked": 1, "staged": 0, "unstaged": 1, "unmerged": 0,
    }
    assert rows[str(anchor)]["git"]["dirty_status"] == "clean"
    assert "PRIVATE_" not in output.read_text()
    assert _snapshot(fleet) == before_fleet
    assert _snapshot(outside.parent) == before_outside
    assert not marker.exists()
    assert not (tmp_path / "wrong-index").exists()
    assert datetime.fromisoformat(report["started_at"]) <= datetime.fromisoformat(report["finished_at"])
    for row in rows.values():
        assert row["errors"] == []
        assert row["inspection_status"] == "ok"
        assert report["started_at"] <= row["observed_started_at"] <= row["observed_finished_at"] <= report["finished_at"]


def _filter_trigger(target: Path, script: Path, operation: str) -> str:
    """A status-triggered filter would change both a marker and tracked bytes."""
    script.write_text(
        "from pathlib import Path\nimport sys\n"
        f"Path({str(target / 'FILTER_EXECUTED')!r}).touch()\n"
        f"Path({str(target / 'tracked.txt')!r}).write_text('mutated by filter\\n')\n"
        + ("sys.stdout.buffer.write(sys.stdin.buffer.read())\n" if operation == "clean"
           else "sys.exit(1)\n")
    )
    tracked = target / "tracked.txt"
    tracked.write_text("COMMITTED FIXTURE\n")  # Same length, changed bytes and stat.
    info = tracked.stat()
    os.utime(tracked, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
    return shlex.join([sys.executable, str(script)])


@pytest.mark.parametrize("operation", ["clean", "process"])
@pytest.mark.parametrize("config_source", ["home", "xdg", "system"])
def test_fixture_git_isolation_preserves_clean_dirty_counts_with_ambient_filters(
    tmp_path, monkeypatch, operation, config_source,
):
    ambient = tmp_path / "ambient"
    home = ambient / "home"
    xdg = ambient / "xdg"
    home.mkdir(parents=True)
    (xdg / "git").mkdir(parents=True)
    marker = ambient / "FILTER_EXECUTED"
    script = ambient / "filter.py"
    script.write_text(
        "from pathlib import Path\nimport sys\n"
        f"Path({str(marker)!r}).touch()\n"
        + ("sys.stdout.buffer.write(sys.stdin.buffer.read())\n" if operation == "clean"
           else "sys.exit(1)\n")
    )
    attributes = ambient / "attributes"
    attributes.write_text("tracked.txt filter=ambient-fixture\n")
    config = {"home": home / ".gitconfig", "xdg": xdg / "git" / "config",
              "system": ambient / "system.config"}[config_source]
    _git(tmp_path, "config", "--file", str(config), f"filter.ambient-fixture.{operation}",
         shlex.join([sys.executable, str(script)]))
    _git(tmp_path, "config", "--file", str(config), "core.attributesFile", str(attributes))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    if config_source == "system":
        # Supply a disposable system config at Git exec, without touching /etc.
        env = _git_wrapper(tmp_path, f"os.environ['GIT_CONFIG_SYSTEM'] = {str(config)!r}\n")
        monkeypatch.setenv("PATH", env["PATH"])

    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    dirty = _repo(fleet / "WorkingRCX-dirty")
    (dirty / "tracked.txt").write_text("changed fixture\n")
    (dirty / "untracked.txt").write_text("untracked fixture\n")
    before_fleet, before_ambient = _snapshot(fleet), _snapshot(ambient)

    result, report = _cli(fleet, anchor, tmp_path / "census.json")

    assert not marker.exists()
    assert _snapshot(fleet) == before_fleet
    assert _snapshot(ambient) == before_ambient
    assert result.returncode == 0, result.stderr
    assert report["coverage_complete"] is True
    rows = _rows(report)
    assert set(rows) == {str(anchor), str(dirty)}
    assert rows[str(anchor)]["git"]["dirty_status"] == "clean"
    assert rows[str(anchor)]["git"]["dirty_counts"] == {
        "entries": 0, "tracked": 0, "untracked": 0, "staged": 0, "unstaged": 0, "unmerged": 0,
    }
    assert rows[str(dirty)]["git"]["dirty_status"] == "dirty"
    assert rows[str(dirty)]["git"]["dirty_counts"] == {
        "entries": 2, "tracked": 1, "untracked": 1, "staged": 0, "unstaged": 1, "unmerged": 0,
    }
    assert all(row["inspection_status"] == "ok" and row["errors"] == [] for row in rows.values())


@pytest.mark.parametrize("operation", ["clean", "process"])
@pytest.mark.parametrize("config_source", ["local", "include", "global", "worktree"])
def test_cli_skips_configured_filters_without_executing_or_mutating_targets(
    tmp_path, operation, config_source,
):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    (anchor / ".gitattributes").write_text("tracked.txt filter=census-fixture\n")
    _git(anchor, "add", ".gitattributes")
    _git(anchor, "commit", "-qm", "filter attributes")
    target = anchor
    if config_source == "worktree":
        target = fleet / "WorkingRCX-linked"
        _git(anchor, "worktree", "add", "--detach", str(target), "HEAD")
        _git(anchor, "config", "extensions.worktreeConfig", "true")
    command = _filter_trigger(target, tmp_path / "filter.py", operation)
    key = f"filter.census-fixture.{operation}"
    env = {}
    if config_source == "include":
        config = tmp_path / "included.config"
        _git(target, "config", "--file", str(config), key, command)
        _git(target, "config", "include.path", str(config))
    elif config_source == "global":
        config_home = tmp_path / "config-home"
        config_home.mkdir()
        _git(target, "config", "--file", str(config_home / ".gitconfig"), key, command)
        env = {"HOME": str(config_home), "XDG_CONFIG_HOME": str(config_home)}
    else:
        _git(target, "config", *(["--worktree"] if config_source == "worktree" else []), key, command)
    before = _snapshot(fleet)

    result, report = _cli(fleet, anchor, tmp_path / "census.json", **env)

    assert not (target / "FILTER_EXECUTED").exists()
    assert _snapshot(fleet) == before
    assert result.returncode == 0, result.stderr
    assert report["coverage_complete"] is True
    row = _rows(report)[str(target)]
    assert row["inspection_status"] == "partial"
    assert row["git"]["HEAD"]
    assert row["git"]["dirty_status"] == "unknown"
    assert row["git"]["dirty_counts"] is None
    assert any("filter" in error["message"] for error in row["errors"])
    assert command not in (tmp_path / "census.json").read_text()


@pytest.mark.parametrize("operation", ["clean", "process"])
def test_cli_does_not_execute_filters_in_submodule_dirty_inspection(tmp_path, operation):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    source = _repo(tmp_path / "submodule-source")
    (source / ".gitattributes").write_text("tracked.txt filter=census-fixture\n")
    _git(source, "add", ".gitattributes")
    _git(source, "commit", "-qm", "filter attributes")
    _git(anchor, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(source), "component")
    _git(anchor, "commit", "-qm", "submodule")
    component = anchor / "component"
    command = _filter_trigger(component, tmp_path / "filter.py", operation)
    _git(component, "config", f"filter.census-fixture.{operation}", command)
    before = _snapshot(fleet)

    result, report = _cli(fleet, anchor, tmp_path / "census.json")

    assert not (component / "FILTER_EXECUTED").exists()
    assert _snapshot(fleet) == before
    assert result.returncode == 0, result.stderr
    assert report["coverage_complete"] is True
    assert set(_rows(report)) == {str(anchor)}
    row = _rows(report)[str(anchor)]
    assert row["inspection_status"] == "partial"
    assert row["git"]["HEAD"]
    assert row["git"]["dirty_status"] == "unknown"
    assert row["git"]["dirty_counts"] is None
    assert any("submodule" in error["message"] for error in row["errors"])


def test_cli_retains_nonrepositories_missing_registration_and_symlink_kinds(tmp_path):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    missing = tmp_path / "missing-registered"
    _git(anchor, "worktree", "add", "--detach", str(missing), "HEAD")
    shutil.rmtree(missing)
    ordinary = fleet / "WorkingRCX-not-repo"
    ordinary.mkdir()
    plain_file = fleet / "WorkingRCX-file"
    plain_file.write_text("not a repository")
    dangling = fleet / "WorkingRCX-dangling"
    dangling.symlink_to(tmp_path / "absent")
    alias = fleet / "WorkingRCX-alias"
    alias.symlink_to(anchor, target_is_directory=True)
    broken = fleet / "WorkingRCX-broken"
    broken.mkdir()
    (broken / ".git").write_text("gitdir: /nonexistent/census-fixture-gitdir\n")

    result, report = _cli(fleet, anchor, tmp_path / "census.json")

    assert result.returncode == 0
    rows = _rows(report)
    assert rows[str(ordinary)]["repository_kind"] == "non_repository"
    assert rows[str(plain_file)]["entry_kind"] == "file"
    assert rows[str(plain_file)]["repository_kind"] == "non_repository"
    assert rows[str(dangling)]["entry_kind"] == "symlink"
    assert rows[str(dangling)]["availability_status"] == "missing"
    assert rows[str(alias)]["entry_kind"] == "symlink"
    assert rows[str(alias)]["git"]["root"] == str(anchor)
    missing_row = rows[str(missing)]
    assert missing_row["entry_kind"] == missing_row["inspection_status"] == "missing"
    assert missing_row["registration_status"] == "registered"
    assert missing_row["registered_worktrees"][0]["HEAD"]
    assert missing_row["git"]["dirty_status"] == "unknown"
    assert missing_row["errors"]
    assert rows[str(broken)]["inspection_status"] == "error"
    assert rows[str(broken)]["repository_kind"] == "unknown"
    assert rows[str(broken)]["errors"]


def test_cli_does_not_mistake_containing_repository_for_an_entry_root(tmp_path):
    anchor = _repo(tmp_path / "anchor")
    child = anchor / "WorkingRCX-ordinary-child"
    child.mkdir()
    result, report = _cli(anchor, anchor, tmp_path / "census.json")
    assert result.returncode == 0
    row = _rows(report)[str(child)]
    assert row["repository_kind"] == "non_repository"
    assert row["git"]["dirty_status"] == "unknown"


def test_cli_counts_rename_once_and_preserves_newlines_in_git_paths(tmp_path):
    anchor = _repo(tmp_path / 'WorkingRCX-"\\\ntrailing \n')
    linked = tmp_path / 'registered-"\\\ntrailing \n'
    _git(anchor, "worktree", "add", "--detach", str(linked), "HEAD")
    _git(anchor, "mv", "tracked.txt", "PRIVATE_RENAMED\nfile")
    result, report = _cli(tmp_path, anchor, tmp_path / "census.json")
    assert result.returncode == 0
    rows = _rows(report)
    assert set(rows) == {str(anchor), str(linked)}
    assert rows[str(anchor)]["git"]["root"] == str(anchor)
    assert rows[str(anchor)]["git"]["common_dir"] == str(anchor / ".git")
    assert rows[str(anchor)]["git"]["dirty_counts"] == {
        "entries": 1, "tracked": 1, "untracked": 0, "staged": 1, "unstaged": 0, "unmerged": 0,
    }
    assert "PRIVATE_RENAMED" not in (tmp_path / "census.json").read_text()


@pytest.mark.skipif(os.name != "posix", reason="POSIX byte pathname fixture")
def test_cli_round_trips_non_utf8_path_bytes(tmp_path):
    anchor = _repo(tmp_path / "WorkingRCX-main")
    raw = os.fsencode(tmp_path) + b"/WorkingRCX-\xff"
    try:
        os.mkdir(raw)
    except OSError as exc:
        if exc.errno in (errno.EILSEQ, errno.EINVAL):
            pytest.skip("Filesystem rejects non-UTF-8 pathnames")
        raise
    result, report = _cli(tmp_path, anchor, tmp_path / "census.json")
    assert result.returncode == 0
    assert raw in {os.fsencode(row["path"]) for row in report["entries"]}
    assert "\ufffd" not in (tmp_path / "census.json").read_text()


def _git_wrapper(tmp_path: Path, body: str) -> dict:
    real_git = shutil.which("git")
    assert real_git
    bindir = tmp_path / "test-bin"
    bindir.mkdir()
    wrapper = bindir / "git"
    wrapper.write_text(
        f"#!{sys.executable}\nimport os, sys\n"
        "assert os.environ.get('GIT_OPTIONAL_LOCKS') == '0'\n"
        "assert '--no-optional-locks' in sys.argv\n"
        + body + f"\nos.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n"
    )
    wrapper.chmod(0o700)
    return {"PATH": str(bindir) + os.pathsep + os.environ["PATH"]}


@pytest.mark.parametrize("operation", ["rev-parse", "status", "config", "ls-files"])
def test_cli_keeps_explicit_inspection_failure_without_clean_claim(tmp_path, operation):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    target = _repo(fleet / "WorkingRCX-error")
    env = _git_wrapper(tmp_path,
        f"if sys.argv[sys.argv.index('-C') + 1] == {str(target)!r} and {operation!r} in sys.argv:\n"
        "    print('forced inspection failure', file=sys.stderr)\n"
        "    sys.exit(73)\n")
    result, report = _cli(fleet, anchor, tmp_path / "census.json", **env)
    assert result.returncode == 0
    assert report["coverage_complete"] is True  # Enumeration succeeded; inspection did not.
    row = _rows(report)[str(target)]
    assert row["inspection_status"] == ("error" if operation == "rev-parse" else "partial")
    assert row["git"]["dirty_status"] == "unknown"
    assert row["git"]["dirty_counts"] is None
    assert row["errors"][0]["returncode"] == 73
    assert "forced inspection failure" in row["errors"][0]["stderr"]
    if operation != "rev-parse":
        assert row["git"]["HEAD"]
        assert row["git"]["common_dir"] == str(target / ".git")


@pytest.mark.parametrize("failed_source", ["fleet_root", "anchor_worktrees"])
def test_cli_reports_top_level_failure_with_partial_coverage(tmp_path, failed_source):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    result, report = _cli(
        tmp_path / "absent" if failed_source == "fleet_root" else fleet,
        tmp_path / "absent" if failed_source == "anchor_worktrees" else anchor,
        tmp_path / "census.json",
    )
    assert result.returncode == 1
    assert report["coverage_complete"] is False
    assert report["enumeration"][failed_source]["status"] == "error"
    assert report["enumeration"][failed_source]["errors"]
    row = _rows(report)[str(anchor)]
    if failed_source == "anchor_worktrees":
        assert row["registration_status"] == "unknown"


def test_cli_retains_paths_from_failed_or_malformed_worktree_listing(tmp_path):
    anchor = _repo(tmp_path / "WorkingRCX-main")
    missing = tmp_path / "outside-prefix-missing"
    raw = b"worktree " + os.fsencode(missing) + b"\0\0malformed\0\0"
    env = _git_wrapper(tmp_path,
        "if 'worktree' in sys.argv:\n"
        f"    sys.stdout.buffer.write({raw!r})\n"
        "    sys.exit(74)\n")
    result, report = _cli(tmp_path, anchor, tmp_path / "census.json", **env)
    assert result.returncode == 1
    assert report["coverage_complete"] is False
    assert len(report["enumeration"]["anchor_worktrees"]["errors"]) == 2
    assert _rows(report)[str(missing)]["inspection_status"] == "missing"
    assert _rows(report)[str(anchor)]["registration_status"] == "unknown"


def test_cli_reports_unsupported_worktree_nul_option_without_fallback(tmp_path):
    anchor = _repo(tmp_path / "WorkingRCX-main")
    env = _git_wrapper(tmp_path,
        "if 'worktree' in sys.argv:\n"
        "    assert '-z' in sys.argv, 'NUL enumeration must not be replaced'\n"
        "    print(\"error: unknown switch `z'\", file=sys.stderr)\n"
        "    sys.exit(129)\n")

    result, report = _cli(tmp_path, anchor, tmp_path / "census.json", **env)

    assert result.returncode == 1
    assert report["coverage_complete"] is False
    enumeration = report["enumeration"]["anchor_worktrees"]
    assert enumeration["status"] == "error"
    assert enumeration["records"] == 0
    assert enumeration["errors"][0]["returncode"] == 129
    assert "unknown switch" in enumeration["errors"][0]["stderr"]
    assert _rows(report)[str(anchor)]["registration_status"] == "unknown"


def test_cli_rejects_legacy_git_echoing_unsupported_common_dir_option(tmp_path):
    anchor = _repo(tmp_path / "WorkingRCX-main")
    env = _git_wrapper(tmp_path,
        "if '--git-common-dir' in sys.argv:\n"
        "    sys.stdout.buffer.write(b'--path-format=absolute\\n.git\\n')\n"
        "    sys.exit(0)\n")

    result, report = _cli(tmp_path, anchor, tmp_path / "census.json", **env)

    assert result.returncode == 0  # Both enumeration sources still succeeded.
    assert report["coverage_complete"] is True
    row = _rows(report)[str(anchor)]
    assert row["inspection_status"] == "partial"
    assert row["repository_kind"] == "unknown"
    assert row["git"]["common_dir"] is None
    assert row["errors"] == [{
        "operation": "git rev-parse --path-format=absolute --git-common-dir",
        "message": "Git did not return the requested absolute path",
    }]


def test_cli_observes_bare_repository_without_claiming_clean_worktree(tmp_path):
    anchor = _repo(tmp_path / "WorkingRCX-main")
    bare = tmp_path / "WorkingRCX-bare"
    _git(tmp_path, "clone", "--bare", str(anchor), str(bare))
    result, report = _cli(tmp_path, anchor, tmp_path / "census.json")
    assert result.returncode == 0
    row = _rows(report)[str(bare)]
    assert row["repository_kind"] == "bare_repository"
    assert row["inspection_status"] == "ok"
    assert row["git"]["HEAD"]
    assert row["git"]["dirty_status"] == "not_applicable"
    assert row["git"]["dirty_counts"] is None


def test_cli_refreshes_existing_census_with_fresh_observations_only(tmp_path):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    removed = fleet / "WorkingRCX-removed"
    removed.mkdir()
    output = tmp_path / "census.json"
    first_result, first = _cli(fleet, anchor, output)
    assert first_result.returncode == 0
    assert _rows(first)[str(anchor)]["git"]["dirty_status"] == "clean"

    removed.rmdir()
    (anchor / "tracked.txt").write_text("changed after the first observation\n")
    before = _snapshot(fleet)
    result, report = _cli(fleet, anchor, output)

    assert result.returncode == 0, result.stderr
    assert report["coverage_complete"] is True
    assert report["started_at"] > first["finished_at"]
    assert set(_rows(report)) == {str(anchor)}
    assert _rows(report)[str(anchor)]["git"]["dirty_status"] == "dirty"
    assert _snapshot(fleet) == before
    assert set(tmp_path.iterdir()) == {fleet, output}


def test_cli_refresh_reports_new_enumeration_failure_instead_of_reusing_success(tmp_path):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    output = tmp_path / "census.json"
    first_result, first = _cli(fleet, anchor, output)
    assert first_result.returncode == 0
    env = _git_wrapper(tmp_path,
        "if 'worktree' in sys.argv:\n"
        "    print('forced enumeration failure', file=sys.stderr)\n"
        "    sys.exit(74)\n")
    before = _snapshot(fleet)

    result, report = _cli(fleet, anchor, output, **env)

    assert result.returncode == 1
    assert report["coverage_complete"] is False
    assert report["started_at"] > first["finished_at"]
    assert report["enumeration"]["anchor_worktrees"]["errors"][0]["returncode"] == 74
    assert _rows(report)[str(anchor)]["registration_status"] == "unknown"
    assert _snapshot(fleet) == before


@pytest.mark.parametrize("changed_input", ["fleet_root", "anchor_repo"])
def test_cli_refuses_to_refresh_census_for_different_inputs(tmp_path, changed_input):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    output = tmp_path / "census.json"
    first_result, _ = _cli(fleet, anchor, output)
    assert first_result.returncode == 0
    before = output.read_bytes(), output.stat().st_mtime_ns
    other_anchor = _repo(tmp_path / "other-fleet" / "WorkingRCX-other")

    result, _ = _cli(
        other_anchor.parent if changed_input == "fleet_root" else fleet,
        other_anchor if changed_input == "anchor_repo" else anchor, output,
    )

    assert result.returncode == 1
    assert b"not a census for this fleet root and anchor" in result.stderr
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_cli_refuses_to_refresh_census_through_a_link(tmp_path, link_kind):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX-main")
    existing = tmp_path / "census.json"
    first_result, _ = _cli(fleet, anchor, existing)
    assert first_result.returncode == 0
    output = tmp_path / "alias.json"
    if link_kind == "symlink":
        output.symlink_to(existing)
    else:
        os.link(existing, output)
    before = _snapshot(tmp_path)

    result, _ = _cli(fleet, anchor, output)

    assert result.returncode == 1
    assert b"Cannot write census artifact" in result.stderr
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("contents", ['{"preserved": true}\n', '[]\n', '{invalid json\n'])
def test_cli_refuses_to_overwrite_unrelated_existing_output(tmp_path, contents):
    anchor = _repo(tmp_path / "WorkingRCX-main")
    existing = tmp_path / "existing.json"
    existing.write_text(contents)
    before = _snapshot(tmp_path)
    with _fixture_git_env() as env:
        result = subprocess.run(
            [sys.executable, str(CLI), "--fleet-root", str(tmp_path),
             "--anchor-repo", str(anchor), "--output", str(existing)], env=env, capture_output=True,
        )
    assert result.returncode == 1
    assert b"Cannot write census artifact" in result.stderr
    assert _snapshot(tmp_path) == before
