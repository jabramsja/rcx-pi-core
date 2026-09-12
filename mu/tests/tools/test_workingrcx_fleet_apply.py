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
        f.reconcile_operation = root / ("fleet-apply-preserved-" + apply.RECONCILE_WAVE_ID)
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
        assert command == ["lsof", "-nP", "+D", str(target), "-Fpn"]
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
