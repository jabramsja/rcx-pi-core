"""Native completion in real disposable repositories, with surviving owners."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import pytest

from mu.tools.executors import worktree_lifecycle as lifecycle
from mu.tools.executors import workingrcx_fleet_apply as fleet
from tests.repo_root import REPO_ROOT


@pytest.fixture
def native_lane(tmp_path, monkeypatch):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="Native fixture", GIT_AUTHOR_EMAIL="native@example.invalid",
        GIT_COMMITTER_NAME="Native fixture", GIT_COMMITTER_EMAIL="native@example.invalid",
        PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(REPO_ROOT))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    root = tmp_path.resolve()
    primary, remote, lane = root / "WorkingRCX", root / "origin.git", root / "WorkingRCX-native"
    primary.mkdir()

    def git(path, *args):
        return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
            "-C", str(path), *args], check=True, capture_output=True, env=env).stdout.decode().strip()

    git(primary, "init", "-b", "dev")
    git(primary, "init", "--bare", str(remote))
    (primary / "tracked").write_bytes(b"native code\n")
    (primary / ".gitignore").write_text(".agent_bus*/\n")
    git(primary, "add", ".")
    git(primary, "commit", "-m", "base")
    git(primary, "remote", "add", "origin", str(remote))
    git(primary, "push", "origin", "dev")
    git(primary, "worktree", "add", "-b", "native-wave", str(lane))
    bus = lane / ".agent_bus"
    bus.mkdir()
    (bus / "receipt.json").write_bytes(b'{"native":"retained"}\n')
    return primary, lane, git, env


def register_from_exited_owner(lane, env, *, status="stopped", result=None,
                               role="native", closeout=False):
    program = (
        "import json,sys; from pathlib import Path; "
        "from mu.tools.executors import worktree_lifecycle as w; "
        "p=Path(sys.argv[1]); r=json.loads(sys.argv[3]); "
        "d=w.register_lane(p, 'native-test-wave',role=sys.argv[4]); "
        "v=w.request_completion(d,status=sys.argv[2],result=r); "
        "w.publish_closeout(Path(v['record']),repo=p, "
        "handoff={'pre_commit_receipt_path':'.agent_bus/receipt.json'},result=r) "
        "if json.loads(sys.argv[5]) else None; print(v['record'])"
    )
    result = subprocess.run([sys.executable, "-c", program, str(lane), status,
        json.dumps(result), role, json.dumps(closeout)],
        check=True, capture_output=True, text=True, env=env)
    return Path(result.stdout.strip())


@pytest.mark.parametrize("status", ["success", "stopped", "failed", "superseded"])
def test_terminal_completion_preserves_lane_history_and_survives_source_absence(native_lane, status):
    primary, lane, git, env = native_lane
    original = git(lane, "rev-parse", "HEAD")
    directory = register_from_exited_owner(lane, env, status=status)
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "COMPLETE", result
    destination = Path(result["destination"])
    assert not lane.exists() and destination.is_dir()
    assert (destination / "tracked").read_bytes() == b"native code\n"
    assert (destination / ".agent_bus/receipt.json").read_bytes() == b'{"native":"retained"}\n'
    assert git(primary, "rev-parse", "native-wave") == original
    assert str(destination) in git(primary, "worktree", "list", "--porcelain")
    recorded = {p.name: p.read_bytes() for p in directory.glob("*.json")}
    assert lifecycle.complete_pending(directory, delay=0) == result
    assert {p.name: p.read_bytes() for p in directory.glob("*.json")} == recorded
    assert not lane.exists()


def test_stopped_useful_candidate_retains_exact_landing_owner(native_lane):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"unlanded staged implementation\n")
    git(lane, "add", "tracked")
    directory = register_from_exited_owner(lane, env)
    before = fleet.tree_manifest(lane)
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "ESCALATED"
    assert result["landing_owner"]["branch"] == "refs/heads/native-wave"
    assert fleet.tree_manifest(lane) == before
    evidence = json.loads(Path(result["landing_owner"]["evidence"]).read_text())
    assert evidence["status"] == "NEEDS_LANDING"
    assert evidence["changes"][0]["path"] == "tracked"
    inspected = subprocess.run(shlex.split(result["next_action"]), env=env,
                               capture_output=True, text=True, check=False)
    assert inspected.returncode == 3
    assert json.loads(inspected.stdout) == result
    assert Path(result["evidence"]).is_dir()
    assert "land or prove dev coverage" in result["required_resolution"]


@pytest.mark.parametrize("status", ["success", "stopped", "failed"])
@pytest.mark.parametrize("work", ["covered", "unlanded"])
def test_detached_completion_inventories_exact_landing_owner_without_retirement(native_lane, status, work):
    primary, lane, git, env = native_lane
    base = git(primary, "rev-parse", "HEAD")
    git(lane, "checkout", "--detach")
    if work == "unlanded":
        (lane / "committed").write_bytes(b"detached-only implementation\n")
        git(lane, "add", "committed")
        git(lane, "commit", "-m", "detached work to land")
        (lane / "tracked").write_bytes(b"staged implementation\n")
        git(lane, "add", "tracked")
        (lane / "tracked").write_bytes(b"unstaged implementation\n")
        (lane / "untracked").write_bytes(b"new implementation\n")
    head = git(lane, "rev-parse", "HEAD")
    directory = register_from_exited_owner(lane, env, status=status)
    index = Path(git(lane, "rev-parse", "--absolute-git-dir")) / "index"
    index_before = index.read_bytes()
    before = fleet.tree_manifest(lane)
    terminal_before = (directory / "terminal.json").read_bytes()

    result = lifecycle.complete_pending(directory, delay=0)

    assert result["state"] == "ESCALATED", result
    assert "Detached" in result["reason"]
    assert result["landing_owner"] == dict(wave_id="native-test-wave", branch="",
        head=head, source=str(lane), evidence=str(directory / "attempt-1/useful-work.json"))
    inventory = json.loads(Path(result["landing_owner"]["evidence"]).read_bytes())
    assert inventory["comparison_commit"] == base
    assert inventory["errors"] == [] and inventory["local_refs"] == []
    assert inventory["status"] == ("NEEDS_LANDING" if work == "unlanded" else "COVERED")
    if work == "unlanded":
        assert inventory["local_commits"] == [head]
        assert inventory["local_commit_changes"][0]["paths"] == ["committed"]
        assert [change["path"] for change in inventory["changes"]] == ["tracked", "untracked"]
        tracked = inventory["changes"][0]
        assert tracked["index"][1] == git(lane, "rev-parse", ":tracked")
        assert tracked["worktree"][1] == git(lane, "hash-object", "tracked")
        assert tracked["index"] != tracked["worktree"]
        assert inventory["staged_patch_sha256"] == fleet.digest(fleet.git(lane,
            "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "--cached"))
        assert inventory["unstaged_patch_sha256"] == fleet.digest(fleet.git(lane,
            "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames"))
    else:
        assert inventory["local_commits"] == [] and inventory["changes"] == []
    assert fleet.tree_manifest(lane) == before and index.read_bytes() == index_before
    assert git(lane, "rev-parse", "HEAD") == head
    assert git(primary, "rev-parse", "native-wave") == base
    assert (directory / "terminal.json").read_bytes() == terminal_before
    assert [p.name for p in directory.glob("attempt-*")] == ["attempt-1"]
    assert not any((directory / "attempt-1" / name).exists() for name in (
        "before.tar", "gitdir-before.tar", "preparation.json", "move-started.json", "worktree"))
    receipts = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*.json")}
    assert lifecycle.complete_pending(directory, delay=0) == result
    assert {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*.json")} == receipts
    assert lane.is_dir() and index.read_bytes() == index_before


@pytest.mark.parametrize("drift", ["head", "branch"])
def test_detached_completion_rejects_changed_terminal_identity(native_lane, drift):
    _, lane, git, env = native_lane
    git(lane, "checkout", "--detach")
    directory = register_from_exited_owner(lane, env)
    terminal = (directory / "terminal.json").read_bytes()
    if drift == "head":
        git(lane, "commit", "--allow-empty", "-m", "later detached identity")
    else:
        git(lane, "checkout", "native-wave")
    before = fleet.tree_manifest(lane)
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "ESCALATED" and result["attempts_exhausted"] == 3
    assert result["reason"] == "Detached native completion identity drift"
    assert "landing_owner" not in result
    assert not list(directory.glob("attempt-*/useful-work.json"))
    assert fleet.tree_manifest(lane) == before
    assert (directory / "terminal.json").read_bytes() == terminal


def test_stopped_pr_retains_its_surviving_disposition_owner(native_lane):
    primary, lane, git, env = native_lane
    from mu.tools.executors import pr_disposition_executor
    owner = dict(task_id="[FLEET-NATIVE-LIFECYCLE-PREVENTION]", wave_id="native-test-wave",
                 packet="reports/control_plane/native-test-wave.md")
    observed = pr_disposition_executor.record_native_pr_lifecycle(primary / ".git", number=123,
        head=git(lane, "rev-parse", "HEAD"), branch="native-wave", owner=owner,
        state="STOPPED", detail="retained native PR")
    before = Path(observed["path"]).read_bytes()
    directory = register_from_exited_owner(lane, env, result={
        "pr_number": 123, "pr_lifecycle": {"path": observed["path"], "owner": owner, "state": "STOPPED"}})
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "ESCALATED"
    assert result["pr_owner"]["owner"] == owner and result["pr_number"] == 123
    assert lane.exists() and Path(observed["path"]).read_bytes() == before


@pytest.mark.parametrize("status", ["success", "stopped"])
@pytest.mark.parametrize("edit", ["staged", "unstaged", "index_only", "untracked"])
def test_completion_rechecks_inventory_before_preservation_admission(native_lane, monkeypatch, status, edit):
    primary, lane, git, env = native_lane
    directory = register_from_exited_owner(lane, env, status=status)
    terminal = (directory / "terminal.json").read_bytes()
    original = (lane / "tracked").read_bytes()
    index = Path(git(lane, "rev-parse", "--absolute-git-dir")) / "index"
    inventory = lifecycle.useful_work
    changed = {}

    def inventory_then_exited_writer(path, base):
        observed = inventory(path, base)
        if not changed:
            assert observed["status"] == "COVERED"
            name = "new-code" if edit == "untracked" else "tracked"
            (lane / name).write_bytes(b"valuable implementation after coverage observation\n")
            if edit in {"staged", "index_only"}:
                git(lane, "add", name)
            if edit == "index_only":
                (lane / name).write_bytes(original)
            changed.update(manifest=fleet.tree_manifest(lane), index=index.read_bytes(),
                           head=git(lane, "rev-parse", "HEAD"), path=name)
            assert inventory(path, base)["status"] == "NEEDS_LANDING"
        return observed

    # Only inject the completed edit; real ownership, inventory, preservation
    # and Git transaction checks still run against the disposable repositories.
    monkeypatch.setattr(lifecycle, "useful_work", inventory_then_exited_writer)
    result = lifecycle.complete_pending(directory, delay=0)

    assert result["state"] == "ESCALATED", result
    assert lane.is_dir()
    assert fleet.tree_manifest(lane) == changed["manifest"]
    assert index.read_bytes() == changed["index"]
    assert git(primary, "rev-parse", "native-wave") == changed["head"]
    assert (directory / "terminal.json").read_bytes() == terminal
    first = json.loads((directory / "attempt-1/result.json").read_text())
    assert first["state"] == "PENDING" and first["outcome"]["status"] == "HOLD"
    assert "useful-work/index identity changed" in first["reason"]
    old_inventory = (directory / "attempt-1/useful-work.json").read_bytes()
    assert json.loads(old_inventory)["status"] == "COVERED"
    owner = result["landing_owner"]
    assert owner["source"] == str(lane) and owner["head"] == changed["head"]
    assert owner["evidence"] == str(directory / "attempt-2/useful-work.json")
    evidence = json.loads(Path(owner["evidence"]).read_text())
    assert evidence["status"] == "NEEDS_LANDING"
    assert [row["path"] for row in evidence["changes"]] == [changed["path"]]
    assert sorted(p.name for p in directory.glob("attempt-*")) == ["attempt-1", "attempt-2"]
    for attempt in directory.glob("attempt-*"):
        assert not any((attempt / name).exists() for name in (
            "before.tar", "gitdir-before.tar", "preparation.json", "move-started.json", "worktree"))
    assert lifecycle.complete_pending(directory, delay=0) == result
    assert (directory / "attempt-1/useful-work.json").read_bytes() == old_inventory
    assert lane.is_dir() and not (directory / "attempt-3").exists()


def test_live_registered_owner_cannot_be_retired(native_lane):
    _, lane, _, _ = native_lane
    directory = lifecycle.register_lane(lane, "native-test-wave")
    lifecycle.request_completion(directory, status="stopped")
    before = fleet.tree_manifest(lane)
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "ESCALATED" and result["attempts_exhausted"] == 3
    assert "owner remains live" in result["reason"]
    assert fleet.tree_manifest(lane) == before
    assert len(list(directory.glob("attempt-*"))) == 3


def test_native_completion_late_index_drift_keeps_explicit_landing_owner(native_lane, monkeypatch):
    primary, lane, git, env = native_lane
    directory = register_from_exited_owner(lane, env, status="success")
    preserve = fleet.preserve_archive

    def archive_then_change_index(root, output, manifest):
        preserve(root, output, manifest)
        if root == lane and output.name == "before.tar":
            blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=lane,
                input=b"late index-only implementation\n", env=env, check=True, capture_output=True).stdout.decode().strip()
            git(lane, "update-index", "--cacheinfo", "100644," + blob + ",tracked")

    monkeypatch.setattr(fleet, "preserve_archive", archive_then_change_index)
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "ESCALATED", result
    assert lane.exists()
    assert result["landing_owner"]
    assert git(lane, "show", ":tracked") == "late index-only implementation"
    assert (lane / "tracked").read_bytes() == b"native code\n"
    first = json.loads((directory / "attempt-1/result.json").read_bytes())
    assert first["landing_owner"]["status"] == "UNRESOLVED_TRANSACTION_DRIFT"


def test_completed_native_receipt_detects_retired_index_only_drift(native_lane):
    _, lane, git, env = native_lane
    directory = register_from_exited_owner(lane, env, status="success")
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "COMPLETE", result
    destination = Path(result["destination"])
    terminal = (directory / "completion.json").read_bytes()
    git(destination, "update-index", "--chmod=+x", "tracked")
    with pytest.raises(fleet.Hold, match="transaction drift"):
        lifecycle.complete_pending(directory, delay=0)
    assert not lane.exists()
    assert (directory / "completion.json").read_bytes() == terminal


@pytest.mark.parametrize("fault", [None, "dependency", "interrupted"])
def test_supported_committed_recovery_retains_original_0600_owner_without_fleet_replay(native_lane, fault):
    from mu.tools.executors import commit_executor
    primary, lane, git, env = native_lane
    dependencies = list(fleet.SYNC_RECOVERY_DEPENDENCIES)
    for name in dependencies:
        destination = primary / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPO_ROOT / name).read_bytes())
    git(primary, "add", ".")
    git(primary, "commit", "-m", "committed native repair")
    git(primary, "push", "origin", "dev")
    authority = git(primary, "rev-parse", "HEAD")
    (lane / "tracked").write_text("original staged owner\n")
    git(lane, "add", "tracked")
    (lane / "tracked").write_text("original private bytes\n")
    (lane / "tracked").chmod(0o600)
    class PendingStash(BaseException):
        pass
    def checkpoint(stage, manifest):
        if stage == "after_stash_before_publish":
            raise PendingStash()
    binding = commit_executor.bind_terminal_target_identity(lane, base_branch="dev")
    with pytest.raises(PendingStash):
        commit_executor.sync_primary_worktree_to_base(primary, "dev", target_identity=binding,
            checkpoint=checkpoint, log=lambda _: None)
    journal = next((primary / ".git/rcx_primary_worktree_sync_transactions").glob("*/manifest.json"))
    pending = json.loads(journal.read_bytes())
    assert pending["stash_oid"] is None and pending["state"] == "PREPARED"
    assert pending["tracked_snapshots"]["tracked"]["worktree"]["mode"] == 0o600
    pending.update(state="HOLD", hold_reason="transaction worktree identity mismatch")
    journal.write_text(json.dumps(pending))
    original_journal = journal.read_bytes()
    stashes = git(primary, "stash", "list", "--format=%H")
    recovery = journal.parent
    if fault == "dependency":
        (primary / dependencies[0]).write_text("uncommitted recovery code\n")
        git(primary, "add", dependencies[0])
    elif fault == "interrupted":
        recovery.mkdir(parents=True, exist_ok=True)
        (recovery / "fleet-recovery-claim.json").write_text("{}")
    if fault:
        with pytest.raises(fleet.Hold):
            lifecycle.recover_pending_sync(journal, authority_commit=authority)
        assert journal.read_bytes() == original_journal
        assert git(primary, "stash", "list", "--format=%H") == stashes
    else:
        assert lifecycle.main(["--record", str(journal), "--recover-sync", "--authority-commit", authority]) == 0
        assert lane.exists() and git(lane, "rev-parse", "HEAD") == authority
        assert (lane / "tracked").read_text() == "original private bytes\n"
        assert (lane / "tracked").stat().st_mode & 0o777 == 0o600
        saved = {p.name: p.read_bytes() for p in recovery.glob("*.json")}
        assert lifecycle.main(["--record", str(journal), "--recover-sync", "--authority-commit", authority]) == 0
        assert saved == {p.name: p.read_bytes() for p in recovery.glob("*.json")}


def test_interrupted_claim_never_repeats_ambiguous_mutation(native_lane):
    _, lane, _, env = native_lane
    directory = register_from_exited_owner(lane, env)
    (directory / "attempt-1").mkdir()
    result = lifecycle.complete_pending(directory, delay=0)
    assert result["state"] == "ESCALATED"
    assert "no replay" in result["reason"]
    assert not (directory / "attempt-2").exists()
    assert lane.exists()


def test_new_native_commit_gets_fresh_completion_without_replaying_stopped_owner(native_lane):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"useful implementation to land\n")
    git(lane, "add", "tracked")
    stopped = register_from_exited_owner(lane, env)
    first = lifecycle.complete_pending(stopped, delay=0)
    assert first["state"] == "ESCALATED"
    old = {name: (stopped / name).read_bytes() for name in ("terminal.json", "completion.json")}
    git(lane, "commit", "-m", "native landing of retained work")
    git(primary, "merge", "--ff-only", "native-wave")
    git(primary, "push", "origin", "dev")
    successor = register_from_exited_owner(lane, env, status="success")
    assert successor != stopped
    result = lifecycle.complete_pending(successor, delay=0)
    assert result["state"] == "COMPLETE", result
    assert not lane.exists()
    assert {name: (stopped / name).read_bytes() for name in old} == old
    assert lifecycle.complete_pending(stopped, delay=0) == first
    assert len(list(stopped.glob("attempt-*"))) == 1


@pytest.mark.parametrize("status", ["merged", "success"])
def test_same_head_merge_completes_with_immutable_stopped_evidence(native_lane, status):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"committed implementation to land\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "retained native implementation")
    head = git(lane, "rev-parse", "HEAD")
    stopped = register_from_exited_owner(lane, env)
    first = lifecycle.complete_pending(stopped, delay=0)
    assert first["state"] == "ESCALATED" and first["landing_owner"]["head"] == head
    old = {p.relative_to(stopped): p.read_bytes() for p in stopped.rglob("*") if p.is_file()}
    git(primary, "merge", "--ff-only", "native-wave")
    git(primary, "push", "origin", "dev")
    assert git(lane, "rev-parse", "HEAD") == head
    assert lifecycle.useful_work(str(lane), head)["status"] == "COVERED"

    successor = register_from_exited_owner(lane, env, status=status, result={"merge_sha": head})
    assert successor != stopped
    terminal = json.loads((successor / "terminal.json").read_text())
    assert terminal["status"] == status and terminal["merge_sha"] == head
    assert lifecycle.request_completion(stopped, status=status, result={"merge_sha": head})["record"] == str(successor)
    completed = lifecycle.complete_pending(successor, delay=0)
    assert completed["state"] == "COMPLETE", completed
    assert not lane.exists()
    assert (Path(completed["destination"]) / "tracked").read_bytes() == b"committed implementation to land\n"
    assert {p: (stopped / p).read_bytes() for p in old} == old
    assert lifecycle.complete_pending(stopped, delay=0) == first
    assert lifecycle.complete_pending(successor, delay=0) == completed
    assert lifecycle.request_completion(stopped, status="success")["record"] == str(successor)
    assert len(list(stopped.glob("attempt-*"))) == 1
    assert [p.name for p in successor.glob("attempt-*")] == ["attempt-2"]


def test_same_head_merge_keeps_consumed_attempt_budget(native_lane, monkeypatch):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"retained committed work\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "retained work")
    head = git(lane, "rev-parse", "HEAD")
    stopped = register_from_exited_owner(lane, env)
    assert lifecycle.complete_pending(stopped, delay=0)["state"] == "ESCALATED"
    git(primary, "merge", "--ff-only", "native-wave")
    git(primary, "push", "origin", "dev")
    successor = register_from_exited_owner(lane, env, status="merged", result={"merge_sha": head})
    assert successor != stopped
    monkeypatch.setattr(fleet, "_absent_pid", lambda _pid: False)
    result = lifecycle.complete_pending(successor, delay=0)
    assert result["state"] == "ESCALATED" and result["attempts_exhausted"] == 3
    assert sorted(p.name for p in successor.glob("attempt-*")) == ["attempt-2", "attempt-3"]
    again = lifecycle.request_completion(stopped, status="success", result={"merge_sha": head})
    assert again["record"] == str(successor)
    assert lifecycle.complete_pending(Path(again["record"]), delay=0) == result
    assert lane.exists()


@pytest.mark.parametrize("authority", ["unlanded", "unrelated"])
def test_same_head_successor_requires_verified_merge_authority(native_lane, authority):
    primary, lane, git, env = native_lane
    base = git(primary, "rev-parse", "HEAD")
    (lane / "tracked").write_bytes(b"still unlanded work\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "unlanded work")
    head = git(lane, "rev-parse", "HEAD")
    stopped = register_from_exited_owner(lane, env)
    first = lifecycle.complete_pending(stopped, delay=0)
    before = fleet.tree_manifest(lane)
    with pytest.raises(fleet.Hold, match="merge authority"):
        lifecycle.request_completion(stopped, status="merged",
            result={"merge_sha": head if authority == "unlanded" else base})
    assert not list(stopped.glob("successor-*.json"))
    assert lifecycle.complete_pending(stopped, delay=0) == first
    assert fleet.tree_manifest(lane) == before


def test_same_head_merge_cannot_replay_an_interrupted_attempt(native_lane):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"retained committed work\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "retained work")
    head = git(lane, "rev-parse", "HEAD")
    stopped = register_from_exited_owner(lane, env)
    attempt = stopped / "attempt-1"
    attempt.mkdir()
    (attempt / "move-started.json").write_text('{"state":"OUTCOME_UNKNOWN"}\n')
    first = lifecycle.complete_pending(stopped, delay=0)
    assert "no replay" in first["reason"]
    old = {p.relative_to(stopped): p.read_bytes() for p in stopped.rglob("*") if p.is_file()}
    git(primary, "merge", "--ff-only", "native-wave")
    git(primary, "push", "origin", "dev")
    with pytest.raises(fleet.Hold, match="pre-mutation"):
        lifecycle.request_completion(stopped, status="merged", result={"merge_sha": head})
    assert not list(stopped.glob("successor-*.json"))
    assert {p: (stopped / p).read_bytes() for p in old} == old
    assert not (stopped / "attempt-2").exists() and lane.exists()


def test_same_head_successor_rechecks_immutable_predecessor_before_completion(native_lane):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"retained committed work\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "retained work")
    head = git(lane, "rev-parse", "HEAD")
    stopped = register_from_exited_owner(lane, env)
    assert lifecycle.complete_pending(stopped, delay=0)["state"] == "ESCALATED"
    git(primary, "merge", "--ff-only", "native-wave")
    git(primary, "push", "origin", "dev")
    successor = register_from_exited_owner(lane, env, status="merged", result={"merge_sha": head})
    assert successor != stopped
    evidence = stopped / "attempt-1/primary-sync.json"
    evidence.write_bytes(evidence.read_bytes() + b"\n")
    with pytest.raises(fleet.Hold, match="predecessor evidence changed"):
        lifecycle.complete_pending(successor, delay=0)
    assert not list(successor.glob("attempt-*")) and lane.exists()


@pytest.mark.parametrize("already_merged,consumed", [(False, 0), (True, 0), (True, 1)])
def test_live_dispatcher_failed_then_successful_commit_children_complete_after_exit(
        native_lane, already_merged, consumed):
    """Exercise the real owner processes, durable APIs and retirement transaction."""
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"live parent implementation\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "implementation retained across commit retry")
    head = git(lane, "rev-parse", "HEAD")
    if already_merged:
        git(primary, "merge", "--ff-only", "native-wave")
        git(primary, "push", "origin", "dev")
    # The real dispatcher and commit lifecycle boundaries run in separate
    # processes. Only the mechanical commit body and recovery decision are
    # supplied by the fixture; all owner, closeout and worker code remains real.
    child_program = """
import json, os, sys
from pathlib import Path
from unittest.mock import patch
from mu.tools.executors import commit_executor as commit
lane = Path(sys.argv[1])
result = json.loads(sys.argv[2])
handoff = dict(wave_id='native-test-wave', pre_commit_receipt_path='.agent_bus/receipt.json')
def mechanical_body(*args, **kwargs):
    if result.get('merge_sha'):
        cleanup = commit._post_merge_cleanup(cleanup_root=lane, repo_root=lane,
            target_branch='native-wave', base_branch='dev', wave_id='native-test-wave',
            log=lambda _: None, terminal_result=result)
        assert cleanup['completion_state'] == 'PENDING', cleanup
    return result
with patch.object(commit, '_run_commit_pipeline_impl', side_effect=mechanical_body), \
     patch.object(commit, '_commit_lifecycle_pager_enabled', return_value=False):
    outcome = commit.run_commit_pipeline(handoff, repo_root=lane)
pending = outcome['worktree_completion']
print(json.dumps(dict(record=pending['record'], pending=pending, pid=os.getpid(),
                      parent=os.getppid(), status=outcome['status'])))
raise SystemExit(0 if outcome['status'] == 'success' else 1)
"""
    parent_program = """
import contextlib, io, json, os, subprocess, sys
from pathlib import Path
from unittest.mock import patch
from mu.tools.executors import executor_dispatch as dispatch
lane = Path(sys.argv[1])
results = [json.loads(sys.argv[3]), json.loads(sys.argv[4])]
handoff = lane / '.agent_bus/executors/phase_b_handoff.json'
handoff.parent.mkdir(parents=True, exist_ok=True)
handoff.write_text(json.dumps(dict(wave_id='native-test-wave')))
args = dispatch.build_surface_parser().parse_args(['commit', '--handoff', str(handoff)])
children = []
output = sys.stdout
def executor(command, **kwargs):
    assert len(children) < 2, 'dispatcher replayed a consumed child'
    run = subprocess.run([sys.executable, '-c', sys.argv[2], str(lane),
                          json.dumps(results[len(children)])], capture_output=True, text=True)
    if not run.stdout:
        raise AssertionError(run.stderr)
    value = json.loads(run.stdout)
    assert value['parent'] == os.getpid()
    assert 'worker_pid' not in value['pending'], value
    children.append(value)
    print(run.stdout.strip(), file=output, flush=True)
    if len(children) == 2:
        assert sys.stdin.readline().strip() == 'complete'
    return run
def recovery(*args, **kwargs):
    assert len(children) == 1
    assert sys.stdin.readline().strip() == 'retry'
    return dict(recovered=True)
with contextlib.redirect_stdout(io.StringIO()) as captured, \
     patch.object(dispatch, '_run_executor_in_group', side_effect=executor), \
     patch.object(dispatch, 'attempt_recovery', side_effect=recovery):
    status = dispatch.run_recoverable_surface_command(args, repo_root=lane, config={})
assert status == 0, captured.getvalue()
assert len(children) == 2
print(json.dumps(dict(dispatch_exit=status, children=len(children))), flush=True)
"""
    failed = dict(status="error", step="post_merge" if already_merged else "wait_ci",
                  errors=["first commit child failed"])
    if already_merged:
        failed["merge_sha"] = head
    success = dict(status="success", merge_sha=head)
    earlier = None
    if consumed:
        earlier = register_from_exited_owner(lane, env, role="commit", closeout=True,
            status="merged", result=failed)
        previous = lifecycle.complete_pending(earlier, delay=0)
        assert previous["reason"] == lifecycle.FAILED_CLOSEOUT_REASON
        earlier_bytes = {p.relative_to(earlier): p.read_bytes()
                         for p in earlier.rglob("*") if p.is_file()}
    parent = subprocess.Popen([sys.executable, "-c", parent_program, str(lane), child_program,
        json.dumps(failed), json.dumps(success)], cwd=primary, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def child_result():
        line = parent.stdout.readline()
        if not line:
            output, errors = parent.communicate(timeout=10)
            pytest.fail(errors + output, pytrace=False)
        value = json.loads(line)
        assert parent.poll() is None
        assert value["parent"] == parent.pid
        assert value["pending"]["continuation"] == "dispatcher terminal finally owns the bounded child"
        assert value["pending"]["state"] == "PENDING"
        return Path(value["record"]), value["pid"]

    try:
        stopped, failed_pid = child_result()
        assert not (stopped / "completion.json").exists()
        assert not list(stopped.glob("attempt-*"))
        old = {p.relative_to(stopped): p.read_bytes() for p in stopped.rglob("*") if p.is_file()}
        assert json.loads(old[Path("closeout.json")])["result"] == failed
        if not already_merged:
            git(primary, "merge", "--ff-only", "native-wave")
            git(primary, "push", "origin", "dev")
        assert git(lane, "rev-parse", "HEAD") == head
        receipt = lane / ".agent_bus/receipt.json"
        receipt.write_bytes(b'{"native":"fresh successful child receipt"}\n')
        parent.stdin.write("retry\n")
        parent.stdin.flush()
        successor, success_pid = child_result()
        assert successor != stopped and success_pid != failed_pid
        assert lane.exists() and not (successor / "completion.json").exists()
        assert not list(successor.glob("attempt-*"))
        predecessor = json.loads((successor / "predecessor.json").read_bytes())
        assert predecessor["attempts_used"] == consumed
        assert predecessor["evidence_sha256"]["closeout.json"] == fleet.digest(old[Path("closeout.json")])
        closeout = json.loads((successor / "closeout.json").read_bytes())
        assert closeout["result"] == success
        assert bytes.fromhex(closeout["artifacts"][str(receipt)]["bytes_hex"]) == receipt.read_bytes()
        assert {p: (stopped / p).read_bytes() for p in old} == old
        output, errors = parent.communicate("complete\n", timeout=20)
        assert parent.returncode == 0, errors
        assert json.loads(output) == dict(dispatch_exit=0, children=2)
        final = successor / "completion.json"
        deadline = time.monotonic() + 60
        while not final.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert final.exists(), (successor / "worker.log").read_text()
        completed = json.loads(final.read_bytes())
        assert completed["state"] == "COMPLETE", completed
        assert not lane.exists()
        destination = Path(completed["destination"])
        assert (destination / "tracked").read_bytes() == b"live parent implementation\n"
        assert (destination / ".agent_bus/receipt.json").read_bytes() == b'{"native":"fresh successful child receipt"}\n'
        assert git(primary, "rev-parse", "native-wave") == head
        assert {p: (stopped / p).read_bytes() for p in old} == old
        assert not list(stopped.glob("attempt-*"))
        attempts = sorted(successor.glob("attempt-*"))
        assert 1 <= len(attempts) <= lifecycle.MAX_ATTEMPTS - consumed
        assert [p.name for p in attempts] == [f"attempt-{n}" for n in range(consumed + 1, consumed + len(attempts) + 1)]
        assert lifecycle.complete_pending(successor, delay=0) == completed
        assert lifecycle.complete_pending(stopped, delay=0) == completed
        assert not list(stopped.glob("attempt-*"))
        if earlier is not None:
            assert {p: (earlier / p).read_bytes() for p in earlier_bytes} == earlier_bytes
            assert lifecycle.complete_pending(earlier, delay=0) == previous
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.communicate(timeout=10)


@pytest.mark.parametrize("already_merged", [False, True])
@pytest.mark.parametrize("closeout_status", ["success", "error", "absent"])
@pytest.mark.parametrize("deferred", [False, True])
def test_failed_commit_closeout_gets_bounded_same_head_continuation(
        native_lane, already_merged, closeout_status, deferred):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"native committed implementation\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "implementation")
    head = git(lane, "rev-parse", "HEAD")
    if already_merged:
        git(primary, "merge", "--ff-only", "native-wave")
        git(primary, "push", "origin", "dev")
    failed_result = dict(status="error", step="refresh_post_merge_package" if already_merged else "wait_ci",
                         errors=["Native closeout needs correction"])
    if already_merged:
        failed_result["merge_sha"] = head
    stopped = register_from_exited_owner(lane, env, role="commit", closeout=True,
        status="merged" if already_merged else "error", result=failed_result)
    if not deferred:
        first = lifecycle.complete_pending(stopped, delay=0)
        assert first["state"] == "ESCALATED" and "closeout failed" in first["reason"]
        assert "landing_owner" not in first and lane.is_dir()
    old = {p.relative_to(stopped): p.read_bytes() for p in stopped.rglob("*") if p.is_file()}
    if not already_merged:
        git(primary, "merge", "--ff-only", "native-wave")
        git(primary, "push", "origin", "dev")
    assert git(lane, "rev-parse", "HEAD") == head
    receipt = lane / ".agent_bus/receipt.json"
    receipt.write_bytes(b'{"native":"fresh continuation receipt"}\n')
    result = dict(status=closeout_status, merge_sha=head)
    successor = register_from_exited_owner(lane, env, role="commit", status="success", result=result,
                                          closeout=closeout_status != "absent")
    assert successor != stopped
    predecessor = json.loads((successor / "predecessor.json").read_bytes())
    assert predecessor["attempts_used"] == (0 if deferred else 1)
    assert predecessor["evidence_sha256"]["closeout.json"] == fleet.digest(old[Path("closeout.json")])
    if closeout_status != "absent":
        closeout = json.loads((successor / "closeout.json").read_bytes())
        assert closeout["result"] == result
        assert bytes.fromhex(closeout["artifacts"][str(receipt)]["bytes_hex"]) == receipt.read_bytes()
    completed = lifecycle.complete_pending(successor, delay=0)
    if closeout_status == "success":
        assert completed["state"] == "COMPLETE", completed
        assert not lane.exists()
        destination = Path(completed["destination"])
        assert (destination / "tracked").read_bytes() == b"native committed implementation\n"
        assert (destination / ".agent_bus/receipt.json").read_bytes() == b'{"native":"fresh continuation receipt"}\n'
        assert git(primary, "rev-parse", "native-wave") == head
    else:
        assert completed["state"] == "ESCALATED" and lane.is_dir()
        reason = "not durably published" if closeout_status == "absent" else "closeout failed"
        assert reason in completed["reason"]
    start = 1 if deferred else 2
    end = 3 if closeout_status == "absent" else start
    expected_attempts = [f"attempt-{n}" for n in range(start, end + 1)]
    assert sorted(p.name for p in successor.glob("attempt-*")) == expected_attempts
    assert {p: (stopped / p).read_bytes() for p in old} == old
    assert lifecycle.complete_pending(stopped, delay=0) == (completed if deferred else first)
    assert lifecycle.complete_pending(successor, delay=0) == completed
    assert lifecycle.request_completion(stopped, status="success")["record"] == str(successor)
    assert [p.name for p in stopped.glob("attempt-*")] == ([] if deferred else ["attempt-1"])


@pytest.mark.parametrize("final_status", ["success", "error"])
def test_repeated_failed_closeout_continuations_keep_original_attempt_budget(native_lane, final_status):
    primary, lane, git, env = native_lane
    head = git(primary, "rev-parse", "HEAD")
    records = []
    snapshots = []
    for number, status in enumerate(("error", "error", final_status), 1):
        directory = register_from_exited_owner(lane, env, role="commit", closeout=True,
            status="merged", result=dict(status=status, merge_sha=head))
        assert directory not in records
        outcome = lifecycle.complete_pending(directory, delay=0)
        assert outcome["state"] == ("COMPLETE" if status == "success" else "ESCALATED"), outcome
        assert [p.name for p in directory.glob("attempt-*")] == [f"attempt-{number}"]
        records.append(directory)
        snapshots.append({p.relative_to(directory): p.read_bytes()
                          for p in directory.rglob("*") if p.is_file()})
    if final_status == "error":
        successor = register_from_exited_owner(lane, env, role="commit", closeout=True,
            status="success", result=dict(status="success", merge_sha=head))
        outcome = lifecycle.complete_pending(successor, delay=0)
        assert outcome["state"] == "ESCALATED" and outcome["attempts_exhausted"] == 3
        assert not list(successor.glob("attempt-*")) and lane.is_dir()
        assert lifecycle.request_completion(records[0], status="success", result={"merge_sha": head})["record"] == str(successor)
        assert lifecycle.complete_pending(successor, delay=0) == outcome
    else:
        assert not lane.exists()
    for directory, snapshot in zip(records, snapshots):
        assert {p: (directory / p).read_bytes() for p in snapshot} == snapshot


@pytest.mark.parametrize("fault", ["move-started.json", "preparation.json", "unfinished", "claim", "unlanded"])
@pytest.mark.parametrize("deferred", [False, True])
def test_failed_closeout_successor_rejects_unverified_or_interrupted_evidence(native_lane, fault, deferred):
    primary, lane, git, env = native_lane
    (lane / "tracked").write_bytes(b"native implementation\n")
    git(lane, "add", "tracked")
    git(lane, "commit", "-m", "implementation")
    head = git(lane, "rev-parse", "HEAD")
    stopped = register_from_exited_owner(lane, env, role="commit", closeout=True,
        status="error", result=dict(status="error"))
    if not deferred:
        assert lifecycle.complete_pending(stopped, delay=0)["state"] == "ESCALATED"
    elif fault != "unlanded":
        (stopped / "attempt-1").mkdir()
    if fault in {"move-started.json", "preparation.json"}:
        (stopped / "attempt-1" / fault).write_text('{"state":"OUTCOME_UNKNOWN"}\n')
    elif fault == "unfinished":
        if not deferred:
            (stopped / "attempt-1/result.json").unlink()
    elif fault == "claim":
        (stopped / "attempt-1/claim.json").write_text('{"number":0}\n')
    if fault != "unlanded":
        git(primary, "merge", "--ff-only", "native-wave")
        git(primary, "push", "origin", "dev")
    old = {p.relative_to(stopped): p.read_bytes() for p in stopped.rglob("*") if p.is_file()}
    before = fleet.tree_manifest(lane)
    with pytest.raises(fleet.Hold, match="merge authority" if fault == "unlanded" else "pre-mutation"):
        lifecycle.request_completion(stopped, status="success", result=dict(status="success", merge_sha=head))
    assert not (stopped / "merged-successor.json").exists()
    assert {p: (stopped / p).read_bytes() for p in old} == old
    assert fleet.tree_manifest(lane) == before and not (stopped / "attempt-2").exists()


@pytest.mark.parametrize("deferred", [False, True])
def test_failed_closeout_successor_rechecks_preserved_closeout_bytes(native_lane, deferred):
    primary, lane, git, env = native_lane
    head = git(primary, "rev-parse", "HEAD")
    stopped = register_from_exited_owner(lane, env, role="commit", closeout=True,
        status="error", result=dict(status="error"))
    if not deferred:
        assert lifecycle.complete_pending(stopped, delay=0)["state"] == "ESCALATED"
    successor = register_from_exited_owner(lane, env, role="commit", closeout=True,
        status="success", result=dict(status="success", merge_sha=head))
    evidence = stopped / "closeout.json"
    evidence.write_bytes(evidence.read_bytes() + b"\n")
    with pytest.raises(fleet.Hold, match="predecessor evidence changed"):
        lifecycle.complete_pending(successor, delay=0)
    assert not list(successor.glob("attempt-*")) and lane.is_dir()
    with pytest.raises(fleet.Hold, match="predecessor evidence changed"):
        lifecycle.request_completion(stopped, status="success", result=dict(merge_sha=head))


def test_native_worker_is_bounded_and_keeps_output_in_surviving_root(native_lane):
    _, lane, _, env = native_lane
    directory = register_from_exited_owner(lane, env)
    result = subprocess.run([sys.executable, str(Path(lifecycle.__file__)),
        "--record", str(directory), "--complete"], capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["source_absent"] is True
    assert not lane.exists()


@pytest.mark.parametrize("closeout_status", ["success", "error", "absent"])
def test_commit_closeout_and_bridge_config_are_durable_before_retirement(native_lane, closeout_status):
    primary, lane, git, env = native_lane
    bus = lane / ".agent_bus"
    config = bus / "bridge_config.json"
    config.write_bytes(b'{"roles":"retained native config"}\n')
    package = bus / "meta/post_merge_package.json"
    package.parent.mkdir()
    package.write_bytes(b'{"owner":"original transactionR2"}\n')
    receipt = bus / "receipt.json"
    receipt_before = receipt.read_bytes()
    program = (
        "import json,sys; from pathlib import Path; "
        "from mu.tools.executors import worktree_lifecycle as w; "
        "p=Path(sys.argv[1]); d=w.register_lane(p,'native-test-wave',role='commit'); "
        "w.request_completion(d,status='merged',result={'merge_sha':sys.argv[3]}); "
        "w.publish_closeout(d,repo=p,handoff={'pre_commit_receipt_path':'.agent_bus/receipt.json'}, "
        "result={'status':sys.argv[2],'post_merge_package_path':'.agent_bus/meta/post_merge_package.json'}) "
        "if sys.argv[2]!='absent' else None; print(d)"
    )
    observed = subprocess.run([sys.executable, "-c", program, str(lane), closeout_status,
                               git(primary, "rev-parse", "HEAD")],
        env=env, capture_output=True, text=True, check=True)
    directory = Path(observed.stdout.strip())
    value = lifecycle.complete_pending(directory, delay=0)
    if closeout_status == "absent":
        assert value["state"] == "ESCALATED" and "not durably published" in value["reason"]
        assert lane.exists() and config.exists() and receipt.read_bytes() == receipt_before
        return
    archived = json.loads((directory / "closeout.json").read_text())
    assert archived["authority"] == "historical_closeout_not_replay_authority"
    assert bytes.fromhex(archived["artifacts"][str(config)]["bytes_hex"]) == b'{"roles":"retained native config"}\n'
    assert bytes.fromhex(archived["artifacts"][str(receipt)]["bytes_hex"]) == receipt_before
    assert str(package) in archived["artifacts"]
    saved = (directory / "closeout.json").read_bytes()
    if closeout_status == "error":
        assert value["state"] == "ESCALATED" and "closeout failed" in value["reason"]
        assert lane.exists() and config.exists()
    else:
        assert value["state"] == "COMPLETE", value
        assert not lane.exists()
        assert (Path(value["destination"]) / ".agent_bus/receipt.json").read_bytes() == receipt_before
    assert lifecycle.complete_pending(directory, delay=0) == value
    assert (directory / "closeout.json").read_bytes() == saved
