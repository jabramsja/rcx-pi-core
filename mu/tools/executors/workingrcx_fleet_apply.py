#!/usr/bin/env python3
"""The four-target fleet operation; planning never inspects the live targets.

Apply is a foreground, postmerge operation only. Immutable local intent and
stage receipts make interruption discoverable; there is deliberately no retry,
resume, force, removal, or configurable candidate mode. Exit 3 means at least
one HOLD/INCOMPLETE outcome, not fleet-wide completion.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
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


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_stat(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def file_hash(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
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


def build_plan(repo: Path, classification: Path, sha256: str, commit: str) -> dict:
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
    return dict(schema_version=1, wave_id=WAVE_ID, mutation_authorized=False,
                classification_path=str(CLASSIFICATION_PATH), classification_sha256=sha256,
                classification_commit=commit, entry_count=411, untouched_holds=407,
                conditional_candidates=4, operation_root=str(OPERATION_ROOT),
                entries=entries, postmerge_command=postmerge_command())


def postmerge_command() -> str:
    return ("PYTHONDONTWRITEBYTECODE=1 python3 " + str(TOOL_PATH)
            + " --classification " + str(CLASSIFICATION_PATH)
            + " --classification-sha256 " + CLASSIFICATION_SHA256
            + " --classification-commit " + CLASSIFICATION_COMMIT
            + " --plan-output " + str(PLAN_PATH)
            + " --apply --operation-root " + shlex.quote(str(OPERATION_ROOT)))


def require_landed(repo: Path, plan: dict) -> str:
    if SCRIPT_PATH != repo / TOOL_PATH:
        raise Hold("Apply must execute the landed carrier tool")
    if (repo / line(git(repo, "rev-parse", "--git-common-dir"))).resolve() != COMMON_DIR:
        raise Hold("Carrier common repository differs from the fixed targets")
    git(repo, "fetch", "origin", "dev")
    landed = line(git(repo, "rev-parse", "origin/dev"))
    git(repo, "merge-base", "--is-ancestor", CLASSIFICATION_COMMIT, landed)
    git(repo, "merge-base", "--is-ancestor", "HEAD", landed)
    for path in (TOOL_PATH, TEST_PATH, PLAN_PATH,
                 Path("mu/tools/executors/commit_executor.py"),
                 Path("mu/tools/executors/executor_common.py")):
        if read_plain(repo / path) != git(repo, "show", f"{landed}:{path}"):
            raise Hold(f"Unlanded or modified apply authority: {path}")
    if read_plain(repo / PLAN_PATH) != encoded(plan):
        raise Hold("Landed plan differs from the fixed operation")
    return landed


def inspect_identity(ident: dict, *, path: Path | None = None, head: str | None = None) -> None:
    target = path if path is not None else Path(ident["path"])
    common, admin = Path(ident["common_dir"]), Path(ident["git_dir"])
    for directory in (target, common, admin):
        plain_directory(directory)
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


def clean_state(target: Path) -> set[str]:
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
    if any(r and not r.startswith(b"!! ") for r in status.split(b"\0")):
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
            raise Hold(f"Unreadable or special content: {rel}")
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
    observed = {}
    with tarfile.open(output, "r") as archive:
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
    if observed != manifest or tree_manifest(root) != manifest:
        raise Hold("Preservation archive/source verification failed")


def process_idle(ident: dict) -> None:
    target = Path(ident["path"])
    proc = subprocess.run(["ps", "-A", "-ww", "-o", "pid=,command="],
                          capture_output=True, timeout=30)
    if proc.returncode or proc.stderr or not proc.stdout.strip():
        raise Hold("Process evidence unavailable")
    for raw in os.fsdecode(proc.stdout).splitlines():
        parts = raw.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            raise Hold("Process evidence malformed")
        if int(parts[0]) != os.getpid() and any(value in parts[1] for value in
                (str(target), ident["git_dir"], ident["branch"].removeprefix("refs/heads/"))):
            raise Hold("Active process references target identity")
    # +D is limited to this exact target, and includes open descendants/cwds.
    proc = subprocess.run(["lsof", "-nP", "+D", str(target), "-Fpn"],
                          capture_output=True, timeout=30)
    if proc.stdout or proc.stderr or proc.returncode != 1:
        raise Hold("Open target files/processes or uncertain lsof evidence")


def native_idle(target: Path, manifest: dict) -> None:
    for name, entry in manifest.items():
        if not any(part.startswith(".agent_bus") for part in Path(name).parts):
            continue
        if entry["kind"] == "symlink":
            raise Hold("Native ownership evidence points outside its recorded tree")
        path = target / name
        if path.name in ("bridge.lock", "meta_bridge.lock"):
            with path.open("rb") as stream:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if stream.read().strip():
                        raise Hold("Native owner lock metadata remains")
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


def inspect_target(repo: Path, ident: dict, *, head: str | None = None) -> tuple[set[str], dict]:
    inspect_identity(ident, head=head)
    target = Path(ident["path"])
    tracked = clean_state(target)
    unprotected(repo, ident)
    manifest = tree_manifest(target)
    native_idle(target, manifest)
    process_idle(ident)
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


def apply_target(repo: Path, entry: dict, directory: Path, boundary) -> dict:
    ident = entry["source_identity"]
    target, destination = Path(ident["path"]), Path(entry["destination"])
    outcome = dict(source_identity=ident, destination=str(destination), status="HOLD",
                   reason=None, prepared_head=None, boundary=None)
    preparation_started = False
    move_started = False
    try:
        with preparation_lock(Path(ident["common_dir"])):
            tracked, before = inspect_target(repo, ident)
            if target.stat().st_dev != directory.stat().st_dev:
                raise Hold("Preservation destination is not on the source filesystem")
            git(target, "merge-base", "--is-ancestor", ident["HEAD"], CLASSIFICATION_COMMIT)
            write_new(directory / "before.json", encoded(before))
            preserve_archive(target, directory / "before.tar", before)
            admin = Path(ident["git_dir"])
            admin_before = tree_manifest(admin)
            write_new(directory / "gitdir-before.json", encoded(admin_before))
            preserve_archive(admin, directory / "gitdir-before.tar", admin_before)
            bundle = directory / "history.bundle"
            git(target, "bundle", "create", str(bundle), ident["branch"])
            with bundle.open("rb") as stream:
                os.fsync(stream.fileno())
            sync_directory(directory)
            git(target, "bundle", "verify", str(bundle))
            if line(git(target, "bundle", "list-heads", str(bundle), ident["branch"])) != (
                    ident["HEAD"] + " " + ident["branch"]):
                raise Hold("Original branch history was not preserved")
            # Preserve admin evidence (including any old FETCH_HEAD) before
            # the first target fetch, as well as before the fast-forward.
            git(target, "fetch", "origin", "dev")
            prepared = line(git(target, "rev-parse", "origin/dev"))
            git(target, "merge-base", "--is-ancestor", ident["HEAD"], prepared)
            _, check = inspect_target(repo, ident)
            if check != before:
                raise Hold("Source changed while preservation was being verified")
            write_new(directory / "preparation.json", encoded(dict(
                state="PREPARATION_STARTED_OUTCOME_UNKNOWN", original=ident,
                prepared_head=prepared, history_bundle_sha256=file_hash(bundle))))
            preparation_started = True
            # Reuse the supported clean never-behind operation. The public
            # sync_primary_worktree_to_base helper deliberately selects the
            # PRIMARY, so it must never be used to prepare these linked targets.
            git(target, "merge", "--ff-only", "--no-overwrite-ignore", prepared)
            _, after = inspect_target(repo, ident, head=prepared)
            tracked_tree = tracked | {str(p) for name in tracked for p in Path(name).parents}
            for name, evidence in before.items():
                if name not in tracked_tree and after.get(name) != evidence:
                    raise Hold("Untracked/ignored evidence changed during preparation")
            git(target, "merge-base", "--is-ancestor", ident["HEAD"], prepared)
            write_new(directory / "prepared.json", encoded(after))
            outcome["prepared_head"] = prepared
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
            _, fresh = inspect_target(repo, ident, head=prepared)
            if fresh != after or os.path.lexists(destination):
                raise Hold("Prepared content or destination drifted before move")
            write_new(directory / "move-started.json", encoded(dict(
                state="TERMINAL_MOVE_STARTED_OUTCOME_UNKNOWN", target_identity=binding)))
            move_started = True
            git(repo, "worktree", "move", str(target), str(destination))
            sync_directory(target.parent)
            sync_directory(destination.parent)
            inspect_identity(ident, path=destination, head=prepared)
            observed = tree_manifest(destination)
            if os.path.lexists(target) or observed != after:
                raise Hold("Moved worktree preservation verification incomplete")
            git(destination, "merge-base", "--is-ancestor", ident["HEAD"], "HEAD")
            write_new(directory / "after.json", encoded(observed))
            return dict(destination=str(destination), manifest_sha256=digest(encoded(observed)))

        result = boundary.execute_terminal_mutation_once(
            repo, binding, terminal_action=move_once, log=lambda _message: None)
        outcome["boundary"] = result
        if result.get("action_succeeded") is True:
            outcome["status"] = "MOVED"
        elif move_started:
            outcome.update(status="INCOMPLETE", reason=result.get("reason"))
        else:
            outcome["reason"] = result.get("reason") or "Terminal boundary HOLD"
    except (Hold, OSError, ValueError, subprocess.SubprocessError) as exc:
        incomplete = move_started or (preparation_started and outcome["prepared_head"] is None)
        outcome.update(status="INCOMPLETE" if incomplete else "HOLD", reason=str(exc))
    write_new(directory / "outcome.json", encoded(outcome))
    return outcome


def apply_plan(repo: Path, plan: dict) -> dict:
    # No caller-supplied plan can broaden the fixed targets or destinations.
    expected = build_plan(repo, repo / CLASSIFICATION_PATH, CLASSIFICATION_SHA256, CLASSIFICATION_COMMIT)
    if plan != expected:
        raise Hold("Apply plan does not match its pinned classification")
    with safe_git_environment(network=True):
        landed = require_landed(repo, plan)
        plain_directory(OPERATION_ROOT.parent)
        plain_directory(COMMON_DIR)
        for entry in plan["entries"]:
            source = Path(entry["path"])
            if OPERATION_ROOT == source or source in OPERATION_ROOT.parents:
                raise Hold("Preservation output lies inside a source target")
        if os.path.lexists(OPERATION_ROOT):
            raise Hold("Operation already consumed or ambiguous; inspect local receipts, never replay")
        intent = dict(wave_id=WAVE_ID, state="OPERATION_STARTED_OUTCOME_UNKNOWN", landed=landed,
                      plan_sha256=digest(encoded(plan)), operation_root=str(OPERATION_ROOT))
        # This second fixed anchor also survives relocation of the receipt tree.
        write_new(COMMON_DIR / f"rcx_fleet_apply_{WAVE_ID}.json", encoded(intent))
        new_directory(OPERATION_ROOT)
        write_new(OPERATION_ROOT / "intent.json", encoded(intent))
        write_new(OPERATION_ROOT / "plan.json", encoded(plan))
        try:
            from . import commit_executor as boundary
        except ImportError:
            import commit_executor as boundary
        outcomes = []
        for entry in plan["entries"]:
            if entry["action"] == "UNTOUCHED_HOLD":
                continue
            directory = OPERATION_ROOT / str(entry["source_index"])
            new_directory(directory)
            write_new(directory / "intent.json", encoded(entry))
            outcomes.append(apply_target(repo, entry, directory, boundary))
        summary = dict(wave_id=WAVE_ID, outcomes=outcomes, untouched_holds=407,
                       outcome_counts=dict(Counter(o["status"] for o in outcomes)),
                       operation_outcomes_recorded=True, fleet_clean=False)
        write_new(OPERATION_ROOT / "summary.json", encoded(summary))
        return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--classification-sha256", required=True)
    parser.add_argument("--classification-commit", required=True)
    parser.add_argument("--plan-output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--operation-root", type=Path)
    args = parser.parse_args(argv)
    try:
        repo = Path.cwd().resolve()
        plan = build_plan(repo, args.classification, args.classification_sha256, args.classification_commit)
        if args.plan_output.absolute() != repo / PLAN_PATH:
            raise Hold("Only the wave-owned plan output is allowed")
        if args.apply:
            if args.operation_root != OPERATION_ROOT:
                raise Hold("Apply requires the exact explicit preservation destination")
            result = apply_plan(repo, plan)
            print(json.dumps(dict(receipts=str(OPERATION_ROOT / "summary.json"),
                                  outcome_counts=result["outcome_counts"], untouched_holds=407)))
            return 0 if result["outcome_counts"] == {"MOVED": 4} else 3
        if args.operation_root is not None:
            raise Hold("--operation-root requires explicit --apply")
        write_new(args.plan_output, encoded(plan), verify_existing=True)
        print("Plan verified: 411 rows; 4 conditional targets; 407 untouched HOLDs; no fleet actions.")
        return 0
    except (Hold, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
