#!/usr/bin/env python3
"""Recoverable fleet operations; planning reads only declared manifests.

--residual plans fresh bounded worktree/shell retirement and explicit local-dev
sync. Apply is foreground, postmerge only; verify is read-only and never resumes
an interrupted operation. Immutable intent and receipts retain exact owners.
The legacy four-target and --reconcile-r1 authorities remain unchanged.
Exit 3 means an owned HOLD/INCOMPLETE outcome, never fleet-wide completion.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tarfile


WAVE_ID = "workingrcx-fleet-apply-r1-2026-09-11"
CLASSIFICATION_PATH = Path("reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json")
CLASSIFICATION_SHA256 = "19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf"
CLASSIFICATION_COMMIT = "23197ef9079ec47a022611dcc90fa848cbf4ee9f"
TOOL_PATH = Path("mu/tools/executors/workingrcx_fleet_apply.py")
TEST_PATH = Path("mu/tests/tools/test_workingrcx_fleet_apply.py")
PLAN_PATH = Path(f"reports/control_plane/{WAVE_ID}_apply_plan.json")
SCRIPT_PATH = Path(__file__).resolve()
FLEET_ROOT = Path("/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal")
COMMON_DIR = FLEET_ROOT / "WorkingRCX/.git"
OPERATION_ROOT = FLEET_ROOT / f"fleet-apply-preserved-{WAVE_ID}"
R1_MERGE = "a9e8d85a3d2f08b1a599c8f8ddecdc23f6ea38ec"
RECONCILE_WAVE_ID = "workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11"
RECONCILE_PLAN_PATH = Path(f"reports/control_plane/{RECONCILE_WAVE_ID}_plan.json")
RECONCILE_OPERATION_ROOT = FLEET_ROOT / f"fleet-apply-preserved-{RECONCILE_WAVE_ID}"
R1_RECEIPT_HASHES = {
    "intent.json": "a5d34bc15ba7a3fb72d000e8fa80a94196fbe0610a7131a9fe11c9f7a7cc2ed8",
    "plan.json": "8387fd46b515a0f939ca2c9a7b1438833584369dc2092babd172a8d67f6e1433",
    "summary.json": "b1f786822c76da35b0f0de916dc71a6adf521489468c5c2ed38ea82f34de21f8",
    "159/outcome.json": "b6b58ddc4a53471df915360657484cb1d64b5c9650c3304b0a84bc2ebaa23cbb",
    "163/outcome.json": "afae12ffde80fffe4dd5d6397fd57d79feb63f91f2a573806a4f13f6d417c615",
    "292/intent.json": "d2cb2d14de9ff97136ab8eaeb016a04b3be9ee872401b2557fe9ec81f43e6fde",
    "292/outcome.json": "1826bbe3c8a512395330e0a1649f800891c3c74deb49ff288e0422c48f388873",
    "292/preparation.json": "552b5d007a9f7c1df177464887a79cc3793cdd6ecbfa009c84d06ccd64fe374f",
    "292/before.json": "444886f28e2b0a343f8ad77a8d9aaef9da6a278b2e7798591334c981c65a8fa5",
    "292/gitdir-before.json": "be8ce4908ad9d009dff3abb6bd7110841a3590d25fba14523a08e6ab8a5b3671",
    "305/outcome.json": "e47921523c305a56b27d16aa5d8410177608572814abd0e2b70a4465f5238271",
}
CANDIDATES = tuple(
    dict(path=str(FLEET_ROOT / name), HEAD=head, branch="refs/heads/" + branch,
         common_dir=str(COMMON_DIR), git_dir=str(COMMON_DIR / "worktrees" / name))
    for name, head, branch in (
        ("WorkingRCX-pr1219-p0imrp-receipt-model-provenance-activation-20260822",
         "a6ee535a702875a62bb9170365d0b969320a9e32",
         "jabramsja/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22"),
        ("WorkingRCX-pr1219-p0imrpas-north-star-numbering-repair-20260822",
         "ff2e0304432b1405cf1584f44e26535e1291fc29",
         "jabramsja/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22"),
        ("workingrcx_pager_route_codex_20260701",
         "ba51ce3e32043fcc529a258ad967c0630a644425",
         "jabramsja/pager-route-codex-default-2026-07-01"),
        ("workingrcx_setrolesdefault_20260628",
         "13849e8aeea5d501078811f8b2b504cd72ff4f8e",
         "jabramsja/set-roles-syncs-default-no-drift-2026-06-28"),
    )
)
GIT_SETTINGS = (
    "core.hooksPath=/dev/null", "core.fsmonitor=false", "core.untrackedCache=false",
    "gc.auto=0", "maintenance.auto=false", "fetch.prune=false", "fetch.pruneTags=false",
    "fetch.writeCommitGraph=false", "fetch.recurseSubmodules=false", "submodule.recurse=false",
    "core.commitGraph=false", "advice.graftFileDeprecated=false",
)


class Hold(RuntimeError):
    """An unmet prerequisite, never permission to adapt the operation."""

    def __init__(self, message: str, *, diagnostic: dict | None = None):
        super().__init__(message)
        self.diagnostic = diagnostic


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_stat(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def file_hash(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise Hold("Evidence is not a regular file")
        h = hashlib.sha256()
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
        if stable_stat(os.fstat(stream.fileno())) != stable_stat(info):
            raise Hold("Evidence changed during hashing")
        return h.hexdigest()


def plain_directory(path: Path) -> None:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise Hold(f"Noncanonical or symlink directory: {path}")
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise Hold(f"Not a directory: {path}")


def read_plain(path: Path) -> bytes:
    plain_directory(path.absolute().parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Hold(f"Not a single-link regular file: {path}")
        data = stream.read()
        if stable_stat(os.fstat(stream.fileno())) != stable_stat(info):
            raise Hold(f"File changed during read: {path}")
        return data


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_new(path: Path, data: bytes, *, verify_existing: bool = False) -> None:
    plain_directory(path.absolute().parent)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if verify_existing and read_plain(path) == data:
            return
        raise Hold(f"Existing or ambiguous output, refusing overwrite: {path}") from None
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def new_directory(path: Path) -> None:
    plain_directory(path.parent)
    path.mkdir(mode=0o700)
    sync_directory(path.parent)


@contextmanager
def safe_git_environment(*, network: bool = False):
    # GIT_CONFIG_PARAMETERS works with the installed Git, including the older
    # Apple Git. It also applies to the existing terminal API's Git children.
    previous = {k: v for k, v in os.environ.items() if k.startswith("GIT_")}
    for key in previous:
        del os.environ[key]
    values = dict(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                  GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1",
                  GIT_NO_LAZY_FETCH="1", GIT_GRAFT_FILE=os.devnull,
                  GIT_TERMINAL_PROMPT="0", GIT_PROTOCOL_FROM_USER="0",
                  GIT_CONFIG_PARAMETERS=" ".join("'" + s + "'" for s in GIT_SETTINGS),
                  GIT_ALLOW_PROTOCOL="file:ssh:https" if network else "")
    os.environ.update(values)
    try:
        yield
    finally:
        for key in tuple(os.environ):
            if key.startswith("GIT_"):
                del os.environ[key]
        os.environ.update(previous)


def git(root: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> bytes:
    proc = subprocess.run(["git", "-C", str(root), *args], stdin=subprocess.DEVNULL,
                          capture_output=True, timeout=60)
    if proc.returncode not in allowed:
        # Do not copy target content or arbitrary executable diagnostics into
        # tracked output. Detailed preservation evidence stays local.
        raise Hold(f"Git {args[0]} failed (exit {proc.returncode})")
    return proc.stdout


def line(data: bytes) -> str:
    return os.fsdecode(data).removesuffix("\n")


def identity_of(row: dict) -> dict:
    return dict(path=row["path"], **{k: row["source"]["git"][k]
                                   for k in ("HEAD", "branch", "common_dir", "git_dir")})


def validate_classification(data: dict) -> None:
    try:
        if (data["schema_version"] != 1 or data["coverage_complete"] is not True
                or data["mutation_authorized"] is not False
                or data["observation_kind"] != "read_only_fleet_classification"
                or data["wave_id"] != "workingrcx-fleet-classification-r1-2026-09-11"
                or data["entry_count"] != 411 or len(data["entries"]) != 411
                or data["decision_counts"] != {"HOLD": 407, "CONDITIONAL_RETIRE_CANDIDATE": 4}):
            raise Hold("Malformed or incomplete classification envelope")
        paths, selected, counts = set(), [], Counter()
        for index, row in enumerate(data["entries"]):
            if (row["source_index"] != index or row["path"] in paths
                    or row["source"]["path"] != row["path"]
                    or not Path(row["path"]).is_absolute()
                    or row["mutation_authorized"] is not False
                    or row["decision"] not in ("HOLD", "CONDITIONAL_RETIRE_CANDIDATE")
                    or not row["reasons"]):
                raise Hold("Incomplete or duplicated classification row")
            paths.add(row["path"])
            counts[row["decision"]] += 1
            if row["decision"] == "CONDITIONAL_RETIRE_CANDIDATE":
                source = row["source"]
                ident = identity_of(row)
                if (source["git"]["dirty_status"] != "clean"
                        or any(source["git"]["dirty_counts"].values())
                        or source["git"]["branch_status"] != "symbolic"
                        or source["git"]["root"] != row["path"]
                        or source["repository_kind"] != "linked_worktree"
                        or source["inspection_status"] != "ok" or source["errors"]
                        or source["registration_status"] != "registered"
                        or source["registered_worktrees"] != [
                            {k: ident[k] for k in ("path", "HEAD", "branch")}]
                        or row["ancestry"]["status"] != "ANCESTOR"
                        or len(row["apply_prerequisites"]) != 7):
                    raise Hold("Incomplete conditional identity/evidence")
                selected.append(ident)
        if counts != data["decision_counts"] or selected != list(CANDIDATES):
            raise Hold("Broadened or mismatched four-candidate set")
    except (KeyError, TypeError, ValueError) as exc:
        raise Hold("Malformed or incomplete classification") from exc


def build_plan(repo: Path, classification: Path, sha256: str, commit: str,
               *, reconcile_r1: bool = False) -> dict:
    if sha256 != CLASSIFICATION_SHA256 or commit != CLASSIFICATION_COMMIT:
        raise Hold("Wrong pinned source hash or predecessor")
    if classification.absolute() != repo / CLASSIFICATION_PATH:
        raise Hold("Wrong classification source path")
    raw = read_plain(classification)
    if digest(raw) != CLASSIFICATION_SHA256:
        raise Hold("Classification raw SHA-256 mismatch")
    with safe_git_environment():
        if git(repo, "show", f"{commit}:{CLASSIFICATION_PATH}") != raw:
            raise Hold("Classification is not the exact landed blob")
        git(repo, "merge-base", "--is-ancestor", commit, "HEAD")
    data = json.loads(raw)
    validate_classification(data)
    entries = []
    for row in data["entries"]:
        entry = dict(source_index=row["source_index"], path=row["path"],
                     classification_decision=row["decision"],
                     source_identity=identity_of(row),
                     reason_codes=[r["code"] for r in row["reasons"]])
        if row["decision"] == "HOLD":
            entry["action"] = "UNTOUCHED_HOLD"
        else:
            entry.update(action="CONDITIONAL_GIT_WORKTREE_MOVE",
                         outcome="PENDING_POSTMERGE_ACTION_TIME_CHECKS",
                         destination=str(OPERATION_ROOT / str(row["source_index"]) / "worktree"))
        entries.append(entry)
    plan = dict(schema_version=1, wave_id=WAVE_ID, mutation_authorized=False,
                classification_path=str(CLASSIFICATION_PATH), classification_sha256=sha256,
                classification_commit=commit, entry_count=411, untouched_holds=407,
                conditional_candidates=4, operation_root=str(OPERATION_ROOT),
                entries=entries, postmerge_command=postmerge_command())
    if not reconcile_r1:
        return plan
    # Only carrier-local landed blobs are read here, including in CI. The
    # pinned local receipts are prerequisites for APPLY, never planning input.
    raw_plan = read_plain(repo / PLAN_PATH)
    with safe_git_environment():
        git(repo, "merge-base", "--is-ancestor", R1_MERGE, "HEAD")
        if (digest(raw_plan) != R1_RECEIPT_HASHES["plan.json"]
                or raw_plan != encoded(plan)
                or raw_plan != git(repo, "show", f"{R1_MERGE}:{PLAN_PATH}")):
            raise Hold("R1 plan differs from exact landed authority")
    for entry in entries:
        if entry["action"] == "UNTOUCHED_HOLD":
            continue
        index = entry["source_index"]
        if index not in (159, 163, 292, 305):
            raise Hold("Reconciliation is outside the four observed outcomes")
        entry.update(
            destination=str(RECONCILE_OPERATION_ROOT / str(index) / "worktree"),
            action_time_head=R1_MERGE if index == 292 else entry["source_identity"]["HEAD"],
            r1_outcome=dict(status="INCOMPLETE" if index == 292 else "HOLD",
                            prepared_head=None, boundary=None,
                            preparation_started=index == 292,
                            terminal_action_started=False))
    plan.update(wave_id=RECONCILE_WAVE_ID, operation_root=str(RECONCILE_OPERATION_ROOT),
                r1_authority=dict(wave_id=WAVE_ID, merge_commit=R1_MERGE,
                                  plan_path=str(PLAN_PATH), operation_root=str(OPERATION_ROOT),
                                  metadata_sha256=dict(R1_RECEIPT_HASHES)),
                postmerge_command=postmerge_command(reconcile_r1=True))
    return plan


def postmerge_command(*, reconcile_r1: bool = False) -> str:
    return ("PYTHONDONTWRITEBYTECODE=1 python3 " + str(TOOL_PATH)
            + " --classification " + str(CLASSIFICATION_PATH)
            + " --classification-sha256 " + CLASSIFICATION_SHA256
            + " --classification-commit " + CLASSIFICATION_COMMIT
            + (" --reconcile-r1" if reconcile_r1 else "")
            + " --plan-output " + str(RECONCILE_PLAN_PATH if reconcile_r1 else PLAN_PATH)
            + " --apply --operation-root "
            + shlex.quote(str(RECONCILE_OPERATION_ROOT if reconcile_r1 else OPERATION_ROOT)))


def require_landed(repo: Path, plan: dict) -> str:
    plan_path = RECONCILE_PLAN_PATH if plan["wave_id"] == RECONCILE_WAVE_ID else PLAN_PATH
    if SCRIPT_PATH != repo / TOOL_PATH:
        raise Hold("Apply must execute the landed carrier tool")
    if (repo / line(git(repo, "rev-parse", "--git-common-dir"))).resolve() != COMMON_DIR:
        raise Hold("Carrier common repository differs from the fixed targets")
    git(repo, "fetch", "origin", "dev")
    landed = line(git(repo, "rev-parse", "origin/dev"))
    git(repo, "merge-base", "--is-ancestor", CLASSIFICATION_COMMIT, landed)
    git(repo, "merge-base", "--is-ancestor", "HEAD", landed)
    for path in (TOOL_PATH, TEST_PATH, PLAN_PATH, plan_path,
                 Path("mu/tools/executors/commit_executor.py"),
                 Path("mu/tools/executors/executor_common.py")):
        if read_plain(repo / path) != git(repo, "show", f"{landed}:{path}"):
            raise Hold(f"Unlanded or modified apply authority: {path}")
    if read_plain(repo / plan_path) != encoded(plan):
        raise Hold("Landed plan differs from the fixed operation")
    return landed


def inspect_identity(ident: dict, *, path: Path | None = None, head: str | None = None) -> None:
    target = path if path is not None else Path(ident["path"])
    common, admin = Path(ident["common_dir"]), Path(ident["git_dir"])
    for directory in (target, common, admin):
        plain_directory(directory)
    if "filesystem_identity" in ident:
        info = target.lstat()
        if ident["filesystem_identity"] != dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode):
            raise Hold("Target filesystem identity drift")
    if (line(git(target, "rev-parse", "--show-toplevel")) != str(target)
            or line(git(target, "rev-parse", "--absolute-git-dir")) != str(admin)
            or (target / line(git(target, "rev-parse", "--git-common-dir"))).resolve() != common
            or line(git(target, "symbolic-ref", "HEAD")) != ident["branch"]
            or line(git(target, "rev-parse", "HEAD")) != (head or ident["HEAD"])
            or read_plain(target / ".git").strip() != b"gitdir: " + os.fsencode(admin)
            or read_plain(admin / "gitdir").strip() != os.fsencode(target / ".git")
            or (admin / line(read_plain(admin / "commondir"))).resolve() != common):
        raise Hold("Source HEAD/branch/path/Git/common-dir identity drift")
    registrations = []
    for block in os.fsdecode(git(target, "worktree", "list", "--porcelain")).split("\n\n"):
        record = dict(item.split(" ", 1) if " " in item else (item, "")
                      for item in block.splitlines())
        if record.get("worktree") == str(target):
            registrations.append(record)
    if registrations != [dict(worktree=str(target), HEAD=head or ident["HEAD"], branch=ident["branch"])]:
        raise Hold("Missing, locked, prunable or drifted registration")
    for root, names in ((admin, ("index.lock", "HEAD.lock", "locked", "MERGE_HEAD",
                                "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD")),
                        (common, ("config.lock", "packed-refs.lock", "shallow", "info/grafts"))):
        if any(os.path.lexists(root / name) for name in names):
            raise Hold("Git operation, lock or incomplete history present")


def clean_state(target: Path, *, allow_wip: bool = False) -> set[str]:
    filters = git(target, "config", "--name-only", "--get-regexp",
                  r"^filter\..*\.(clean|smudge|process)$", allowed=(0, 1))
    if filters:
        raise Hold("Configured filters make content inspection/preparation unsafe")
    stages = git(target, "ls-files", "--stage", "-z").split(b"\0")
    if any(r and (r.startswith(b"160000 ") or r.split(b"\t", 1)[0].split()[-1] != b"0")
           for r in stages):
        raise Hold("Submodule or unmerged index is ineligible")
    flags = git(target, "ls-files", "-v", "-z").split(b"\0")
    if any(r and r[:1] != b"H" for r in flags):
        raise Hold("Index flags hide action-time tracked state")
    status = git(target, "status", "--porcelain=v1", "-z", "--untracked-files=all",
                 "--ignored", "--ignore-submodules=all")
    if not allow_wip and any(r and not r.startswith(b"!! ") for r in status.split(b"\0")):
        raise Hold("Dirty tracked/untracked or unmerged worktree")
    return {os.fsdecode(r.split(b"\t", 1)[1]) for r in stages if r}


def tree_manifest(root: Path) -> dict:
    """Byte/mode accounting without following symlinks or executing filters."""
    plain_directory(root)
    result = {}

    def visit(path: Path, rel: str) -> None:
        info = path.lstat()
        record = {"mode": stat.S_IMODE(info.st_mode)}
        if stat.S_ISDIR(info.st_mode):
            if info.st_dev != root.stat().st_dev:
                raise Hold("Nested mount cannot be safely relocated")
            record["kind"] = "directory"
            result[rel] = record
            with os.scandir(path) as children:
                names = sorted(child.name for child in children)
            for name in names:
                visit(path / name, name if rel == "." else rel + "/" + name)
        elif stat.S_ISLNK(info.st_mode):
            record.update(kind="symlink", target=os.readlink(path))
        elif stat.S_ISREG(info.st_mode):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                if stable_stat(os.fstat(stream.fileno())) != stable_stat(info):
                    raise Hold("Content identity changed during accounting")
                h = hashlib.sha256()
                while chunk := stream.read(1024 * 1024):
                    h.update(chunk)
                if stable_stat(os.fstat(stream.fileno())) != stable_stat(info):
                    raise Hold("Content changed during accounting")
            record.update(kind="file", size=info.st_size, sha256=h.hexdigest())
        else:
            raise Hold(f"Unreadable or special content: {root / rel}; owner must resolve this exact entry before a fresh preservation operation")
        result[rel] = record

    visit(root, ".")
    return result


def preserve_archive(root: Path, output: Path, manifest: dict) -> None:
    # O_EXCL also prevents tarfile from replacing an unrelated artifact.
    with output.open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w", dereference=False) as archive:
            archive.add(root, arcname=".", recursive=True)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(output.parent)
    verify_archive(output, manifest)
    if tree_manifest(root) != manifest:
        raise Hold("Preservation archive/source verification failed")


def verify_archive(path: Path, manifest: dict) -> None:
    """Verify archived bytes/modes without extracting or following links."""
    plain_directory(path.parent)
    observed = {}
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Hold("Preservation archive is not a single-link regular file")
        with tarfile.open(fileobj=source, mode="r") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                entry = {"mode": member.mode}
                if member.isdir():
                    entry["kind"] = "directory"
                elif member.issym():
                    entry.update(kind="symlink", target=member.linkname)
                elif member.isfile() or member.islnk():
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise Hold("Archive member is unreadable")
                    h, size = hashlib.sha256(), 0
                    with stream:
                        while chunk := stream.read(1024 * 1024):
                            h.update(chunk)
                            size += len(chunk)
                    entry.update(kind="file", size=size, sha256=h.hexdigest())
                else:
                    raise Hold("Unsupported preservation archive entry")
                if name in observed:
                    raise Hold("Duplicate preservation archive entry")
                observed[name] = entry
        if stable_stat(os.fstat(source.fileno())) != stable_stat(info):
            raise Hold("Preservation archive changed during verification")
    if observed != manifest:
        raise Hold("Preservation archive/manifest verification failed")


def read_r1_receipts(repo: Path) -> dict:
    """Exact consumed receipt shape; any added stage also refuses follow-up."""
    plain_directory(OPERATION_ROOT)
    expected_root = {"intent.json", "plan.json", "summary.json", "159", "163", "292", "305"}
    if {p.name for p in OPERATION_ROOT.iterdir()} != expected_root:
        raise Hold("R1 operation contents changed or a prior terminal action started")
    receipts = {}
    for name, expected_hash in R1_RECEIPT_HASHES.items():
        raw = read_plain(OPERATION_ROOT / name)
        if digest(raw) != expected_hash:
            raise Hold(f"R1 receipt SHA-256 changed: {name}")
        receipts[name] = json.loads(raw)
    old_plan = build_plan(repo, repo / CLASSIFICATION_PATH, CLASSIFICATION_SHA256, CLASSIFICATION_COMMIT)
    if (receipts["plan.json"] != old_plan
            or read_plain(repo / PLAN_PATH) != encoded(old_plan)
            or git(repo, "show", f"{R1_MERGE}:{PLAN_PATH}") != encoded(old_plan)):
        raise Hold("R1 receipt plan contradicts landed classification/plan authority")
    intent = dict(wave_id=WAVE_ID, state="OPERATION_STARTED_OUTCOME_UNKNOWN", landed=R1_MERGE,
                  plan_sha256=R1_RECEIPT_HASHES["plan.json"], operation_root=str(OPERATION_ROOT))
    if (receipts["intent.json"] != intent
            or read_plain(COMMON_DIR / f"rcx_fleet_apply_{WAVE_ID}.json") != encoded(intent)):
        raise Hold("R1 consumed common-directory claim changed")
    outcomes = []
    for entry in old_plan["entries"]:
        if entry["action"] == "UNTOUCHED_HOLD":
            continue
        index = entry["source_index"]
        directory = OPERATION_ROOT / str(index)
        plain_directory(directory)
        names = {"intent.json", "outcome.json"}
        if index == 292:
            names |= {"preparation.json", "before.json", "before.tar", "gitdir-before.json",
                      "gitdir-before.tar", "history.bundle"}
        if {p.name for p in directory.iterdir()} != names:
            raise Hold("R1 receipt stages changed or a prior terminal action started")
        if read_plain(directory / "intent.json") != encoded(entry):
            raise Hold("R1 target intent contradicts the original plan")
        outcome = dict(source_identity=entry["source_identity"], destination=entry["destination"],
                       status="INCOMPLETE" if index == 292 else "HOLD", prepared_head=None,
                       boundary=None, reason=("Open target files/processes or uncertain lsof evidence"
                                             if index == 292 else
                                             "Native ownership status is active or uncertain"))
        if receipts[f"{index}/outcome.json"] != outcome:
            raise Hold("R1 outcome contradicts the exact no-terminal-action observation")
        outcomes.append(outcome)
    summary = dict(wave_id=WAVE_ID, outcomes=outcomes, untouched_holds=407,
                   outcome_counts={"HOLD": 3, "INCOMPLETE": 1},
                   operation_outcomes_recorded=True, fleet_clean=False)
    if receipts["summary.json"] != summary:
        raise Hold("R1 summary contradicts its four recorded outcomes")
    preparation = receipts["292/preparation.json"]
    if (not isinstance(preparation, dict) or set(preparation) != {
            "state", "original", "prepared_head", "history_bundle_sha256"}
            or preparation["state"] != "PREPARATION_STARTED_OUTCOME_UNKNOWN"
            or preparation["original"] != old_plan["entries"][292]["source_identity"]
            or preparation["prepared_head"] != R1_MERGE):
        raise Hold("R1 preparation contradicts original/prepared identity")
    return receipts


def verify_r1_preservation(repo: Path) -> dict:
    receipts = read_r1_receipts(repo)
    directory = OPERATION_ROOT / "292"
    hashes = {name: file_hash(directory / name)
              for name in ("before.tar", "gitdir-before.tar", "history.bundle")}
    verify_archive(directory / "before.tar", receipts["292/before.json"])
    verify_archive(directory / "gitdir-before.tar", receipts["292/gitdir-before.json"])
    preparation = receipts["292/preparation.json"]
    bundle = directory / "history.bundle"
    if hashes["history.bundle"] != preparation["history_bundle_sha256"]:
        raise Hold("R1 preserved history bundle SHA-256 changed")
    git(repo, "bundle", "verify", str(bundle))
    ident = preparation["original"]
    if line(git(repo, "bundle", "list-heads", str(bundle))) != ident["HEAD"] + " " + ident["branch"]:
        raise Hold("R1 bundle does not preserve exactly the original branch history")
    git(repo, "merge-base", "--is-ancestor", ident["HEAD"], R1_MERGE)
    verify_r1_unchanged(repo, hashes)
    return hashes


def verify_r1_unchanged(repo: Path, preservation_hashes: dict) -> None:
    read_r1_receipts(repo)
    for name, expected in preservation_hashes.items():
        if file_hash(OPERATION_ROOT / "292" / name) != expected:
            raise Hold(f"R1 preservation changed: {name}")


def verify_r1_prepared_target(ident: dict, current: dict) -> None:
    target, admin = Path(ident["path"]), Path(ident["git_dir"])
    git(target, "merge-base", "--is-ancestor", ident["HEAD"], R1_MERGE)
    last_log = read_plain(admin / "logs/HEAD").splitlines()
    if (read_plain(admin / "ORIG_HEAD").strip() != ident["HEAD"].encode()
            or not last_log or last_log[-1].split()[:2] != [ident["HEAD"].encode(), R1_MERGE.encode()]):
        raise Hold("R1 original-to-prepared fast-forward transition is unverifiable")
    tracked = {os.fsdecode(p) for p in git(target, "ls-tree", "-r", "--name-only", "-z",
                                         ident["HEAD"]).split(b"\0") if p}
    original = json.loads(read_plain(OPERATION_ROOT / "292/before.json"))
    verify_untracked_preserved(tracked, original, current)


def verify_untracked_preserved(tracked: set[str], before: dict, after: dict) -> None:
    tracked_tree = tracked | {str(p) for name in tracked for p in Path(name).parents}
    for name, evidence in before.items():
        if name not in tracked_tree and after.get(name) != evidence:
            raise Hold("Untracked/ignored evidence changed during preparation")


def process_idle(ident: dict) -> dict:
    target = Path(ident["path"])
    branch_token = str(ident.get("branch") or "").removeprefix("refs/heads/")
    if branch_token in {"dev", "main", "master"}:
        branch_token = ""  # A common branch word does not identify a process owner.
    proc = subprocess.run(["ps", "-A", "-ww", "-o", "pid=,command="],
                          capture_output=True, timeout=30)
    if proc.returncode or proc.stderr or not proc.stdout.strip():
        raise Hold("Process evidence unavailable")
    for raw in os.fsdecode(proc.stdout).splitlines():
        parts = raw.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            raise Hold("Process evidence malformed")
        if int(parts[0]) != os.getpid() and any(value in parts[1] for value in
                tuple(v for v in (str(target), ident.get("git_dir"), branch_token) if v)):
            raise Hold("Active process references target identity")
    # +D is limited to this exact target, and includes open descendants/cwds.
    command = ["lsof", "-nP", "+D", str(target), "-FpcfatDin"]
    diagnostic = dict(probe="lsof", command=command,
                      observed_at=datetime.now(timezone.utc).isoformat())
    try:
        proc = subprocess.run(command, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        diagnostic.update(returncode=None, error=str(exc),
                          stdout=os.fsdecode(getattr(exc, "stdout", None) or b""),
                          stderr=os.fsdecode(getattr(exc, "stderr", None) or b""))
        raise Hold("Open target files/processes or uncertain lsof evidence",
                   diagnostic=diagnostic) from exc
    diagnostic.update(returncode=proc.returncode, stdout=os.fsdecode(proc.stdout),
                      stderr=os.fsdecode(proc.stderr))
    # The captured macOS probe returns 1 even with complete descriptor output.
    # Such output still needs every reader identity/content proof below; empty
    # or malformed partial records never release ownership.
    if proc.stderr or proc.returncode not in (0, 1):
        raise Hold("Open target files/processes or uncertain lsof evidence", diagnostic=diagnostic)
    if proc.stdout:
        readers = _verified_indexing_readers(proc.stdout, target)
        if not readers:
            raise Hold("Open target files/processes or uncertain lsof evidence", diagnostic=diagnostic)
        diagnostic["verified_read_only_indexers"] = readers
    elif proc.returncode != 1:
        raise Hold("Open target files/processes or uncertain lsof evidence", diagnostic=diagnostic)
    return diagnostic


def _indexer_executable(pid: int) -> bool:
    """Only the observed system indexer, from its OS executable identity."""
    proc = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, timeout=10)
    executable = os.fsdecode(proc.stdout).strip()
    return (proc.returncode == 0 and not proc.stderr and executable ==
        "/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/Metadata.framework/Versions/A/Support/mdworker_shared")


def _verified_indexing_readers(raw: bytes, target: Path) -> list[dict]:
    """Require numeric read-only regular FDs, exact inode/device and stable bytes.

    cwd/root/mappings/writers/unknown processes remain fences. A command name
    alone grants no exception. Each subsequent mutation probe repeats this.
    """
    # -F without 0 emits newline-terminated fields. Validate the whole stream
    # before accepting any reader: a process without a descriptor is incomplete
    # ownership evidence even when earlier processes have verified read-only FDs.
    if not raw.endswith(b"\n"):
        return []
    records, pid, command, current = [], None, None, None
    try:
        for field in os.fsdecode(raw).split("\n")[:-1]:
            if not field:
                return []
            key, value = field[0], field[1:]
            if key == "p":
                if ((pid is not None and current is None)
                        or not value.isascii() or not value.isdigit() or int(value) <= 0):
                    return []
                pid, command, current = int(value), None, None
            elif key == "c":
                if pid is None or command is not None or current is not None or not value:
                    return []
                command = value
            elif key == "f":
                if command is None:
                    return []
                current = dict(pid=pid, f=value)
                records.append(current)
            elif key in "atDin":
                if current is None or key in current or not value:
                    return []
                current[key] = value
            else:
                return []
        if current is None or any(set(record) != {"pid", "f", "a", "t", "D", "i", "n"}
                                  for record in records):
            return []
        trusted = {}
        verified = []
        for record in records:
            pid = record["pid"]
            if pid not in trusted:
                trusted[pid] = bool(pid and _indexer_executable(pid))
            path = Path(record["n"])
            if (not trusted[pid] or not record["f"].isdigit() or record["a"] != "r"
                    or record["t"] != "REG" or not path.is_relative_to(target)
                    or path.resolve(strict=True) != path):
                return []
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or int(record["i"]) != info.st_ino
                    or int(record["D"], 16) != info.st_dev):
                return []
            sha256 = file_hash(path)
            if stable_stat(path.lstat()) != stable_stat(info):
                return []
            verified.append(dict(pid=pid, path=str(path), device=info.st_dev,
                                 inode=info.st_ino, sha256=sha256, access="read_only"))
        return verified
    except (KeyError, TypeError, ValueError, OSError, Hold, subprocess.SubprocessError):
        return []


def _absent_pid(pid: object) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass
    return False


def native_idle(target: Path, manifest: dict, *, reconcile_r1: bool = False) -> None:
    """Contain uncertain read-only ownership evidence before target admission."""
    try:
        _read_native_ownership(target, manifest, reconcile_r1=reconcile_r1)
    except Hold:
        # Preserve specific active/ambiguous ownership reasons and diagnostics.
        raise
    except Exception as exc:
        # Metadata and OS observation are untrusted. A failed read/probe never
        # proves absence; only this read-only boundary converts ordinary faults.
        # BaseException interruptions and errors in mutation code still escape.
        raise Hold(
            f"Native ownership evidence is uncertain ({type(exc).__name__}) at {target}: {exc}"
        ) from exc


def _read_native_ownership(target: Path, manifest: dict, *, reconcile_r1: bool) -> None:
    for name, entry in manifest.items():
        # Native buses are direct lane children. A saved pytest repository or
        # archived bus is evidence, even when it contains active:true fixtures.
        # Process/file checks still cover the entire tree, including saved data.
        if not Path(name).parts or not Path(name).parts[0].startswith(".agent_bus"):
            continue
        if entry["kind"] == "symlink":
            raise Hold("Native ownership evidence points outside its recorded tree")
        path = target / name
        if path.name in ("bridge.lock", "meta_bridge.lock"):
            with path.open("rb") as stream:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    raw = stream.read().strip()
                    if raw:
                        try:
                            value = json.loads(raw)
                        except ValueError:
                            raise Hold("Native owner lock metadata is malformed") from None
                        if (not reconcile_r1 or not isinstance(value, dict)
                                or not isinstance(value.get("holder"), str)
                                or value.get("holder") not in {"bridge_supervisor", "meta_bridge_supervisor"}
                                or value.get("lock_path") != str(path)
                                or not _absent_pid(value.get("pid"))):
                            raise Hold("Native owner lock metadata remains ambiguous or live")
                        try:
                            acquired = datetime.fromisoformat(value.get("acquired_at_utc", ""))
                        except (TypeError, ValueError):
                            # Malformed persisted evidence must reach this
                            # target's HOLD receipt without aborting its peers.
                            raise Hold("Native owner lock timestamp is uncertain") from None
                        if acquired.tzinfo is None:
                            raise Hold("Native owner lock timestamp is uncertain")
                except BlockingIOError as exc:
                    raise Hold("Native owner lock is active") from exc
        if path.name == "status.json" or path.name.endswith("_status.json"):
            value = json.loads(read_plain(path))
            if not isinstance(value, dict):
                raise Hold("Native status is malformed")
            for key in ("pid", "owner_pid", "child_pid"):
                pid = value.get(key, 0)
                if type(pid) is not int or pid < 0:
                    raise Hold("Native process identity is uncertain")
                if pid:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        pass
                    else:
                        raise Hold("Native process identity remains live")
            state = str(value.get("state", value.get("status", ""))).lower()
            terminal_states = {"idle", "done", "complete", "completed", "failed", "stopped"}
            finished_schemas = {
                **{f"tier{tier}_fixed": ("success", True, False) for tier in (1, 2)},
                **{f"tier{tier}_failed": ("failed", False, False) for tier in (1, 2)},
                **{f"tier{tier}_unhandled": ("failed", False, False) for tier in (1, 2)},
                **{f"tier{tier}_exhausted": ("exhausted", False, True) for tier in (1, 2, 4)},
                "tier4_escalated": ("escalated", False, False),
                "tier3_escalated": ("escalated", False, True),
                "tier3_skipped": ("skipped", False, False),
                "tier3_no_durable_edits": ("no_durable_edits", False, True),
                "tier3_verify_pass": ("success", True, False),
                "tier3_upstream_connectivity_retryable": ("success", True, False),
                "tier3_retry_requested": ("retry_requested", True, False),
                "resolved_by_later_success": ("cleared", True, False),
            }
            if reconcile_r1 and state in finished_schemas:
                try:
                    finished = datetime.fromisoformat(value.get("finished_at", ""))
                except (TypeError, ValueError):
                    raise Hold("Native recovery finish evidence is uncertain") from None
                expected = finished_schemas[state]
                if (path.name != "recovery_status.json" or value.get("active") is not False
                        or finished.tzinfo is None or value.get("child_pid") != 0
                        or value.get("child_role") != "" or value.get("current_command") != ""
                        or value.get("outcome") != expected[0]
                        or value.get("recovered") is not expected[1]
                        or value.get("exhausted") is not expected[2]
                        or not value.get("last_action")):
                    raise Hold("Native ownership status is active or uncertain")
                terminal_states.add(state)
            if reconcile_r1 and (not state or ("state" in value and "status" in value
                                               and value["state"] != value["status"])):
                raise Hold("Native ownership status is active or uncertain")
            if reconcile_r1 and state in {"tier3_exhausted", "tier3_short_circuited"}:
                # Only the two observed _finish_recovery_status records. No
                # inference from a state name alone, and no status-file edits.
                try:
                    finished = datetime.fromisoformat(value.get("finished_at", ""))
                except (TypeError, ValueError):
                    raise Hold("Native recovery finish evidence is uncertain") from None
                expected_outcome = ("exhausted" if state == "tier3_exhausted"
                                    else "short_circuited_non_actionable")
                if (path.name != "recovery_status.json" or value.get("state") != state
                        or value.get("status", state) != state or value.get("active") is not False
                        or finished.tzinfo is None or value.get("recovered") is not False
                        or type(value.get("exhausted")) is not bool
                        or value.get("child_pid") != 0 or value.get("child_role") != ""
                        or value.get("current_command") != "" or value.get("outcome") != expected_outcome
                        or (state == "tier3_exhausted" and (
                            value["exhausted"] is not True or value.get("last_action") != "exhausted"))
                        or (state == "tier3_short_circuited" and (
                            (value.get("last_action"), value["exhausted"])
                            not in (("escalate", True), ("skip", False))))):
                    raise Hold("Native ownership status is active or uncertain")
                terminal_states.add(state)
            if (value.get("active") is True
                    or ("active" in value and type(value["active"]) is not bool)
                    or (state and state not in terminal_states)
                    or (value.get("active") is not False and state not in terminal_states)):
                raise Hold("Native ownership status is active or uncertain")


def unprotected(repo: Path, ident: dict) -> None:
    sources = [read_plain(repo / "TASKS.md"), git(repo, "show", "origin/dev:TASKS.md")]
    primary_tasks = Path(ident["common_dir"]).parent / "TASKS.md"
    if primary_tasks != repo / "TASKS.md":
        sources.append(read_plain(primary_tasks))
    tokens = (ident["path"], Path(ident["path"]).name, ident["HEAD"],
              ident["branch"].removeprefix("refs/heads/"))
    classification_row = "| `" + Path(ident["path"]).name + "` | CONDITIONAL_RETIRE_CANDIDATE |"
    for raw in sources:
        text = raw.decode("utf-8")
        if "[FLEET-CLEANUP-APPLY]" not in text:
            raise Hold("TASKS does not retain the bounded apply authorization")
        for task_line in text.splitlines():
            # The exact existing classification row records candidacy only.
            # No other mention (including an edited row) releases protection.
            if task_line.strip() != classification_row and any(token in task_line for token in tokens):
                raise Hold("TASKS retains an exact target identity; protection is not disproved")


def inspect_target(repo: Path, ident: dict, *, head: str | None = None,
                   reconcile_r1: bool = False, process_checks: list | None = None,
                   residual: bool = False) -> tuple[set[str], dict]:
    inspect_identity(ident, head=head)
    target = Path(ident["path"])
    tracked = clean_state(target, allow_wip=residual)
    if residual:
        if target == repo or target == Path(ident["common_dir"]).parent:
            raise Hold("Active carrier and PRIMARY are protected")
    else:
        unprotected(repo, ident)
    manifest = tree_manifest(target)
    native_idle(target, manifest, reconcile_r1=reconcile_r1 or residual)
    try:
        diagnostic = process_idle(ident)
    except Hold as exc:
        if process_checks is not None and exc.diagnostic is not None:
            process_checks.append(exc.diagnostic)
        raise
    if process_checks is not None and diagnostic is not None:
        process_checks.append(diagnostic)
    return tracked, manifest


@contextmanager
def preparation_lock(common: Path):
    path = common / "rcx_primary_worktree_sync.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+b") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Hold("Existing terminal lock is not a single-link regular file")
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def git_entries(target: Path, revision: str | None = None) -> dict:
    """Semantic index/tree entries; stat-cache and index extensions are not WIP."""
    raw = (git(target, "ls-files", "--stage", "-z") if revision is None else
           git(target, "ls-tree", "-r", "-z", revision))
    entries = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, middle, last = metadata.split()
        if (revision is None and last != b"0") or (revision is not None and middle != b"blob"):
            raise Hold("Transaction index/tree contains an unmerged or non-blob entry")
        entries[os.fsdecode(path)] = [mode.decode(), (middle if revision is None else last).decode()]
    return entries


def transaction_state(target: Path) -> dict:
    """Bind the full semantic index to the bytes read between two index probes."""
    head = line(git(target, "rev-parse", "HEAD"))
    index = git_entries(target)
    flags = os.fsdecode(git(target, "ls-files", "-v", "-z"))
    content = tree_manifest(target)
    wip = set()
    for options in (("--cached",), ()):
        wip.update(os.fsdecode(p) for p in git(target, "diff", *options, "--no-renames",
                                              "--name-only", "-z").split(b"\0") if p)
    if (index != git_entries(target) or flags != os.fsdecode(git(target, "ls-files", "-v", "-z"))
            or head != line(git(target, "rev-parse", "HEAD"))):
        raise Hold("Transaction index/HEAD changed during content accounting")
    return dict(head=head, index=index, index_flags=flags, content=content, tracked_wip=sorted(wip))


def transaction_drift(phase: str, scope, detail: str) -> None:
    raise Hold(f"Preservation transaction drift at {phase}: {detail}",
               diagnostic=dict(kind="transaction_drift", phase=phase, scope=sorted(set(scope))))


def require_transaction_state(target: Path, expected: dict, phase: str) -> dict:
    observed = transaction_state(target)
    if observed != expected:
        scope = {p for field in ("index", "content")
                 for p in set(expected[field]) | set(observed[field])
                 if expected[field].get(p) != observed[field].get(p)}
        transaction_drift(phase, scope, "admitted index/content no longer matches")
    return observed


def blob_record(target: Path, entry: list) -> tuple[dict, bytes]:
    mode, oid = entry
    content = git(target, "cat-file", "blob", oid)
    if mode == "120000":
        return dict(kind="symlink", mode=0o777, target=os.fsdecode(content)), content
    if mode not in {"100644", "100755"}:
        raise Hold("Unsupported transaction blob mode")
    return dict(kind="file", mode=int(mode, 8) & 0o777,
                size=len(content), sha256=digest(content)), content


def preserve_index_blobs(target: Path, directory: Path, admitted: dict) -> None:
    """Index-only objects need bytes of their own; a history bundle omits them."""
    head = git_entries(target, admitted["head"])
    objects = {entry[1] for path, entry in admitted["index"].items() if head.get(path) != entry}
    manifest = {}
    with (directory / "index-blobs.tar").open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for oid in sorted(objects):
                content = git(target, "cat-file", "blob", oid)
                member = tarfile.TarInfo(oid)
                member.mode, member.size = 0o600, len(content)
                archive.addfile(member, io.BytesIO(content))
                manifest[oid] = dict(kind="file", mode=0o600, size=len(content), sha256=digest(content))
        stream.flush()
        os.fsync(stream.fileno())
    write_new(directory / "index-blobs.json", encoded(manifest))
    verify_archive(directory / "index-blobs.tar", manifest)


def require_stash_binding(admitted: dict, evidence: dict) -> None:
    scope = set(admitted["tracked_wip"]) | set(evidence["content"])
    if evidence["base"] != admitted["head"] or evidence["index"] != admitted["index"]:
        scope.update(p for p in set(evidence["index"]) | set(admitted["index"])
                     if evidence["index"].get(p) != admitted["index"].get(p))
        transaction_drift("checkout-sync-stashed", scope, "native stash index differs from admission")
    if evidence["content"] != {p: admitted["content"].get(p) for p in admitted["tracked_wip"]}:
        transaction_drift("checkout-sync-stashed", scope, "native stash content differs from admission")


def prepared_transaction_state(target: Path, admitted: dict, prepared: str, sync: dict,
                               *, source_path: Path | None = None, stash_evidence: dict | None = None) -> dict:
    """Derive the permitted ff/WIP transition from admission, never from its result.

    Changed base paths take their new committed values. Non-overlapping staged
    and unstaged WIP keeps its admitted values; overlapping WIP must match the
    retained native stash, and untracked collisions must match native backups.
    """
    old_tree = git_entries(target, admitted["head"])
    new_tree = git_entries(target, prepared)
    changed = {p for p in set(old_tree) | set(new_tree) if old_tree.get(p) != new_tree.get(p)}
    wip = set(admitted["tracked_wip"])
    if prepared != admitted["head"]:
        sync_wip = set(sync.get("tracked_wip_paths", []))
        if sync_wip != wip or set(sync.get("tracked_wip_held_paths", [])) != wip & changed:
            transaction_drift("checkout-sync", wip | sync_wip, "native WIP partition changed")
        if wip:
            stash = sync.get("tracked_wip_stash_oid")
            if not stash_evidence or stash_evidence["oid"] != stash:
                transaction_drift("checkout-sync", wip, "native stash preservation evidence missing")
            require_stash_binding(admitted, stash_evidence)
            # Native sync may finish its own temporary stash after restoration.
            # Overlapping WIP remains held; its live stash must still be present.
            if wip & changed and stash.encode() not in git(target, "stash", "list", "--format=%H").splitlines():
                transaction_drift("checkout-sync", wip & changed, "held overlap stash is no longer retained")
        collisions = set(sync.get("untracked_collision_paths", []))
        for path in collisions:
            if path in old_tree or path in admitted["index"] or path not in changed:
                transaction_drift("checkout-sync", [path], "unadmitted collision")
        backups = sync.get("untracked_wip_backup_paths", [])
        if len(backups) != len(collisions):
            transaction_drift("checkout-sync", collisions, "collision backup evidence missing")
        for path in collisions:
            matches = [Path(p) for p in backups if str(p).endswith("/backup/" + path)]
            if len(matches) != 1 or tree_manifest(matches[0].parent).get(matches[0].name) != admitted["content"].get(path):
                transaction_drift("checkout-sync", [path], "collision backup differs from admission")

    expected = json.loads(encoded(admitted))
    expected["head"] = prepared
    expected["tracked_wip"] = sorted(wip - changed)
    for path in changed:
        if path in new_tree:
            expected["index"][path] = new_tree[path]
            expected["content"][path] = blob_record(target, new_tree[path])[0]
        else:
            expected["index"].pop(path, None)
            expected["content"].pop(path, None)
    expected["index_flags"] = "".join("H " + p + "\0" for p in sorted(expected["index"], key=os.fsencode))
    # Git creates/removes parents of changed tracked paths. Every surviving
    # original directory retains its mode; unrelated empty directories remain.
    parents = {str(parent) for p in changed for parent in Path(p).parents if str(parent) != "."}
    for path in sorted(parents, key=lambda p: len(Path(p).parts), reverse=True):
        children = any(p.startswith(path + "/") for p in expected["content"])
        if children:
            expected["content"].setdefault(path, dict(kind="directory", mode=0o755))
        elif expected["content"].get(path, {}).get("kind") == "directory":
            expected["content"].pop(path)
    if sync.get("behind_dev_signal_cleared"):
        signal = Path(sync["behind_dev_signal_path"])
        relative = signal.relative_to(source_path or target).as_posix()
        if len(Path(relative).parts) != 2 or not relative.startswith(".agent_bus") or signal.name != "behind_dev.json":
            transaction_drift("checkout-sync", [relative], "unexpected native signal removal")
        expected["content"].pop(relative, None)
    return expected


def apply_target(repo: Path, entry: dict, directory: Path, boundary,
                 *, r1_preservation: dict | None = None, residual: bool = False) -> dict:
    ident = entry["source_identity"]
    target, destination = Path(ident["path"]), Path(entry["destination"])
    outcome = dict(source_identity=ident, destination=str(destination), status="HOLD",
                   reason=None, prepared_head=None, boundary=None)
    starting_head = entry.get("action_time_head", ident["HEAD"])
    reconcile_r1 = r1_preservation is not None
    process_checks = [] if residual else None
    if r1_preservation is not None:
        process_checks = []
        outcome.update(action_time_head=starting_head, r1_outcome=entry["r1_outcome"],
                       process_checks=process_checks, residual=residual)
    if residual:
        outcome.update(owner=entry["owner"], process_checks=process_checks, residual=residual)
        if entry.get("landing_owner"):
            outcome["landing_owner"] = {**entry["landing_owner"], "retained_path": str(target)}
    preparation_started = False
    move_started = False
    preserved = {}
    admitted = None
    prepared_state = None
    stash_evidence = None
    phase = "admission"
    if residual:
        outcome["transaction_checks"] = []
        outcome["preservation_sha256"] = preserved

    def check_transaction(expected: dict, stage: str, path: Path = target):
        nonlocal phase
        phase = stage
        observed = require_transaction_state(path, expected, stage)
        outcome["transaction_checks"].append(dict(phase=stage, state_sha256=digest(encoded(observed))))
        return observed

    def check_preservation():
        if reconcile_r1:
            verify_r1_unchanged(repo, r1_preservation)
        if reconcile_r1 or residual:
            if any(file_hash(directory / name) != expected for name, expected in preserved.items()):
                raise Hold("Current preservation changed before mutation")

    def pin_preservation(*names):
        for name in names:
            actual = file_hash(directory / name)
            if name in preserved and preserved[name] != actual:
                raise Hold("Current preservation changed before mutation")
            preserved[name] = actual

    try:
        with preparation_lock(Path(ident["common_dir"])):
            check_preservation()
            tracked, before = inspect_target(repo, ident, head=starting_head,
                                             reconcile_r1=reconcile_r1, process_checks=process_checks, residual=residual)
            if residual:
                admitted = transaction_state(target)
                if admitted["head"] != starting_head or admitted["content"] != before:
                    transaction_drift(phase, admitted["index"], "source changed during admission")
            if entry.get("useful_work") is not None:
                try:
                    from .workingrcx_fleet_census import useful_work
                except ImportError:
                    from workingrcx_fleet_census import useful_work
                observed_useful = useful_work(str(target), entry["comparison_commit"])
                # JSON normalizes tuple-valued blob identities to arrays.
                if encoded(observed_useful) != encoded(entry["useful_work"]):
                    transaction_drift(phase, [c["path"] for c in observed_useful.get("changes", [])],
                                      "useful-work/index identity changed since the committed inventory")
                if entry.get("landing_owner"):
                    outcome["landing_owner"] = {**entry["landing_owner"],
                        "preserved_at": str(directory), "destination": str(destination),
                        "original_index_archive": str(directory / "gitdir-before.tar"),
                        "original_bytes_archive": str(directory / "before.tar"),
                        "history_bundle": str(directory / "history.bundle")}
            if residual:
                check_transaction(admitted, "admission")
                write_new(directory / "admitted-state.json", encoded(admitted))
                pin_preservation("admitted-state.json")
            if r1_preservation is not None and entry["source_index"] == 292:
                verify_r1_prepared_target(ident, before)
            if target.stat().st_dev != directory.stat().st_dev:
                raise Hold("Preservation destination is not on the source filesystem")
            git(target, "merge-base", "--is-ancestor", ident["HEAD"],
                entry["comparison_commit"] if residual else CLASSIFICATION_COMMIT)
            write_new(directory / "before.json", encoded(before))
            preserve_archive(target, directory / "before.tar", before)
            if residual:
                pin_preservation("before.json", "before.tar")
                check_transaction(admitted, "after-before.tar")
            admin = Path(ident["git_dir"])
            admin_before = tree_manifest(admin)
            write_new(directory / "gitdir-before.json", encoded(admin_before))
            preserve_archive(admin, directory / "gitdir-before.tar", admin_before)
            if residual:
                pin_preservation("gitdir-before.json", "gitdir-before.tar")
                check_transaction(admitted, "after-gitdir-before.tar")
                preserve_index_blobs(target, directory, admitted)
                pin_preservation("index-blobs.json", "index-blobs.tar")
                check_transaction(admitted, "after-index-blobs.tar")
            bundle = directory / "history.bundle"
            if residual:
                refs_before = git(target, "show-ref")
                stashes_before = git(target, "stash", "list", "--format=%H").splitlines()
                write_new(directory / "refs-before.txt", refs_before)
                write_new(directory / "stashes-before.json", encoded([line(v) for v in stashes_before]))
                git(target, "bundle", "create", str(bundle), "--all", "--reflog")
            else:
                git(target, "bundle", "create", str(bundle), ident["branch"])
            with bundle.open("rb") as stream:
                os.fsync(stream.fileno())
            sync_directory(directory)
            git(target, "bundle", "verify", str(bundle))
            if line(git(target, "bundle", "list-heads", str(bundle), ident["branch"])) != (
                    starting_head + " " + ident["branch"]):
                raise Hold("Original branch history was not preserved")
            if reconcile_r1 or residual:
                pin_preservation("before.json", "before.tar", "gitdir-before.json", "gitdir-before.tar", "history.bundle")
                if residual:
                    pin_preservation("admitted-state.json", "index-blobs.json", "index-blobs.tar",
                                     "refs-before.txt", "stashes-before.json")
                    check_transaction(admitted, "after-history.bundle")
                outcome["preservation_sha256"] = preserved
            # Preserve admin evidence (including any old FETCH_HEAD) before
            # the first target fetch, as well as before the fast-forward.
            git(target, "fetch", "origin", "dev")
            prepared = line(git(target, "rev-parse", "origin/dev"))
            git(target, "merge-base", "--is-ancestor", starting_head, prepared)
            _, check = inspect_target(repo, ident, head=starting_head,
                                      reconcile_r1=reconcile_r1, process_checks=process_checks, residual=residual)
            if check != before:
                raise Hold("Source changed while preservation was being verified")
            if residual:
                check_transaction(admitted, "before-preparation")
            check_preservation()
            preparation = dict(
                state="PREPARATION_STARTED_OUTCOME_UNKNOWN", original=ident,
                prepared_head=prepared, history_bundle_sha256=file_hash(bundle))
            if r1_preservation is not None:
                preparation["action_time_head"] = starting_head
            write_new(directory / "preparation.json", encoded(preparation))
            preparation_started = True
            # Legacy clean preparation is unchanged. Fresh residuals use the
            # native transaction with an explicit target, never default PRIMARY.
            if not residual:
                git(target, "merge", "--ff-only", "--no-overwrite-ignore", prepared)
        if residual:
            preparation_binding = boundary.bind_terminal_target_identity(target, base_branch="dev")
            if (preparation_binding.get("expected_head") != starting_head
                    or preparation_binding.get("expected_branch") != ident["branch"].removeprefix("refs/heads/")):
                raise Hold("Original checkout identity changed before safe preparation")
            check_transaction(admitted, "before-checkout-sync")

            def preparation_checkpoint(stage, _manifest):
                nonlocal stash_evidence, phase
                # This existing callback runs under the native sync lock before
                # stash creation, closing the lock handoff admission window.
                if stage == "after_prepared":
                    check_transaction(admitted, "checkout-sync-prepared")
                elif stage == "after_stash_before_publish":
                    phase = "checkout-sync-stashed"
                    oid = _manifest["stash_oid"]
                    stash_tree = git_entries(target, oid)
                    stash_evidence = dict(oid=oid, base=line(git(target, "rev-parse", oid + "^1")),
                        index=git_entries(target, oid + "^2"),
                        content={p: blob_record(target, stash_tree[p])[0] if p in stash_tree else None
                                 for p in _manifest["tracked_paths"]})
                    write_new(directory / "sync-stash.json", encoded(stash_evidence))
                    bundle = directory / "sync-stash.bundle"
                    git(target, "bundle", "create", str(bundle), "refs/stash")
                    with bundle.open("rb") as stream:
                        os.fsync(stream.fileno())
                    sync_directory(directory)
                    git(target, "bundle", "verify", str(bundle))
                    if line(git(target, "bundle", "list-heads", str(bundle))) != oid + " refs/stash":
                        transaction_drift(phase, _manifest["tracked_paths"], "native stash history changed during preservation")
                    pin_preservation("sync-stash.json", "sync-stash.bundle")
                    check_preservation()
                    require_stash_binding(admitted, stash_evidence)

            sync = boundary.sync_primary_worktree_to_base(
                repo, "dev", target_identity=preparation_binding, log=lambda _message: None,
                checkpoint=preparation_checkpoint)
            outcome["checkout_sync"] = sync
            write_new(directory / "checkout-sync.json", encoded(sync))
            if (line(git(target, "rev-parse", "HEAD")) != prepared or sync.get("recovery_hold")
                    or not (sync.get("synced") is True or
                            str(sync.get("reason") or "").startswith("primary worktree already current"))):
                raise Hold("Preservation-safe checkout sync did not reach a verified outcome")
            if not set(stashes_before).issubset(git(target, "stash", "list", "--format=%H").splitlines()):
                raise Hold("An existing held stash is no longer retained")
            phase = "checkout-sync"
            prepared_state = prepared_transaction_state(target, admitted, prepared, sync, stash_evidence=stash_evidence)
            check_transaction(prepared_state, "after-checkout-sync")
        with preparation_lock(Path(ident["common_dir"])):
            _, after = inspect_target(repo, ident, head=prepared,
                                      reconcile_r1=reconcile_r1, process_checks=process_checks, residual=residual)
            held_collisions = set(outcome.get("checkout_sync", {}).get("untracked_collision_paths", []))
            verify_untracked_preserved(tracked | held_collisions, before, after)
            git(target, "merge-base", "--is-ancestor", ident["HEAD"], prepared)
            write_new(directory / "prepared.json", encoded(after))
            outcome["prepared_head"] = prepared
            if residual:
                check_transaction(prepared_state, "prepared")
                write_new(directory / "prepared-state.json", encoded(prepared_state))
                pin_preservation("prepared-state.json")
        binding = boundary.bind_terminal_target_identity(target, base_branch="dev")
        write_new(directory / "terminal-identity.json", encoded(binding))
        if (binding.get("bound") is not True or binding.get("expected_head") != prepared
                or binding.get("expected_branch") != ident["branch"].removeprefix("refs/heads/")
                or binding.get("worktree_identity", {}).get("path") != str(target)):
            raise Hold("Existing API cannot bind the exact prepared target")

        def move_once():
            nonlocal move_started
            # Called only after the existing boundary's fresh fetch and
            # behind-zero proof, continuously under its common-directory lock.
            check_preservation()
            _, fresh = inspect_target(repo, ident, head=prepared,
                                      reconcile_r1=reconcile_r1, process_checks=process_checks, residual=residual)
            if fresh != after or os.path.lexists(destination):
                raise Hold("Prepared content or destination drifted before move")
            if residual:
                check_transaction(prepared_state, "before-terminal-move")
            write_new(directory / "move-started.json", encoded(dict(
                state="TERMINAL_MOVE_STARTED_OUTCOME_UNKNOWN", target_identity=binding)))
            if residual:
                check_transaction(prepared_state, "terminal-move-started")
            move_started = True
            sync_only = residual and entry["action"] == "SYNC_LOCAL_DEV"
            if not sync_only:
                git(repo, "worktree", "move", str(target), str(destination))
                sync_directory(target.parent)
                sync_directory(destination.parent)
            final_path = target if sync_only else destination
            inspect_identity(ident, path=final_path, head=prepared)
            observed = tree_manifest(final_path)
            if (not sync_only and os.path.lexists(target)) or observed != after:
                raise Hold("Moved worktree preservation verification incomplete")
            git(final_path, "merge-base", "--is-ancestor", ident["HEAD"], "HEAD")
            write_new(directory / "after.json", encoded(observed))
            if residual:
                retired = check_transaction(prepared_state, "after-terminal-move", final_path)
                write_new(directory / "retired-state.json", encoded(retired))
                pin_preservation("retired-state.json")
            return dict(destination=str(final_path), manifest_sha256=digest(encoded(observed)))

        result = boundary.execute_terminal_mutation_once(
            repo, binding, terminal_action=move_once, log=lambda _message: None)
        outcome["boundary"] = result
        if result.get("action_succeeded") is True:
            if residual:
                check_preservation()
                check_transaction(prepared_state, "after-terminal-boundary",
                                  target if entry["action"] == "SYNC_LOCAL_DEV" else destination)
            outcome["status"] = "SYNCED_LOCAL_DEV" if residual and entry["action"] == "SYNC_LOCAL_DEV" else "MOVED"
        elif move_started:
            outcome.update(status="INCOMPLETE", reason=result.get("reason"))
        else:
            outcome["reason"] = result.get("reason") or "Terminal boundary HOLD"
    except (Hold, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as exc:
        incomplete = move_started or (preparation_started and outcome["prepared_head"] is None)
        outcome.update(status="INCOMPLETE" if incomplete else "HOLD", reason=str(exc))
    if residual and outcome["status"] in {"HOLD", "INCOMPLETE"}:
        if admitted is not None:
            # The boundary may catch our callback exception. Always retain an
            # explicit landing obligation once an admitted transaction stops,
            # including drift discovered after the directory was moved.
            retained = destination if move_started and destination.is_dir() else target
            try:
                observed = transaction_state(retained)
                expected = prepared_state or admitted
                scope = {p for field in ("index", "content")
                         for p in set(expected[field]) | set(observed[field])
                         if expected[field].get(p) != observed[field].get(p)}
                write_new(directory / "unresolved-state.json", encoded(observed))
            except (Hold, OSError, ValueError, subprocess.SubprocessError) as exc:
                scope = set()
                outcome["unresolved_inventory_error"] = str(exc)
            scope.update(admitted["tracked_wip"])
            scope.update(outcome.get("checkout_sync", {}).get("tracked_wip_paths", []))
            if stash_evidence:
                scope.update(p for p in set(stash_evidence["index"]) | set(admitted["index"])
                             if stash_evidence["index"].get(p) != admitted["index"].get(p))
            original_owner = entry.get("landing_owner") or {}
            outcome["landing_owner"] = {**original_owner,
                "task": "FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION",
                "wave_id": original_owner.get("wave_id") or "fleet-transaction-drift-" + digest(os.fsencode(directory))[:20],
                "status": "UNRESOLVED_TRANSACTION_DRIFT", "phase": phase,
                "source_path": str(target), "retained_path": str(retained),
                "source_head": starting_head, "source_branch": ident["branch"],
                "comparison_commit": entry["comparison_commit"],
                "scope": sorted(scope | set(original_owner.get("scope", []))),
                "admitted_landing_owner": entry.get("landing_owner"),
                "preserved_at": str(directory), "live_index": ident["git_dir"] + "/index",
                "next_action": "Compare admitted, preserved, native stash/backup and retained index/content to dev; land missing hunks through fresh native authority before resolving this owner."}
        outcome["next_action"] = (
            f"Owner {outcome.get('owner', '[FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]')} must resolve "
            f"the exact target {target}: {outcome.get('reason')}. Verify {directory} before "
            "preparing fresh committed operation authority; this operation cannot be replayed.")
    write_new(directory / "outcome.json", encoded(outcome))
    return outcome


def apply_plan(repo: Path, plan: dict, *, reconcile_r1: bool = False) -> dict:
    # No caller-supplied plan can broaden the fixed targets or destinations.
    expected = build_plan(repo, repo / CLASSIFICATION_PATH, CLASSIFICATION_SHA256,
                          CLASSIFICATION_COMMIT, reconcile_r1=reconcile_r1)
    if plan != expected:
        raise Hold("Apply plan does not match its pinned classification")
    with safe_git_environment(network=True):
        landed = require_landed(repo, plan)
        operation_root = RECONCILE_OPERATION_ROOT if reconcile_r1 else OPERATION_ROOT
        wave_id = RECONCILE_WAVE_ID if reconcile_r1 else WAVE_ID
        plain_directory(operation_root.parent)
        plain_directory(COMMON_DIR)
        for entry in plan["entries"]:
            source = Path(entry["path"])
            if operation_root == source or source in operation_root.parents:
                raise Hold("Preservation output lies inside a source target")
        if os.path.lexists(operation_root):
            raise Hold("Operation already consumed or ambiguous; inspect local receipts, never replay")
        r1_preservation = verify_r1_preservation(repo) if reconcile_r1 else None
        intent = dict(wave_id=wave_id, state="OPERATION_STARTED_OUTCOME_UNKNOWN", landed=landed,
                      plan_sha256=digest(encoded(plan)), operation_root=str(operation_root))
        # This second fixed anchor also survives relocation of the receipt tree.
        write_new(COMMON_DIR / f"rcx_fleet_apply_{wave_id}.json", encoded(intent))
        new_directory(operation_root)
        write_new(operation_root / "intent.json", encoded(intent))
        write_new(operation_root / "plan.json", encoded(plan))
        try:
            from . import commit_executor as boundary
        except ImportError:
            import commit_executor as boundary
        outcomes = []
        for entry in plan["entries"]:
            if entry["action"] == "UNTOUCHED_HOLD":
                continue
            directory = operation_root / str(entry["source_index"])
            new_directory(directory)
            write_new(directory / "intent.json", encoded(entry))
            outcomes.append(apply_target(repo, entry, directory, boundary, r1_preservation=r1_preservation))
        summary = dict(wave_id=wave_id, outcomes=outcomes, untouched_holds=407,
                       outcome_counts=dict(Counter(o["status"] for o in outcomes)),
                       operation_outcomes_recorded=True, fleet_clean=False)
        write_new(operation_root / "summary.json", encoded(summary))
        return summary


RESIDUAL_WAVE_ID = "workingrcx-fleet-residual-completion-r1-2026-09-13"
RESIDUAL_CLASSIFICATION_PATH = Path(f"reports/control_plane/{RESIDUAL_WAVE_ID}_classification.json")
RESIDUAL_CENSUS_PATH = Path(f"reports/control_plane/{RESIDUAL_WAVE_ID}_census.json")
RESIDUAL_PLAN_PATH = Path(f"reports/control_plane/{RESIDUAL_WAVE_ID}_apply_plan.json")
RESIDUAL_ACTIONS = {"PRESERVE_WORKTREE", "PRESERVE_BUS_SHELL", "SYNC_LOCAL_DEV"}


def residual_paths(wave_id: str) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,160}", wave_id or ""):
        raise Hold("Invalid residual wave identity")
    if wave_id in {WAVE_ID, RECONCILE_WAVE_ID, "workingrcx-fleet-classification-r1-2026-09-11"}:
        raise Hold("Historical operation authority cannot be rebound as a fresh residual wave")
    return tuple(Path(f"reports/control_plane/{wave_id}_{suffix}.json")
                 for suffix in ("classification", "census", "apply_plan"))


def build_residual_plan(repo: Path, classification: Path, sha256: str,
                        *, wave_id: str = RESIDUAL_WAVE_ID) -> dict:
    """Pure manifest planning; all actions remain behind committed authority."""
    classification_path, census_path, plan_path = residual_paths(wave_id)
    fresh_wave = wave_id != RESIDUAL_WAVE_ID
    if classification.absolute() != repo / classification_path:
        raise Hold("Residual classification must use its exact wave-owned path")
    raw = read_plain(classification)
    if digest(raw) != sha256:
        raise Hold("Residual classification hash mismatch")
    data = json.loads(raw)
    census_raw = read_plain(repo / census_path)
    census = json.loads(census_raw)
    try:
        from . import workingrcx_fleet_classification as classifier
    except ImportError:
        import workingrcx_fleet_classification as classifier
    classifier._validate_inventory(census)
    if fresh_wave:
        useful_path = repo / f"reports/control_plane/{wave_id}_useful_work.json"
        if json.loads(read_plain(useful_path)) != classifier.useful_work_report(data, sha256):
            raise Hold("Fresh useful-work/landing authority does not match classification")
    if (data.get("wave_id") != wave_id or data.get("schema_version") != 1
            or data.get("coverage_complete") is not True or data.get("mutation_authorized") is not False
            or data.get("source_sha256") != digest(census_raw)
            or data.get("source_metadata") != {k: v for k, v in census.items() if k != "entries"}
            or data.get("entry_count") != census["entry_count"]
            or len(data.get("entries", [])) != census["entry_count"]
            or not classifier._oid(data.get("comparison_commit"))):
        raise Hold("Residual classification lacks complete fresh census authority")
    root = Path(census["fleet_root"])
    common = root / "WorkingRCX/.git"
    if data.get("policy", {}).get("canonical_common_dir") != str(common):
        raise Hold("Residual common-directory authority mismatch")
    selected, rows = [], []
    counts = Counter()
    for index, row in enumerate(data["entries"]):
        source = census["entries"][index]
        path = Path(source["path"])
        action = row.get("proposed_action")
        decision = row.get("decision")
        if (row.get("source_index") != index or row.get("source") != source
                or row.get("path") != str(path) or not row.get("owner")
                or row.get("mutation_authorized") is not False
                or decision not in {"HOLD", "CONDITIONAL_RETIRE_CANDIDATE"}
                or (decision == "HOLD") != (action == "UNTOUCHED_HOLD")):
            raise Hold("Residual row identity/ownership mismatch")
        counts[decision] += 1
        ident = identity_of(row)
        ident["filesystem_identity"] = source.get("filesystem_identity")
        entry = dict(source_index=index, path=str(path), source_identity=ident,
                     action=action, owner=row["owner"], comparison_commit=data["comparison_commit"],
                     reason_codes=[r["code"] for r in row["reasons"]])
        if fresh_wave:
            useful = source.get("useful_work")
            entry.update(useful_work=useful, landing_owner=row.get("landing_owner"))
            if action not in {"UNTOUCHED_HOLD", "PRESERVE_BUS_SHELL"} and (
                    not isinstance(useful, dict) or useful.get("status") == "UNKNOWN"
                    or (useful.get("status") != "COVERED" and not row.get("landing_owner"))):
                raise Hold("Fresh residual lacks exact useful-work coverage or native landing owner")
        if action != "UNTOUCHED_HOLD":
            if (action not in RESIDUAL_ACTIONS or path.parent != root
                    or not path.name.casefold().startswith("workingrcx")
                    or source.get("availability_status") != "present"
                    or source.get("entry_kind") != "directory" or source.get("errors")
                    or not isinstance(ident["filesystem_identity"], dict)
                    or str(path) in data["policy"]["protected_paths"]):
                raise Hold("Residual candidate is outside the exact bounded policy")
            if action == "PRESERVE_BUS_SHELL":
                if (source.get("bus_only_shell") is not True or source["registered_worktrees"]
                        or source["repository_kind"] != "non_repository"):
                    raise Hold("Residual shell has ambiguous repository ownership")
                entry["shell_entries"] = source["shell_entries"]
            else:
                if (source["repository_kind"] != "linked_worktree"
                        or ident["common_dir"] != str(common)
                        or Path(ident["git_dir"]).parent != common / "worktrees"
                        or row["ancestry"]["status"] != "ANCESTOR"
                        or source["registered_worktrees"] != [{k: ident[k] for k in ("path", "HEAD", "branch")}]
                        or ident["branch"] in {"refs/heads/main", "refs/heads/master"}
                        or (ident["branch"] == "refs/heads/dev") != (action == "SYNC_LOCAL_DEV")):
                    raise Hold("Residual candidate Git/history authority mismatch")
                if not fresh_wave and action == "SYNC_LOCAL_DEV" and path.name != "workingrcx_clarolesfull_20260627":
                    raise Hold("Only the explicit dev owner may use preservation-safe dev sync")
            selected.append(index)
        rows.append(entry)
    batches = [selected[i:i + 12] for i in range(0, len(selected), 12)]
    if data.get("batches") != batches or data.get("batch_size") != 12 or counts != data.get("decision_counts"):
        raise Hold("Residual batches do not account for every candidate exactly once")
    operations = []
    for number, indices in enumerate(batches, 1):
        operation_id = f"{wave_id}-{sha256[:16]}-{number:03d}"
        operation_root = root / ("fleet-apply-preserved-" + operation_id)
        operations.append(dict(batch=number, operation_id=operation_id,
                               operation_root=str(operation_root), source_indices=indices))
        for index in indices:
            rows[index]["destination"] = str(operation_root / str(index) / "worktree")
    return dict(schema_version=2, wave_id=wave_id, mutation_authorized=False,
                classification_path=str(classification_path), classification_sha256=sha256,
                census_path=str(census_path), census_sha256=digest(census_raw),
                comparison_commit=data["comparison_commit"], fleet_root=str(root), common_dir=str(common),
                entry_count=len(rows), conditional_candidates=len(selected), untouched_holds=counts["HOLD"],
                operations=operations, entries=rows,
                completion="PENDING_COMMITTED_FOREGROUND_APPLY_AND_VERIFY",
                command_template=(f"PYTHONDONTWRITEBYTECODE=1 python3 {TOOL_PATH} --residual"
                                  + (f" --wave-id {wave_id}" if fresh_wave else "")
                                  + f" --classification {classification_path} --classification-sha256 {sha256}"
                                  f" --plan-output {plan_path} --authority-commit <landed-commit>"
                                  " --batch <batch> --operation-root <exact-operation-root> --apply (then --verify)"))


def require_residual_authority(repo: Path, plan: dict, commit: str, *, fetch: bool) -> None:
    classification_path, census_path, plan_path = residual_paths(plan["wave_id"])
    if SCRIPT_PATH != repo / TOOL_PATH or re.fullmatch(r"[0-9a-f]{40}", commit or "") is None:
        raise Hold("Residual operation requires the committed native tool and exact authority commit")
    if (repo / line(git(repo, "rev-parse", "--git-common-dir"))).resolve() != Path(plan["common_dir"]):
        raise Hold("Residual carrier repository identity mismatch")
    if fetch:
        git(repo, "fetch", "origin", "dev")
    git(repo, "merge-base", "--is-ancestor", commit, "origin/dev")
    git(repo, "merge-base", "--is-ancestor", plan["comparison_commit"], commit)
    paths = (TOOL_PATH, TEST_PATH, plan_path, classification_path, census_path,
             Path("mu/tools/executors/workingrcx_fleet_census.py"),
             Path("mu/tools/executors/workingrcx_fleet_classification.py"),
             Path("mu/tools/executors/commit_executor.py"), Path("mu/tools/executors/executor_common.py"),
             Path("mu/tools/observability/pipeline_agent_pager.py"))
    if plan["wave_id"] != RESIDUAL_WAVE_ID:
        paths += (Path(f"reports/control_plane/{plan['wave_id']}_useful_work.json"),)
    for path in paths:
        committed = git(repo, "show", f"{commit}:{path}")
        if read_plain(repo / path) != committed:
            raise Hold(f"Residual authority is uncommitted or modified: {path}")
        tree = git(repo, "ls-tree", "-z", commit, "--", str(path))
        mode, _kind, rest = tree.split(b" ", 2)
        oid, name = rest.split(b"\t", 1)
        index = git(repo, "ls-files", "--stage", "-z", "--", str(path))
        if (index != mode + b" " + oid + b" 0\t" + name
                or bool((repo / path).stat().st_mode & 0o111) != (mode == b"100755")
                or git(repo, "ls-files", "-v", "-z", "--", str(path)) != b"H " + os.fsencode(path) + b"\0"):
            raise Hold(f"Residual authority index/mode identity differs from commit: {path}")
    if read_plain(repo / plan_path) != encoded(plan):
        raise Hold("Residual plan differs from committed authority")
    if fetch and (repo != Path(plan["common_dir"]).parent
                  or line(git(repo, "rev-parse", "HEAD")) != line(git(repo, "rev-parse", "origin/dev"))):
        raise Hold("Foreground apply requires separately synchronized surviving PRIMARY")


def inspect_shell(repo: Path, entry: dict) -> dict:
    target = Path(entry["path"])
    plain_directory(target)
    info = target.lstat()
    if entry["source_identity"]["filesystem_identity"] != dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode):
        raise Hold("Residual shell filesystem identity changed")
    children = sorted(p.name for p in target.iterdir())
    if children != entry["shell_entries"] or not children or any(
        not name.startswith(".agent_bus") or not (target / name).is_dir() or (target / name).is_symlink()
        for name in children
    ):
        raise Hold("Residual shell shape changed")
    try:
        from .workingrcx_fleet_census import _worktrees
    except ImportError:
        from workingrcx_fleet_census import _worktrees
    registrations, errors = _worktrees(git(repo, "worktree", "list", "--porcelain", "-z"))
    if errors or any(r["path"] == str(target) or r["path"].startswith(str(target) + "/") for r in registrations):
        raise Hold("Residual shell acquired or ambiguously owns a Git registration")
    manifest = tree_manifest(target)
    native_idle(target, manifest, reconcile_r1=True)
    process_idle(entry["source_identity"])
    return manifest


def apply_shell(repo: Path, entry: dict, directory: Path, boundary) -> dict:
    target, destination = Path(entry["path"]), Path(entry["destination"])
    outcome = dict(source_identity=entry["source_identity"], destination=str(destination),
                   owner=entry["owner"], status="HOLD", reason=None, boundary=None)
    moved = False
    try:
        before = inspect_shell(repo, entry)
        if target.stat().st_dev != directory.stat().st_dev:
            raise Hold("Shell preservation destination is on another filesystem")
        write_new(directory / "before.json", encoded(before))
        preserve_archive(target, directory / "before.tar", before)
        archive_hash = file_hash(directory / "before.tar")
        outcome["preservation_sha256"] = {name: file_hash(directory / name)
                                          for name in ("before.json", "before.tar")}
        # A shell has no Git HEAD. Bind the synchronized surviving carrier;
        # exact shell identity, bytes, registration absence and idleness are
        # rechecked inside that same consumed, fresh behind-zero callback.
        binding = boundary.bind_terminal_target_identity(repo, base_branch="dev")
        write_new(directory / "terminal-identity.json", encoded(binding))
        def move_once():
            nonlocal moved
            if (inspect_shell(repo, entry) != before or os.path.lexists(destination)
                    or file_hash(directory / "before.tar") != archive_hash):
                raise Hold("Shell/evidence/destination drift before terminal action")
            write_new(directory / "move-started.json", encoded(dict(target_identity=binding)))
            os.rename(target, destination)
            moved = True
            sync_directory(target.parent)
            sync_directory(destination.parent)
            after = tree_manifest(destination)
            if os.path.lexists(target) or after != before:
                raise Hold("Shell preservation verification incomplete")
            write_new(directory / "after.json", encoded(after))
            return dict(destination=str(destination), manifest_sha256=digest(encoded(after)))
        outcome["boundary"] = boundary.execute_terminal_mutation_once(
            repo, binding, terminal_action=move_once, log=lambda _message: None)
        if outcome["boundary"].get("action_succeeded") is True:
            outcome["status"] = "MOVED"
        else:
            outcome.update(status="INCOMPLETE" if moved else "HOLD", reason=outcome["boundary"].get("reason"))
    except (Hold, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as exc:
        outcome.update(status="INCOMPLETE" if moved else "HOLD", reason=str(exc))
    write_new(directory / "outcome.json", encoded(outcome))
    return outcome


def residual_operation(plan: dict, batch: int, operation_root: Path) -> dict:
    matches = [o for o in plan["operations"] if o["batch"] == batch]
    if len(matches) != 1 or Path(matches[0]["operation_root"]) != operation_root:
        raise Hold("Exact explicit residual batch/destination required")
    return matches[0]


def prefix_directory_count(root: Path) -> int:
    return sum(p.name.casefold().startswith("workingrcx") and p.is_dir() and not p.is_symlink()
               for p in root.iterdir())


def apply_residual_plan(repo: Path, plan: dict, *, authority_commit: str,
                        batch: int, operation_root: Path) -> dict:
    classification_path, _, _ = residual_paths(plan["wave_id"])
    expected = build_residual_plan(repo, repo / classification_path, plan["classification_sha256"], wave_id=plan["wave_id"])
    if expected != plan:
        raise Hold("Residual plan does not match fresh classification")
    operation = residual_operation(plan, batch, operation_root)
    with safe_git_environment(network=True):
        require_residual_authority(repo, plan, authority_commit, fetch=True)
        common = Path(plan["common_dir"])
        if os.path.lexists(operation_root):
            raise Hold("Residual operation consumed; inspect/verify receipts, never replay")
        intent = dict(operation=operation, plan_sha256=digest(encoded(plan)),
                      authority_commit=authority_commit, state="OPERATION_STARTED_OUTCOME_UNKNOWN")
        write_new(common / ("rcx_fleet_apply_" + operation["operation_id"] + ".json"), encoded(intent))
        new_directory(operation_root)
        write_new(operation_root / "intent.json", encoded(intent))
        write_new(operation_root / "plan.json", encoded(plan))
        before_count = prefix_directory_count(Path(plan["fleet_root"]))
        write_new(operation_root / "before-count.json", encoded(dict(prefix_directories=before_count)))
        try:
            from . import commit_executor as boundary
        except ImportError:
            import commit_executor as boundary
        outcomes = []
        for index in operation["source_indices"]:
            entry = plan["entries"][index]
            directory = operation_root / str(index)
            new_directory(directory)
            write_new(directory / "intent.json", encoded(entry))
            action = apply_shell if entry["action"] == "PRESERVE_BUS_SHELL" else apply_target
            kwargs = {} if action is apply_shell else {"residual": True}
            outcomes.append(action(repo, entry, directory, boundary, **kwargs))
        summary = dict(wave_id=plan["wave_id"], operation=operation, outcomes=outcomes,
                       outcome_counts=dict(Counter(o["status"] for o in outcomes)),
                       before_prefix_directories=before_count,
                       after_prefix_directories=prefix_directory_count(Path(plan["fleet_root"])),
                       untouched_holds=plan["untouched_holds"], fleet_clean=False)
        write_new(operation_root / "summary.json", encoded(summary))
        return summary


def verify_residual_plan(repo: Path, plan: dict, *, authority_commit: str,
                         batch: int, operation_root: Path) -> dict:
    """Re-read actual destinations and preserved bytes; never resume a mutation."""
    operation = residual_operation(plan, batch, operation_root)
    with safe_git_environment():
        require_residual_authority(repo, plan, authority_commit, fetch=False)
        intent = dict(operation=operation, plan_sha256=digest(encoded(plan)),
                      authority_commit=authority_commit, state="OPERATION_STARTED_OUTCOME_UNKNOWN")
        if (read_plain(operation_root / "intent.json") != encoded(intent)
                or read_plain(Path(plan["common_dir"]) / ("rcx_fleet_apply_" + operation["operation_id"] + ".json")) != encoded(intent)
                or read_plain(operation_root / "plan.json") != encoded(plan)):
            raise Hold("Residual consumed operation authority changed")
        summary = json.loads(read_plain(operation_root / "summary.json"))
        verified = []
        for index in operation["source_indices"]:
            entry = plan["entries"][index]
            directory = operation_root / str(index)
            if read_plain(directory / "intent.json") != encoded(entry):
                raise Hold("Residual per-target intent changed")
            outcome = json.loads(read_plain(directory / "outcome.json"))
            if outcome.get("source_identity") != entry["source_identity"] or outcome.get("owner") != entry["owner"]:
                raise Hold("Residual per-target outcome identity changed")
            if outcome["status"] in {"MOVED", "SYNCED_LOCAL_DEV"}:
                target = Path(entry["path"])
                destination = target if outcome["status"] == "SYNCED_LOCAL_DEV" else Path(entry["destination"])
                if outcome["status"] == "MOVED" and os.path.lexists(target):
                    raise Hold("Retired source exists again")
                if outcome.get("boundary", {}).get("action_succeeded") is not True:
                    raise Hold("Residual successful outcome lacks terminal-boundary evidence")
                before = json.loads(read_plain(directory / "before.json"))
                verify_archive(directory / "before.tar", before)
                after = json.loads(read_plain(directory / "after.json"))
                for name, expected_hash in outcome["preservation_sha256"].items():
                    if file_hash(directory / name) != expected_hash:
                        raise Hold("Residual preservation artifact changed")
                if outcome["boundary"].get("action_outcome", {}).get("manifest_sha256") != digest(encoded(after)):
                    raise Hold("Residual terminal manifest receipt changed")
                if tree_manifest(destination) != after:
                    raise Hold("Residual destination bytes changed")
                if entry["action"] != "PRESERVE_BUS_SHELL":
                    inspect_identity(entry["source_identity"], path=destination, head=outcome["prepared_head"])
                    verify_archive(directory / "gitdir-before.tar", json.loads(read_plain(directory / "gitdir-before.json")))
                    git(repo, "bundle", "verify", str(directory / "history.bundle"))
                    held = json.loads(read_plain(directory / "stashes-before.json"))
                    if not set(held).issubset(git(repo, "stash", "list", "--format=%H").decode().splitlines()):
                        raise Hold("Previously held stash is no longer retained")
                    if entry.get("useful_work") is not None:
                        required = {"admitted-state.json", "prepared-state.json", "retired-state.json",
                                    "index-blobs.json", "index-blobs.tar"}
                        if not required <= outcome["preservation_sha256"].keys():
                            raise Hold("Residual success lacks preservation transaction binding")
                        admitted = json.loads(read_plain(directory / "admitted-state.json"))
                        prepared_state = json.loads(read_plain(directory / "prepared-state.json"))
                        retired_state = json.loads(read_plain(directory / "retired-state.json"))
                        stash_evidence = None
                        if admitted["tracked_wip"] and admitted["head"] != outcome["prepared_head"]:
                            if not {"sync-stash.json", "sync-stash.bundle"} <= outcome["preservation_sha256"].keys():
                                raise Hold("Residual success lacks native stash preservation")
                            stash_evidence = json.loads(read_plain(directory / "sync-stash.json"))
                            bundle = directory / "sync-stash.bundle"
                            git(repo, "bundle", "verify", str(bundle))
                            if line(git(repo, "bundle", "list-heads", str(bundle))) != stash_evidence["oid"] + " refs/stash":
                                raise Hold("Residual native stash history differs from its receipt")
                        expected = prepared_transaction_state(destination, admitted, outcome["prepared_head"],
                            outcome["checkout_sync"], source_path=target, stash_evidence=stash_evidence)
                        if (admitted["content"] != before or admitted["head"] != entry["source_identity"]["HEAD"]
                                or prepared_state != expected or retired_state != expected
                                or retired_state["content"] != after):
                            raise Hold("Residual preservation transaction receipts disagree")
                        require_transaction_state(destination, retired_state, "verification")
                        verify_archive(directory / "index-blobs.tar", json.loads(read_plain(directory / "index-blobs.json")))
                        if any(outcome.get("landing_owner", {}).get(k) != v
                               for k, v in (entry.get("landing_owner") or {}).items()):
                            raise Hold("Residual useful-work landing ownership changed")
            verified.append(outcome)
        if summary.get("operation") != operation or summary.get("outcomes") != verified:
            raise Hold("Residual summary does not match per-target receipts")
        counts = dict(Counter(o["status"] for o in verified))
        if counts != summary.get("outcome_counts"):
            raise Hold("Residual outcome counts changed")
        return dict(operation=operation, verified_outcomes=counts,
                    batch_complete=all(o["status"] in {"MOVED", "SYNCED_LOCAL_DEV"} for o in verified),
                    actual_prefix_directories=prefix_directory_count(Path(plan["fleet_root"])),
                    recorded_before=summary["before_prefix_directories"],
                    recorded_after=summary["after_prefix_directories"], fleet_clean=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--classification-sha256", required=True)
    parser.add_argument("--classification-commit")
    parser.add_argument("--residual", action="store_true")
    parser.add_argument("--wave-id", help="Fresh residual owner; no rebinding of a consumed operation")
    parser.add_argument("--authority-commit")
    parser.add_argument("--batch", type=int)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--plan-output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reconcile-r1", action="store_true",
                        help="Plan the fixed follow-up to the four pinned R1 zero-move outcomes")
    parser.add_argument("--operation-root", type=Path)
    args = parser.parse_args(argv)
    try:
        repo = Path.cwd().resolve()
        if args.residual:
            if args.reconcile_r1 or args.classification_commit or (args.apply and args.verify):
                raise Hold("Residual, legacy and verification modes cannot be mixed")
            wave_id = args.wave_id or RESIDUAL_WAVE_ID
            plan = build_residual_plan(repo, args.classification, args.classification_sha256, wave_id=wave_id)
            if args.plan_output.absolute() != repo / residual_paths(wave_id)[2]:
                raise Hold("Residual plan may write only its wave-owned output")
            if args.apply or args.verify:
                action = apply_residual_plan if args.apply else verify_residual_plan
                result = action(repo, plan, authority_commit=args.authority_commit,
                                batch=args.batch, operation_root=args.operation_root)
                print(json.dumps(result, sort_keys=True))
                counts = result.get("outcome_counts", result.get("verified_outcomes", {}))
                return 3 if any(k not in {"MOVED", "SYNCED_LOCAL_DEV"} for k in counts) else 0
            if any(v is not None for v in (args.batch, args.authority_commit, args.operation_root)):
                raise Hold("Residual batch authority requires explicit --apply or --verify")
            write_new(args.plan_output, encoded(plan), verify_existing=True)
            print(json.dumps({k: plan[k] for k in ("entry_count", "conditional_candidates", "untouched_holds")}
                             | {"bounded_operations": len(plan["operations"])}))
            return 0
        if args.verify or args.batch is not None or args.authority_commit is not None or args.wave_id:
            raise Hold("Fresh verification/batch authority requires --residual")
        plan = build_plan(repo, args.classification, args.classification_sha256,
                          args.classification_commit, reconcile_r1=args.reconcile_r1)
        plan_path = RECONCILE_PLAN_PATH if args.reconcile_r1 else PLAN_PATH
        operation_root = RECONCILE_OPERATION_ROOT if args.reconcile_r1 else OPERATION_ROOT
        if args.plan_output.absolute() != repo / plan_path:
            raise Hold("Only the wave-owned plan output is allowed")
        if args.apply:
            if args.operation_root != operation_root:
                raise Hold("Apply requires the exact explicit preservation destination")
            result = apply_plan(repo, plan, reconcile_r1=args.reconcile_r1)
            print(json.dumps(dict(receipts=str(operation_root / "summary.json"),
                                  outcome_counts=result["outcome_counts"], untouched_holds=407)))
            return 0 if result["outcome_counts"] == {"MOVED": 4} else 3
        if args.operation_root is not None:
            raise Hold("--operation-root requires explicit --apply")
        write_new(args.plan_output, encoded(plan), verify_existing=True)
        print("Plan verified: 411 rows; 4 conditional targets; 407 untouched HOLDs; no fleet actions.")
        return 0
    except (Hold, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
