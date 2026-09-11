"""Bounded operation proofs in disposable repositories, never in the fleet."""
from __future__ import annotations

from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu/tools/executors"))
import workingrcx_fleet_apply as apply
import commit_executor as boundary


SOURCE = REPO_ROOT / apply.CLASSIFICATION_PATH
REAL_SCRIPT = REPO_ROOT / apply.TOOL_PATH
REAL_CANDIDATES = deepcopy(apply.CANDIDATES)


def git(f, root, *args):
    return subprocess.run(
        [f.git, "-c", "init.defaultBranch=dev", "-c", "gc.auto=0",
         "-c", "maintenance.auto=false", "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgsign=false", "-c", "user.name=Fleet Apply Fixture",
         "-c", "user.email=fleet-apply@example.invalid", "-C", str(root), *args],
        env=f.env, capture_output=True, check=True,
    ).stdout.decode().strip()


def commit(f, message):
    git(f, f.repo, "add", ".")
    git(f, f.repo, "commit", "-qm", message)
    return git(f, f.repo, "rev-parse", "HEAD")


@pytest.fixture
def fleet(monkeypatch):
    # Explicit /tmp avoids inherited pytest basetemp/.scratch routing. All
    # commits, pushes, hooks, and worktree operations below are disposable.
    with tempfile.TemporaryDirectory(prefix="rcx-fleet-apply-", dir="/tmp") as directory:
        root = Path(directory).resolve()
        home = root / "home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home), GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.devnull, PYTHONDONTWRITEBYTECODE="1", LC_ALL="C")
        for key in tuple(os.environ):
            if key.startswith("GIT_"):
                monkeypatch.delenv(key)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        f = SimpleNamespace(root=root, repo=root / "WorkingRCX", remote=root / "remote.git",
                            git=shutil.which("git"), env=env, original_idle=apply.process_idle)
        assert f.git
        f.repo.mkdir()
        f.remote.mkdir()
        git(f, f.repo, "init", "-q")
        git(f, f.remote, "init", "--bare", "-q")
        (f.repo / "TASKS.md").write_text(
            (REPO_ROOT / "TASKS.md").read_text().replace(str(apply.FLEET_ROOT), str(root)))
        (f.repo / "tracked").write_bytes(b"original tracked evidence\n")
        (f.repo / ".gitignore").write_text("ignored*\n.agent_bus*\n")
        f.original = commit(f, "recorded source heads")
        f.targets, identities = [], []
        for real in REAL_CANDIDATES:
            target = root / Path(real["path"]).name
            git(f, f.repo, "worktree", "add", "-qb", real["branch"].removeprefix("refs/heads/"),
                str(target), f.original)
            evidence = target / "ignored-evidence"
            evidence.mkdir()
            (evidence / "private.bin").write_bytes(b"\x00private evidence\xff\n")
            (evidence / "link").symlink_to("../tracked")
            (evidence / "dangling").symlink_to("missing-symlink-destination")
            (f.repo / ".git/worktrees" / target.name / "FETCH_HEAD").write_text(
                f.original + "\t\toriginal fetch evidence\n")
            f.targets.append(target)
            identities.append(dict(path=str(target), HEAD=f.original, branch=real["branch"],
                                   common_dir=str(f.repo / ".git"),
                                   git_dir=str(f.repo / ".git/worktrees" / target.name)))
        f.common = f.repo / ".git"
        f.operation = root / ("fleet-apply-preserved-" + apply.WAVE_ID)
        old_root = str(apply.FLEET_ROOT)
        data = json.loads(SOURCE.read_text().replace(old_root, str(root)))
        for row in data["entries"]:
            if row["decision"] == "CONDITIONAL_RETIRE_CANDIDATE":
                row["source"]["git"]["HEAD"] = f.original
                row["source"]["registered_worktrees"][0]["HEAD"] = f.original
        f.data = data
        classification = f.repo / apply.CLASSIFICATION_PATH
        classification.parent.mkdir(parents=True)
        classification.write_bytes(apply.encoded(data))
        f.classification_commit = commit(f, "disposable landed classification")
        for key, value in dict(CLASSIFICATION_COMMIT=f.classification_commit,
                               CLASSIFICATION_SHA256=apply.digest(classification.read_bytes()),
                               FLEET_ROOT=root, COMMON_DIR=f.common, OPERATION_ROOT=f.operation,
                               CANDIDATES=tuple(identities), SCRIPT_PATH=f.repo / apply.TOOL_PATH).items():
            monkeypatch.setattr(apply, key, value)
        f.plan = apply.build_plan(f.repo, classification, apply.CLASSIFICATION_SHA256,
                                  apply.CLASSIFICATION_COMMIT)
        f.candidates = [r for r in f.plan["entries"] if r["action"] != "UNTOUCHED_HOLD"]
        for rel in (apply.TOOL_PATH, apply.TEST_PATH, Path("mu/tools/executors/commit_executor.py"),
                    Path("mu/tools/executors/executor_common.py")):
            path = f.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((REPO_ROOT / rel).read_bytes())
        (f.repo / apply.PLAN_PATH).write_bytes(apply.encoded(f.plan))
        (f.repo / "tracked").write_text("landed tracked revision\n")
        f.landed = commit(f, "disposable reviewed tool and plan")
        git(f, f.repo, "remote", "add", "origin", str(f.remote))
        git(f, f.repo, "push", "-q", "origin", "dev")
        # Tests concerned with Git and preservation isolate OS process timing.
        # The complete four-candidate success test below restores real probes.
        monkeypatch.setattr(apply, "process_idle", lambda _ident: None)
        yield f


def run(f):
    return apply.apply_plan(f.repo, f.plan)


def cli_args(f):
    return ["--classification", str(f.repo / apply.CLASSIFICATION_PATH),
            "--classification-sha256", apply.CLASSIFICATION_SHA256,
            "--classification-commit", apply.CLASSIFICATION_COMMIT,
            "--plan-output", str(f.repo / apply.PLAN_PATH)]


def test_complete_four_candidate_flow_preserves_evidence_and_uses_real_boundary(fleet, monkeypatch):
    f = fleet
    monkeypatch.setattr(apply, "process_idle", f.original_idle)
    before = [apply.tree_manifest(t) for t in f.targets]
    calls, real_execute = [], boundary.execute_terminal_mutation_once

    def observed_execute(repo, ident, *, terminal_action, log):
        assert ident["worktree_identity"]["path"] in {str(t) for t in f.targets}
        assert ident["expected_head"] == f.landed

        def under_lock():
            with (f.common / "rcx_primary_worktree_sync.lock").open("rb") as stream:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return terminal_action()

        result = real_execute(repo, ident, terminal_action=under_lock, log=log)
        calls.append(result)
        return result

    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", observed_execute)
    result = run(f)
    assert result["outcome_counts"] == {"MOVED": 4}, result
    assert result["untouched_holds"] == 407 and result["fleet_clean"] is False
    assert len(calls) == 4
    for result, entry, old in zip(calls, f.candidates, before):
        assert result["fresh_fetch"] is True and result["behind_count"] == 0
        assert result["authority_consumed"] is True and result["action_succeeded"] is True
        assert Path(result["authority_record_path"]).is_file()
        dest = Path(entry["destination"])
        receipt = dest.parent
        assert not Path(entry["path"]).exists()
        assert json.loads((receipt / "before.json").read_text()) == old
        assert json.loads((receipt / "prepared.json").read_text()) == apply.tree_manifest(dest)
        assert json.loads((receipt / "after.json").read_text()) == apply.tree_manifest(dest)
        assert (dest / "ignored-evidence/private.bin").read_bytes() == b"\x00private evidence\xff\n"
        assert os.readlink(dest / "ignored-evidence/dangling") == "missing-symlink-destination"
        assert (dest / "tracked").read_text() == "landed tracked revision\n"
        with tarfile.open(receipt / "before.tar") as archive:
            assert archive.extractfile("./tracked").read() == b"original tracked evidence\n"
        with tarfile.open(receipt / "gitdir-before.tar") as archive:
            assert archive.extractfile("./FETCH_HEAD").read() == (
                f.original + "\t\toriginal fetch evidence\n").encode()
        git(f, dest, "merge-base", "--is-ancestor", f.original, "HEAD")
        assert git(f, dest, "bundle", "list-heads", str(receipt / "history.bundle")) == (
            f.original + " " + entry["source_identity"]["branch"])
    with pytest.raises(apply.Hold, match="consumed|ambiguous"):
        run(f)


@pytest.mark.parametrize("field", ["path", "HEAD", "branch", "common_dir", "git_dir"])
def test_source_identity_mismatch_is_rejected(fleet, field):
    data = deepcopy(fleet.data)
    row = next(r for r in data["entries"] if r["decision"] == "CONDITIONAL_RETIRE_CANDIDATE")
    if field == "path":
        row["path"] += "-different"
    else:
        row["source"]["git"][field] += "-different"
    with pytest.raises(apply.Hold):
        apply.validate_classification(data)


@pytest.mark.parametrize("change", ["missing_row", "promote_hold", "counts", "coverage", "registration"])
def test_malformed_incomplete_or_broadened_source_stops(fleet, change):
    data = deepcopy(fleet.data)
    if change == "missing_row":
        data["entries"].pop()
    elif change == "promote_hold":
        data["entries"][0]["decision"] = "CONDITIONAL_RETIRE_CANDIDATE"
    elif change == "counts":
        data["decision_counts"]["HOLD"] = 406
    elif change == "coverage":
        data["coverage_complete"] = False
    else:
        next(r for r in data["entries"] if r["decision"] == "CONDITIONAL_RETIRE_CANDIDATE")[
            "source"]["registered_worktrees"] = []
    with pytest.raises(apply.Hold):
        apply.validate_classification(data)


def test_plan_is_read_only_repeatable_and_refuses_unrelated_output(fleet, monkeypatch):
    f = fleet
    before = [apply.tree_manifest(p) for p in f.targets]
    common_before = apply.tree_manifest(f.common)
    monkeypatch.chdir(f.repo)
    assert apply.main(cli_args(f)) == 0
    assert apply.main(cli_args(f)) == 0
    assert [apply.tree_manifest(p) for p in f.targets] == before
    assert apply.tree_manifest(f.common) == common_before
    assert not f.operation.exists()
    assert len(f.plan["entries"]) == 411
    assert sum(r["action"] == "UNTOUCHED_HOLD" for r in f.plan["entries"]) == 407
    output = f.repo / apply.PLAN_PATH
    output.write_text("unrelated output\n")
    assert apply.main(cli_args(f)) == 2
    assert output.read_text() == "unrelated output\n"


@pytest.mark.parametrize("kind", ["hash", "commit", "path", "raw_bytes"])
def test_wrong_binding_stops_before_output(fleet, kind):
    f = fleet
    source, sha, predecessor = f.repo / apply.CLASSIFICATION_PATH, apply.CLASSIFICATION_SHA256, apply.CLASSIFICATION_COMMIT
    if kind == "hash":
        sha = "0" * 64
    elif kind == "commit":
        predecessor = f.original
    elif kind == "path":
        source = f.root / "other.json"
        source.write_bytes((f.repo / apply.CLASSIFICATION_PATH).read_bytes())
    else:
        source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(apply.Hold):
        apply.build_plan(f.repo, source, sha, predecessor)
    assert not f.operation.exists()


def test_premerge_and_modified_authority_refuse_all_actions(fleet):
    f = fleet
    (f.repo / apply.TOOL_PATH).write_text("unlanded tool\n")
    with pytest.raises(apply.Hold, match="Unlanded|modified"):
        run(f)
    assert not f.operation.exists()
    assert not (f.common / f"rcx_fleet_apply_{apply.WAVE_ID}.json").exists()
    commit(f, "unmerged tool")
    with pytest.raises(apply.Hold):
        run(f)
    assert all(t.exists() for t in f.targets)


def test_dirty_active_and_newly_protected_hold_while_valid_target_moves(fleet, monkeypatch):
    f = fleet
    (f.targets[0] / "untracked-wip").write_bytes(b"valuable untracked work")
    bus = f.targets[1] / ".agent_bus/meta"
    bus.mkdir(parents=True)
    (bus / "recovery_status.json").write_text(json.dumps(dict(active=True, owner_pid=os.getpid())))
    with (f.repo / "TASKS.md").open("a") as stream:
        stream.write("\nPreserve " + str(f.targets[2]) + "\n")
    before = [apply.tree_manifest(t) for t in f.targets[:3]]
    result = run(f)
    assert [o["status"] for o in result["outcomes"]] == ["HOLD", "HOLD", "HOLD", "MOVED"]
    assert [apply.tree_manifest(t) for t in f.targets[:3]] == before
    assert result["untouched_holds"] == 407


@pytest.mark.parametrize("drift", ["head", "branch", "registration", "index_flag", "tracked_dirty", "locked"])
def test_live_drift_holds_only_that_target(fleet, drift):
    f, target = fleet, fleet.targets[0]
    if drift == "head":
        git(f, target, "merge", "--ff-only", f.classification_commit)
    elif drift == "branch":
        git(f, target, "checkout", "-qb", "fixture/different")
    elif drift == "registration":
        (Path(f.candidates[0]["source_identity"]["git_dir"]) / "gitdir").write_text(str(f.root / "wrong/.git"))
    elif drift == "index_flag":
        git(f, target, "update-index", "--assume-unchanged", "tracked")
    elif drift == "tracked_dirty":
        (target / "tracked").write_text("uncommitted tracked work")
    else:
        git(f, f.repo, "worktree", "lock", str(target))
    result = run(f)
    assert [o["status"] for o in result["outcomes"]] == ["HOLD", "MOVED", "MOVED", "MOVED"]


def test_configured_filters_never_execute_and_preservation_is_retained(fleet):
    f = fleet
    sentinel = f.root / "FILTER_EXECUTED"
    git(f, f.repo, "config", "filter.evil.clean", "touch " + shlex.quote(str(sentinel)))
    git(f, f.repo, "config", "filter.evil.smudge", "touch " + shlex.quote(str(sentinel)))
    (f.common / "info/attributes").write_text("tracked filter=evil\n")
    for target in f.targets:
        os.utime(target / "tracked", ns=(1_000_000_000, 1_000_000_000))
    # Effective attributes and changed stat data would activate the filter
    # during status; the guard must refuse that probe before reading content.
    before = [apply.tree_manifest(t) for t in f.targets]
    result = run(f)
    assert result["outcome_counts"] == {"HOLD": 4}
    assert not sentinel.exists()
    assert [apply.tree_manifest(t) for t in f.targets] == before


def test_target_hooks_are_disabled_for_preparation_and_boundary_fetch(fleet):
    f = fleet
    hooks = f.root / "hooks"
    hooks.mkdir()
    sentinel = f.root / "HOOK_EXECUTED"
    for name in ("post-merge", "reference-transaction"):
        hook = hooks / name
        hook.write_text("#!/bin/sh\ntouch " + shlex.quote(str(sentinel)) + "\n")
        hook.chmod(0o755)
    git(f, f.repo, "config", "core.hooksPath", str(hooks))
    assert run(f)["outcome_counts"] == {"MOVED": 4}
    assert not sentinel.exists()


def test_fresh_boundary_fetch_detects_remote_advance(fleet, monkeypatch):
    f = fleet
    real_execute = boundary.execute_terminal_mutation_once
    count = 0

    def advance(repo, ident, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            (f.repo / "new-upstream").write_text("advanced after preparation\n")
            commit(f, "remote advanced before terminal invocation")
            git(f, f.repo, "push", "-q", "origin", "dev")
        return real_execute(repo, ident, **kwargs)

    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", advance)
    result = run(f)
    first = result["outcomes"][0]
    assert first["status"] == "HOLD"
    assert first["boundary"]["fresh_fetch"] is True
    assert first["boundary"]["behind_count"] == 1
    assert first["boundary"]["action_invoked"] is False
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}


@pytest.mark.parametrize("after_move", [False, True])
def test_move_failure_is_incomplete_and_cannot_replay(fleet, monkeypatch, after_move):
    f = fleet
    real_git = apply.git

    def fail_move(root, *args, **kwargs):
        if args[:2] == ("worktree", "move") and args[2] == str(f.targets[0]):
            if after_move:
                real_git(root, *args, **kwargs)
            raise apply.Hold("disposable supported move failure")
        return real_git(root, *args, **kwargs)

    monkeypatch.setattr(apply, "git", fail_move)
    result = run(f)
    assert result["outcome_counts"] == {"INCOMPLETE": 1, "MOVED": 3}
    first = result["outcomes"][0]
    assert first["boundary"]["authority_consumed"] is True
    assert first["boundary"]["action_invoked"] is True
    receipt = Path(first["destination"]).parent
    assert (receipt / "move-started.json").exists() and (receipt / "before.tar").exists()
    assert Path(first["destination"]).exists() is after_move
    # Reusing this exact API identity cannot invoke a second callback, even
    # when the first failed before Git moved the source directory.
    identity = json.loads((receipt / "terminal-identity.json").read_text())
    with apply.safe_git_environment(network=True):
        replay = boundary.execute_terminal_mutation_once(
            f.repo, identity, terminal_action=lambda: pytest.fail("terminal replay"), log=lambda _: None)
    assert replay["action_invoked"] is False
    # Even relocating the durable local receipt tree cannot mint a second
    # operation; the fixed common-directory intent remains consumed.
    f.operation.rename(f.root / "receipts-preserved-elsewhere")
    with pytest.raises(apply.Hold, match="Existing|ambiguous"):
        run(f)


def test_ambiguous_interruption_blocks_second_preparation(fleet, monkeypatch):
    f = fleet
    real_git = apply.git

    def interrupt(root, *args, **kwargs):
        if args[:2] == ("merge", "--ff-only"):
            raise KeyboardInterrupt("disposable interruption")
        return real_git(root, *args, **kwargs)

    monkeypatch.setattr(apply, "git", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run(f)
    receipt = Path(f.candidates[0]["destination"]).parent
    assert (receipt / "preparation.json").exists()
    assert not (receipt / "outcome.json").exists()
    with pytest.raises(apply.Hold, match="consumed|ambiguous"):
        run(f)


def test_process_probe_detects_target_cwd(fleet):
    f = fleet
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], cwd=f.targets[0])
    try:
        with pytest.raises(apply.Hold, match="Open target"):
            f.original_idle(f.candidates[0]["source_identity"])
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_explicit_apply_destination_and_incomplete_exit(fleet, monkeypatch):
    f = fleet
    monkeypatch.chdir(f.repo)
    assert apply.main(cli_args(f) + ["--apply"]) == 2
    assert not f.operation.exists()
    (f.targets[0] / "tracked").write_text("keep dirty work")
    assert apply.main(cli_args(f) + ["--apply", "--operation-root", str(f.operation)]) == 3


def test_plan_output_symlinks_and_hardlinks_are_refused(fleet, monkeypatch):
    f = fleet
    monkeypatch.chdir(f.repo)
    output = f.repo / apply.PLAN_PATH
    saved = f.root / "unrelated.json"
    output.rename(saved)
    output.symlink_to(saved)
    assert apply.main(cli_args(f)) == 2
    output.unlink()
    os.link(saved, output)
    assert apply.main(cli_args(f)) == 2


@pytest.mark.parametrize("status", [dict(active=True, state="completed"),
                                    dict(active=False, state="running"),
                                    dict(state="unknown")])
def test_contradictory_or_uncertain_native_status_holds(fleet, status):
    target = fleet.targets[0]
    bus = target / ".agent_bus/meta"
    bus.mkdir(parents=True)
    (bus / "recovery_status.json").write_text(json.dumps(status))
    with pytest.raises(apply.Hold, match="active or uncertain"):
        apply.native_idle(target, apply.tree_manifest(target))


def test_ignored_collision_is_archived_and_never_overwritten(fleet):
    f = fleet
    (f.repo / "collision").write_text("new tracked upstream file")
    commit(f, "new upstream path collides with ignored evidence")
    git(f, f.repo, "push", "-q", "origin", "dev")
    with (f.common / "info/exclude").open("a") as stream:
        stream.write("\ncollision\n")
    (f.targets[0] / "collision").write_text("private ignored evidence")
    result = run(f)
    assert result["outcome_counts"] == {"INCOMPLETE": 1, "MOVED": 3}
    assert (f.targets[0] / "collision").read_text() == "private ignored evidence"
    receipt = Path(result["outcomes"][0]["destination"]).parent
    with tarfile.open(receipt / "before.tar") as archive:
        assert archive.extractfile("./collision").read() == b"private ignored evidence"


def test_special_unreadable_content_holds_without_blocking_other_targets(fleet):
    f = fleet
    fifo = f.targets[0] / "ignored-fifo"
    os.mkfifo(fifo)
    result = run(f)
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}
    assert "special content" in result["outcomes"][0]["reason"]
    assert fifo.exists()


def test_dirty_state_created_after_binding_is_caught_inside_callback(fleet, monkeypatch):
    f = fleet
    real_execute = boundary.execute_terminal_mutation_once

    def dirty_after_binding(repo, identity, **kwargs):
        if identity["worktree_identity"]["path"] == str(f.targets[0]):
            (f.targets[0] / "tracked").write_text("concurrent WIP must survive")
        return real_execute(repo, identity, **kwargs)

    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", dirty_after_binding)
    result = run(f)
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}
    assert result["outcomes"][0]["boundary"]["action_invoked"] is True
    assert (f.targets[0] / "tracked").read_text() == "concurrent WIP must survive"


def test_existing_api_binding_refusal_is_a_target_hold(fleet, monkeypatch):
    f = fleet
    real_bind = boundary.bind_terminal_target_identity

    def cannot_bind(target, **kwargs):
        if target == f.targets[0]:
            return dict(bound=False, reason="disposable identity capture refusal")
        return real_bind(target, **kwargs)

    monkeypatch.setattr(boundary, "bind_terminal_target_identity", cannot_bind)
    result = run(f)
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}
    assert result["outcomes"][0]["prepared_head"] == f.landed
    assert result["outcomes"][0]["boundary"] is None
    assert f.targets[0].exists()
