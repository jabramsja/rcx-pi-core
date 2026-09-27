#!/usr/bin/env python3
"""Observe direct WorkingRCX* entries and the anchor's registered worktrees.

This is a read-only, non-atomic observation, never deletion-safety evidence or
mutation authorization. Git status contributes counts, not a dirty-file list.
Configured clean/process filters and submodule worktrees make dirty inspection
unsafe: retain unknown dirty status/counts without running status in those cases.
Paths use filesystem surrogateescape and ASCII JSON escapes so os.fsencode on
the parsed strings recovers the original path bytes, including non-UTF-8 names.
The Git executable on PATH must support worktree list --porcelain -z and
rev-parse --path-format=absolute; unsupported probes remain explicit errors.
Repeating a command refreshes its declared output with new observations only
when the existing file is a census for the same fleet root and anchor.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(path: str, *args: str, alternate_objects: str | None = None) -> tuple[bytes, dict | None]:
    # An inherited GIT_DIR / index / config override must not redirect a probe.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    env["GIT_ALLOW_PROTOCOL"] = ""  # Object probes cannot trigger an implicit promisor fetch.
    if alternate_objects:
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = alternate_objects
    operation = "git " + " ".join(args)
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-c", "core.untrackedCache=false", "-C", path, *args],
            env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return b"", {"operation": operation, "error": type(exc).__name__, "message": str(exc)}
    if result.returncode:
        return result.stdout, {
            "operation": operation, "returncode": result.returncode,
            "stderr": os.fsdecode(result.stderr[:1024]),
            "stderr_truncated": len(result.stderr) > 1024,
        }
    return result.stdout, None


def _line(raw: bytes) -> str:
    # Remove only Git's terminator; whitespace/newlines can belong to a path.
    if not raw.endswith(b"\n"):
        raise ValueError("Git metadata lacks its line terminator")
    return os.fsdecode(raw[:-1])


def _worktrees(raw: bytes) -> tuple[list[dict], list[dict]]:
    records, errors = [], []
    if not raw or not raw.endswith(b"\0\0"):
        errors.append({"operation": "parse worktree list", "message": "Missing NUL record terminator"})
    for block in raw.split(b"\0\0"):
        if not block:
            continue
        fields = block.split(b"\0")
        if not fields[0].startswith(b"worktree ") or not os.path.isabs(fields[0][9:]):
            errors.append({"operation": "parse worktree list", "message": "Missing absolute worktree path"})
            continue
        record = {"path": os.fsdecode(fields[0][9:])}
        for field in fields[1:]:
            key, _, value = field.partition(b" ")
            if key in (b"HEAD", b"branch"):
                record[os.fsdecode(key)] = os.fsdecode(value)
            elif key in (b"bare", b"detached", b"locked", b"prunable"):
                record[os.fsdecode(key)] = True
        records.append(record)
    return records, errors


def _dirty_counts(raw: bytes) -> dict:
    counts = dict(entries=0, tracked=0, untracked=0, staged=0, unstaged=0, unmerged=0)
    if not raw:
        return counts
    if not raw.endswith(b"\0"):
        raise ValueError("Git status lacks its NUL terminator")
    fields = raw[:-1].split(b"\0")
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if len(field) < 4 or field[2:3] != b" ":
            raise ValueError("Malformed porcelain status record")
        xy = field[:2]
        if xy == b"??":
            counts["untracked"] += 1
        elif all(code in b" MADRCUT" for code in xy) and xy != b"  ":
            counts["tracked"] += 1
            if xy in (b"DD", b"AU", b"UD", b"UA", b"DU", b"AA", b"UU"):
                counts["unmerged"] += 1
            else:
                counts["staged"] += xy[0:1] != b" "
                counts["unstaged"] += xy[1:2] != b" "
            if b"R" in xy or b"C" in xy:
                if index >= len(fields) or not fields[index]:
                    raise ValueError("Missing rename/copy source in porcelain status")
                index += 1
        else:
            raise ValueError("Unknown porcelain status code")
        counts["entries"] += 1
    return counts


def _kind(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def _status(path: str) -> tuple[bytes, dict | None]:
    # Optional locks and fsmonitor settings do not disable content conversion.
    # Query effective config (including includes/global/worktree config) without
    # reading command values, and skip status if a clean/process filter exists.
    filters, error = _git(
        path, "config", "--null", "--name-only", "--get-regexp",
        r"^filter\..*\.(clean|process)$",
    )
    if error is None:
        return b"", {
            "operation": "git status",
            "message": "Dirty inspection skipped: configured clean/process filters may execute code.",
        }
    # git config returns 1 with no output for no matches. Any other failure
    # leaves filter configuration unknown, so no content-reading probe follows.
    if error.get("returncode") != 1 or filters or error.get("stderr"):
        return b"", error

    # Status can invoke Git in submodules, whose local filter settings are not
    # covered by the parent config query. Inspect only index metadata; never
    # recurse into their worktrees or claim a clean parent while ignoring them.
    index, error = _git(path, "ls-files", "--stage", "-z")
    if error:
        return b"", error
    if index and not index.endswith(b"\0"):
        return b"", {"operation": "git ls-files", "message": "Index listing lacks its NUL terminator"}
    if any(entry.startswith(b"160000 ") for entry in index.split(b"\0")):
        return b"", {
            "operation": "git status",
            "message": "Dirty inspection skipped: submodule worktrees may configure executable filters.",
        }
    return _git(path, "status", "--porcelain=v1", "-z", "--untracked-files=normal", "--ignore-submodules=all")


def _inspect(row: dict) -> None:
    path, errors = row["path"], row["errors"]
    git = row["git"]
    try:
        info = os.lstat(path)
        row["entry_kind"] = _kind(info.st_mode)
        row["filesystem_identity"] = {"device": info.st_dev, "inode": info.st_ino,
                                      "mode": info.st_mode}
        if stat.S_ISLNK(info.st_mode):
            row["symlink_target"] = os.readlink(path)
            info = os.stat(path)
            row["symlink_target_kind"] = _kind(info.st_mode)
    except FileNotFoundError as exc:
        row["availability_status"] = "missing"
        if row["entry_kind"] == "unknown":
            row["entry_kind"] = "missing"
        row["inspection_status"] = "missing"
        errors.append({"operation": "stat", "error": type(exc).__name__, "message": str(exc)})
        return
    except OSError as exc:
        row["availability_status"] = "error"
        errors.append({"operation": "stat", "error": type(exc).__name__, "message": str(exc)})
        return
    row["availability_status"] = "present"
    if not stat.S_ISDIR(info.st_mode):
        row.update(repository_kind="non_repository", inspection_status="not_repository")
        return

    raw, error = _git(path, "rev-parse", "--is-bare-repository")
    if error:
        # A broken .git or bare-repository marker is uncertainty, not proof that
        # the entry is an ordinary non-repository directory.
        try:
            markers = []
            for name in (".git", "HEAD", "objects"):
                try:
                    os.lstat(os.path.join(path, name))
                    markers.append(name)
                except FileNotFoundError:
                    pass
        except OSError as exc:
            errors.append({"operation": "repository markers", "message": str(exc)})
            markers = ["unknown"]
        if not markers and error.get("stderr", "").startswith("fatal: not a git repository"):
            row.update(repository_kind="non_repository", inspection_status="not_repository")

        else:
            errors.append(error)
        return
    if raw not in (b"true\n", b"false\n"):
        errors.append({"operation": "rev-parse", "message": "Invalid bare-repository result"})
        return
    bare = raw == b"true\n"

    def metadata(key: str, *args: str) -> None:
        value, failure = _git(path, *args)
        if failure:
            errors.append(failure)
            return
        try:
            parsed = _line(value)
            if key in ("root", "git_dir", "common_dir") and not os.path.isabs(parsed):
                raise ValueError("Git did not return the requested absolute path")
            git[key] = parsed
        except ValueError as exc:
            errors.append({"operation": "git " + " ".join(args), "message": str(exc)})

    if not bare:
        metadata("root", "rev-parse", "--show-toplevel")
        if git["root"] is not None and os.path.realpath(git["root"]) != os.path.realpath(path):
            row.update(repository_kind="non_repository", inspection_status="not_repository")
            row["note"] = "Git discovered a containing repository; this entry is not its root."
            return
    metadata("git_dir", "rev-parse", "--absolute-git-dir")
    metadata("common_dir", "rev-parse", "--path-format=absolute", "--git-common-dir")
    if bare:
        row["repository_kind"] = "bare_repository"
    elif git["root"] is not None and git["git_dir"] is not None and git["common_dir"] is not None:
        row["repository_kind"] = (
            "linked_worktree" if os.path.realpath(git["git_dir"]) != os.path.realpath(git["common_dir"])
            else "standalone_repository"
        )

    branch, branch_error = _git(path, "symbolic-ref", "--quiet", "HEAD")
    if branch_error and branch_error.get("returncode") == 1 and not branch_error.get("stderr"):
        git["branch_status"] = "detached"
    elif branch_error:
        errors.append(branch_error)
    else:
        try:
            git["branch"] = _line(branch)
            git["branch_status"] = "symbolic"
        except ValueError as exc:
            errors.append({"operation": "symbolic-ref", "message": str(exc)})
    metadata("HEAD", "rev-parse", "--verify", "HEAD")

    if bare:
        git["dirty_status"] = "not_applicable"
    else:
        status, error = _status(path)
        if error:
            errors.append(error)
        else:
            try:
                git["dirty_counts"] = _dirty_counts(status)
                git["dirty_status"] = "dirty" if git["dirty_counts"]["entries"] else "clean"
            except ValueError as exc:
                errors.append({"operation": "git status", "message": str(exc)})
    row["inspection_status"] = "partial" if errors else "ok"


def useful_work(path: str, comparison_commit: str, *, comparison_repo: str | None = None,
                coverage: bool = False) -> dict:
    """Inventory local history and WIP without filters, fetching or index writes.

    Equality is conservative: changed bytes not identical to the comparison
    tree need a native landing owner. A backup is never an integration proof.
    Patch hashes bind the complete staged/unstaged diffs retained at the source.
    """
    result = dict(comparison_commit=comparison_commit, status="UNKNOWN", errors=[],
                  changes=[], local_commits=[], local_refs=[])
    alternate_objects = None
    if comparison_repo:
        raw_common, error = _git(comparison_repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        local_common, local_error = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if error or local_error:
            result["errors"].append(error or local_error)
            return result
        if raw_common != local_common:
            # Ephemeral read-only object lookup, never an alternates file, fetch
            # or object import into a retained clone. Local-only objects remain
            # visible alongside the exact canonical comparison commit.
            alternate_objects = os.path.join(_line(raw_common), "objects")

    def probe(*args):
        raw, error = _git(path, *args, alternate_objects=alternate_objects)
        if error:
            result["errors"].append(error)
            raise ValueError("useful-work probe failed")
        return raw

    try:
        probe("cat-file", "-e", comparison_commit + "^{commit}")
        ahead, behind = map(int, probe("rev-list", "--left-right", "--count",
                                     "HEAD..." + comparison_commit).split())
        result.update(ahead=ahead, behind=behind)
        admin = _line(probe("rev-parse", "--absolute-git-dir"))
        common = _line(probe("rev-parse", "--path-format=absolute", "--git-common-dir"))
        result["local_commits"] = probe("rev-list", "--all" if admin == common else "HEAD",
                                        "--not", comparison_commit).decode().splitlines()
        refs = ["refs/heads", "refs/stash"]
        if admin != common:
            branch, error = _git(path, "symbolic-ref", "--quiet", "HEAD",
                                 alternate_objects=alternate_objects)
            if error:
                if (error.get("returncode") != 1 or branch or error.get("stderr")
                        or error.get("stderr_truncated") is not False):
                    result["errors"].append(error)
                    return result
                # A detached HEAD still owns its commits and index/WIP. Do not
                # pass an empty ref filter to for-each-ref: it means all lanes.
                refs = []
            else:
                refs = [_line(branch)]
        if refs:
            result["local_refs"] = os.fsdecode(probe("for-each-ref", "--format=%(refname) %(objectname)", *refs)).splitlines()
        result["local_commit_changes"] = []
        for commit in result["local_commits"]:
            paths = probe("diff-tree", "--root", "--no-commit-id", "--name-only", "--no-renames",
                          "-r", "-m", "--first-parent", "-z", commit)
            patch = probe("diff-tree", "--root", "--binary", "--no-ext-diff", "--no-textconv",
                          "--no-renames", "-r", "-m", "--first-parent", commit)
            result["local_commit_changes"].append(dict(commit=commit,
                paths=sorted({os.fsdecode(p) for p in paths.split(b"\0") if p}, key=os.fsencode),
                patch_sha256=hashlib.sha256(patch).hexdigest()))
        _, error = _status(path)
        if error:
            result["errors"].append(error)
            return result
        base_tree = {}
        for entry in probe("ls-tree", "-r", "-z", comparison_commit).split(b"\0"):
            if entry:
                metadata, name = entry.split(b"\t", 1)
                mode, _, oid = metadata.split()
                base_tree[os.fsdecode(name)] = (mode.decode(), oid.decode())
        index_tree = {}
        for entry in probe("ls-files", "--stage", "-z").split(b"\0"):
            if entry:
                metadata, name = entry.split(b"\t", 1)
                mode, oid, stage = metadata.split()
                if stage != b"0":
                    raise ValueError("Unmerged useful-work index")
                index_tree[os.fsdecode(name)] = (mode.decode(), oid.decode())
        changed = set()
        for args in (("diff", "--cached", "--no-renames", "--name-only", "-z"),
                     ("diff", "--no-renames", "--name-only", "-z"),
                     ("ls-files", "--others", "--exclude-standard", "-z")):
            changed.update(os.fsdecode(p) for p in probe(*args).split(b"\0") if p)
        for label, args in (("staged", ("--cached",)), ("unstaged", ())):
            patch = probe("diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", *args)
            result[label + "_patch_sha256"] = hashlib.sha256(patch).hexdigest()
        for name in sorted(changed, key=os.fsencode):
            file = os.path.join(path, name)
            try:
                info = os.lstat(file)
                if stat.S_ISLNK(info.st_mode):
                    content, mode = os.fsencode(os.readlink(file)), "120000"
                elif stat.S_ISREG(info.st_mode):
                    if os.path.realpath(os.path.dirname(file)) != os.path.dirname(file):
                        raise ValueError("Useful-work parent alias requires exact preservation review: " + name)
                    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    with os.fdopen(fd, "rb") as stream:
                        before = os.fstat(stream.fileno())
                        content = stream.read()
                        after = os.fstat(stream.fileno())
                    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                            after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise ValueError("Useful-work content changed during inventory")
                    mode = "100755" if info.st_mode & 0o111 else "100644"
                else:
                    raise ValueError("Useful-work special entry requires preservation owner: " + name)
                oid = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
                worktree = (mode, oid)
                content_sha = hashlib.sha256(content).hexdigest()
            except FileNotFoundError:
                worktree, content_sha = None, None
            index = index_tree.get(name)
            base = base_tree.get(name)
            result["changes"].append(dict(path=name, index=index, worktree=worktree,
                comparison=base, content_sha256=content_sha,
                dev_covered=index == base and worktree == base))
        result["status"] = "COVERED" if not result["local_commits"] and all(
            change["dev_covered"] for change in result["changes"]) else "NEEDS_LANDING"
        if coverage:
            # A non-ancestor commit is history, not evidence of missing code.
            # Reverse-check its exact binary patch against independent dev
            # bytes. Failure means review, never proof that code is missing.
            def covered_patch(patch, names):
                with tempfile.TemporaryDirectory(prefix="rcx-coverage-", dir="/tmp") as temp:
                    for name in names:
                        parts = Path(name).parts
                        if not parts or Path(name).is_absolute() or ".." in parts:
                            raise ValueError("Unsafe coverage path")
                        entry = base_tree.get(name)
                        if entry is None:
                            continue
                        mode, oid = entry
                        out = Path(temp) / name
                        out.parent.mkdir(parents=True, exist_ok=True)
                        content = probe("cat-file", "blob", oid)
                        if mode == "120000":
                            out.symlink_to(os.fsdecode(content))
                        elif mode in {"100644", "100755"}:
                            out.write_bytes(content)
                            out.chmod(int(mode, 8) & 0o777)
                        else:
                            raise ValueError("Unsupported coverage tree mode")
                    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
                    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                               GIT_ALLOW_PROTOCOL="", GIT_OPTIONAL_LOCKS="0")
                    checked = subprocess.run(["git", "apply", "--reverse", "--check", "--binary", "-"],
                        cwd=temp, env=env, input=patch, capture_output=True, timeout=30)
                    return checked.returncode == 0

            for change in result["local_commit_changes"]:
                patch = probe("diff-tree", "--root", "--binary", "--no-ext-diff", "--no-textconv",
                              "--no-renames", "-r", "-m", "--first-parent", change["commit"])
                change["coverage"] = ("EXACT_REVERSE_PATCH" if not patch or covered_patch(patch, change["paths"])
                                      else "REQUIRES_HUNK_REVIEW")
                change["comparison_blobs"] = {p: base_tree.get(p) for p in change["paths"]}
            for change in result["changes"]:
                name = change["path"]
                for label, options in (("index", ("--cached",)), ("worktree", ())):
                    patch = probe("diff", "--binary", "--no-ext-diff", "--no-textconv",
                                  "--no-renames", *options, "--", name)
                    change[label + "_patch_sha256"] = hashlib.sha256(patch).hexdigest()
                    exact = change[label] == change["comparison"]
                    # An untracked file has no diff. Its absent index is not a
                    # coverage proof for the independently retained bytes.
                    untracked = label == "worktree" and name not in index_tree
                    change[label + "_coverage"] = ("EXACT_BLOB" if exact else
                        "NO_CHANGE" if not patch and not untracked else
                        "EXACT_REVERSE_PATCH" if patch and covered_patch(patch, [name]) else
                        "REQUIRES_HUNK_REVIEW")
                change["dev_covered"] = all(change[k + "_coverage"] != "REQUIRES_HUNK_REVIEW"
                                            for k in ("index", "worktree"))
            result["coverage_method"] = "exact_binary_reverse_patch_against_comparison_blobs"
            result["status"] = "COVERED" if (all(c["dev_covered"] for c in result["changes"])
                and all(c["coverage"] != "REQUIRES_HUNK_REVIEW" for c in result["local_commit_changes"])) else "NEEDS_LANDING"
    except (OSError, ValueError) as exc:
        result["errors"].append(dict(operation="useful_work", message=str(exc)))
    return result


def preserved_operation_owners(fleet_root: str) -> dict:
    """Index original useful-work owners, including spent HOLD/INCOMPLETE rows."""
    try:
        from . import workingrcx_fleet_apply as fleet
    except ImportError:
        import workingrcx_fleet_apply as fleet
    result = {}
    for path in sorted(Path(fleet_root).glob("fleet-apply-preserved-*/*/outcome.json")):
        if not path.parent.name.isdigit():
            continue
        raw = fleet.read_plain(path)
        value = json.loads(raw)
        identity = value.get("source_identity")
        if not isinstance(identity, dict) or not isinstance(identity.get("path"), str):
            raise ValueError("Original operation receipt lacks source ownership: " + str(path))
        result.setdefault(identity["path"], []).append(dict(receipt_path=str(path), sha256=fleet.digest(raw),
            status=value.get("status"), source_identity=identity, destination=value.get("destination"),
            landing_owner=value.get("landing_owner"), preservation_sha256=value.get("preservation_sha256", {})))
    return result


def missing_registration(path: str, common: str) -> dict:
    """Resolve an absent checkout through its unique, original Git admin.

    No worktree status is inferred. Hashes cover the raw admin (including
    reflogs/index extensions), semantic index and Git's indexed-object closure.
    This observation is evidence only; fresh finite authority is still required.
    """
    try:
        from . import workingrcx_fleet_apply as fleet
    except ImportError:
        import workingrcx_fleet_apply as fleet
    result = dict(status="UNKNOWN", errors=[], path=path)
    try:
        target, shared = Path(path), Path(common)
        if (not target.is_absolute() or target.resolve() != target
                or os.path.lexists(target)):
            raise fleet.Hold("Missing source reappeared or has an aliased path")
        fleet.plain_directory(shared)
        registry = shared / "worktrees"
        fleet.plain_directory(registry)
        matches = []
        for admin in sorted(registry.iterdir()):
            fleet.plain_directory(admin)
            pointer = fleet.read_plain(admin / "gitdir")
            if pointer == os.fsencode(target / ".git") + b"\n":
                matches.append(admin)
        if len(matches) != 1:
            raise fleet.Hold("Missing source lacks exactly one admin/gitdir mapping")
        admin = matches[0]
        if (admin / fleet.line(fleet.read_plain(admin / "commondir"))).resolve() != shared:
            raise fleet.Hold("Missing registration common-directory mismatch")
        ownership_holds = []
        for root, names in ((admin, ("index.lock", "HEAD.lock", "locked", "MERGE_HEAD",
                                    "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD")),
                            (shared, ("config.lock", "packed-refs.lock", "shallow", "info/grafts"))):
            ownership_holds.extend(str(root / name) for name in names if os.path.lexists(root / name))
        ownership_holds.extend(str(p) for p in sorted(shared.glob("refs/**/*.lock")))
        before = fleet.tree_manifest(admin)
        if any(r["kind"] not in {"file", "directory"} for r in before.values()):
            raise fleet.Hold("Missing admin contains an aliased or special record")
        with fleet.safe_git_environment():
            head = fleet.line(fleet.git(admin, "rev-parse", "--verify", "HEAD^{commit}"))
            branch = fleet.line(fleet.git(admin, "symbolic-ref", "--quiet", "HEAD", allowed=(0, 1))) or None
            records, errors = _worktrees(fleet.git(shared, "worktree", "list", "--porcelain", "-z"))
            registrations = [r for r in records if r["path"] == path]
            expected = dict(path=path, HEAD=head, **({"branch": branch} if branch else {"detached": True}))
            if errors or len(registrations) != 1 or {
                    k: v for k, v in registrations[0].items() if k not in {"prunable", "locked"}} != expected:
                raise fleet.Hold("Missing registration HEAD/ref/flags do not match its admin")
            index = fleet.git_entries(admin)
            if any(v[0] not in {"100644", "100755", "120000"} for v in index.values()):
                raise fleet.Hold("Missing index contains an unsupported object mode")
            objects = sorted(set(fleet.git(admin, "rev-list", "--single-worktree", "--objects", "--indexed-objects",
                                          "--no-object-names").splitlines()))
            typed = fleet.git_input(admin, b"".join(o + b"\n" for o in objects),
                                   "cat-file", "--batch-check=%(objectname) %(objecttype)")
            if (len(typed.splitlines()) != len(objects) or any(row.split() not in (
                    [oid, b"blob"], [oid, b"tree"]) for oid, row in zip(objects, typed.splitlines()))):
                raise fleet.Hold("Missing raw-index object closure is unavailable")
            history = fleet.git(admin, "rev-list", "HEAD")
            head_raw = fleet.read_plain(admin / "HEAD")
            if head_raw != (("ref: " + branch) if branch else head).encode() + b"\n":
                raise fleet.Hold("Missing raw HEAD differs from its resolved identity")
        info = admin.lstat()
        if fleet.tree_manifest(admin) != before or os.path.lexists(target):
            raise fleet.Hold("Missing registration changed during observation")
        result.update(status="OBSERVED", ownership_holds=ownership_holds, identity=dict(path=path, HEAD=head, branch=branch,
            common_dir=common, git_dir=str(admin)), registration=registrations[0],
            admin_filesystem_identity=dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode),
            admin_manifest=before, head_raw_hex=head_raw.hex(),
            gitdir_raw_hex=fleet.read_plain(admin / "gitdir").hex(),
            commondir_raw_hex=fleet.read_plain(admin / "commondir").hex(),
            index_sha256=fleet.file_hash(admin / "index"), index_entry_count=len(index),
            index_entries_sha256=fleet.digest(fleet.encoded(index)),
            indexed_objects_count=len(objects), indexed_objects_sha256=fleet.digest(typed),
            history_count=len(history.splitlines()), history_sha256=fleet.digest(history),
            reference_files=fleet.missing_reference_files(shared, branch),
            absent_worktree_bytes="UNKNOWN; no unstaged/untracked preservation claim")
    except (OSError, ValueError, fleet.Hold, subprocess.SubprocessError) as exc:
        result["errors"].append(str(exc))
    return result


def missing_useful_work(observation: dict, comparison_commit: str) -> dict:
    """Account for index intent separately from absent, unknowable worktree bytes."""
    try:
        from . import workingrcx_fleet_apply as fleet
    except ImportError:
        import workingrcx_fleet_apply as fleet
    result = dict(comparison_commit=comparison_commit, status="UNKNOWN", errors=[], changes=[],
                  local_commits=[], local_commit_changes=[], local_refs=[],
                  coverage_method="exact_retained_index_and_comparison_blobs",
                  unstaged_untracked_intent="UNKNOWN_ABSENT_CHECKOUT", integration_completed=False)
    try:
        if observation.get("status") != "OBSERVED":
            raise fleet.Hold("Missing registration inventory is uncertain")
        admin = Path(observation["identity"]["git_dir"])
        with fleet.safe_git_environment():
            index = fleet.git_entries(admin)
            head = fleet.git_entries(admin, "HEAD")
            dev = fleet.git_entries(admin, comparison_commit)
            for name in sorted(set(index) | set(head)):
                if index.get(name) == head.get(name):
                    continue
                retained = index.get(name)
                result["changes"].append(dict(path=name, original=head.get(name), index=retained,
                    comparison=dev.get(name), worktree=None,
                    index_blob_sha256=fleet.digest(fleet.git(admin, "cat-file", "blob", retained[1])) if retained else None,
                    dev_covered=retained == dev.get(name),
                    disposition="EXACT_CURRENT_BLOB" if retained == dev.get(name) else "REQUIRES_EXACT_HUNK_REVIEW"))
            result["staged_patch_sha256"] = fleet.digest(fleet.git(admin, "diff", "--cached", "--binary",
                "--no-ext-diff", "--no-textconv", "--no-renames", "HEAD"))
            result["local_commits"] = fleet.git(admin, "rev-list", "HEAD", "--not", comparison_commit).decode().splitlines()
            for commit in result["local_commits"]:
                paths = fleet.git(admin, "diff-tree", "--root", "--no-commit-id", "--name-only",
                                  "--no-renames", "-r", "-m", "--first-parent", "-z", commit)
                result["local_commit_changes"].append(dict(commit=commit,
                    paths=sorted({os.fsdecode(p) for p in paths.split(b"\0") if p}), coverage="REQUIRES_HUNK_REVIEW"))
            # Even a HEAD-equal index cannot close lost unstaged/untracked intent.
            result.update(status="NEEDS_LANDING", retained_index_changed=bool(result["changes"]))
    except (OSError, ValueError, fleet.Hold, subprocess.SubprocessError) as exc:
        result["errors"].append(str(exc))
    return result


def missing_registration_report(observed: dict, *, wave_id: str, census_sha256: str,
                                prior_inventory: Path, inherited_ledgers: tuple[Path, ...],
                                retained_reports: tuple[Path, ...] = ()) -> dict:
    """Account for the entire observed cohort and retain earlier owner ledgers.

    Historical blob/receipt matches identify available evidence, never semantic
    integration or closure of an original owner. Inputs are retained by hash.
    """
    try:
        from . import workingrcx_fleet_apply as fleet
    except ImportError:
        import workingrcx_fleet_apply as fleet
    raw = fleet.read_plain(prior_inventory)
    prior = json.loads(raw)
    original = {r["path"]: r for r in prior["rows"]}
    if len(original) != len(prior["rows"]):
        raise ValueError("Original missing inventory has duplicate sources")
    rows = {r["path"]: r for r in observed["entries"]}
    if not original.keys() <= rows.keys():
        raise ValueError("Fresh census silently excludes an original missing owner")
    comparisons = {r["useful_work"]["comparison_commit"] for r in observed["entries"] if r.get("useful_work")}
    if len(comparisons) != 1:
        raise ValueError("Missing owners require one exact fresh comparison commit")
    comparison_commit = comparisons.pop()
    ledgers, retained, blob_owners = [], [], {}
    for path in inherited_ledgers:
        content = fleet.read_plain(path)
        ledger = json.loads(content)
        owners = [r for r in ledger["entries"] if r.get("landing_owner")]
        ledgers.append(dict(path=str(path), sha256=fleet.digest(content), wave_id=ledger["wave_id"],
            owner_count=len(owners), original_owners=[dict(source_index=r["source_index"], path=r["path"],
                landing_owner=r["landing_owner"]) for r in owners], integration_completed=False))
        for row in ledger["entries"]:
            for change in (row.get("inventory") or {}).get("changes", []):
                for version in ("index", "worktree"):
                    blob = change.get(version)
                    if blob:
                        blob_owners.setdefault((change["path"], tuple(blob)), []).append(dict(
                            ledger=str(path), source_index=row["source_index"], source_path=row["path"], version=version))
    for path in retained_reports:
        content = fleet.read_plain(path)
        retained.append(dict(path=str(path), sha256=fleet.digest(content), evidence=json.loads(content),
                             grants_owner_closure=False))
    entries = []
    for path, previous in original.items():
        source = rows[path]
        evidence = source.get("missing_registration") or {}
        useful = source.get("useful_work") or {}
        changes = []
        for change in useful.get("changes", []):
            value = dict(change)
            value["retained_source_matches"] = blob_owners.get((change["path"], tuple(change["index"] or ())), [])
            value["historical_dev_blob"] = None
            if change["index"] and not change["dev_covered"]:
                mode, oid = change["index"]
                admin = Path(evidence["identity"]["git_dir"])
                with fleet.safe_git_environment():
                    commits = fleet.git(admin, "log", "--format=%H", "--find-object=" + oid,
                                        comparison_commit, "--", change["path"]).decode().splitlines()
                    for commit in commits:
                        tree = fleet.git(admin, "ls-tree", "-z", commit, "--", change["path"])
                        expected = f"{mode} blob {oid}\t".encode() + os.fsencode(change["path"]) + b"\0"
                        if tree == expected:
                            value["historical_dev_blob"] = dict(commit=commit, mode=mode, oid=oid,
                                proof="EXACT_HISTORICAL_DEV_BLOB; not semantic integration")
                            break
            value["landing_obligation"] = ("Retain original owner; exact current blob is evidence only."
                if change["dev_covered"] else "Review this exact HEAD-to-index hunk against dev and retained receipts; land only a demonstrated missing behavior.")
            changes.append(value)
        entries.append(dict(path=path, original_inventory=previous, current=evidence,
            original_admin_matches=(evidence.get("identity", {}).get("git_dir") == previous["git_dir"]),
            original_raw_index_matches=evidence.get("index_sha256") == previous["index_sha256"],
            original_head_matches=(bytes.fromhex(evidence.get("head_raw_hex", "")).decode().rstrip("\n") == previous["head"]),
            useful_work=useful, staged_hunk_obligations=changes,
            inherited_source_mapping=source.get("retirement_evidence"),
            owner=dict(task="FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION", source_path=path,
                status="PENDING_EXACT_INDEX_AND_ORIGINAL_INTENT_REVIEW", integration_completed=False),
            unstaged_untracked_bytes="UNKNOWN_UNLESS_AN_EXACT_EARLIER_RECEIPT_PROVES_THEM"))
    return dict(schema_version=1, observation_kind="read_only_missing_registration_owners", wave_id=wave_id,
        census_sha256=census_sha256, comparison_commit=comparison_commit, mutation_authorized=False,
        prior_inventory=dict(path=str(prior_inventory), sha256=fleet.digest(raw), comparison_commit=prior.get("comparison_commit")), entry_count=len(entries),
        staged_owner_count=sum(bool(e["staged_hunk_obligations"]) for e in entries), entries=entries,
        inherited_ledgers=ledgers, retained_triage=retained,
        proof_limits=["No source, registration, index, lock or historical receipt was mutated.",
            "Independent preservation and public terminal apply/verify remain required after landing.",
            "Absent unstaged/untracked bytes and original intent remain unresolved; equality is not owner closure."])


def retirement_observation(path: str, fleet_root: str, common: str, *, prior_owners: dict | None = None) -> dict:
    """Read native ownership evidence without releasing any original claim."""
    result = dict(status="OBSERVED", errors=[], preserved_operation=None, prior_owners=[], journals=[],
                  native_links=[], fifos=[])
    target = Path(path)
    try:
        from . import workingrcx_fleet_apply as fleet
    except ImportError:
        import workingrcx_fleet_apply as fleet
    try:
        relative = target.relative_to(fleet_root) if target.is_relative_to(fleet_root) else Path(".")
        fleet_archive = (len(relative.parts) == 3 and relative.parts[0].startswith("fleet-apply-preserved-")
                         and relative.parts[1].isdigit() and relative.parts[2] == "worktree")
        lifecycle_root = Path(common) / "rcx_worktree_lifecycle"
        native_archive = (target.is_relative_to(lifecycle_root)
            and len(target.relative_to(lifecycle_root).parts) == 3
            and target.parent.name in {"attempt-1", "attempt-2", "attempt-3"} and target.name == "worktree")
        if fleet_archive or native_archive:
            receipt = target.parent / "outcome.json"
            raw = fleet.read_plain(receipt)
            value = json.loads(raw)
            if (value.get("status") != "MOVED" or value.get("destination") != path
                    or value.get("boundary", {}).get("action_succeeded") is not True
                    or value.get("boundary", {}).get("authority_consumed") is not True):
                raise ValueError("Archive lacks its exact successful native move receipt")
            result["preserved_operation"] = dict(receipt_path=str(receipt), sha256=fleet.digest(raw),
                source_identity=value["source_identity"], landing_owner=value.get("landing_owner"),
                original_operation_id=value["boundary"]["operation_id"],
                preservation_sha256=value.get("preservation_sha256", {}))
            if native_archive:
                completed = target.parent.parent / "completion.json"
                completed_raw = fleet.read_plain(completed)
                completion = json.loads(completed_raw)
                if completion.get("state") != "COMPLETE" or completion.get("destination") != path:
                    raise ValueError("Native archive has no exact completed owner")
                result["preserved_operation"].update(lifecycle_completion=str(completed),
                    lifecycle_completion_sha256=fleet.digest(completed_raw))
        original = (result["preserved_operation"] or {}).get("source_identity", {}).get("path", path)
        owners = preserved_operation_owners(fleet_root) if prior_owners is None else prior_owners
        result["prior_owners"] = owners.get(original, [])
        journal_root = Path(common) / "rcx_primary_worktree_sync_transactions"
        for journal in sorted(journal_root.glob("*/manifest.json")):
            raw = fleet.read_plain(journal)
            value = json.loads(raw)
            if value.get("worktree_identity", {}).get("path") in {path, original}:
                result["journals"].append(dict(path=str(journal), sha256=fleet.digest(raw),
                    state=value.get("state"), owner=value.get("owner"),
                    transaction_id=value.get("transaction_id"), stash_oid=value.get("stash_oid"),
                    worktree_identity=value.get("worktree_identity"), old_head=value.get("old_head"),
                    held_paths=sorted(set(value.get("held_tracked_paths", [])) | set(value.get("held_untracked_paths", []))),
                    tracked_snapshots=value.get("tracked_snapshots", {}),
                    tracked_patch_fingerprints=value.get("tracked_patch_fingerprints", {})))
        for directory, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in dirs + files:
                file = Path(directory) / name
                info = file.lstat()
                rel = str(file.relative_to(target))
                if stat.S_ISFIFO(info.st_mode):
                    result["fifos"].append(dict(path=rel, mode=stat.S_IMODE(info.st_mode)))
                if stat.S_ISLNK(info.st_mode) and Path(rel).parts[0].startswith(".agent_bus"):
                    result["native_links"].append(dict(path=rel, target=os.readlink(file),
                        dangling=not os.path.exists(file)))
        result["fifos"].sort(key=lambda r: r["path"])
        result["native_links"].sort(key=lambda r: r["path"])
    except (OSError, ValueError, fleet.Hold) as exc:
        result.update(status="UNKNOWN", errors=[str(exc)])
    return result


def census(fleet_root: str, anchor_repo: str, *, comparison_commit: str | None = None,
           retirement: bool = False) -> dict:
    """Return fresh metadata; only main() writes the explicitly named output."""
    started = _now()
    # Resolve the input directories once (e.g. /var -> /private/var on macOS).
    # Child symlink entries retain their own paths and kinds, not target identity.
    root, anchor = os.path.realpath(fleet_root), os.path.realpath(anchor_repo)
    targets: dict[str, dict] = {}

    def target(path: str, source: str) -> dict:
        path = os.path.abspath(path)
        row = targets.setdefault(path, {"path": path, "sources": [], "registered_worktrees": []})
        if source not in row["sources"]:
            row["sources"].append(source)
        return row

    siblings = {"started_at": _now(), "status": "complete", "errors": [], "matching_entries": 0}
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if entry.name.casefold().startswith("workingrcx"):
                    target(entry.path, "fleet_root")
                    siblings["matching_entries"] += 1
    except OSError as exc:
        siblings["status"] = "error"
        siblings["errors"].append({"operation": "scandir", "error": type(exc).__name__, "message": str(exc)})
    siblings["finished_at"] = _now()

    registered = {"started_at": _now(), "status": "complete", "errors": []}
    raw, error = _git(anchor, "worktree", "list", "--porcelain", "-z")
    if error:
        registered["errors"].append(error)
    records, parse_errors = _worktrees(raw)
    registered["errors"].extend(parse_errors)
    for record in records:
        target(record["path"], "anchor_worktrees")["registered_worktrees"].append(record)
    if registered["errors"]:
        registered["status"] = "error"
    registered.update(records=len(records), finished_at=_now())

    rows = []
    prior_owners = preserved_operation_owners(root) if retirement else None
    for path in sorted(targets, key=os.fsencode):
        row = targets[path]
        row.update(
            classification="UNCLASSIFIED", observed_started_at=_now(),
            registration_status=("registered" if row["registered_worktrees"] else
                                 "not_registered" if registered["status"] == "complete" else "unknown"),
            entry_kind="unknown", availability_status="unknown", repository_kind="unknown",
            inspection_status="error", errors=[],
            git=dict(root=None, git_dir=None, common_dir=None, HEAD=None, branch=None,
                     branch_status="unknown", dirty_status="unknown", dirty_counts=None),
        )
        _inspect(row)
        if retirement and row["availability_status"] == "missing" and row["registration_status"] == "registered":
            common_raw, common_error = _git(anchor, "rev-parse", "--path-format=absolute", "--git-common-dir")
            observation = (missing_registration(path, _line(common_raw)) if not common_error else
                           dict(status="UNKNOWN", errors=[common_error]))
            row["missing_registration"] = observation
            if observation["status"] == "OBSERVED":
                row["git"].update(observation["identity"], root=path,
                    branch_status="symbolic" if observation["identity"]["branch"] else "detached")
                row["git"].pop("path", None)
                row.update(repository_kind="missing_linked_worktree", inspection_status="admin_only", errors=[])
                row["retirement_evidence"] = retirement_observation(path, root, _line(common_raw), prior_owners=prior_owners)
                if comparison_commit:
                    row["useful_work"] = missing_useful_work(observation, comparison_commit)
        if comparison_commit and row["repository_kind"] in ("linked_worktree", "standalone_repository"):
            row["useful_work"] = useful_work(path, comparison_commit, comparison_repo=anchor, coverage=retirement)
        if retirement and Path(path).is_relative_to(root) and row["entry_kind"] == "directory":
            row["retirement_evidence"] = retirement_observation(path, root, os.path.join(anchor, ".git"), prior_owners=prior_owners)
        if row["repository_kind"] == "non_repository" and row["entry_kind"] == "directory":
            # Includes shells inside a containing Git checkout: rev-parse can
            # succeed there without this directory owning any Git registration.
            try:
                with os.scandir(path) as children:
                    children = list(children)
                row["bus_only_shell"] = bool(children) and all(
                    child.name.startswith(".agent_bus") and child.is_dir(follow_symlinks=False)
                    for child in children
                )
                row["shell_entries"] = sorted(child.name for child in children)
            except OSError as exc:
                row["errors"].append({"operation": "shell inventory", "message": str(exc)})
                row["inspection_status"] = "partial"
        row["observed_finished_at"] = _now()
        rows.append(row)
    return {
        "schema_version": 1, "observation_kind": "read_only_fleet_census",
        "started_at": started, "finished_at": _now(),
        "fleet_root_input": fleet_root, "fleet_root": root,
        "anchor_repo_input": anchor_repo, "anchor_repo": anchor,
        "path_encoding": f"os.fsdecode / os.fsencode ({sys.getfilesystemencoding()}, surrogateescape); ASCII JSON escapes",
        "coverage_complete": siblings["status"] == registered["status"] == "complete",
        "enumeration": {"fleet_root": siblings, "anchor_worktrees": registered},
        "limitations": [
            "Sequential action-time observations, not a coherent deletion-safety snapshot or authorization.",
            "Only direct case-insensitive WorkingRCX* entries and anchor worktree registrations are enumerated.",
            "Coverage describes these two enumerations only; inspection failures remain explicit and unknown.",
            "All entries are UNCLASSIFIED. No fetch, process or GitHub inspection, safety decision or target mutation.",
            "Dirty counts are porcelain v1 entries; untracked directories may be collapsed, and ignored files are excluded.",
            "Git optional locks, fsmonitor and untracked-cache writes are disabled; lazy fetching is disabled.",
            "Dirty status/counts remain unknown when clean/process filters are configured, submodules are present, or their metadata checks fail.",
        ],
        "entry_count": len(rows), "entries": rows,
    }


def _write_report(path: str, report: dict) -> None:
    # Serialize before touching the destination. Only this declared file is
    # written: no temporary/backup artifact, directory creation or Git writes.
    payload = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    try:
        output = open(path, "x", encoding="ascii")
    except FileExistsError:
        # The evidence command runs again before commit. Refresh only a regular,
        # unaliased census for these inputs; never truncate an unrelated file or
        # follow a symlink. Validate and write through the same open descriptor.
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "r+", encoding="ascii") as output:
            info = os.fstat(output.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Existing output must be a regular file with one link")
            previous = json.load(output)
            identity_keys = ("schema_version", "observation_kind", "fleet_root", "anchor_repo")
            if not isinstance(previous, dict) or any(
                previous.get(key) != report[key] for key in identity_keys
            ):
                raise ValueError("Existing output is not a census for this fleet root and anchor")
            # Prior entries and findings are never reused as observation data.
            output.seek(0)
            output.write(payload)
            output.truncate()
    else:
        with output:
            output.write(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fleet-root", required=True)
    parser.add_argument("--anchor-repo", required=True)
    parser.add_argument("--comparison-commit", help="Exact local comparison commit for useful-work inventory")
    parser.add_argument("--retirement", action="store_true", help="Observe native archive/journal owners and exact patch coverage")
    parser.add_argument(
        "--output", required=True,
        help="JSON artifact; a census for the same fleet root and anchor may be refreshed",
    )
    args = parser.parse_args(argv)
    report = census(args.fleet_root, args.anchor_repo, comparison_commit=args.comparison_commit, retirement=args.retirement)
    try:
        _write_report(args.output, report)
    except (OSError, ValueError) as exc:
        print(f"Cannot write census artifact: {exc}", file=sys.stderr)
        return 1
    complete = report["coverage_complete"]
    print(f"Observed {report['entry_count']} UNCLASSIFIED entries; coverage_complete={complete}")
    if not complete:
        print("Enumeration failed; the artifact retains partial coverage and errors.", file=sys.stderr)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
