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
    # The declared dependency modules also load commit_executor at collection.
    # Keep callback/fetch spies attached to the module dynamically imported by
    # this CLI, preserving the real-boundary assertions in the combined gate.
    monkeypatch.setitem(sys.modules, "commit_executor", boundary)
    # Explicit /tmp avoids inherited pytest basetemp/.scratch routing. All
    # commits, pushes, hooks, and worktree operations below are disposable.
    with tempfile.TemporaryDirectory(prefix="rcx-fleet-apply-", dir="/tmp") as directory:
        root = Path(directory).resolve()
        home = root / "home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home), GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.devnull, PYTHONDONTWRITEBYTECODE="1", LC_ALL="C")
        real_git = shutil.which("git", path=env["PATH"])
        assert real_git
        bindir = root / "bin"
        bindir.mkdir()
        wrapper = bindir / "git"
        # Census drops GIT_* overrides before probing effective config. Keep
        # runner system filters out of disposable repos at the exec boundary.
        wrapper.write_text(f'#!/bin/sh\nGIT_CONFIG_NOSYSTEM=1 exec {shlex.quote(real_git)} "$@"\n')
        wrapper.chmod(0o700)
        env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
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
            # The real process probe matches branch tokens. Parallel fixtures
            # must not mistake each other's Git commands for a target owner.
            branch = real["branch"] + "-" + root.name
            git(f, f.repo, "worktree", "add", "-qb", branch.removeprefix("refs/heads/"),
                str(target), f.original)
            evidence = target / "ignored-evidence"
            evidence.mkdir()
            (evidence / "private.bin").write_bytes(b"\x00private evidence\xff\n")
            (evidence / "link").symlink_to("../tracked")
            (evidence / "dangling").symlink_to("missing-symlink-destination")
            (f.repo / ".git/worktrees" / target.name / "FETCH_HEAD").write_text(
                f.original + "\t\toriginal fetch evidence\n")
            f.targets.append(target)
            identities.append(dict(path=str(target), HEAD=f.original, branch=branch,
                                   common_dir=str(f.repo / ".git"),
                                   git_dir=str(f.repo / ".git/worktrees" / target.name)))
        f.common = f.repo / ".git"
        f.operation = root / ("fleet-apply-preserved-" + apply.WAVE_ID)
        f.reconcile_operation = root / ("fleet-apply-preserved-" + apply.RECONCILE_WAVE_ID)
        old_root = str(apply.FLEET_ROOT)
        fixture_data = SOURCE.read_text().replace(old_root, str(root))
        for real, identity in zip(REAL_CANDIDATES, identities):
            fixture_data = fixture_data.replace(json.dumps(real["branch"]), json.dumps(identity["branch"]))
        data = json.loads(fixture_data)
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
                               RECONCILE_OPERATION_ROOT=f.reconcile_operation,
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


def finished_recovery(state, owner_pid=0):
    return dict(state=state, active=False, owner_pid=owner_pid, child_pid=0,
                child_role="", current_command="", finished_at="2026-08-22T11:07:15.738351+00:00",
                recovered=False, exhausted=True,
                outcome="exhausted" if state == "tier3_exhausted" else "short_circuited_non_actionable",
                last_action="exhausted" if state == "tier3_exhausted" else "escalate")


def land_reconciliation(f, monkeypatch):
    # Pins belong only to this disposable, actually executed R1 operation.
    monkeypatch.setattr(apply, "R1_MERGE", f.landed)
    monkeypatch.setattr(apply, "R1_RECEIPT_HASHES", {
        name: apply.digest((f.operation / name).read_bytes()) for name in apply.R1_RECEIPT_HASHES})
    f.reconcile_plan = apply.build_plan(f.repo, f.repo / apply.CLASSIFICATION_PATH,
                                       apply.CLASSIFICATION_SHA256, apply.CLASSIFICATION_COMMIT,
                                       reconcile_r1=True)
    (f.repo / apply.RECONCILE_PLAN_PATH).write_bytes(apply.encoded(f.reconcile_plan))
    f.reconcile_landed = commit(f, "disposable landed reconciliation")
    git(f, f.repo, "push", "-q", "origin", "dev")


@pytest.fixture
def reconciliation(fleet, monkeypatch):
    f = fleet
    # A reaped owner is evidence of a finished invocation, not a live process
    # whose PID is blanket-ignored by a mock.
    owner = int(subprocess.check_output([sys.executable, "-c", "import os; print(os.getpid())"]))
    for number, state in ((0, "tier3_exhausted"), (1, "tier3_exhausted"), (3, "tier3_short_circuited")):
        bus = f.targets[number] / ".agent_bus/recovery"
        bus.mkdir(parents=True)
        (bus / "recovery_status.json").write_bytes(apply.encoded(finished_recovery(state, owner)))

    def r1_idle(ident):
        if ident["path"] == str(f.targets[2]) and git(f, f.targets[2], "rev-parse", "HEAD") == f.landed:
            raise apply.Hold("Open target files/processes or uncertain lsof evidence")

    monkeypatch.setattr(apply, "process_idle", r1_idle)
    result = run(f)
    assert result["outcome_counts"] == {"HOLD": 3, "INCOMPLETE": 1}
    assert all(o["boundary"] is None and o["prepared_head"] is None for o in result["outcomes"])
    assert [git(f, t, "rev-parse", "HEAD") for t in f.targets] == [f.original, f.original, f.landed, f.original]
    assert all(not (f.operation / str(i) / "terminal-identity.json").exists() for i in (159, 163, 292, 305))
    monkeypatch.setattr(apply, "process_idle", lambda _ident: None)
    (f.repo / "tracked").write_text("reconciliation tracked revision\n")
    land_reconciliation(f, monkeypatch)
    return f


def run_reconciliation(f):
    return apply.apply_plan(f.repo, f.reconcile_plan, reconcile_r1=True)


def reconciliation_args(f):
    args = cli_args(f)
    args[-1] = str(f.repo / apply.RECONCILE_PLAN_PATH)
    return args + ["--reconcile-r1"]


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
    assert result["outcome_counts"] == {"MOVED": 4}, json.dumps(result, sort_keys=True, indent=2)
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


def test_reconciliation_moves_exact_four_with_original_provenance_and_new_preservation(reconciliation, monkeypatch):
    f = reconciliation
    original_receipts = apply.tree_manifest(f.operation)
    original_stats = {str(p): apply.stable_stat(p.stat()) for p in f.operation.rglob("*")}
    old_claim = f.common / f"rcx_fleet_apply_{apply.WAVE_ID}.json"
    claim_stat, claim_bytes = apply.stable_stat(old_claim.stat()), old_claim.read_bytes()
    (f.targets[2] / "ignored-evidence/new-before-reconciliation").write_bytes(b"new valuable evidence")
    before = [apply.tree_manifest(t) for t in f.targets]
    monkeypatch.setattr(apply, "process_idle", f.original_idle)
    invocations, real_execute = [], boundary.execute_terminal_mutation_once

    def observe(repo, identity, *, terminal_action, log):
        assert identity["worktree_identity"]["path"] in {str(t) for t in f.targets}
        assert identity["worktree_identity"]["path"] != str(f.repo)
        assert identity["expected_head"] == f.reconcile_landed

        def locked_move():
            with (f.common / "rcx_primary_worktree_sync.lock").open("rb") as stream:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return terminal_action()

        result = real_execute(repo, identity, terminal_action=locked_move, log=log)
        invocations.append(result)
        return result

    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", observe)
    result = run_reconciliation(f)
    assert result["outcome_counts"] == {"MOVED": 4}, result
    assert result["wave_id"] == apply.RECONCILE_WAVE_ID
    assert result["untouched_holds"] == 407 and result["fleet_clean"] is False
    assert len(invocations) == 4
    for index, (outcome, prior, invocation) in enumerate(zip(result["outcomes"], before, invocations)):
        assert invocation["fresh_fetch"] is True and invocation["behind_count"] == 0
        assert invocation["authority_consumed"] is True and invocation["action_succeeded"] is True
        assert outcome["source_identity"] == f.candidates[index]["source_identity"]
        assert outcome["source_identity"]["HEAD"] == f.original
        starting = f.landed if index == 2 else f.original
        assert outcome["action_time_head"] == starting
        assert outcome["prepared_head"] == f.reconcile_landed
        dest = Path(outcome["destination"])
        receipt = dest.parent
        assert json.loads((receipt / "before.json").read_bytes()) == prior
        assert (dest / "ignored-evidence/private.bin").read_bytes() == b"\x00private evidence\xff\n"
        assert (dest / "tracked").read_text() == "reconciliation tracked revision\n"
        assert os.readlink(dest / "ignored-evidence/dangling") == "missing-symlink-destination"
        assert git(f, dest, "bundle", "list-heads", str(receipt / "history.bundle")) == (
            starting + " " + outcome["source_identity"]["branch"])
        preparation = json.loads((receipt / "preparation.json").read_bytes())
        assert preparation["original"]["HEAD"] == f.original and preparation["action_time_head"] == starting
        assert len(outcome["process_checks"]) == 4
        assert all(d["returncode"] == 1 and d["stdout"] == d["stderr"] == ""
                   for d in outcome["process_checks"])
        assert not f.targets[index].exists()
    assert (Path(result["outcomes"][2]["destination"]) /
            "ignored-evidence/new-before-reconciliation").read_bytes() == b"new valuable evidence"
    assert apply.tree_manifest(f.operation) == original_receipts
    assert {str(p): apply.stable_stat(p.stat()) for p in f.operation.rglob("*")} == original_stats
    assert old_claim.read_bytes() == claim_bytes and apply.stable_stat(old_claim.stat()) == claim_stat
    with pytest.raises(apply.Hold, match="consumed|ambiguous"):
        run(f)
    with pytest.raises(apply.Hold, match="consumed|ambiguous"):
        run_reconciliation(f)
    f.reconcile_operation.rename(f.root / "new-receipts-preserved-elsewhere")
    with pytest.raises(apply.Hold, match="Existing|ambiguous"):
        run_reconciliation(f)


def test_reconciliation_planning_needs_no_local_receipts_or_live_target_reads(fleet, monkeypatch):
    f = fleet
    monkeypatch.setattr(apply, "R1_MERGE", f.landed)
    monkeypatch.setitem(apply.R1_RECEIPT_HASHES, "plan.json", apply.digest(apply.encoded(f.plan)))
    monkeypatch.setattr(apply, "read_r1_receipts", lambda *_: pytest.fail("planning read local R1 receipts"))
    monkeypatch.setattr(apply, "inspect_target", lambda *a, **k: pytest.fail("planning inspected a target"))
    before = [apply.tree_manifest(t) for t in f.targets] + [apply.tree_manifest(f.common)]
    monkeypatch.chdir(f.repo)
    assert apply.main(reconciliation_args(f)) == 0
    output = f.repo / apply.RECONCILE_PLAN_PATH
    raw = output.read_bytes()
    assert apply.main(reconciliation_args(f)) == 0 and output.read_bytes() == raw
    plan = json.loads(raw)
    assert plan["mutation_authorized"] is False and plan["conditional_candidates"] == 4
    assert plan["r1_authority"]["metadata_sha256"] == apply.R1_RECEIPT_HASHES
    candidates = [e for e in plan["entries"] if e["action"] != "UNTOUCHED_HOLD"]
    assert [e["source_index"] for e in candidates] == [159, 163, 292, 305]
    assert all(e == f.plan["entries"][e["source_index"]]
               for e in plan["entries"] if e["action"] == "UNTOUCHED_HOLD")
    assert " --reconcile-r1 " in plan["postmerge_command"]
    assert plan["operation_root"] == str(f.reconcile_operation)
    assert [apply.tree_manifest(t) for t in f.targets] + [apply.tree_manifest(f.common)] == before
    assert not f.operation.exists() and not f.reconcile_operation.exists()
    assert (f.repo / apply.PLAN_PATH).read_bytes() == apply.encoded(f.plan)
    output.write_bytes(b"unrelated output\n")
    assert apply.main(reconciliation_args(f)) == 2
    assert output.read_bytes() == b"unrelated output\n"


@pytest.mark.parametrize("name", tuple(apply.R1_RECEIPT_HASHES))
def test_changed_pinned_r1_receipt_stops_before_followup_claim(reconciliation, name):
    f = reconciliation
    path = f.operation / name
    path.write_bytes(path.read_bytes() + b"\n")
    before = [apply.tree_manifest(t) for t in f.targets]
    with pytest.raises(apply.Hold, match="R1 receipt SHA-256 changed"):
        run_reconciliation(f)
    assert not f.reconcile_operation.exists()
    assert not (f.common / f"rcx_fleet_apply_{apply.RECONCILE_WAVE_ID}.json").exists()
    assert [apply.tree_manifest(t) for t in f.targets] == before


@pytest.mark.parametrize("index", (159, 163, 292, 305))
def test_nonnull_old_boundary_is_never_reconciled(reconciliation, monkeypatch, index):
    f = reconciliation
    path = f.operation / str(index) / "outcome.json"
    value = json.loads(path.read_bytes())
    value["boundary"] = {"action_invoked": True}
    path.write_bytes(apply.encoded(value))
    # Even a re-pinned contradictory packet cannot make an old callback safe.
    land_reconciliation(f, monkeypatch)
    with pytest.raises(apply.Hold, match="no-terminal-action"):
        run_reconciliation(f)
    assert not f.reconcile_operation.exists()


@pytest.mark.parametrize("relative", ("159/preparation.json", "163/terminal-identity.json",
                                      "292/move-started.json", "305/worktree"))
def test_prior_stage_or_destination_refuses_followup(reconciliation, relative):
    f = reconciliation
    path = f.operation / relative
    if path.name == "worktree":
        path.mkdir()
    else:
        path.write_bytes(b"{}\n")
    with pytest.raises(apply.Hold, match="stages changed|terminal action"):
        run_reconciliation(f)
    assert not f.reconcile_operation.exists()


@pytest.mark.parametrize("name,field", (("292/preparation.json", "prepared_head"),
                                       ("292/outcome.json", "prepared_head"),
                                       ("summary.json", "untouched_holds")))
def test_contradictory_receipt_semantics_hold_even_when_repinned(reconciliation, monkeypatch, name, field):
    f = reconciliation
    path = f.operation / name
    value = json.loads(path.read_bytes())
    value[field] = f.original if field == "prepared_head" else 406
    path.write_bytes(apply.encoded(value))
    land_reconciliation(f, monkeypatch)
    with pytest.raises(apply.Hold, match="contradicts"):
        run_reconciliation(f)
    assert not f.reconcile_operation.exists()


@pytest.mark.parametrize("name", ("before.tar", "gitdir-before.tar", "history.bundle"))
def test_corrupt_r1_preservation_stops_before_adopting_prepared_target(reconciliation, name):
    f = reconciliation
    path = f.operation / "292" / name
    raw = path.read_bytes()
    if name == "before.tar":
        raw = raw.replace(b"original tracked evidence", b"CORRUPT! tracked evidence", 1)
    elif name == "gitdir-before.tar":
        raw = raw.replace(b"original fetch evidence", b"CORRUPT! fetch evidence", 1)
    else:
        raw += b"changed history"
    assert raw != path.read_bytes()
    path.write_bytes(raw)
    with pytest.raises(apply.Hold, match="archive|bundle"):
        run_reconciliation(f)
    assert not f.reconcile_operation.exists()


def test_missing_r1_evidence_and_changed_common_claim_refuse_apply(reconciliation):
    f = reconciliation
    path = f.common / f"rcx_fleet_apply_{apply.WAVE_ID}.json"
    raw = path.read_bytes()
    path.write_bytes(raw + b"\n")
    with pytest.raises(apply.Hold, match="claim changed"):
        run_reconciliation(f)
    path.write_bytes(raw)
    (f.operation / "292/before.tar").unlink()
    with pytest.raises(apply.Hold, match="stages changed"):
        run_reconciliation(f)
    assert not f.reconcile_operation.exists()


@pytest.mark.parametrize("drift", ("prepared_head", "original_head", "transition", "ignored_evidence"))
def test_r1_action_time_drift_holds_only_the_affected_identity(reconciliation, drift):
    f = reconciliation
    affected = 0 if drift == "original_head" else 2
    target = f.targets[affected]
    if drift in ("prepared_head", "original_head"):
        git(f, target, "merge", "--ff-only", f.reconcile_landed)
    elif drift == "transition":
        (Path(f.candidates[2]["source_identity"]["git_dir"]) / "ORIG_HEAD").write_text(f.classification_commit)
    else:
        (target / "ignored-evidence/private.bin").write_bytes(b"changed original evidence")
    before = apply.tree_manifest(target)
    result = run_reconciliation(f)
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}, result
    assert result["outcomes"][affected]["status"] == "HOLD"
    assert apply.tree_manifest(target) == before
    assert not (Path(result["outcomes"][affected]["destination"]).parent / "preparation.json").exists()


@pytest.fixture
def native_evidence():
    with tempfile.TemporaryDirectory(prefix="rcx-native-idle-", dir="/tmp") as directory:
        target = Path(directory).resolve()
        bus = target / ".agent_bus/recovery"
        bus.mkdir(parents=True)
        yield target, bus / "recovery_status.json"


@pytest.mark.parametrize("state", ("tier3_exhausted", "tier3_short_circuited"))
def test_observed_finished_recovery_is_accepted_only_in_reconciliation(native_evidence, state):
    target, status = native_evidence
    status.write_bytes(apply.encoded(finished_recovery(state)))
    before = apply.tree_manifest(target)
    apply.native_idle(target, before, reconcile_r1=True)
    with pytest.raises(apply.Hold, match="active or uncertain"):
        apply.native_idle(target, before)
    assert apply.tree_manifest(target) == before


@pytest.mark.parametrize("change", (
    dict(active=True), dict(active=None), dict(finished_at=None), dict(finished_at=""),
    dict(finished_at="2026-08-22T11:07:15"), dict(status="running"), dict(state="tier3_error"),
    dict(recovered=True), dict(exhausted=False), dict(current_command="still working"),
    dict(child_pid=os.getpid()), dict(owner_pid=os.getpid()),
))
def test_incoherent_finish_or_live_ownership_stays_hold(native_evidence, change):
    target, status = native_evidence
    value = finished_recovery("tier3_exhausted")
    value.update(change)
    status.write_bytes(apply.encoded(value))
    with pytest.raises(apply.Hold):
        apply.native_idle(target, apply.tree_manifest(target), reconcile_r1=True)


def test_finished_record_does_not_override_a_held_native_lock(native_evidence):
    target, status = native_evidence
    status.write_bytes(apply.encoded(finished_recovery("tier3_short_circuited")))
    with (status.parent / "bridge.lock").open("wb") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(apply.Hold, match="lock is active"):
            apply.native_idle(target, apply.tree_manifest(target), reconcile_r1=True)


@pytest.mark.parametrize("value", (dict(active=False), dict(active=False, state="completed", status="running")))
def test_reconciliation_holds_missing_or_conflicting_native_state(native_evidence, value):
    target, status = native_evidence
    status.write_bytes(apply.encoded(value))
    with pytest.raises(apply.Hold, match="active or uncertain"):
        apply.native_idle(target, apply.tree_manifest(target), reconcile_r1=True)


def test_saved_pytest_bus_is_preserved_without_becoming_native_owner(native_evidence):
    target, status = native_evidence
    status.write_bytes(apply.encoded(finished_recovery("tier3_exhausted")))
    saved = target / ".scratch/phase-b/tmp/pytest-4/repo/.agent_bus-test/recovery/recovery_status.json"
    saved.parent.mkdir(parents=True)
    saved.write_text('{"active":true,"wave_id":"saved-fixture"}')
    before = apply.tree_manifest(target)
    apply.native_idle(target, before, reconcile_r1=True)
    assert apply.tree_manifest(target) == before


@pytest.mark.parametrize("lock_name, holder", (
    ("bridge.lock", "bridge_supervisor"), ("meta_bridge.lock", "meta_bridge_supervisor"),
))
def test_available_lock_reconciles_exact_dead_native_metadata(native_evidence, lock_name, holder):
    target, status = native_evidence
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    lock = status.parent.parent / lock_name
    lock.write_bytes(apply.encoded(dict(pid=child.pid, holder=holder,
        acquired_at_utc="2026-07-22T03:30:03.376325+00:00", lock_path=str(lock))))
    before = apply.tree_manifest(target)
    apply.native_idle(target, before, reconcile_r1=True)
    with pytest.raises(apply.Hold, match="metadata remains ambiguous or live"):
        apply.native_idle(target, before)
    assert apply.tree_manifest(target) == before


@pytest.mark.parametrize("change, reason", (
    (dict(acquired_at_utc=None), "timestamp"),
    (dict(acquired_at_utc=123), "timestamp"),
    (dict(acquired_at_utc=False), "timestamp"),
    (dict(acquired_at_utc=[]), "timestamp"),
    (dict(acquired_at_utc={}), "timestamp"),
    (dict(acquired_at_utc=""), "timestamp"),
    (dict(acquired_at_utc="not-a-timestamp"), "timestamp"),
    (dict(acquired_at_utc="2026-07-22T03:30:03"), "timestamp"),
    (dict(holder=[]), "metadata"),
    (dict(holder={}), "metadata"),
    (dict(lock_path=None), "metadata"),
    (dict(pid=True), "metadata"),
    (dict(pid=os.getpid()), "metadata"),
))
def test_malformed_stale_lock_metadata_holds_without_changing_evidence(native_evidence, change, reason):
    target, status = native_evidence
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    lock = status.parent.parent / "bridge.lock"
    value = dict(pid=child.pid, holder="bridge_supervisor",
                 acquired_at_utc="2026-07-22T03:30:03.376325+00:00", lock_path=str(lock))
    value.update(change)
    lock.write_bytes(apply.encoded(value))
    before = apply.tree_manifest(target)
    with pytest.raises(apply.Hold, match="Native owner lock " + reason):
        apply.native_idle(target, before, reconcile_r1=True)
    assert apply.tree_manifest(target) == before


@pytest.mark.parametrize("raw", (b'{"pid":', b"\xff", b"[]", b"null"))
def test_malformed_stale_lock_document_is_a_hold(native_evidence, raw):
    target, status = native_evidence
    lock = status.parent.parent / "bridge.lock"
    lock.write_bytes(raw)
    before = apply.tree_manifest(target)
    with pytest.raises(apply.Hold, match="Native owner lock metadata"):
        apply.native_idle(target, before, reconcile_r1=True)
    assert apply.tree_manifest(target) == before


@pytest.mark.parametrize("mode, trusted, allowed", [("r", True, True), ("w", True, False),
                                                    ("cwd", True, False), ("r", False, False)])
def test_real_open_descriptors_distinguish_readers_writers_and_cwd(native_evidence, monkeypatch, mode, trusted, allowed):
    if not shutil.which("lsof"):
        pytest.skip("lsof unavailable; production holds when OS evidence is unavailable")
    target, _ = native_evidence
    source = target / "content.bin"
    source.write_bytes(b"stable captured bytes")
    code = ("import os,sys; p=sys.stdin.readline().strip(); m=sys.argv[1]; "
            "fd=os.chdir(p) if m=='cwd' else os.open(p,os.O_RDONLY if m=='r' else os.O_WRONLY); "
            "print('ready',flush=True); sys.stdin.read()")
    child = subprocess.Popen([sys.executable, "-c", code, mode], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)
    try:
        child.stdin.write(str(target if mode == "cwd" else source) + "\n")
        child.stdin.flush()
        assert child.stdout.readline().strip() == "ready"
        # Simulate only OS executable identity; descriptor/access/inode/device
        # discovery and byte verification use the real kernel and filesystem.
        monkeypatch.setattr(apply, "_indexer_executable", lambda pid: trusted and pid == child.pid)
        ident = dict(path=str(target), git_dir=None, branch="")
        if allowed:
            try:
                result = apply.process_idle(ident)
            except apply.Hold as exc:
                pytest.fail(json.dumps(exc.diagnostic))
            readers = result["verified_read_only_indexers"]
            assert readers[0]["inode"] == source.stat().st_ino
            assert readers[0]["sha256"] == apply.file_hash(source)
        else:
            with pytest.raises(apply.Hold):
                apply.process_idle(ident)
        assert source.read_bytes() == b"stable captured bytes"
    finally:
        child.terminate()
        child.wait(timeout=10)
        child.stdin.close()
        child.stdout.close()


@pytest.mark.parametrize("returncode", (0, 1))
@pytest.mark.parametrize("shape,allowed", (
    ("complete_reader", True), ("complete_readers", True),
    ("trailing_pid", False), ("unterminated_pid", False),
    ("trailing_process", False), ("unterminated_command", False),
    ("leading_process_without_descriptor", False),
    ("intermediate_process_without_descriptor", False),
    ("trailing_descriptor", False), ("unterminated_descriptor", False),
    ("missing_access", False), ("missing_type", False),
    ("missing_device", False), ("missing_inode", False), ("missing_path", False),
    ("orphan_command", False), ("missing_command", False),
    ("duplicate_command", False), ("unknown_field", False),
    ("writer", False), ("cwd", False), ("unknown_reader", False),
))
def test_indexing_exception_requires_complete_lsof_records(native_evidence, monkeypatch,
                                                          returncode, shape, allowed):
    target, _ = native_evidence
    source = target / "content.bin"
    source.write_bytes(b"stable captured bytes\x00\xff")
    before = apply.tree_manifest(target)
    info = source.stat()

    def record(pid, *, command="mdworker_shared", fd="4", access="r", kind="REG", path=source):
        return (f"p{pid}\nc{command}\nf{fd}\na{access}\nt{kind}\n"
                f"D{info.st_dev:x}\ni{info.st_ino}\nn{path}\n").encode()

    first, second = record(12345), record(23456)
    incomplete_process = b"p43434\ncunknown\n"
    output = {
        "complete_reader": first,
        "complete_readers": first + second,
        "trailing_pid": first + b"p43434\n",
        "unterminated_pid": first + b"p43434",
        "trailing_process": first + incomplete_process,
        "unterminated_command": first + incomplete_process.rstrip(b"\n"),
        "leading_process_without_descriptor": incomplete_process + first,
        "intermediate_process_without_descriptor": first + incomplete_process + second,
        "trailing_descriptor": first + incomplete_process + b"f5\n",
        "unterminated_descriptor": first + second.rstrip(b"\n"),
        "orphan_command": b"cunknown\n" + first,
        "missing_command": first + second.replace(b"cmdworker_shared\n", b""),
        "duplicate_command": first + second.replace(b"cmdworker_shared\n", b"cmdworker_shared\ncunknown\n"),
        "unknown_field": first + b"?unresolved\n",
        "writer": first + record(23456, access="w"),
        "cwd": first + record(23456, fd="cwd", access=" ", kind="DIR", path=target),
        "unknown_reader": first + record(43434, command="unknown"),
    }
    for name, key in (("access", b"a"), ("type", b"t"), ("device", b"D"),
                      ("inode", b"i"), ("path", b"n")):
        output["missing_" + name] = first + b"".join(
            field for field in second.splitlines(keepends=True) if not field.startswith(key))
    stdout = output[shape]

    def probe(command, **kwargs):
        if command == ["ps", "-A", "-ww", "-o", "pid=,command="]:
            return SimpleNamespace(returncode=0, stdout=f"{os.getpid()} test\n".encode(), stderr=b"")
        assert command == ["lsof", "-nP", "+D", str(target), "-FpcfatDin"]
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=b"")

    monkeypatch.setattr(apply.subprocess, "run", probe)
    monkeypatch.setattr(apply, "_indexer_executable", lambda pid: pid in {12345, 23456})
    ident = dict(path=str(target), git_dir=None, branch="")
    if allowed:
        diagnostic = apply.process_idle(ident)
        readers = diagnostic["verified_read_only_indexers"]
        assert [reader["pid"] for reader in readers] == (
            [12345, 23456] if shape == "complete_readers" else [12345])
        assert all(reader["inode"] == info.st_ino and reader["device"] == info.st_dev
                   and reader["sha256"] == apply.file_hash(source) for reader in readers)
    else:
        with pytest.raises(apply.Hold, match="uncertain lsof") as raised:
            apply.process_idle(ident)
        diagnostic = raised.value.diagnostic
        assert "verified_read_only_indexers" not in diagnostic
    assert diagnostic["returncode"] == returncode
    assert diagnostic["stdout"] == stdout.decode() and diagnostic["stderr"] == ""
    assert apply.tree_manifest(target) == before


def test_actual_later_success_recovery_schema_is_historical(native_evidence):
    target, status = native_evidence
    value = finished_recovery("tier3_exhausted")
    value.update(state="resolved_by_later_success", outcome="cleared", recovered=True,
                 exhausted=False, last_action="later_success")
    status.write_bytes(apply.encoded(value))
    before = apply.tree_manifest(target)
    apply.native_idle(target, before, reconcile_r1=True)
    assert apply.tree_manifest(target) == before


@pytest.mark.parametrize("returncode,stdout,stderr", (
    (0, b"p123\nnopen-file\n", b""), (1, b"", b"lsof: warning: cannot stat"),
    (1, b"unresolved handle", b""), (2, b"", b""), (1, b"", b""),
))
def test_lsof_requires_clear_fresh_evidence_and_retains_diagnostics(native_evidence, monkeypatch,
                                                                 returncode, stdout, stderr):
    target, _ = native_evidence
    ident = dict(path=str(target), git_dir=str(target / "admin"), branch="refs/heads/fixture")
    calls = []

    def probe(command, **kwargs):
        calls.append(command)
        if command[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=f"{os.getpid()} test\n".encode(), stderr=b"")
        assert command == ["lsof", "-nP", "+D", str(target), "-FpcfatDin"]
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(apply.subprocess, "run", probe)
    if (returncode, stdout, stderr) == (1, b"", b""):
        diagnostic = apply.process_idle(ident)
    else:
        with pytest.raises(apply.Hold, match="uncertain lsof") as raised:
            apply.process_idle(ident)
        diagnostic = raised.value.diagnostic
    assert diagnostic["returncode"] == returncode
    assert diagnostic["stdout"] == stdout.decode() and diagnostic["stderr"] == stderr.decode()
    assert diagnostic["command"] == calls[-1] and diagnostic["observed_at"]


def test_lsof_timeout_retains_partial_evidence(native_evidence, monkeypatch):
    target, _ = native_evidence

    def probe(command, **kwargs):
        if command[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=f"{os.getpid()} test\n".encode(), stderr=b"")
        raise subprocess.TimeoutExpired(command, 30, output=b"p123", stderr=b"unresolved")

    monkeypatch.setattr(apply.subprocess, "run", probe)
    with pytest.raises(apply.Hold, match="uncertain lsof") as raised:
        apply.process_idle(dict(path=str(target), git_dir=str(target / "admin"), branch="refs/heads/fixture"))
    assert raised.value.diagnostic["returncode"] is None
    assert raised.value.diagnostic["stdout"] == "p123" and raised.value.diagnostic["stderr"] == "unresolved"


def test_reconciliation_protection_and_active_ownership_remain_individual_holds(reconciliation):
    f = reconciliation
    status = f.targets[0] / ".agent_bus/recovery/recovery_status.json"
    value = json.loads(status.read_bytes())
    value["owner_pid"] = os.getpid()
    status.write_bytes(apply.encoded(value))
    with (f.repo / "TASKS.md").open("a") as stream:
        stream.write("\nPreserve " + str(f.targets[1]) + "\n")
    before = [apply.tree_manifest(t) for t in f.targets[:2]]
    result = run_reconciliation(f)
    assert [o["status"] for o in result["outcomes"]] == ["HOLD", "HOLD", "MOVED", "MOVED"]
    assert [apply.tree_manifest(t) for t in f.targets[:2]] == before


def test_reconciliation_callback_refetch_holds_on_remote_advance(reconciliation, monkeypatch):
    f = reconciliation
    real_execute = boundary.execute_terminal_mutation_once

    def advance(repo, ident, **kwargs):
        if ident["worktree_identity"]["path"] == str(f.targets[0]):
            (f.repo / "new-upstream").write_text("remote advanced after exact target binding\n")
            commit(f, "remote advancement before reconciliation callback")
            git(f, f.repo, "push", "-q", "origin", "dev")
        return real_execute(repo, ident, **kwargs)

    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", advance)
    result = run_reconciliation(f)
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}
    first = result["outcomes"][0]
    assert first["boundary"]["fresh_fetch"] is True
    assert first["boundary"]["behind_count"] == 1 and first["boundary"]["action_invoked"] is False
    assert not (Path(first["destination"]).parent / "move-started.json").exists()


def test_reconciliation_callback_never_reuses_an_earlier_clear_lsof(reconciliation, monkeypatch):
    f = reconciliation
    real_run, real_execute = apply.subprocess.run, boundary.execute_terminal_mutation_once
    binding_finished = False

    def probe(command, **kwargs):
        if command[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=f"{os.getpid()} test\n".encode(), stderr=b"")
        if command[0] == "lsof":
            stderr = b"lsof: uncertain callback observation" if binding_finished and str(f.targets[0]) in command else b""
            return SimpleNamespace(returncode=1, stdout=b"", stderr=stderr)
        return real_run(command, **kwargs)

    def execute(repo, ident, **kwargs):
        nonlocal binding_finished
        binding_finished = True
        return real_execute(repo, ident, **kwargs)

    monkeypatch.setattr(apply.subprocess, "run", probe)
    monkeypatch.setattr(apply, "process_idle", f.original_idle)
    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", execute)
    result = run_reconciliation(f)
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}
    first = result["outcomes"][0]
    assert first["boundary"]["action_invoked"] is True and first["boundary"]["fresh_fetch"] is True
    assert first["process_checks"][0]["stderr"] == ""
    assert first["process_checks"][-1]["stderr"] == "lsof: uncertain callback observation"
    assert not (Path(first["destination"]).parent / "move-started.json").exists()


def test_changed_r1_receipt_after_binding_prevents_all_remaining_moves(reconciliation, monkeypatch):
    f = reconciliation
    real_execute = boundary.execute_terminal_mutation_once

    def change_receipt(repo, identity, **kwargs):
        with (f.operation / "summary.json").open("ab") as stream:
            stream.write(b"\n")
        return real_execute(repo, identity, **kwargs)

    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", change_receipt)
    result = run_reconciliation(f)
    assert result["outcome_counts"] == {"HOLD": 4}, result
    assert all(t.exists() for t in f.targets)
    assert all(not (Path(o["destination"]).parent / "move-started.json").exists() for o in result["outcomes"])


def test_reconciliation_callback_rechecks_new_preservation(reconciliation, monkeypatch):
    f = reconciliation
    real_execute = boundary.execute_terminal_mutation_once

    def change_archive(repo, identity, **kwargs):
        if identity["worktree_identity"]["path"] == str(f.targets[0]):
            with (f.reconcile_operation / "159/before.tar").open("ab") as stream:
                stream.write(b"changed after binding")
        return real_execute(repo, identity, **kwargs)

    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", change_archive)
    result = run_reconciliation(f)
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 3}
    first = result["outcomes"][0]
    assert first["boundary"]["fresh_fetch"] is True and first["boundary"]["action_invoked"] is True
    assert first["boundary"]["action_error"] == "Hold: Current preservation changed before mutation"
    assert f.targets[0].exists() and not (f.reconcile_operation / "159/move-started.json").exists()


def test_prepared_target_new_ignored_collision_is_preserved_before_further_fast_forward(reconciliation):
    f = reconciliation
    (f.repo / "collision").write_text("upstream tracked file\n")
    commit(f, "new reconciliation collision")
    git(f, f.repo, "push", "-q", "origin", "dev")
    with (f.common / "info/exclude").open("a") as stream:
        stream.write("\ncollision\n")
    (f.targets[2] / "collision").write_bytes(b"current private evidence")
    result = run_reconciliation(f)
    assert result["outcome_counts"] == {"MOVED": 3, "INCOMPLETE": 1}, result
    assert (f.targets[2] / "collision").read_bytes() == b"current private evidence"
    outcome = result["outcomes"][2]
    assert outcome["boundary"] is None
    with tarfile.open(Path(outcome["destination"]).parent / "before.tar") as archive:
        assert archive.extractfile("./collision").read() == b"current private evidence"


def test_reconciliation_requires_merged_authority_exact_mode_and_destination(reconciliation, monkeypatch):
    f = reconciliation
    monkeypatch.chdir(f.repo)
    assert apply.main(reconciliation_args(f) + ["--apply", "--operation-root", str(f.operation)]) == 2
    with pytest.raises(apply.Hold, match="plan does not match"):
        apply.apply_plan(f.repo, f.reconcile_plan)
    (f.repo / apply.TOOL_PATH).write_bytes(b"unlanded reconciliation tool\n")
    with pytest.raises(apply.Hold, match="Unlanded|modified"):
        run_reconciliation(f)
    assert not f.reconcile_operation.exists()


def residual_fixture(f, monkeypatch, *, shell_count=1, dev=False, wave_id=None):
    import workingrcx_fleet_census as census_tool
    import workingrcx_fleet_classification as classifier
    git(f, f.repo, "checkout", "-qb", "founder/primary")
    shells = []
    for index in range(shell_count):
        shell = f.root / f"WorkingRCX-retired-shell-{index:02d}"
        bus = shell / ".agent_bus-retired/observability"
        bus.mkdir(parents=True)
        (bus / "events.jsonl").write_bytes(b'{"terminal":true}\n')
        shells.append(shell)
    if dev:
        target = f.root / "workingrcx_clarolesfull_20260627"
        git(f, f.repo, "worktree", "add", str(target), "dev")
        (target / "tracked").write_bytes(b"held dev work\n")
        git(f, target, "stash", "push", "-m", "held TASKS history")
        f.held_stash = git(f, target, "rev-parse", "refs/stash")
        (target / "tracked").write_bytes(b"current dev WIP\n")
        (target / "new-evidence").write_bytes(b"\xffuntracked dev\n")
        f.local_dev = target
    classification_rel, census_rel, plan_rel = apply.residual_paths(wave_id or apply.RESIDUAL_WAVE_ID)
    census = census_tool.census(str(f.root), str(f.repo), comparison_commit=f.landed if wave_id else None)
    census_path = f.repo / census_rel
    census_path.write_bytes(apply.encoded(census))
    classification = classifier.classify(census, source_sha256=apply.digest(census_path.read_bytes()),
        base_commit=f.landed, carrier=str(f.repo), landed=False, residual=True, wave_id=wave_id)
    expected_actions = {str(f.repo): "UNTOUCHED_HOLD",
                        **{str(t): "PRESERVE_WORKTREE" for t in f.targets},
                        **{str(s): "PRESERVE_BUS_SHELL" for s in shells}}
    if dev:
        expected_actions[str(f.local_dev)] = "SYNC_LOCAL_DEV"
    assert {r["path"]: r["proposed_action"] for r in classification["entries"]} == expected_actions, json.dumps([
        dict(path=r["path"], action=r["proposed_action"], reasons=r["reasons"], errors=r["source"]["errors"])
        for r in classification["entries"]
    ], indent=2)
    classification_path = f.repo / classification_rel
    classification_path.write_bytes(apply.encoded(classification))
    sha = apply.digest(classification_path.read_bytes())
    if wave_id:
        (f.repo / f"reports/control_plane/{wave_id}_useful_work.json").write_bytes(
            apply.encoded(classifier.useful_work_report(classification, sha)))
    plan = apply.build_residual_plan(f.repo, classification_path, sha, wave_id=wave_id or apply.RESIDUAL_WAVE_ID)
    (f.repo / plan_rel).write_bytes(apply.encoded(plan))
    for rel in ("mu/tools/executors/workingrcx_fleet_census.py",
                "mu/tools/executors/workingrcx_fleet_classification.py",
                "mu/tools/observability/pipeline_agent_pager.py"):
        path = f.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REPO_ROOT / rel).read_bytes())
    (f.repo / "tracked").write_bytes(b"new authority dev revision\n")
    f.residual_authority = commit(f, "reviewed residual classification/tool/plan")
    git(f, f.repo, "push", "-q", "origin", "HEAD:dev")
    f.residual_plan, f.shells = plan, shells
    return plan


def test_fresh_wave_authority_is_isolated_and_keeps_prior_operations_immutable(fleet, monkeypatch):
    f = fleet
    prior = {name: (f.repo / name).read_bytes() for name in (
        apply.PLAN_PATH, apply.CLASSIFICATION_PATH)}
    wave = "fresh-native-lifecycle-2026-09-14"
    plan = residual_fixture(f, monkeypatch, wave_id=wave)
    assert not (f.repo / "mu/tools/executors/worktree_lifecycle.py").exists()
    assert plan["wave_id"] == wave
    operation = plan["operations"][0]
    assert operation["operation_id"].startswith(wave + "-")
    kwargs = dict(authority_commit=f.residual_authority, batch=1,
                  operation_root=Path(operation["operation_root"]))
    result = apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert result["outcome_counts"] == {"MOVED": 5}, result
    assert apply.verify_residual_plan(f.repo, plan, **kwargs)["batch_complete"] is True
    with pytest.raises(apply.Hold, match="consumed"):
        apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert {name: (f.repo / name).read_bytes() for name in prior} == prior


def test_residual_bounded_operations_preserve_bytes_registration_and_no_replay(fleet, monkeypatch):
    f = fleet
    plan = residual_fixture(f, monkeypatch, shell_count=13)
    assert len(plan["operations"]) == 2
    assert all(len(o["source_indices"]) <= 12 for o in plan["operations"])
    original_branches = [git(f, t, "symbolic-ref", "HEAD") for t in f.targets]
    for operation in plan["operations"]:
        kwargs = dict(authority_commit=f.residual_authority, batch=operation["batch"],
                      operation_root=Path(operation["operation_root"]))
        result = apply.apply_residual_plan(f.repo, plan, **kwargs)
        assert result["outcome_counts"] == {"MOVED": len(operation["source_indices"])}, json.dumps(result, indent=2)
        verified = apply.verify_residual_plan(f.repo, plan, **kwargs)
        assert verified["batch_complete"] is True
        assert verified["recorded_before"] - verified["recorded_after"] == len(operation["source_indices"])
        with pytest.raises(apply.Hold, match="consumed"):
            apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert all(not t.exists() for t in [*f.targets, *f.shells])
    for branch in original_branches:
        assert git(f, f.repo, "rev-parse", branch) == f.residual_authority
    registrations = git(f, f.repo, "worktree", "list", "--porcelain")
    for entry in plan["entries"]:
        if entry["action"] == "PRESERVE_WORKTREE":
            assert entry["destination"] in registrations
            assert (Path(entry["destination"]) / "ignored-evidence/private.bin").read_bytes() == b"\x00private evidence\xff\n"
    # Tampered preserved bytes cannot verify even with a recorded success.
    shell_entry = next(e for e in plan["entries"] if e["action"] == "PRESERVE_BUS_SHELL")
    (Path(shell_entry["destination"]) / ".agent_bus-retired/observability/events.jsonl").write_bytes(b"changed")
    operation = next(o for o in plan["operations"] if shell_entry["source_index"] in o["source_indices"])
    with pytest.raises(apply.Hold, match="destination bytes"):
        apply.verify_residual_plan(f.repo, plan, authority_commit=f.residual_authority,
            batch=operation["batch"], operation_root=Path(operation["operation_root"]))


def test_residual_dirty_dev_sync_and_independent_changed_shell_hold(fleet, monkeypatch):
    f = fleet
    plan = residual_fixture(f, monkeypatch, dev=True)
    # A new file invalidates this shell's exact shape. Eligible peers still run.
    (f.shells[0] / "unexpected").write_bytes(b"valuable new WIP")
    operation = plan["operations"][0]
    kwargs = dict(authority_commit=f.residual_authority, batch=1,
                  operation_root=Path(operation["operation_root"]))
    result = apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert result["outcome_counts"] == {"MOVED": 4, "HOLD": 1, "SYNCED_LOCAL_DEV": 1}, json.dumps(result, indent=2)
    held = next(o for o in result["outcomes"] if o["status"] == "HOLD")
    assert held["source_identity"]["path"] == str(f.shells[0])
    assert held["reason"] == "Residual shell shape changed"
    assert (f.shells[0] / "unexpected").read_bytes() == b"valuable new WIP"
    assert f.local_dev.is_dir() and f.shells[0].is_dir()
    assert git(f, f.local_dev, "rev-parse", "HEAD") == f.residual_authority
    assert git(f, f.local_dev, "symbolic-ref", "HEAD") == "refs/heads/dev"
    assert f.held_stash in git(f, f.repo, "stash", "list", "--format=%H").splitlines()
    assert (f.local_dev / "new-evidence").read_bytes() == b"\xffuntracked dev\n"
    outcome = next(o for o in result["outcomes"] if o["status"] == "SYNCED_LOCAL_DEV")
    stash = outcome["checkout_sync"]["tracked_wip_stash_oid"]
    assert git(f, f.repo, "show", stash + ":tracked") == "current dev WIP"
    assert apply.verify_residual_plan(f.repo, plan, **kwargs)["batch_complete"] is False


def test_residual_refuses_unlanded_authority_and_modified_manifest(fleet, monkeypatch):
    f = fleet
    plan = residual_fixture(f, monkeypatch)
    operation = plan["operations"][0]
    root = Path(operation["operation_root"])
    (f.repo / apply.TOOL_PATH).write_bytes(b"unreviewed tool")
    with pytest.raises(apply.Hold, match="uncommitted or modified"):
        apply.apply_residual_plan(f.repo, plan, authority_commit=f.residual_authority,
                                  batch=1, operation_root=root)
    assert not root.exists()
    forged = deepcopy(plan)
    forged["entries"][operation["source_indices"][0]]["destination"] = str(f.repo)
    with pytest.raises(apply.Hold, match="fresh classification"):
        apply.apply_residual_plan(f.repo, forged, authority_commit=f.residual_authority,
                                  batch=1, operation_root=root)
    assert all(t.exists() for t in f.targets)


def transaction_case(f, *, current=True, wip="clean"):
    import workingrcx_fleet_census as census_tool
    target = f.targets[0]
    if current:
        git(f, target, "merge", "--ff-only", f.landed)
    if wip == "mixed":
        (target / "wip.txt").write_bytes(b"staged useful bytes\n")
        git(f, target, "add", "wip.txt")
        (target / "wip.txt").write_bytes(b"unstaged useful bytes\n")
    elif wip == "deletion":
        git(f, target, "rm", "--", ".gitignore")
    elif wip == "overlap":
        (target / "tracked").write_bytes(b"staged overlapping bytes\n")
        git(f, target, "add", "tracked")
        (target / "tracked").write_bytes(b"unstaged overlapping bytes\n")
    directory = f.root / "transaction-evidence"
    directory.mkdir()
    useful = census_tool.useful_work(str(target), f.landed)
    entry = dict(source_identity={**f.candidates[0]["source_identity"], "HEAD": f.landed if current else f.original},
        path=str(target), destination=str(directory / "worktree"), action="PRESERVE_WORKTREE",
        owner="[FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]", comparison_commit=f.landed,
        useful_work=useful, landing_owner=None if useful["status"] == "COVERED" else dict(
            task="FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION", wave_id="transaction-fixture-missing-work",
            source_path=str(target), source_branch=git(f, target, "symbolic-ref", "HEAD"),
            scope=[c["path"] for c in useful["changes"]], status="PENDING_NATIVE_LANDING_REVIEW"))
    return target, entry, directory


def stage_index_only(f, target):
    blob = subprocess.run([f.git, "-C", str(target), "hash-object", "-w", "--stdin"],
        input=b"late index-only useful work\n", env=f.env, capture_output=True, check=True).stdout.decode().strip()
    git(f, target, "update-index", "--cacheinfo", "100644," + blob + ",tracked")
    return blob


@pytest.mark.parametrize("mode", [0o600, 0o640, 0o700])
def test_native_stash_keeps_git_identity_and_restores_filesystem_permissions(fleet, mode):
    f = fleet
    target, entry, directory = transaction_case(f, current=False, wip="mixed")
    (target / "wip.txt").chmod(mode)
    # Rebind the fresh fixture admission after its deliberate permission edit.
    import workingrcx_fleet_census as census_tool
    entry["useful_work"] = census_tool.useful_work(str(target), f.landed)
    original = apply.transaction_state(target)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert outcome["status"] == "MOVED", outcome
    admitted = json.loads((directory / "admitted-state.json").read_text())
    stash = json.loads((directory / "sync-stash.json").read_text())
    assert stash["base"] == admitted["head"]
    assert stash["index"] == admitted["index"]
    assert admitted["content"]["wip.txt"]["mode"] == mode
    assert stash["content"]["wip.txt"] == {
        **original["content"]["wip.txt"], "mode": 0o755 if mode & 0o100 else 0o644,
    }
    destination = Path(entry["destination"])
    assert destination.joinpath("wip.txt").stat().st_mode & 0o777 == mode
    assert apply.transaction_state(destination)["index"]["wip.txt"] == original["index"]["wip.txt"]
    apply.verify_archive(directory / "before.tar", json.loads((directory / "before.json").read_text()))


@pytest.mark.parametrize("drift", [None, "untracked", "index", "permissions", "signal", "stash"])
def test_native_signal_removal_uses_prepared_authority_and_other_drift_stays_owned(fleet, monkeypatch, drift):
    f = fleet
    target, entry, directory = transaction_case(f, current=False)
    bus = target / ".agent_bus"
    bus.mkdir()
    signal = bus / "behind_dev.json"
    signal.write_text(json.dumps({"behind": 1, "primary": str(target)}))
    signal.chmod(0o600)
    (target / "untracked-evidence").write_bytes(b"retained evidence\n")
    import workingrcx_fleet_census as census_tool
    entry["useful_work"] = census_tool.useful_work(str(target), f.landed)
    original_sync = boundary.sync_primary_worktree_to_base

    def sync(*args, **kwargs):
        result = original_sync(*args, **kwargs)
        assert result["synced"] is True, result
        assert result["behind_dev_signal_cleared"] is True
        assert not signal.exists()
        if drift == "untracked":
            (target / "untracked-evidence").write_bytes(b"changed\n")
        elif drift == "index":
            stage_index_only(f, target)
        elif drift == "permissions":
            (target / "tracked").chmod(0o600)
        elif drift == "signal":
            signal.write_text("unrelated later owner\n")
        elif drift == "stash":
            (target / "tracked").write_text("held owner\n")
            git(f, target, "stash", "push", "-m", "new foreign stash")
        return result

    if drift == "stash":
        # The native transaction must also retain every preexisting held stash.
        (target / "tracked").write_text("earlier held owner\n")
        git(f, target, "stash", "push", "-m", "earlier held stash")
        saved_sync = original_sync
        def original_sync(*args, **kwargs):
            result = saved_sync(*args, **kwargs)
            git(f, target, "stash", "drop", "stash@{0}")
            return result
    monkeypatch.setattr(boundary, "sync_primary_worktree_to_base", sync)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    if drift is None:
        assert outcome["status"] == "MOVED", outcome
        assert not target.exists()
        assert not (Path(entry["destination"]) / ".agent_bus/behind_dev.json").exists()
        assert json.loads((directory / "before.json").read_text())[".agent_bus/behind_dev.json"]["mode"] == 0o600
    else:
        assert outcome["status"] == "INCOMPLETE", outcome
        assert target.exists()


def pending_sync_case(f, *, legacy_hold=True, overlap=False):
    """Prepare source23's actual crash shape with committed disposable authority."""
    for rel in apply.SYNC_RECOVERY_DEPENDENCIES:
        path = f.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REPO_ROOT / rel).read_bytes())
    authority = commit(f, "land original-owner recovery dependencies")
    git(f, f.repo, "push", "-q", "origin", "dev")
    target, peer = f.targets[:2]
    (peer / "tracked").write_text("unrelated held stash bytes\n")
    git(f, peer, "stash", "push", "-m", "retained foreign owner")
    foreign_oid = git(f, peer, "rev-parse", "refs/stash")
    rel = "tracked" if overlap else "original-owner-wip.txt"
    (target / rel).write_text("distinct staged owner bytes\n")
    git(f, target, "add", rel)
    (target / rel).write_text("distinct unstaged owner bytes\n")
    (target / rel).chmod(0o600)

    class PendingOwnerStash(BaseException):
        pass

    def stop(stage, manifest):
        if stage == "after_stash_before_publish":
            raise PendingOwnerStash()

    with pytest.raises(PendingOwnerStash), apply.safe_git_environment(network=True):
        binding = boundary.bind_terminal_target_identity(target, base_branch="dev")
        boundary.sync_primary_worktree_to_base(f.repo, "dev", target_identity=binding,
                                               checkpoint=stop, log=lambda _: None)
    journal = next((f.common / "rcx_primary_worktree_sync_transactions").glob("*/manifest.json"))
    manifest = json.loads(journal.read_bytes())
    assert manifest["state"] == "PREPARED" and manifest["stash_oid"] is None
    assert manifest["tracked_snapshots"][rel]["worktree"]["mode"] == 0o600
    if legacy_hold:
        manifest.update(state="HOLD", hold_reason="transaction worktree identity mismatch")
        journal.write_bytes(apply.encoded(manifest))
    return SimpleNamespace(target=target, rel=rel, journal=journal, authority=authority,
                           foreign_oid=foreign_oid, manifest=manifest,
                           claim=journal.parent / "fleet-recovery-claim.json",
                           result=journal.parent / "fleet-recovery-result.json")


def recovery_cli(f, case, *extra, script=None, manifest=None, authority=None):
    # Exercise the installed public CLI and its real committed imports, not a
    # private recovery helper or an in-process authority-check replacement.
    return subprocess.run([sys.executable, str(script or f.repo / apply.TOOL_PATH),
        "--recover-sync", str(manifest or case.journal), "--authority-commit", authority or case.authority,
        *extra], cwd=f.repo, env=f.env, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("legacy_hold", [False, True])
def test_supported_original_owner_cli_restores_0600_wip_and_only_observes_repeated_results(fleet, legacy_hold):
    f = fleet
    case = pending_sync_case(f, legacy_hold=legacy_hold)
    foreign_bytes = git(f, f.repo, "cat-file", "-p", case.foreign_oid)
    first = recovery_cli(f, case)
    assert first.returncode == 0, (first.stdout, first.stderr)
    value = json.loads(first.stdout)
    assert value["state"] == "RECOVERED"
    assert case.target.exists() and git(f, case.target, "rev-parse", "HEAD") == case.authority
    assert (case.target / case.rel).read_text() == "distinct unstaged owner bytes\n"
    assert (case.target / case.rel).stat().st_mode & 0o777 == 0o600
    assert git(f, case.target, "show", ":" + case.rel) == "distinct staged owner bytes"
    assert git(f, f.repo, "stash", "list", "--format=%H") == case.foreign_oid
    assert git(f, f.repo, "cat-file", "-p", case.foreign_oid) == foreign_bytes
    native_root = case.journal.parent.parent
    saved = {str(p): p.read_bytes() for p in native_root.glob("*/*.json")}
    index = (f.common / "worktrees" / case.target.name / "index").read_bytes()
    repeated = recovery_cli(f, case)
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout) == value
    assert {str(p): p.read_bytes() for p in native_root.glob("*/*.json")} == saved
    assert (f.common / "worktrees" / case.target.name / "index").read_bytes() == index
    assert not (f.common / "rcx_fleet_apply_operations").exists()


@pytest.mark.parametrize("dependency", apply.SYNC_RECOVERY_DEPENDENCIES)
def test_original_owner_cli_rejects_each_uncommitted_dependency_before_claim(fleet, dependency):
    f = fleet
    case = pending_sync_case(f)
    path = f.repo / dependency
    path.write_bytes(path.read_bytes() + b"\n# uncommitted recovery authority\n")
    git(f, f.repo, "add", str(dependency))
    original = case.journal.read_bytes()
    stashes = git(f, f.repo, "stash", "list", "--format=%H")
    result = recovery_cli(f, case)
    assert result.returncode == 2 and "dependency differs from committed authority" in result.stderr, result.stderr
    assert not case.claim.exists() and not case.result.exists()
    assert case.journal.read_bytes() == original
    assert git(f, f.repo, "stash", "list", "--format=%H") == stashes


@pytest.mark.parametrize("fault", [
    "index", "mode", "flags", "unlanded", "primary-behind", "executing-copy",
    "manifest-copy", "manifest-symlink", "common-identity", "owner-identity",
    "branch", "head", "active", "interrupted", "terminal", "duplicate-owner",
])
def test_original_owner_cli_refuses_ambiguous_admission_and_replay(fleet, fault):
    f = fleet
    case = pending_sync_case(f)
    options = {}
    if fault == "index":
        git(f, f.repo, "update-index", "--chmod=+x", str(apply.SYNC_RECOVERY_DEPENDENCIES[1]))
    elif fault == "mode":
        (f.repo / apply.SYNC_RECOVERY_DEPENDENCIES[1]).chmod(0o755)
    elif fault == "flags":
        git(f, f.repo, "update-index", "--assume-unchanged", str(apply.SYNC_RECOVERY_DEPENDENCIES[1]))
    elif fault == "unlanded":
        git(f, f.repo, "commit", "--allow-empty", "-qm", "not on origin dev")
        options["authority"] = git(f, f.repo, "rev-parse", "HEAD")
    elif fault == "primary-behind":
        git(f, f.repo, "checkout", "--detach", f.landed)
    elif fault == "executing-copy":
        copied = f.root / "unlanded-recovery.py"
        copied.write_bytes((f.repo / apply.TOOL_PATH).read_bytes())
        options["script"] = copied
    elif fault.startswith("manifest-"):
        copied = f.root / "manifest.json"
        if fault == "manifest-copy":
            copied.write_bytes(case.journal.read_bytes())
        else:
            copied.symlink_to(case.journal)
        options["manifest"] = copied
    elif fault in {"common-identity", "owner-identity"}:
        key = "common_dir_identity" if fault == "common-identity" else "worktree_identity"
        case.manifest[key]["inode"] += 1
        case.journal.write_bytes(apply.encoded(case.manifest))
    elif fault == "branch":
        git(f, case.target, "checkout", "-qb", "changed-original-owner")
    elif fault == "head":
        git(f, case.target, "commit", "--allow-empty", "-qm", "unrelated owner head")
    elif fault == "active":
        bus = case.target / ".agent_bus"
        bus.mkdir()
        (bus / "status.json").write_bytes(apply.encoded(dict(active=True, state="running", pid=os.getpid())))
    elif fault == "interrupted":
        case.claim.write_text('{"state":"unknown interrupted outcome"}\n')
    elif fault == "terminal":
        case.manifest["state"] = "RECOVERED"
        case.journal.write_bytes(apply.encoded(case.manifest))
    else:
        duplicate = case.journal.parent.parent / ("f" * 32)
        duplicate.mkdir()
        (duplicate / "manifest.json").write_bytes(case.journal.read_bytes())
    original = case.journal.read_bytes()
    before = apply.transaction_state(case.target)
    stash = git(f, f.repo, "stash", "list", "--format=%H")
    result = recovery_cli(f, case, **options)
    assert result.returncode == 2 and "HOLD:" in result.stderr, (result.stdout, result.stderr)
    assert not case.result.exists()
    assert case.claim.exists() is (fault == "interrupted")
    assert case.journal.read_bytes() == original
    assert apply.transaction_state(case.target) == before
    assert git(f, f.repo, "stash", "list", "--format=%H") == stash


@pytest.mark.parametrize("fault", ["content", "index", "overlap"])
def test_original_owner_cli_records_native_hold_without_losing_wip_or_replaying(fleet, fault):
    f = fleet
    case = pending_sync_case(f, overlap=fault == "overlap")
    original_stashes = git(f, f.repo, "stash", "list", "--format=%H")
    if fault != "overlap":
        (case.target / case.rel).write_text("later owner bytes\n")
        if fault == "index":
            git(f, case.target, "add", case.rel)
    first = recovery_cli(f, case)
    assert first.returncode == 3, (first.stdout, first.stderr)
    assert json.loads(first.stdout)["state"] == "INCOMPLETE"
    assert case.target.exists()
    if fault == "overlap":
        stashes = git(f, f.repo, "stash", "list", "--format=%H").splitlines()
        assert case.foreign_oid in stashes and len(stashes) == 2
        assert git(f, f.repo, "show", stashes[0] + ":tracked") == "distinct unstaged owner bytes"
        assert git(f, f.repo, "show", stashes[0] + "^2:tracked") == "distinct staged owner bytes"
    else:
        assert (case.target / case.rel).read_text() == "later owner bytes\n"
        assert git(f, f.repo, "stash", "list", "--format=%H") == original_stashes
    saved = {str(p): p.read_bytes() for p in case.journal.parent.parent.glob("*/*.json")}
    repeated = recovery_cli(f, case)
    assert repeated.returncode == 3, repeated.stderr
    assert repeated.stdout == first.stdout
    assert {str(p): p.read_bytes() for p in case.journal.parent.parent.glob("*/*.json")} == saved


def test_original_owner_cli_rejects_saved_recovered_state_with_native_held_wip(fleet):
    """Changing only the saved state cannot turn the native overlap HOLD into success."""
    f = fleet
    case = pending_sync_case(f, overlap=True)
    # Observe the real CLI's native calls without editing committed authority.
    probe = f.root / "recovery-observer"
    probe.mkdir()
    calls = probe / "native-sync-calls"
    (probe / "sitecustomize.py").write_text(
        "import sys\n"
        "def observe(frame, event, arg):\n"
        "    native = frame.f_globals.get('sync_primary_worktree_to_base')\n"
        "    if event == 'call' and getattr(native, '__code__', None) is frame.f_code:\n"
        f"        with open({str(calls)!r}, 'a') as stream:\n"
        "            stream.write('native sync\\n')\n"
        "sys.setprofile(observe)\n"
    )
    f.env["PYTHONPATH"] = str(probe)
    first = recovery_cli(f, case)
    assert first.returncode == 3, (first.stdout, first.stderr)
    value = json.loads(first.stdout)
    assert value["state"] == "INCOMPLETE"
    assert value["checkout_sync"]["tracked_wip_held_paths"] == ["tracked"]
    assert calls.read_text() == "native sync\n"

    saved = json.loads(case.result.read_bytes())
    assert saved == value
    saved["state"] = "RECOVERED"
    case.result.write_bytes(apply.encoded(saved))
    # This is the sole state change after recovery, exactly as in the veto.
    native_root = case.journal.parent.parent
    journals = apply.tree_manifest(native_root)
    claim, result = case.claim.read_bytes(), case.result.read_bytes()
    checkout = apply.transaction_state(case.target)
    index_path = f.common / "worktrees" / case.target.name / "index"
    index = index_path.read_bytes()
    stashes = git(f, f.repo, "stash", "list", "--format=%H%x00%gs")
    stash_oids = git(f, f.repo, "stash", "list", "--format=%H").splitlines()
    stash_bytes = {ref: git(f, f.repo, "cat-file", "-p", ref)
                   for oid in stash_oids for ref in (oid, oid + ":tracked", oid + "^2:tracked")}

    repeated = recovery_cli(f, case)
    assert repeated.returncode == 2 and "HOLD:" in repeated.stderr, (repeated.stdout, repeated.stderr)
    assert "saved recovery result contradicts native outcome" in repeated.stderr
    assert calls.read_text() == "native sync\n"
    assert case.claim.read_bytes() == claim and case.result.read_bytes() == result
    assert apply.tree_manifest(native_root) == journals
    assert apply.transaction_state(case.target) == checkout
    assert index_path.read_bytes() == index
    assert git(f, f.repo, "stash", "list", "--format=%H%x00%gs") == stashes
    assert {ref: git(f, f.repo, "cat-file", "-p", ref) for ref in stash_bytes} == stash_bytes


@pytest.mark.parametrize("drift", ["content", "index", "permissions", "journal", "stash", "authority"])
def test_original_owner_cli_rechecks_exact_retained_state_before_repeated_observation(fleet, drift):
    f = fleet
    case = pending_sync_case(f)
    first = recovery_cli(f, case)
    assert first.returncode == 0, (first.stdout, first.stderr)
    claim, result = case.claim.read_bytes(), case.result.read_bytes()
    options = {}
    if drift == "content":
        (case.target / case.rel).write_text("new retained work\n")
    elif drift == "index":
        git(f, case.target, "update-index", "--chmod=+x", case.rel)
    elif drift == "permissions":
        (case.target / case.rel).chmod(0o644)
    elif drift == "journal":
        case.journal.write_bytes(case.journal.read_bytes() + b"\n")
    elif drift == "stash":
        git(f, f.repo, "stash", "drop", "stash@{0}")
    else:
        git(f, f.repo, "commit", "--allow-empty", "-qm", "new landed observation authority")
        git(f, f.repo, "push", "-q", "origin", "dev")
        options["authority"] = git(f, f.repo, "rev-parse", "HEAD")
    before = apply.transaction_state(case.target)
    repeated = recovery_cli(f, case, **options)
    assert repeated.returncode == 2 and "no replay" in repeated.stderr, repeated.stderr
    assert case.claim.read_bytes() == claim and case.result.read_bytes() == result
    assert apply.transaction_state(case.target) == before


@pytest.mark.parametrize("extra", [["--apply"], ["--verify"], ["--residual"], ["--batch", "3"]])
def test_original_owner_cli_does_not_mix_fleet_operation_authority(fleet, extra):
    f = fleet
    case = pending_sync_case(f)
    result = recovery_cli(f, case, *extra)
    assert result.returncode == 2 and "excludes fleet plan/apply/verify" in result.stderr
    assert not case.claim.exists()


def test_late_index_only_drift_after_before_tar_cannot_retire_without_owner(fleet, monkeypatch):
    """Reproduce the stopped R2 race with real objects/index and the real boundary."""
    f = fleet
    target, entry, directory = transaction_case(f)
    assert entry["useful_work"]["status"] == "COVERED"
    assert entry["landing_owner"] is None
    original_archive = apply.preserve_archive
    injected = []

    def archive_then_stage(root, output, manifest):
        original_archive(root, output, manifest)
        if root == target and output.name == "before.tar":
            injected.append(stage_index_only(f, target))

    monkeypatch.setattr(apply, "preserve_archive", archive_then_stage)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert injected
    assert outcome["status"] in {"HOLD", "INCOMPLETE"}, outcome
    assert outcome.get("landing_owner", {}).get("status") == "UNRESOLVED_TRANSACTION_DRIFT", outcome
    assert "tracked" in outcome["landing_owner"]["scope"]
    assert target.is_dir()
    assert git(f, target, "show", ":tracked") == "late index-only useful work"
    assert (target / "tracked").read_bytes() == b"landed tracked revision\n"


@pytest.mark.parametrize("kind", ["index", "content"])
@pytest.mark.parametrize("current", [False, True])
@pytest.mark.parametrize("stage", ["gitdir-before.tar", "history.bundle", "before-sync", "after-sync",
                                   "prepared.json", "move-started.json", "after-move", "after-boundary"])
def test_transaction_drift_at_subsequent_boundaries_stays_owned(fleet, monkeypatch, stage, kind, current):
    f = fleet
    target, entry, directory = transaction_case(f, current=current)
    injected = []

    def inject(path):
        if injected:
            return
        if kind == "index":
            injected.append(stage_index_only(f, path))
        else:
            (path / "tracked").write_bytes(b"late useful worktree bytes\n")
            injected.append(True)

    original_archive, original_git = apply.preserve_archive, apply.git
    original_write = apply.write_new
    original_sync, original_boundary = boundary.sync_primary_worktree_to_base, boundary.execute_terminal_mutation_once

    def archive(root, output, manifest):
        original_archive(root, output, manifest)
        if stage == output.name:
            inject(target)

    def git_action(root, *args, **kwargs):
        result = original_git(root, *args, **kwargs)
        if stage == "history.bundle" and args[:2] == ("bundle", "verify"):
            inject(target)
        if stage == "after-move" and args[:2] == ("worktree", "move"):
            inject(Path(entry["destination"]))
        return result

    def write(path, data, **kwargs):
        original_write(path, data, **kwargs)
        if path.name == stage:
            inject(target)

    def sync(*args, **kwargs):
        if stage == "before-sync":
            inject(target)
        result = original_sync(*args, **kwargs)
        if stage == "after-sync":
            inject(target)
        return result

    def terminal(*args, **kwargs):
        result = original_boundary(*args, **kwargs)
        if stage == "after-boundary":
            inject(Path(entry["destination"]))
        return result

    monkeypatch.setattr(apply, "preserve_archive", archive)
    monkeypatch.setattr(apply, "git", git_action)
    monkeypatch.setattr(apply, "write_new", write)
    monkeypatch.setattr(boundary, "sync_primary_worktree_to_base", sync)
    monkeypatch.setattr(boundary, "execute_terminal_mutation_once", terminal)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert injected
    assert outcome["status"] in {"HOLD", "INCOMPLETE"}, outcome
    owner = outcome["landing_owner"]
    assert owner["status"] == "UNRESOLVED_TRANSACTION_DRIFT"
    assert "tracked" in owner["scope"], outcome
    retained = Path(owner["retained_path"])
    assert retained.is_dir()
    if kind == "index":
        assert git(f, retained, "show", ":tracked") == "late index-only useful work"
    else:
        assert (retained / "tracked").read_bytes() == b"late useful worktree bytes\n"
    before = json.loads((directory / "before.json").read_text())
    apply.verify_archive(directory / "before.tar", before)
    assert json.loads((directory / "outcome.json").read_text()) == outcome


@pytest.mark.parametrize("current", [False, True])
@pytest.mark.parametrize("wip", ["clean", "mixed", "deletion", "overlap"])
def test_transaction_allows_exact_fast_forward_and_preserved_wip(fleet, current, wip):
    f = fleet
    target, entry, directory = transaction_case(f, current=current, wip=wip)
    original = apply.transaction_state(target)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert outcome["status"] == "MOVED", json.dumps({k: outcome.get(k) for k in ("reason", "checkout_sync")}, indent=2)
    destination = Path(entry["destination"])
    assert not target.exists()
    assert git(f, destination, "rev-parse", "HEAD") == f.landed
    assert (destination / "ignored-evidence/private.bin").read_bytes() == b"\x00private evidence\xff\n"
    retired = json.loads((directory / "retired-state.json").read_text())
    assert apply.transaction_state(destination) == retired
    assert {c["phase"] for c in outcome["transaction_checks"]} >= {
        "after-before.tar", "after-gitdir-before.tar", "after-checkout-sync",
        "before-terminal-move", "after-terminal-move", "after-terminal-boundary"}
    if wip != "clean":
        assert outcome["landing_owner"]["wave_id"] == entry["landing_owner"]["wave_id"]
    if wip == "mixed":
        assert git(f, destination, "show", ":wip.txt") == "staged useful bytes"
        assert (destination / "wip.txt").read_bytes() == b"unstaged useful bytes\n"
        with tarfile.open(directory / "index-blobs.tar") as archive:
            assert archive.extractfile(original["index"]["wip.txt"][1]).read() == b"staged useful bytes\n"
    if wip == "deletion":
        assert not (destination / ".gitignore").exists()
        assert ".gitignore" not in retired["index"]
    if wip == "overlap" and not current:
        stash = outcome["checkout_sync"]["tracked_wip_stash_oid"]
        assert git(f, destination, "show", stash + "^2:tracked") == "staged overlapping bytes"
        assert git(f, destination, "show", stash + ":tracked") == "unstaged overlapping bytes"
        assert (destination / "tracked").read_bytes() == b"landed tracked revision\n"


@pytest.mark.parametrize("stage", ["after_prepared", "after_stash_before_publish", "after_fast_forward_before_publish"])
@pytest.mark.parametrize("kind", ["index", "content"])
def test_native_preparation_drift_preserves_new_work_and_retains_owner(fleet, monkeypatch, stage, kind):
    f = fleet
    target, entry, directory = transaction_case(f, current=False, wip="mixed")
    original_sync = boundary.sync_primary_worktree_to_base
    injected = []

    def sync(*args, **kwargs):
        original_checkpoint = kwargs["checkpoint"]

        def checkpoint(observed_stage, manifest):
            original_checkpoint(observed_stage, manifest)
            if observed_stage == stage:
                if kind == "index":
                    injected.append(stage_index_only(f, target))
                else:
                    (target / "tracked").write_bytes(b"late useful worktree bytes\n")
                    injected.append(True)

        return original_sync(*args, **{**kwargs, "checkpoint": checkpoint})

    monkeypatch.setattr(boundary, "sync_primary_worktree_to_base", sync)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert injected
    assert outcome["status"] in {"HOLD", "INCOMPLETE"}, outcome
    assert target.exists()
    assert "tracked" in outcome["landing_owner"]["scope"]
    if kind == "index":
        assert git(f, target, "show", ":tracked") == "late index-only useful work"
    else:
        assert (target / "tracked").read_bytes() == b"late useful worktree bytes\n"
    assert outcome["landing_owner"]["admitted_landing_owner"] == entry["landing_owner"]
    assert outcome["preservation_sha256"]["before.tar"] == apply.file_hash(directory / "before.tar")


def test_transaction_ignores_git_index_stat_cache_refresh(fleet, monkeypatch):
    f = fleet
    target, entry, directory = transaction_case(f)
    original_archive = apply.preserve_archive
    index_path = Path(entry["source_identity"]["git_dir"]) / "index"
    refreshed = []

    def archive(root, output, manifest):
        original_archive(root, output, manifest)
        if root == target and output.name == "before.tar":
            before = index_path.read_bytes()
            info = (target / "tracked").stat()
            os.utime(target / "tracked", ns=(info.st_atime_ns, info.st_mtime_ns - 2_000_000_000))
            git(f, target, "update-index", "--refresh")
            refreshed.append(before != index_path.read_bytes())

    monkeypatch.setattr(apply, "preserve_archive", archive)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert refreshed == [True]
    assert outcome["status"] == "MOVED", outcome


def test_transaction_never_repins_an_earlier_corrupted_archive(fleet, monkeypatch):
    f = fleet
    target, entry, directory = transaction_case(f)
    original_archive = apply.preserve_archive
    original_hashes = []

    def archive(root, output, manifest):
        original_archive(root, output, manifest)
        if output.name == "gitdir-before.tar":
            original_hashes.append(apply.file_hash(directory / "before.tar"))
            with (directory / "before.tar").open("ab") as stream:
                stream.write(b"late artifact corruption")

    monkeypatch.setattr(apply, "preserve_archive", archive)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert outcome["status"] == "HOLD", outcome
    assert target.exists()
    assert outcome["preservation_sha256"]["before.tar"] == original_hashes[0]
    assert outcome["preservation_sha256"]["before.tar"] != apply.file_hash(directory / "before.tar")
    assert "preservation changed" in outcome["reason"]


def test_bulk_late_drift_holds_one_target_and_verification_never_replays(fleet, monkeypatch):
    f = fleet
    plan = residual_fixture(f, monkeypatch, wave_id="transaction-peer-drift-2026-09-15")
    target = f.targets[0]
    original_archive = apply.preserve_archive

    def archive(root, output, manifest):
        original_archive(root, output, manifest)
        if root == target and output.name == "before.tar":
            stage_index_only(f, target)

    monkeypatch.setattr(apply, "preserve_archive", archive)
    operation = plan["operations"][0]
    kwargs = dict(authority_commit=f.residual_authority, batch=1,
                  operation_root=Path(operation["operation_root"]))
    result = apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert result["outcome_counts"] == {"MOVED": 4, "HOLD": 1}, result
    held = next(o for o in result["outcomes"] if o["status"] == "HOLD")
    assert held["landing_owner"]["retained_path"] == str(target)
    assert "tracked" in held["landing_owner"]["scope"]
    claim = f.common / ("rcx_fleet_apply_" + operation["operation_id"] + ".json")
    evidence = {p: p.read_bytes() for p in (claim, Path(operation["operation_root"]) / "summary.json")}
    assert apply.verify_residual_plan(f.repo, plan, **kwargs)["batch_complete"] is False
    with pytest.raises(apply.Hold, match="consumed"):
        apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert {p: p.read_bytes() for p in evidence} == evidence


class OwnershipObservationFault(Exception):
    """An ordinary observation failure outside the existing exception lists."""


@pytest.mark.parametrize("change, fault, reason", (
    (dict(acquired_at_utc=None), None, "Native owner lock timestamp"),
    (dict(acquired_at_utc=[]), None, "Native owner lock timestamp"),
    (dict(acquired_at_utc="not-a-timestamp"), None, "Native owner lock timestamp"),
    (dict(holder=[]), None, "Native owner lock metadata"),
    (dict(pid=2**128), None, "Native ownership evidence is uncertain (OverflowError)"),
    ({}, OwnershipObservationFault, "Native ownership evidence is uncertain (OwnershipObservationFault)"),
    ({}, PermissionError, "Native owner lock metadata remains ambiguous or live"),
))
def test_bulk_malformed_stale_lock_records_hold_continues_peers_and_never_replays(
        fleet, monkeypatch, change, fault, reason):
    f = fleet
    target = f.targets[0]
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    lock = target / ".agent_bus/meta/bridge.lock"
    lock.parent.mkdir(parents=True)
    value = dict(pid=child.pid, holder="bridge_supervisor",
                 acquired_at_utc="2026-07-22T03:30:03.376325+00:00", lock_path=str(lock))
    value.update(change)
    lock.write_bytes(apply.encoded(value))
    plan = residual_fixture(f, monkeypatch, wave_id="transaction-malformed-lock-2026-09-15")
    entry = next(e for e in plan["entries"] if e["path"] == str(target))
    operation = plan["operations"][0]
    assert operation["source_indices"][0] == entry["source_index"]
    operation_root = Path(operation["operation_root"])
    kwargs = dict(authority_commit=f.residual_authority, batch=operation["batch"],
                  operation_root=operation_root)
    before = apply.tree_manifest(target)
    index = Path(entry["source_identity"]["git_dir"]) / "index"
    before_index = index.read_bytes()
    observed = []
    if fault is not None:
        original_kill = os.kill

        def observe_pid(pid, signal):
            if pid == child.pid and signal == 0:
                observed.append(pid)
                raise fault("disposable read-only PID observation failure")
            return original_kill(pid, signal)

        monkeypatch.setattr(os, "kill", observe_pid)

    result = apply.apply_residual_plan(f.repo, plan, **kwargs)

    if fault is not None:
        assert observed == [child.pid]
    assert result["outcome_counts"] == {"HOLD": 1, "MOVED": 4}, result
    held, *peers = result["outcomes"]
    assert held["status"] == "HOLD"
    assert held["reason"].startswith(reason)
    assert held["source_identity"] == entry["source_identity"]
    assert held["owner"] == entry["owner"]
    assert str(target) in held["next_action"] and "cannot be replayed" in held["next_action"]
    assert held["prepared_head"] is None and held["boundary"] is None
    assert apply.tree_manifest(target) == before
    assert index.read_bytes() == before_index
    assert git(f, target, "rev-parse", "HEAD") == entry["source_identity"]["HEAD"]
    assert not Path(entry["destination"]).exists()
    assert all(o["status"] == "MOVED" and Path(o["destination"]).is_dir()
               and not Path(o["source_identity"]["path"]).exists() for o in peers)
    receipt = operation_root / str(entry["source_index"]) / "outcome.json"
    assert json.loads(receipt.read_bytes()) == held
    assert json.loads((operation_root / "summary.json").read_bytes()) == result
    evidence = apply.tree_manifest(operation_root)
    claim = f.common / ("rcx_fleet_apply_" + operation["operation_id"] + ".json")
    claim_bytes = claim.read_bytes()
    verified = apply.verify_residual_plan(f.repo, plan, **kwargs)
    assert verified["verified_outcomes"] == result["outcome_counts"]
    assert verified["batch_complete"] is False
    assert verified["recorded_before"] - verified["recorded_after"] == 4
    with pytest.raises(apply.Hold, match="consumed"):
        apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert claim.read_bytes() == claim_bytes
    assert apply.tree_manifest(operation_root) == evidence
    assert apply.tree_manifest(target) == before and index.read_bytes() == before_index


@pytest.mark.parametrize("filename", ["bridge.lock", "status.json"])
@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_native_ownership_observation_preserves_operator_interruptions(
        native_evidence, monkeypatch, filename, interruption):
    target, status = native_evidence
    path = status.parent / filename
    path.write_bytes(apply.encoded(dict(pid=os.getpid(), holder="bridge_supervisor",
        acquired_at_utc="2026-07-22T03:30:03.376325+00:00", lock_path=str(path),
        active=False, state="completed")))
    before = apply.tree_manifest(target)
    stop = interruption("operator stopped ownership observation")

    def observe_pid(pid, signal):
        assert pid == os.getpid() and signal == 0
        raise stop

    monkeypatch.setattr(os, "kill", observe_pid)
    with pytest.raises(interruption) as caught:
        apply.native_idle(target, before, reconcile_r1=True)
    assert caught.value is stop
    assert apply.tree_manifest(target) == before


def test_fresh_verification_detects_index_only_drift_at_retired_destination(fleet, monkeypatch):
    f = fleet
    plan = residual_fixture(f, monkeypatch, wave_id="transaction-verify-index-2026-09-15")
    operation = plan["operations"][0]
    kwargs = dict(authority_commit=f.residual_authority, batch=1,
                  operation_root=Path(operation["operation_root"]))
    result = apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert result["outcome_counts"] == {"MOVED": 5}, result
    entry = next(e for e in plan["entries"] if e["action"] == "PRESERVE_WORKTREE")
    destination = Path(entry["destination"])
    before = apply.tree_manifest(destination)
    stage_index_only(f, destination)
    assert apply.tree_manifest(destination) == before
    with pytest.raises(apply.Hold, match="transaction drift at verification"):
        apply.verify_residual_plan(f.repo, plan, **kwargs)


def test_fresh_restored_wip_keeps_recoverable_stash_history_and_verifies(fleet, monkeypatch):
    f = fleet
    target = f.targets[0]
    (target / "wip.txt").write_bytes(b"staged useful bytes\n")
    git(f, target, "add", "wip.txt")
    (target / "wip.txt").write_bytes(b"unstaged useful bytes\n")
    plan = residual_fixture(f, monkeypatch, wave_id="transaction-restored-wip-2026-09-15")
    operation = plan["operations"][0]
    kwargs = dict(authority_commit=f.residual_authority, batch=1,
                  operation_root=Path(operation["operation_root"]))
    result = apply.apply_residual_plan(f.repo, plan, **kwargs)
    assert result["outcome_counts"] == {"MOVED": 5}, json.dumps(result, indent=2)
    assert apply.verify_residual_plan(f.repo, plan, **kwargs)["batch_complete"] is True
    entry = next(e for e in plan["entries"] if e["path"] == str(target))
    directory = Path(operation["operation_root"]) / str(entry["source_index"])
    proof = json.loads((directory / "sync-stash.json").read_text())
    recovered = f.root / "restored-stash-history"
    recovered.mkdir()
    git(f, recovered, "init", "-q")
    git(f, recovered, "fetch", str(directory / "sync-stash.bundle"), "refs/stash:refs/heads/recovered")
    assert git(f, recovered, "rev-parse", "recovered") == proof["oid"]
    assert git(f, recovered, "show", "recovered^2:wip.txt") == "staged useful bytes"
    assert git(f, recovered, "show", "recovered:wip.txt") == "unstaged useful bytes"
    assert entry["landing_owner"]["status"] == "PENDING_NATIVE_LANDING_REVIEW"
    with (directory / "sync-stash.bundle").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(apply.Hold, match="preservation artifact changed"):
        apply.verify_residual_plan(f.repo, plan, **kwargs)


@pytest.mark.parametrize("dependency", ["mu/tools/executors/workingrcx_fleet_census.py",
    "mu/tools/executors/workingrcx_fleet_classification.py", "mu/tools/executors/commit_executor.py",
    "mu/tools/executors/executor_common.py", "mu/tools/observability/pipeline_agent_pager.py",
    "reports/control_plane/transaction-dependency-2026-09-15_useful_work.json"])
def test_fresh_bulk_dependency_index_drift_refuses_before_claim(fleet, monkeypatch, dependency):
    f = fleet
    plan = residual_fixture(f, monkeypatch, wave_id="transaction-dependency-2026-09-15")
    operation = plan["operations"][0]
    original = (f.repo / dependency).read_bytes()
    blob = subprocess.run([f.git, "-C", str(f.repo), "hash-object", "-w", "--stdin"],
        input=b"unreviewed index-only dependency\n", env=f.env, capture_output=True, check=True).stdout.decode().strip()
    git(f, f.repo, "update-index", "--cacheinfo", "100644," + blob + "," + dependency)
    assert (f.repo / dependency).read_bytes() == original
    with pytest.raises(apply.Hold, match="authority index/mode identity"):
        apply.apply_residual_plan(f.repo, plan, authority_commit=f.residual_authority,
            batch=1, operation_root=Path(operation["operation_root"]))
    assert not Path(operation["operation_root"]).exists()
    assert not (f.common / ("rcx_fleet_apply_" + operation["operation_id"] + ".json")).exists()


@pytest.mark.parametrize("staged", [False, True])
def test_source196_tracked_report_deletion_is_bound_in_native_journal_and_stash(fleet, staged):
    f = fleet
    deleted = "reports/deferred/non_blocking/source196_bridge_nonblockers.md"
    report = f.repo / deleted
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_bytes(b"historically tracked generated report\n")
    # Recorded source196 has 141 other entries under this directory, including
    # README.md. Preserve that topology; this is the missing deletion-intent
    # contract, not an empty-directory retirement fixture.
    neighbor = report.parent / "README.md"
    neighbor.write_bytes(b"retained neighboring report index\n")
    f.original = commit(f, "tracked report at source196 base")
    git(f, f.targets[0], "merge", "--ff-only", f.original)
    (f.repo / "next-base.txt").write_text("unrelated landed change\n")
    f.landed = commit(f, "fresh merge for source196 sync")
    git(f, f.repo, "push", "origin", "dev")
    if staged:
        git(f, f.targets[0], "rm", "--", deleted)
    else:
        (f.targets[0] / deleted).unlink()
    target, entry, directory = transaction_case(f, current=False, wip="mixed")
    before = apply.transaction_state(target)
    with apply.safe_git_environment(network=True):
        outcome = apply.apply_target(f.repo, entry, directory, boundary, residual=True)
    assert outcome["status"] == "MOVED", json.dumps(outcome, indent=2)
    admitted = json.loads((directory / "admitted-state.json").read_text())
    stash = json.loads((directory / "sync-stash.json").read_text())
    journal = json.loads(Path(outcome["checkout_sync"]["primary_sync_transaction_path"]).read_text())
    assert deleted in admitted["tracked_wip"] and deleted not in admitted["content"]
    assert deleted in journal["tracked_paths"]
    assert journal["tracked_snapshots"][deleted]["worktree"]["kind"] == "absent"
    assert deleted in stash["content"] and stash["content"][deleted] is None
    assert stash["index"] == before["index"] and stash["base"] == before["head"]
    destination = Path(entry["destination"])
    assert not (destination / deleted).exists()
    assert (destination / neighbor.relative_to(f.repo)).read_bytes() == neighbor.read_bytes()
    assert apply.transaction_state(destination)["index"] == before["index"] | {
        "next-base.txt": apply.git_entries(f.repo)["next-base.txt"]}
    omitted = deepcopy(stash)
    del omitted["content"][deleted]
    with pytest.raises(apply.Hold, match="native stash content differs"):
        apply.require_stash_binding(admitted, omitted)
    omitted = deepcopy(stash)
    del omitted["content"]["wip.txt"]
    with pytest.raises(apply.Hold, match="native stash content differs"):
        apply.require_stash_binding(admitted, omitted)
