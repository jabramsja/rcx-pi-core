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
from datetime import datetime, timezone
import json
import os
import stat
import subprocess
import sys


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(path: str, *args: str) -> tuple[bytes, dict | None]:
    # An inherited GIT_DIR / index / config override must not redirect a probe.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
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


def census(fleet_root: str, anchor_repo: str) -> dict:
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
    parser.add_argument(
        "--output", required=True,
        help="JSON artifact; a census for the same fleet root and anchor may be refreshed",
    )
    args = parser.parse_args(argv)
    report = census(args.fleet_root, args.anchor_repo)
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
