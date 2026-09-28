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
        # Detached post-commit maintenance can remove maintenance.lock during
        # _snapshot, even with optional locks disabled. Keep fixture setup quiet.
        result = subprocess.run(
            ["git", "--no-optional-locks", "-c", "init.defaultBranch=main",
             "-c", "maintenance.auto=false",
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


def test_useful_inventory_retains_clone_local_branches_and_exact_index_wip(tmp_path):
    fleet = tmp_path / "fleet"
    clone = _repo(fleet / "WorkingRCX-clone")
    base = _git(clone, "rev-parse", "HEAD")
    _git(clone, "checkout", "-b", "unlanded-history")
    (clone / "valuable.py").write_text("value = 42\n")
    _git(clone, "add", "valuable.py")
    _git(clone, "commit", "-m", "missing implementation")
    local = _git(clone, "rev-parse", "HEAD")
    _git(clone, "checkout", "main")
    (clone / "tracked.txt").write_text("staged implementation\n")
    _git(clone, "add", "tracked.txt")
    (clone / "tracked.txt").write_text("unstaged follow-up\n")
    before = _snapshot(fleet)
    output = tmp_path / "useful-census.json"
    with _fixture_git_env() as env:
        result = subprocess.run([sys.executable, str(CLI), "--fleet-root", str(fleet),
            "--anchor-repo", str(clone), "--comparison-commit", base, "--output", str(output)],
            env=env, capture_output=True)
    assert result.returncode == 0, result.stderr
    work = json.loads(output.read_text())["entries"][0]["useful_work"]
    assert work["status"] == "NEEDS_LANDING"
    assert work["local_commits"] == [local]
    assert any("refs/heads/unlanded-history" in ref for ref in work["local_refs"])
    change = work["changes"][0]
    assert change["path"] == "tracked.txt" and change["dev_covered"] is False
    assert change["index"] != change["worktree"] != change["comparison"]
    assert _snapshot(fleet) == before


def test_retirement_coverage_proves_nonancestor_hunks_and_retains_missing_work():
    with tempfile.TemporaryDirectory(prefix="rcx-retirement-coverage-", dir="/tmp") as tmp:
        root = Path(tmp).resolve()
        primary = _repo(root / "WorkingRCX")
        old = _git(primary, "rev-parse", "HEAD")
        detached = root / "WorkingRCX-detached"
        _git(primary, "worktree", "add", "--detach", str(detached), old)
        (detached / "valuable.py").write_text("implemented = 42\n")
        _git(detached, "add", "valuable.py")
        _git(detached, "commit", "-qm", "historical implementation")
        source = _git(detached, "rev-parse", "HEAD")
        # Same useful code under an independently authored dev commit.
        (primary / "valuable.py").write_text("implemented = 42\n")
        _git(primary, "add", "valuable.py")
        _git(primary, "commit", "-qm", "independent landed implementation")
        base = _git(primary, "rev-parse", "HEAD")
        assert source != base
        before = _snapshot(detached)
        output = root / "census.json"
        with _fixture_git_env() as env:
            result = subprocess.run([sys.executable, str(CLI), "--fleet-root", str(root),
                "--anchor-repo", str(primary), "--comparison-commit", base, "--retirement",
                "--output", str(output)], env=env, capture_output=True)
        assert result.returncode == 0, result.stderr
        work = _rows(json.loads(output.read_bytes()))[str(detached)]["useful_work"]
        assert work["local_commits"] == [source] and work["status"] == "COVERED"
        assert work["local_commit_changes"][0]["coverage"] == "EXACT_REVERSE_PATCH"
        assert work["local_commit_changes"][0]["comparison_blobs"]["valuable.py"][1] == _git(primary, "rev-parse", "HEAD:valuable.py")
        assert _snapshot(detached) == before
        (detached / "valuable.py").write_text("independent_missing = 7\n")
        _git(detached, "add", "valuable.py")
        (detached / "valuable.py").write_text("different_unstaged_intent = 9\n")
        with _fixture_git_env() as env:
            result = subprocess.run([sys.executable, str(CLI), "--fleet-root", str(root),
                "--anchor-repo", str(primary), "--comparison-commit", base, "--retirement",
                "--output", str(output)], env=env, capture_output=True)
        assert result.returncode == 0, result.stderr
        work = _rows(json.loads(output.read_bytes()))[str(detached)]["useful_work"]
        assert work["status"] == "NEEDS_LANDING"
        change = work["changes"][0]
        assert change["index_coverage"] == change["worktree_coverage"] == "REQUIRES_HUNK_REVIEW"
        assert change["index"] != change["worktree"] != change["comparison"]


@pytest.mark.parametrize("state", ["covered", "wip", "local_history"])
def test_useful_inventory_reads_detached_head_history_and_wip_without_writes(tmp_path, state):
    fleet = tmp_path / "fleet"
    anchor = _repo(fleet / "WorkingRCX")
    base = _git(anchor, "rev-parse", "HEAD")
    detached = fleet / "WorkingRCX-detached"
    _git(anchor, "worktree", "add", "--detach", str(detached), base)
    if state == "local_history":
        (detached / "valuable.py").write_text("value = 42\n")
        _git(detached, "add", "valuable.py")
        _git(detached, "commit", "-qm", "detached implementation")
    head = _git(detached, "rev-parse", "HEAD")
    if state == "wip":
        (detached / "tracked.txt").write_text("staged implementation\n")
        _git(detached, "add", "tracked.txt")
        (detached / "tracked.txt").write_text("unstaged follow-up\n")
        (detached / "untracked.txt").write_bytes(b"valuable untracked bytes\x00\xff")
    staged_patch = _git(detached, "diff", "--cached", "--binary")
    unstaged_patch = _git(detached, "diff", "--binary")
    before = _snapshot(fleet)
    output = tmp_path / "detached-census.json"
    with _fixture_git_env() as env:
        result = subprocess.run([sys.executable, str(CLI), "--fleet-root", str(fleet),
            "--anchor-repo", str(anchor), "--comparison-commit", base, "--output", str(output)],
            env=env, capture_output=True)
    assert result.returncode == 0, result.stderr
    row = _rows(json.loads(output.read_text()))[str(detached)]
    assert row["inspection_status"] == "ok" and row["errors"] == []
    assert row["git"]["branch_status"] == "detached" and row["git"]["HEAD"] == head
    work = row["useful_work"]
    assert work["errors"] == []
    assert work["status"] == ("COVERED" if state == "covered" else "NEEDS_LANDING")
    assert work["local_refs"] == []  # Never enumerate other lanes' shared branch refs.
    assert work["local_commits"] == ([head] if state == "local_history" else [])
    for label, patch in (("staged", staged_patch), ("unstaged", unstaged_patch)):
        raw = os.fsencode(patch + "\n") if patch else b""
        assert work[label + "_patch_sha256"] == hashlib.sha256(raw).hexdigest()
    if state == "wip":
        changes = {change["path"]: change for change in work["changes"]}
        assert set(changes) == {"tracked.txt", "untracked.txt"}
        tracked = changes["tracked.txt"]
        assert tracked["index"] != tracked["worktree"] != tracked["comparison"]
        assert not tracked["dev_covered"]
        assert changes["untracked.txt"]["content_sha256"] == hashlib.sha256(
            (detached / "untracked.txt").read_bytes()).hexdigest()
    else:
        assert work["changes"] == []
    if state == "local_history":
        assert work["local_commit_changes"][0]["commit"] == head
        assert work["local_commit_changes"][0]["paths"] == ["valuable.py"]
        assert len(work["local_commit_changes"][0]["patch_sha256"]) == 64
    assert _snapshot(fleet) == before


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


def test_fixture_git_does_not_launch_automatic_maintenance(tmp_path, monkeypatch):
    trace = tmp_path / "git-trace.jsonl"
    env = _git_wrapper(tmp_path, f"os.environ['GIT_TRACE2_EVENT'] = {str(trace)!r}\n")
    monkeypatch.setenv("PATH", env["PATH"])

    _repo(tmp_path / "WorkingRCX-main")

    events = [json.loads(line) for line in trace.read_text().splitlines()]
    assert any(event.get("event") == "cmd_name" and event.get("name") == "commit"
               for event in events)
    maintenance = [event["argv"] for event in events
                   if event.get("event") == "child_start"
                   and event.get("argv", [])[:2] in (["git", "maintenance"], ["git", "gc"])]
    assert maintenance == []


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


def test_bus_shell_inside_containing_repository_has_fresh_filesystem_identity(tmp_path):
    containing = _repo(tmp_path / "containing")
    fleet = containing / "fleet"
    fleet.mkdir()
    anchor = _repo(fleet / "WorkingRCX")
    shell = fleet / "WorkingRCX-retired"
    (shell / ".agent_bus-retired/observability").mkdir(parents=True)
    evidence = shell / ".agent_bus-retired/observability/events.jsonl"
    evidence.write_bytes(b'{"terminal":true}\n')
    before = _snapshot(shell)
    result, report = _cli(fleet, anchor, tmp_path / "census.json")
    assert result.returncode == 0
    row = _rows(report)[str(shell)]
    assert row["repository_kind"] == "non_repository"
    assert row["bus_only_shell"] is True
    assert row["shell_entries"] == [".agent_bus-retired"]
    info = shell.stat()
    assert row["filesystem_identity"] == {"device": info.st_dev, "inode": info.st_ino, "mode": info.st_mode}
    assert row["registered_worktrees"] == []
    assert _snapshot(shell) == before


@pytest.mark.parametrize('detached', [False, True])
@pytest.mark.parametrize('staged', [False, True])
def test_absent_checkout_inventory_preserves_raw_index_and_unknown_bytes(tmp_path, detached, staged):
    from mu.tools.executors import workingrcx_fleet_census as census_tool
    root = (tmp_path / 'fleet').resolve()
    anchor = _repo(root / 'WorkingRCX')
    target = root / 'WorkingRCX-source-observed'
    options = ('--detach',) if detached else ('-b', 'historical-source')
    _git(anchor, 'worktree', 'add', *options, str(target), 'HEAD')
    base = _git(anchor, 'rev-parse', 'HEAD')
    if staged:
        (target / 'index-only').write_bytes(b'only staged bytes\x00\xff')
        _git(target, 'add', 'index-only')
        _git(target, 'write-tree')
    admin = Path(_git(target, 'rev-parse', '--absolute-git-dir'))
    original = _snapshot(admin)
    raw_index = (admin / 'index').read_bytes()
    shutil.rmtree(target)
    observed = census_tool.census(str(root), str(anchor), comparison_commit=base, retirement=True)
    row = _rows(observed)[str(target)]
    proof = row['missing_registration']
    assert proof['status'] == 'OBSERVED', proof
    assert row['inspection_status'] == 'admin_only'
    assert row['git']['dirty_status'] == 'unknown' and row['git']['dirty_counts'] is None
    assert proof['identity']['git_dir'] == str(admin)
    assert proof['index_sha256'] == hashlib.sha256(raw_index).hexdigest()
    assert proof['head_raw_hex'] == (admin / 'HEAD').read_bytes().hex()
    assert proof['indexed_objects_count'] > 0 and proof['history_count'] == 1
    assert row['useful_work']['retained_index_changed'] is staged
    assert row['useful_work']['unstaged_untracked_intent'] == 'UNKNOWN_ABSENT_CHECKOUT'
    assert _snapshot(admin) == original
    (admin / 'index.lock').write_text('held owner')
    locked = census_tool.missing_registration(str(target), str(anchor / '.git'))
    assert locked['status'] == 'OBSERVED' and locked['ownership_holds'] == [str(admin / 'index.lock')]


def test_missing_owner_report_keeps_historical_blob_and_open_ledger(tmp_path):
    from mu.tools.executors import workingrcx_fleet_census as census_tool
    root = (tmp_path / 'fleet').resolve()
    repo = _repo(root / 'WorkingRCX')
    target = root / 'WorkingRCX-missing'
    _git(repo, 'worktree', 'add', '-b', 'retained-index-owner', str(target), 'HEAD')
    (target / 'tracked.txt').write_text('once landed\n')
    _git(target, 'add', 'tracked.txt')
    admin = Path(_git(target, 'rev-parse', '--absolute-git-dir'))
    original = dict(path=str(target), git_dir=str(admin), head=(admin / 'HEAD').read_text().strip(),
                    index_sha256=hashlib.sha256((admin / 'index').read_bytes()).hexdigest())
    (repo / 'tracked.txt').write_text('once landed\n')
    _git(repo, 'commit', '-qam', 'historical equivalent')
    historical = _git(repo, 'rev-parse', 'HEAD')
    (repo / 'tracked.txt').write_text('later implementation\n')
    _git(repo, 'commit', '-qam', 'later implementation')
    comparison = _git(repo, 'rev-parse', 'HEAD')
    shutil.rmtree(target)
    observed = census_tool.census(str(root), str(repo), comparison_commit=comparison, retirement=True)
    prior = tmp_path / 'prior.json'
    prior.write_text(json.dumps(dict(rows=[original], comparison_commit=comparison)))
    ledger = tmp_path / 'owners.json'
    owner = dict(status='PENDING_EXACT_HUNK_REVIEW', source_path=str(target))
    ledger.write_text(json.dumps(dict(wave_id='older-wave', entries=[dict(path=str(target),
        source_index=0, landing_owner=owner, inventory=None)])))
    report = census_tool.missing_registration_report(observed, wave_id='new-wave', census_sha256='1'*64,
        prior_inventory=prior, inherited_ledgers=(ledger,))
    row = report['entries'][0]
    assert row['original_admin_matches'] and row['original_raw_index_matches'] and row['original_head_matches']
    assert row['staged_hunk_obligations'][0]['historical_dev_blob']['commit'] == historical
    assert row['owner']['integration_completed'] is False
    assert report['inherited_ledgers'][0]['original_owners'][0]['landing_owner'] == owner
    assert report['inherited_ledgers'][0]['owner_count'] == 1


# Reuse the disposable real-Git boundary fixture for consumed predecessor proof.
from mu.tests.tools.test_workingrcx_fleet_apply import (
    fleet as retirement_fleet, git as retirement_git, retirement_fixture, commit as retirement_commit,
)


def test_readonly_census_preserves_consumed_failure_and_prior_holds(retirement_fleet, monkeypatch):
    import workingrcx_fleet_apply as fleet
    import workingrcx_fleet_census as census_tool
    import workingrcx_fleet_classification as classifier
    f = retirement_fleet
    for target in f.targets[:3]:
        target.chmod(0o555)
    active = f.targets[3] / '.agent_bus/recovery/status.json'
    active.parent.mkdir(parents=True)
    active.write_text(json.dumps(dict(state='running', active=True, owner_pid=os.getpid())))
    old, kwargs = retirement_fixture(f, wave='fixture-readonly-consumed')
    rename = os.rename
    def failed(source, destination):
        if source in f.targets[:3]:
            raise PermissionError(errno.EACCES, 'original macOS permission failure')
        rename(source, destination)
    with monkeypatch.context() as context:
        context.setattr(fleet.os, 'rename', failed)
        result = fleet.apply_residual_plan(f.repo, old, **kwargs)
    assert result['outcome_counts'] == {'INCOMPLETE': 3, 'HOLD': 1}, result
    active.unlink()  # The disposable carrier's original live owner exits.
    names = {i: t.name for i, t in zip((7, 8, 9, 2), f.targets)}
    for index in (14, 17):
        target = f.root / f'WorkingRCX-protected-{index}'
        retirement_git(f, f.repo, 'worktree', 'add', '-qb', f'held-{index}-{f.root.name}', str(target), f.original)
        names[index] = target.name
    monkeypatch.setattr(classifier, 'READONLY_PREDECESSORS', names)
    observed = census_tool.census(str(f.root), str(f.repo), comparison_commit=f.landed, retirement=True)
    by_path = {r['path']: r for r in observed['entries']}
    # Export the exact native receipt owners at the locked predecessor indices.
    # The original executed plan and all claims stay unchanged in their owners.
    exported = dict(wave_id=classifier.MISSING_WAVE_ID, fleet_root=str(f.root), entries=[{} for _ in range(18)])
    owner = dict(task='FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION', status='PENDING_EXACT_HUNK_REVIEW')
    for index, name in names.items():
        path = str(f.root / name)
        row = by_path[path]
        prior = next((r for r in old['entries'] if r['path'] == path), None)
        exported['entries'][index] = ({**prior, 'source_index': index} if prior else dict(
            source_index=index, path=path, source_identity=dict(path=path,
                **{k: row['git'][k] for k in ('HEAD', 'branch', 'common_dir', 'git_dir')},
                filesystem_identity=row['filesystem_identity']), reason_codes=['protected_evidence'],
            action='UNTOUCHED_HOLD', landing_owner=owner))
    predecessor = f.repo / 'reports/control_plane' / (classifier.MISSING_WAVE_ID + '_apply_plan.json')
    predecessor.write_bytes(fleet.encoded(exported))
    before = {p: p.read_bytes() for p in (f.common / 'rcx_terminal_mutation_attempts').glob('*.json')}
    manifests = [fleet.tree_manifest(target) for target in f.targets]
    native_git = fleet.git
    def read_only_git(root, *args, **options):
        assert os.environ.get('GIT_OPTIONAL_LOCKS') == '0'
        assert os.environ.get('GIT_NO_LAZY_FETCH') == '1'
        return native_git(root, *args, **options)
    monkeypatch.setattr(fleet, 'git', read_only_git)
    census_tool.readonly_source_reviews(observed, predecessor, f.landed)
    reviews = {r['readonly_source_review']['predecessor_index']: r['readonly_source_review']
               for r in observed['entries'] if r.get('readonly_source_review')}
    assert all(reviews[i]['status'] == 'VERIFIED' for i in (2, 7, 8, 9)), reviews
    assert all(reviews[i]['status'] == 'HOLD' and reviews[i]['inherited_landing_owners'] == [owner] for i in (14, 17))
    assert reviews[7]['root_permissions']['mode'] == 0o555
    assert reviews[7]['consumed_predecessor']['replay_authorized'] is False
    assert manifests == [fleet.tree_manifest(target) for target in f.targets]
    assert before == {p: p.read_bytes() for p in before}
    with pytest.raises(fleet.Hold, match='consumed'):
        fleet.apply_residual_plan(f.repo, old, **kwargs)
    # An old recovery artifact changes: the exact source holds, peers remain
    # eligible and no consumed evidence is rewritten by the observer.
    receipt_dir = Path(reviews[7]['consumed_predecessor']['directory'])
    archive = receipt_dir / 'before.tar'
    archive.write_bytes(archive.read_bytes() + b'changed')
    census_tool.readonly_source_reviews(observed, predecessor, f.landed)
    reviews = {r['readonly_source_review']['predecessor_index']: r['readonly_source_review']
               for r in observed['entries'] if r.get('readonly_source_review')}
    assert reviews[7]['status'] == 'HOLD'
    assert reviews[8]['status'] == reviews[9]['status'] == 'VERIFIED'
    assert before == {p: p.read_bytes() for p in before}
    # Publish only in this disposable fixture, then exercise the exact new-wave
    # plan through native APPLY/VERIFY. The damaged predecessor remains held.
    wave = classifier.READONLY_WAVE_ID
    classification_path, census_path, plan_path = fleet.residual_paths(wave)
    raw = fleet.encoded(observed)
    (f.repo / census_path).write_bytes(raw)
    classified = classifier.classify(observed, source_sha256=fleet.digest(raw), base_commit=f.landed,
        carrier=str(f.repo), landed=False, residual=True, retirement=True,
        retirement_predecessor=f.landed, wave_id=wave,
        historical_paths=tuple(str(f.root / n) for n in names.values()))
    raw = fleet.encoded(classified)
    sha = fleet.digest(raw)
    (f.repo / classification_path).write_bytes(raw)
    for suffix, builder in (('useful_work', classifier.useful_work_report),
                            ('useful_work_coverage', classifier.retirement_coverage_report)):
        (f.repo / f'reports/control_plane/{wave}_{suffix}.json').write_bytes(fleet.encoded(builder(classified, sha)))
    fresh = fleet.build_residual_plan(f.repo, f.repo / classification_path, sha, wave_id=wave)
    (f.repo / plan_path).write_bytes(fleet.encoded(fresh))
    authority = retirement_commit(f, 'bounded read-only source renewal fixture')
    retirement_git(f, f.repo, 'push', '-q', 'origin', 'HEAD:dev')
    operation = fresh['operations'][0]
    fresh_args = dict(authority_commit=authority, batch=operation['batch'], operation_root=Path(operation['operation_root']))
    assert {r['readonly_source_review']['predecessor_index'] for r in fresh['entries']
            if r['action'] != 'UNTOUCHED_HOLD'} == {2, 8, 9}
    result = fleet.apply_residual_plan(f.repo, fresh, **fresh_args)
    assert result['outcome_counts'] == {'RETIRED': 3}, result
    assert fleet.verify_residual_plan(f.repo, fresh, **fresh_args)['batch_complete']
    assert f.targets[0].exists() and stat.S_IMODE(f.targets[0].stat().st_mode) == 0o555
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize('generation', ['r1', 'r2'])
def test_stopped_readonly_candidate_requires_exact_index_packet_receipt_and_recovery(retirement_fleet, monkeypatch, generation):
    import workingrcx_fleet_apply as fleet
    import workingrcx_fleet_census as census_tool
    import workingrcx_fleet_classification as classifier
    f = retirement_fleet
    source = f.targets[1]
    monkeypatch.setattr(classifier, 'READONLY_PREDECESSORS', {2: f.targets[0].name})
    source_constant = 'STOPPED_READONLY_SOURCE' if generation == 'r1' else 'STOPPED_READONLY_R2_SOURCE'
    monkeypatch.setattr(classifier, source_constant, source.name)
    spec = classifier.stopped_readonly_sources()[source.name]
    manifest_argument = 'stopped_manifest' if generation == 'r1' else 'stopped_r2_manifest'
    packet = source / ('reports/control_plane/' + spec['wave_id'] + '_2026-09-27.md')
    packet.parent.mkdir(parents=True)
    packet.write_text('# Preserved failed packet\n\n## Forbidden implementation section\n' if generation == 'r1'
                      else '# Reviewed packet\nStatus: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT\n')
    (source / 'tracked').write_bytes(b'original staged-only stopped intent\x00\xff')
    retirement_git(f, source, 'add', 'tracked', str(packet.relative_to(source)))
    (source / 'tracked').write_bytes(b'distinct unstaged stopped intent\n')
    receipt = source / spec['receipt']
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(dict(state='available', returncode=1)))
    lifecycle = f.common / 'rcx_worktree_lifecycle/frozen-stopped-owner'
    lifecycle.mkdir(parents=True)
    completion = lifecycle / 'completion.json'
    completion.write_text(json.dumps(dict(state='ESCALATED', attempts_used=3)))
    observed = census_tool.census(str(f.root), str(f.repo), comparison_commit=f.landed, retirement=True)
    sources = {row['path']: row for row in observed['entries']}
    def identity(row):
        return dict(path=row['path'], **{k: row['git'][k] for k in ('HEAD', 'branch', 'common_dir', 'git_dir')},
                    filesystem_identity=row['filesystem_identity'])
    prior = identity(sources[str(f.targets[0])])
    predecessor = f.repo / 'reports/control_plane' / (classifier.MISSING_WAVE_ID + '_apply_plan.json')
    predecessor.write_bytes(fleet.encoded(dict(wave_id=classifier.MISSING_WAVE_ID, fleet_root=str(f.root),
        entries=[{}, {}, dict(source_index=2, path=prior['path'], source_identity=prior, reason_codes=['active_carrier'])])))
    ident = identity(sources[str(source)])
    index = fleet.git_entries(source)
    manifest = dict(wave=spec['wave_id'], path=str(source), head=ident['HEAD'],
        branch=ident['branch'], git_dir=ident['git_dir'], index_sha256=fleet.file_hash(Path(ident['git_dir']) / 'index'),
        files=[dict(path=str(p.relative_to(source)), worktree_sha256=fleet.file_hash(p),
                    index_blob=index[str(p.relative_to(source))][1]) for p in (source / 'tracked', packet)],
        packet_sha256=fleet.file_hash(packet), terminal_receipt_sha256=fleet.file_hash(receipt),
        lifecycle=dict(path=str(lifecycle), records=[dict(name=completion.name, sha256=fleet.file_hash(completion))]),
        state=spec['state'], public_pairs_executed=0)
    manifest_path = f.repo / 'stopped-candidate.json'
    manifest_path.write_bytes(fleet.encoded(manifest))
    before = fleet.tree_manifest(source)
    admin_before = fleet.tree_manifest(Path(ident['git_dir']))
    def observe():
        census_tool.readonly_source_reviews(observed, predecessor, f.landed, **{manifest_argument: manifest_path})
        return sources[str(source)]['readonly_source_review']
    review = observe()
    assert review['status'] == 'VERIFIED', review
    assert review['independent_recovery_verified'] and review['recovery_observation']['raw_index_sha256'] == manifest['index_sha256']
    assert before == fleet.tree_manifest(source) and admin_before == fleet.tree_manifest(Path(ident['git_dir']))
    # R2's tested/reviewed stop is distinct from R1's unreviewed failed packet.
    # A newly observed manifest cannot exchange terminal states or source names.
    other = classifier.stopped_readonly_sources()[
        classifier.STOPPED_READONLY_R2_SOURCE if generation == 'r1' else classifier.STOPPED_READONLY_SOURCE]
    for key, value in [('state', other['state']), ('wave', other['wave_id']),
                       ('path', str(f.targets[2])), ('public_pairs_executed', 1)]:
        manifest_path.write_bytes(fleet.encoded({**manifest, key: value}))
        assert observe()['status'] == 'HOLD'
        assert sources[str(f.targets[0])]['readonly_source_review']['status'] == 'VERIFIED'
    manifest_path.write_bytes(fleet.encoded(manifest))
    # Each exact stopped artifact is mandatory. Damage holds this source only;
    # an eligible peer keeps its independent authority and all budgets survive.
    for path in (source / 'tracked', packet, receipt, completion, Path(ident['git_dir']) / 'index'):
        raw = path.read_bytes()
        try:
            path.write_bytes(raw + b'changed')
            assert observe()['status'] == 'HOLD'
            assert sources[str(f.targets[0])]['readonly_source_review']['status'] == 'VERIFIED'
        finally:
            path.write_bytes(raw)
    active = source / '.agent_bus/recovery/status.json'
    active.parent.mkdir(parents=True)
    active.write_text(json.dumps(dict(state='running', active=True, owner_pid=os.getpid())))
    assert observe()['status'] == 'HOLD'
    active.unlink()
    assert observe()['status'] == 'VERIFIED'
    wave = classifier.READONLY_WAVE_ID
    classification_path, census_path, plan_path = fleet.residual_paths(wave)
    raw = fleet.encoded(observed)
    (f.repo / census_path).write_bytes(raw)
    options = dict(source_sha256=fleet.digest(raw), base_commit=f.landed,
        carrier=str(f.repo), landed=False, residual=True, retirement=True, retirement_predecessor=f.landed,
        wave_id=wave, historical_paths=tuple(str(f.root / p) for p in classifier.readonly_source_paths()
                                             if str(f.root / p) in sources))
    saved_binding = sources[str(source)]['readonly_source_review']['stopped_candidate']
    sources[str(source)]['readonly_source_review']['stopped_candidate'] = {**saved_binding, 'sha256': '0' * 64}
    rejected = classifier.classify(observed, **options)
    assert next(row for row in rejected['entries'] if row['path'] == str(source))['decision'] == 'HOLD'
    sources[str(source)]['readonly_source_review']['stopped_candidate'] = saved_binding
    classified = classifier.classify(observed, **options)
    raw = fleet.encoded(classified)
    sha = fleet.digest(raw)
    (f.repo / classification_path).write_bytes(raw)
    for suffix, builder in (('useful_work', classifier.useful_work_report),
                            ('useful_work_coverage', classifier.retirement_coverage_report)):
        (f.repo / f'reports/control_plane/{wave}_{suffix}.json').write_bytes(fleet.encoded(builder(classified, sha)))
    plan = fleet.build_residual_plan(f.repo, f.repo / classification_path, sha, wave_id=wave)
    assert plan['conditional_candidates'] == 2
    (f.repo / plan_path).write_bytes(fleet.encoded(plan))
    for relative in ('mu/tools/executors/workingrcx_fleet_census.py',
                     'mu/tools/executors/workingrcx_fleet_classification.py',
                     'mu/tools/executors/worktree_lifecycle.py',
                     'mu/tools/observability/pipeline_agent_pager.py'):
        path = f.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REPO_ROOT / relative).read_bytes())
    authority = retirement_commit(f, 'exact stopped candidate recovery fixture')
    retirement_git(f, f.repo, 'push', '-q', 'origin', 'HEAD:dev')
    operation = plan['operations'][0]
    args = dict(authority_commit=authority, batch=operation['batch'], operation_root=Path(operation['operation_root']))
    # Identify any subprocess that rewrites the original index: preservation
    # is required to remain byte-for-byte read-only until registration removal.
    native_run = subprocess.run
    original_index = Path(ident['git_dir']) / 'index'
    def preserve_original_index(*argv, **kwargs):
        before_index = fleet.file_hash(original_index) if original_index.exists() else None
        completed = native_run(*argv, **kwargs)
        if before_index is not None and original_index.exists() and fleet.file_hash(original_index) != before_index:
            pytest.fail(f"Original stopped index rewritten by {argv[0]!r}; optional_locks={kwargs.get('env', os.environ).get('GIT_OPTIONAL_LOCKS')}")
        return completed
    monkeypatch.setattr(subprocess, 'run', preserve_original_index)
    result = fleet.apply_residual_plan(f.repo, plan, **args)
    assert result['outcome_counts'] == {'RETIRED': 2}, [
        (Path(row['source_identity']['path']).name, row['status'], row.get('reason'))
        for row in result['outcomes'] if row['status'] != 'RETIRED']
    assert fleet.verify_residual_plan(f.repo, plan, **args)['batch_complete']
    entry = next(e for e in plan['entries'] if e['path'] == str(source))
    destination = Path(entry['destination'])
    assert fleet.file_hash(destination / packet.relative_to(source)) == manifest['packet_sha256']
    assert fleet.file_hash(destination.parent / 'recovery.git/index') == manifest['index_sha256']
    assert fleet.file_hash(destination / spec['receipt']) == manifest['terminal_receipt_sha256']
    assert fleet.file_hash(completion) == manifest['lifecycle']['records'][0]['sha256']
