#!/usr/bin/env python3
"""Fixed-set, restart-conservative executor for eight stale pull requests.

``contract-check`` and ``verify`` are read-only.  ``apply`` is intentionally
bounded to the literal manifest below.  It composes the public one-shot
terminal boundary in :mod:`commit_executor`; it does not expose an arbitrary
repository or pull-request mutation surface.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence


WAVE_ID = "pr-disposition-executor-enabler-r1-2026-09-09"
REPOSITORY_NAME = "jabramsja/rcx-pi-core"
MANIFEST_RELATIVE_PATH = Path(
    "reports/control_plane/"
    "pr-disposition-executor-enabler-r1-2026-09-09_targets.json"
)
INTENT_ROOT_NAME = "rcx_pr_disposition_operations"
RECEIPT_ROOT_NAME = "rcx_pr_disposition_receipts"
INTENT_SCHEMA_VERSION = 1
RECEIPT_SCHEMA_VERSION = 1

# Apply R2 completed the fixed-set provider mutations but could not land because
# the providerless commit pipeline had no post-cleanup terminal transition.  The
# transition below is intentionally specific to that consumed wave: it verifies
# and preserves its evidence without ever making ``apply`` launchable again.
TERMINAL_SWEEP_WAVE_ID = "pr-disposition-apply-r2-2026-09-10"
TERMINAL_SWEEP_COMPARISON_COMMIT = (
    "2b4218dc7c3e6f3e3d688dc6773d1777071529ee"
)
TERMINAL_SWEEP_PACKET_RELATIVE_PATH = Path(
    "reports/control_plane/pr-disposition-apply-r2-2026-09-10_2026-09-10.md"
)
TERMINAL_SWEEP_RECEIPTS_RELATIVE_PATH = Path(
    "reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts"
)
TERMINAL_SWEEP_PACKET_SHA256 = (
    "b85adda0f1e66c3b4bccff86f84f8cb835464ce31252d926d3de364e1872c444"
)
TERMINAL_SWEEP_CANDIDATE_SHA256 = (
    "36677e05e5fa5f865442e341ff1c64c60a9ef821d4d84fddfd56f5bd3e4df102"
)
TERMINAL_RECEIPT_ROOT_NAME = "rcx_post_merge_terminal_receipts"
TERMINAL_RECEIPT_SCHEMA_VERSION = 1
TERMINAL_FLEET_CANDIDATE = "fleet-cleanup-builder"
TERMINAL_RECONCILIATION_CANDIDATE = "pr-disposition-reconciliation"

EXPECTED_REPOSITORY: dict[str, Any] = {
    "id": "R_kgDOQvy8bg",
    "nameWithOwner": REPOSITORY_NAME,
    "url": "https://github.com/jabramsja/rcx-pi-core",
}
EXPECTED_HEAD_REPOSITORY: dict[str, Any] = {
    "id": "R_kgDOQvy8bg",
    "owner": {
        "id": "MDQ6VXNlcjI3MjU3NDg3",
        "login": "jabramsja",
    },
}


def _target(
    number: int,
    node_id: str,
    branch: str,
    head: str,
) -> dict[str, Any]:
    return {
        "baseRefName": "dev",
        "headRefName": branch,
        "headRefOid": head,
        "headRepository": copy.deepcopy(EXPECTED_HEAD_REPOSITORY),
        "id": node_id,
        "mergedAt": None,
        "number": number,
        "state": "OPEN",
    }


EXPECTED_TARGETS: tuple[dict[str, Any], ...] = (
    _target(
        1219,
        "PR_kwDOQvy8bs74MpV0",
        "jabramsja/roles-all-codex-current-dev-2026-07-29",
        "28081acd74c549a7afd4292351b214228d45f451",
    ),
    _target(
        1213,
        "PR_kwDOQvy8bs7wx1P-",
        "jabramsja/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12",
        "28b9beed3b8fbc793058446bf9854f363b82ead5",
    ),
    _target(
        1212,
        "PR_kwDOQvy8bs7wnEHo",
        "jabramsja/codex-reviewer-56sol-ultra-2026-07-11",
        "b6eb91a61439c2cb3a08f377d0d07a69546fd7db",
    ),
    _target(
        1211,
        "PR_kwDOQvy8bs7t2Sw3",
        "jabramsja/never-behind-checkignore-fence-2026-07-04",
        "10d157c4eb5b667b07006686fea86d88af268646",
    ),
    _target(
        1210,
        "PR_kwDOQvy8bs7t02-L",
        "jabramsja/never-behind-stash-ff-hold-surface-2026-07-04",
        "b846d2e93be9ffbd3e25b30c1b7983ceb52c4ae7",
    ),
    _target(
        1203,
        "PR_kwDOQvy8bs7tral-",
        "jabramsja/post-reentry-defer-not-loop-2026-07-03",
        "4c466d1001b838e69ce141801fbbbe35f410d466",
    ),
    _target(
        1197,
        "PR_kwDOQvy8bs7tS-PM",
        "jabramsja/pager-route-claude-2026-07-01",
        "02d6900ec39c3bd9da1e95e7cf0ae5507e4c7f92",
    ),
    _target(
        1196,
        "PR_kwDOQvy8bs7s8IjQ",
        "jabramsja/roles-claude-opus-2026-07-01",
        "1131ae748dc373f0a96f0d0875a40d4e3ccc68ba",
    ),
)

TARGET_BY_NUMBER = {target["number"]: target for target in EXPECTED_TARGETS}
TARGET_BY_NODE = {target["id"]: target for target in EXPECTED_TARGETS}
EXPECTED_NUMBERS = tuple(target["number"] for target in EXPECTED_TARGETS)

COMPLETE_STATUSES = frozenset({"CLOSED", "CLOSED_RECONCILED"})
HOLD_STATUSES = frozenset(
    {
        "HOLD_REMOTE_DRIFT",
        "HOLD_ACTION_OR_POSTVERIFY",
        "HOLD_SHARED_UNATTEMPTED",
    }
)
ALLOWED_STATUSES = COMPLETE_STATUSES | HOLD_STATUSES
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_OPERATION_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class ContractError(RuntimeError):
    """A fixed-set, persistence, remote, or receipt contract was violated."""


GhRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[Any]]


def _canonical_json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    options: dict[str, Any] = {
        "allow_nan": False,
        "ensure_ascii": False,
        "sort_keys": True,
    }
    if pretty:
        options["indent"] = 2
    else:
        options["separators"] = (",", ":")
    return (json.dumps(value, **options) + ("\n" if pretty else "")).encode(
        "utf-8"
    )


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _json_exact_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool/int/float equivalence."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _json_exact_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_exact_equal(a, b) for a, b in zip(left, right)
        )
    return bool(left == right)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _reject_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_json(raw: bytes, *, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ContractError(f"{label} is not strict JSON: {exc}") from exc


def _read_regular_bytes(path: Path, *, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ContractError(f"cannot inspect {label} {path}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ContractError(f"{label} must be a regular non-symlink file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read {label} {path}: {exc}") from exc


def _read_canonical_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    raw = _read_regular_bytes(path, label=label)
    value = _decode_json(raw, label=label)
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be a JSON object")
    if raw != _canonical_json_bytes(value, pretty=True):
        raise ContractError(
            f"{label} bytes are not canonical sorted UTF-8 JSON with one newline"
        )
    return value, raw


def _manifest_payload() -> dict[str, Any]:
    return {
        "repository": copy.deepcopy(EXPECTED_REPOSITORY),
        "schema_version": 1,
        "targets": copy.deepcopy(list(EXPECTED_TARGETS)),
        "wave_id": WAVE_ID,
    }


def validate_manifest_contract(
    manifest_path: Path | str,
    *,
    repository: str = REPOSITORY_NAME,
) -> dict[str, Any]:
    """Validate canonical self-hash and the literal repository/eight-target set."""
    if repository != REPOSITORY_NAME:
        raise ContractError(
            f"repository must be exactly {REPOSITORY_NAME}; got {repository!r}"
        )
    path = Path(manifest_path)
    manifest, raw = _read_canonical_json(path, label="target manifest")
    if set(manifest) != {
        "manifest_sha256",
        "repository",
        "schema_version",
        "targets",
        "wave_id",
    }:
        raise ContractError("target manifest has an unexpected top-level schema")
    claimed_hash = manifest.get("manifest_sha256")
    if not isinstance(claimed_hash, str) or _DIGEST_RE.fullmatch(claimed_hash) is None:
        raise ContractError("target manifest manifest_sha256 is invalid")
    unhashed = dict(manifest)
    del unhashed["manifest_sha256"]
    actual_hash = _canonical_sha256(unhashed)
    if claimed_hash != actual_hash:
        raise ContractError(
            "target manifest self-hash mismatch: "
            f"expected {actual_hash}, found {claimed_hash}"
        )
    expected = _manifest_payload()
    if not _json_exact_equal(unhashed, expected):
        raise ContractError(
            "target manifest is not the literal repository and ordered eight-PR set"
        )
    return {
        "manifest": manifest,
        "manifest_path": str(path),
        "manifest_sha256": claimed_hash,
        "raw_bytes": raw,
    }


def contract_check(
    manifest_path: Path | str,
    *,
    repository: str = REPOSITORY_NAME,
) -> dict[str, Any]:
    validated = validate_manifest_contract(manifest_path, repository=repository)
    return {
        "decision": "CONTRACT_OK",
        "manifest_sha256": validated["manifest_sha256"],
        "repository": repository,
        "target_count": len(EXPECTED_TARGETS),
        "targets": list(EXPECTED_NUMBERS),
        "wave_id": WAVE_ID,
    }


def _default_git_run(
    args: Sequence[str],
    *,
    cwd: Path,
    binary: bool = False,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        check=False,
        text=not binary,
    )


def _git_stdout(
    args: Sequence[str],
    *,
    cwd: Path,
    git_run: Callable[..., subprocess.CompletedProcess[Any]],
) -> str:
    proc = git_run(args, cwd=cwd, binary=False)
    if proc.returncode != 0:
        detail = str(proc.stderr or proc.stdout or "").strip()
        raise ContractError(
            f"git command failed ({' '.join(args)}): {detail[:300] or proc.returncode}"
        )
    return str(proc.stdout).strip()


def _validate_manifest_comparison_ancestry(
    *,
    repo_root: Path,
    manifest_path: Path,
    manifest_bytes: bytes,
    comparison_commit: str,
    git_run: Callable[..., subprocess.CompletedProcess[Any]] = _default_git_run,
) -> None:
    if _SHA_RE.fullmatch(comparison_commit) is None:
        raise ContractError("comparison commit must be an exact lowercase 40-hex SHA")
    root = repo_root.resolve(strict=True)
    top = Path(
        _git_stdout(
            ["git", "rev-parse", "--show-toplevel"], cwd=root, git_run=git_run
        )
    ).resolve(strict=True)
    if top != root:
        raise ContractError(f"repo root mismatch: expected {root}, git reports {top}")
    expected_manifest_path = (root / MANIFEST_RELATIVE_PATH).resolve(strict=True)
    if manifest_path.resolve(strict=True) != expected_manifest_path:
        raise ContractError(
            f"apply requires the fixed manifest path {MANIFEST_RELATIVE_PATH}"
        )
    resolved_commit = _git_stdout(
        ["git", "rev-parse", "--verify", f"{comparison_commit}^{{commit}}"],
        cwd=root,
        git_run=git_run,
    )
    if resolved_commit != comparison_commit:
        raise ContractError("comparison commit did not resolve to its exact supplied SHA")
    ancestor = git_run(
        ["git", "merge-base", "--is-ancestor", comparison_commit, "HEAD"],
        cwd=root,
        binary=False,
    )
    if ancestor.returncode != 0:
        raise ContractError("comparison commit is not an ancestor of the apply HEAD")
    tracked = git_run(
        ["git", "ls-files", "--error-unmatch", "--", str(MANIFEST_RELATIVE_PATH)],
        cwd=root,
        binary=False,
    )
    if tracked.returncode != 0:
        raise ContractError("fixed target manifest is not tracked in the apply worktree")
    committed = git_run(
        ["git", "show", f"{comparison_commit}:{MANIFEST_RELATIVE_PATH.as_posix()}"],
        cwd=root,
        binary=True,
    )
    if committed.returncode != 0:
        detail_value = committed.stderr or committed.stdout or b""
        if isinstance(detail_value, bytes):
            detail = detail_value.decode("utf-8", errors="replace")
        else:
            detail = str(detail_value)
        raise ContractError(
            "target manifest is absent from the exact comparison commit: "
            f"{detail.strip()[:300] or committed.returncode}"
        )
    committed_bytes = committed.stdout
    if isinstance(committed_bytes, str):
        committed_bytes = committed_bytes.encode("utf-8")
    if committed_bytes != manifest_bytes:
        raise ContractError(
            "working target manifest bytes differ from the exact comparison commit"
        )


def _resolve_common_git_dir(
    repo_root: Path,
    *,
    git_run: Callable[..., subprocess.CompletedProcess[Any]] = _default_git_run,
) -> Path:
    raw = _git_stdout(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=repo_root,
        git_run=git_run,
    )
    reported = Path(raw)
    common = (
        reported if reported.is_absolute() else repo_root / reported
    ).resolve(strict=True)
    if not common.is_dir():
        raise ContractError(f"git common dir is not a directory: {common}")
    return common


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_durable_directory(path: Path) -> None:
    missing: list[Path] = []
    cursor = path
    while not os.path.lexists(cursor):
        missing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    if os.path.lexists(cursor):
        info = cursor.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise ContractError(f"directory ancestor is not a real directory: {cursor}")
    for directory in reversed(missing):
        os.mkdir(directory, 0o700)
        _fsync_directory(directory)
        _fsync_directory(directory.parent)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ContractError(f"durable path is not a real directory: {path}")


@contextmanager
def _wave_apply_lock(common_dir: Path) -> Iterator[None]:
    """Exclude live peers without reusing commit_executor's terminal lock."""
    lock_path = common_dir / INTENT_ROOT_NAME / WAVE_ID / ".apply.lock"
    _ensure_durable_directory(lock_path.parent)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ContractError(f"cannot open fixed-wave apply lock {lock_path}: {exc}") from exc
    locked = False
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ContractError(f"fixed-wave apply lock is not a regular file: {lock_path}")
        os.fsync(fd)
        _fsync_directory(lock_path.parent)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ContractError(
                "another fixed-wave disposition executor holds the apply lock"
            ) from exc
        locked = True
        yield
    finally:
        if locked:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    _ensure_durable_directory(path.parent)
    data = _canonical_json_bytes(payload, pretty=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd: int | None = None
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)


def _atomic_replace_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_durable_directory(path.parent)
    try:
        info = path.lstat()
    except OSError as exc:
        raise ContractError(f"cannot inspect intent before state advance: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ContractError(f"intent is not a regular file: {path}")
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    data = _canonical_json_bytes(payload, pretty=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd: int | None = None
    try:
        fd = os.open(temporary, flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _publish_receipt_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Publish complete receipt bytes atomically without clobbering a peer."""
    _ensure_durable_directory(path.parent)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    data = _canonical_json_bytes(payload, pretty=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd: int | None = None
    linked = False
    try:
        fd = os.open(temporary, flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        linked = True
        temporary.unlink()
        _fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        if not linked and os.path.lexists(path):
            # The caller decides whether an existing receipt is valid.  Never
            # replace it, even when a concurrent writer raced this publication.
            pass


_TERMINAL_IDENTITY_KEYS = {
    "authority",
    "base_branch",
    "base_ref",
    "bound",
    "common_dir_identity",
    "expected_branch",
    "expected_head",
    "operation_id",
    "reason",
    "version",
    "worktree_identity",
}


def _validate_terminal_identity(
    identity: Any,
    *,
    repo_root: Path | None = None,
    common_dir: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(identity, dict):
        return ["terminal target identity is not an object"]
    if set(identity) != _TERMINAL_IDENTITY_KEYS:
        errors.append("terminal target identity schema mismatch")
    expected_scalars = {
        "authority": "identity_only_not_terminal_authority",
        "base_branch": "dev",
        "base_ref": "origin/dev",
        "bound": True,
        "reason": None,
        "version": 2,
    }
    for key, expected in expected_scalars.items():
        if not _json_exact_equal(identity.get(key), expected):
            errors.append(f"terminal target identity {key} mismatch")
    operation_id = identity.get("operation_id")
    if not isinstance(operation_id, str) or _OPERATION_ID_RE.fullmatch(operation_id) is None:
        errors.append("terminal target operation id is invalid")
    if not isinstance(identity.get("expected_branch"), str) or not identity.get(
        "expected_branch"
    ):
        errors.append("terminal target expected branch is invalid")
    expected_head = identity.get("expected_head")
    if not isinstance(expected_head, str) or _SHA_RE.fullmatch(expected_head) is None:
        errors.append("terminal target expected HEAD is invalid")
    for field, expected_path in (
        ("worktree_identity", repo_root),
        ("common_dir_identity", common_dir),
    ):
        value = identity.get(field)
        if not isinstance(value, dict) or set(value) != {"device", "inode", "path"}:
            errors.append(f"terminal target {field} is invalid")
            continue
        raw_path = value.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(f"terminal target {field} path is invalid")
            continue
        recorded = Path(raw_path)
        if not recorded.is_absolute():
            errors.append(f"terminal target {field} path is not absolute")
        elif raw_path != os.path.normpath(raw_path) or raw_path != str(recorded):
            errors.append(f"terminal target {field} path is not lexically canonical")
        elif expected_path is not None:
            try:
                recorded_path = recorded.resolve(strict=True)
            except OSError:
                errors.append(f"terminal target {field} path is unresolved")
                continue
            if recorded_path != expected_path.resolve(strict=True):
                errors.append(f"terminal target {field} path mismatch")
            try:
                current_info = recorded_path.stat()
            except OSError:
                errors.append(f"terminal target {field} filesystem identity is unreadable")
            else:
                if (
                    value.get("device") != current_info.st_dev
                    or value.get("inode") != current_info.st_ino
                ):
                    errors.append(f"terminal target {field} device/inode drifted")
        for numeric in ("device", "inode"):
            if type(value.get(numeric)) is not int:
                errors.append(f"terminal target {field}.{numeric} is invalid")
    return errors


def _intent_path(common_dir: Path, number: int) -> Path:
    return common_dir / INTENT_ROOT_NAME / WAVE_ID / f"pr-{number}.json"


def _receipt_path(receipts_dir: Path, number: int) -> Path:
    return receipts_dir / f"pr-{number}.json"


def _new_intent(
    *,
    target: dict[str, Any],
    identity: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    return {
        "comparison_commit": comparison_commit,
        "manifest_sha256": manifest_sha256,
        "operation_id": identity["operation_id"],
        "repository": copy.deepcopy(EXPECTED_REPOSITORY),
        "schema_version": INTENT_SCHEMA_VERSION,
        "state": "PREPARED",
        "target": copy.deepcopy(target),
        "terminal_target_identity": copy.deepcopy(identity),
        "wave_id": WAVE_ID,
    }


_INTENT_BASE_KEYS = {
    "comparison_commit",
    "manifest_sha256",
    "operation_id",
    "repository",
    "schema_version",
    "state",
    "target",
    "terminal_target_identity",
    "wave_id",
}
_INTENT_STATE_EXTRA_KEYS = {
    "PREPARED": set(),
    "REMOTE_DRIFT_NO_ACTION": {"callback_drift", "callback_snapshot"},
    "CALLBACK_VALIDATED_CLOSE_PENDING": {"callback_snapshot"},
    "CLOSE_RESPONSE_OBSERVED": {"callback_snapshot", "close_response"},
}


def _intent_errors(
    intent: Any,
    *,
    target: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
    repo_root: Path | None,
    common_dir: Path | None,
) -> list[str]:
    if not isinstance(intent, dict):
        return ["intent is not an object"]
    errors: list[str] = []
    state = intent.get("state")
    extras = _INTENT_STATE_EXTRA_KEYS.get(state)
    if extras is None:
        errors.append("intent state is invalid")
        extras = set()
    if set(intent) != _INTENT_BASE_KEYS | extras:
        errors.append("intent schema does not match its state")
    expected = {
        "comparison_commit": comparison_commit,
        "manifest_sha256": manifest_sha256,
        "repository": EXPECTED_REPOSITORY,
        "schema_version": INTENT_SCHEMA_VERSION,
        "target": target,
        "wave_id": WAVE_ID,
    }
    for key, value in expected.items():
        if not _json_exact_equal(intent.get(key), value):
            errors.append(f"intent {key} mismatch")
    identity_errors = _validate_terminal_identity(
        intent.get("terminal_target_identity"),
        repo_root=repo_root,
        common_dir=common_dir,
    )
    errors.extend(identity_errors)
    operation_id = intent.get("operation_id")
    if not isinstance(operation_id, str) or _OPERATION_ID_RE.fullmatch(operation_id) is None:
        errors.append("intent operation id is invalid")
    if isinstance(intent.get("terminal_target_identity"), dict) and operation_id != intent[
        "terminal_target_identity"
    ].get("operation_id"):
        errors.append("intent operation id does not match terminal binding")
    if state in {"REMOTE_DRIFT_NO_ACTION", "CALLBACK_VALIDATED_CLOSE_PENDING", "CLOSE_RESPONSE_OBSERVED"}:
        callback_snapshot = intent.get("callback_snapshot")
        if not isinstance(callback_snapshot, dict):
            errors.append("intent callback snapshot is absent")
        elif state in {"CALLBACK_VALIDATED_CLOSE_PENDING", "CLOSE_RESPONSE_OBSERVED"}:
            errors.extend(
                f"intent callback: {item}"
                for item in _snapshot_errors(callback_snapshot, target, state="OPEN")
            )
    if state == "REMOTE_DRIFT_NO_ACTION":
        drift = intent.get("callback_drift")
        if not isinstance(drift, list) or not drift or not all(
            isinstance(item, str) and item for item in drift
        ):
            errors.append("remote-drift intent lacks exact drift reasons")
        elif isinstance(intent.get("callback_snapshot"), dict) and drift != _snapshot_errors(
            intent["callback_snapshot"], target, state="OPEN"
        ):
            errors.append("remote-drift intent reasons contradict its callback snapshot")
    if state == "CLOSE_RESPONSE_OBSERVED" and not isinstance(
        intent.get("close_response"), dict
    ):
        errors.append("close-observed intent lacks close response")
    elif state == "CLOSE_RESPONSE_OBSERVED":
        errors.extend(
            f"intent close response: {item}"
            for item in _node_errors(intent.get("close_response"), target, state="CLOSED")
        )
    return errors


def _read_intent(
    path: Path,
    *,
    target: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
    repo_root: Path,
    common_dir: Path,
) -> dict[str, Any]:
    intent, _ = _read_canonical_json(path, label="PR disposition intent")
    errors = _intent_errors(
        intent,
        target=target,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
        repo_root=repo_root,
        common_dir=common_dir,
    )
    if errors:
        raise ContractError("invalid PR disposition intent: " + "; ".join(errors))
    return intent


def _advance_intent(
    path: Path,
    intent: dict[str, Any],
    *,
    expected_state: str,
    new_state: str,
    additions: dict[str, Any],
    target: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
    repo_root: Path,
    common_dir: Path,
) -> dict[str, Any]:
    current = _read_intent(
        path,
        target=target,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
        repo_root=repo_root,
        common_dir=common_dir,
    )
    if not _json_exact_equal(current, intent) or current.get("state") != expected_state:
        raise ContractError("intent changed before its durable state advance")
    updated = copy.deepcopy(current)
    updated["state"] = new_state
    updated.update(copy.deepcopy(additions))
    errors = _intent_errors(
        updated,
        target=target,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
        repo_root=repo_root,
        common_dir=common_dir,
    )
    if errors:
        raise ContractError("refusing invalid intent state advance: " + "; ".join(errors))
    _atomic_replace_json(path, updated)
    return updated


_PR_FIELDS = (
    "id,number,state,mergedAt,baseRefName,headRefName,headRefOid,"
    "headRepository,headRepositoryOwner"
)
_NODE_QUERY = """query PRDispositionNode($id: ID!, $headRef: String!) {
  node(id: $id) {
    __typename
    ... on PullRequest {
      id number state mergedAt baseRefName headRefName headRefOid
      repository { id nameWithOwner url }
      headRepository {
        id nameWithOwner
        ref(qualifiedName: $headRef) {
          name prefix
          target { __typename ... on Commit { oid } }
        }
      }
      headRepositoryOwner { id login }
    }
  }
}"""
_CLOSE_MUTATION = """mutation PRDispositionClose($id: ID!, $headRef: String!) {
  closePullRequest(input: {pullRequestId: $id}) {
    pullRequest {
      __typename
      id number state mergedAt baseRefName headRefName headRefOid
      repository { id nameWithOwner url }
      headRepository {
        id nameWithOwner
        ref(qualifiedName: $headRef) {
          name prefix
          target { __typename ... on Commit { oid } }
        }
      }
      headRepositoryOwner { id login }
    }
  }
}"""


def _default_gh_runner(
    args: Sequence[str], cwd: Path
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        check=False,
        text=True,
    )


def _gh_json(
    args: Sequence[str],
    *,
    cwd: Path,
    gh_runner: GhRunner,
    label: str,
) -> dict[str, Any]:
    proc = gh_runner(tuple(args), cwd)
    if proc.returncode != 0:
        detail_value = proc.stderr or proc.stdout or ""
        if isinstance(detail_value, bytes):
            detail = detail_value.decode("utf-8", errors="replace")
        else:
            detail = str(detail_value)
        raise ContractError(
            f"{label} failed: {detail.strip()[:300] or proc.returncode}"
        )
    raw = proc.stdout
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    value = _decode_json(raw, label=label)
    if not isinstance(value, dict):
        raise ContractError(f"{label} did not return a JSON object")
    return value


def _normalized_repository(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        "id": source.get("id"),
        "nameWithOwner": source.get("nameWithOwner"),
        "url": source.get("url"),
    }


def _normalized_pr(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    head_repository = source.get("headRepository")
    if not isinstance(head_repository, dict):
        head_repository = {}
    owner = source.get("headRepositoryOwner")
    if not isinstance(owner, dict):
        owner = {}
    return {
        "baseRefName": source.get("baseRefName"),
        "headRefName": source.get("headRefName"),
        "headRefOid": source.get("headRefOid"),
        "headRepository": {
            "id": head_repository.get("id"),
            "nameWithOwner": head_repository.get("nameWithOwner"),
            "owner": {"id": owner.get("id"), "login": owner.get("login")},
        },
        "id": source.get("id"),
        "mergedAt": source.get("mergedAt"),
        "number": source.get("number"),
        "state": source.get("state"),
    }


def _normalized_head_ref(node: Any) -> Any:
    source = node if isinstance(node, dict) else {}
    head_repository = source.get("headRepository")
    if not isinstance(head_repository, dict):
        return None
    ref = head_repository.get("ref")
    if ref is None:
        return None
    if not isinstance(ref, dict):
        return {"invalid": True}
    target = ref.get("target")
    if not isinstance(target, dict):
        target = {}
    return {
        "name": ref.get("name"),
        "prefix": ref.get("prefix"),
        "target": {
            "oid": target.get("oid"),
            "type": target.get("__typename"),
        },
    }


def _normalized_node(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        "headRef": _normalized_head_ref(source),
        "pullRequest": _normalized_pr(source),
        "repository": _normalized_repository(source.get("repository")),
        "type": source.get("__typename"),
    }


def _read_remote_snapshot(
    target: dict[str, Any],
    *,
    repo_root: Path,
    gh_runner: GhRunner,
) -> dict[str, Any]:
    repository = _gh_json(
        ["gh", "repo", "view", REPOSITORY_NAME, "--json", "id,nameWithOwner,url"],
        cwd=repo_root,
        gh_runner=gh_runner,
        label="authoritative repository read",
    )
    pr = _gh_json(
        [
            "gh",
            "pr",
            "view",
            str(target["number"]),
            "--repo",
            REPOSITORY_NAME,
            "--json",
            _PR_FIELDS,
        ],
        cwd=repo_root,
        gh_runner=gh_runner,
        label=f"authoritative PR #{target['number']} read",
    )
    node_result = _gh_json(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={_NODE_QUERY}",
            "-F",
            f"id={target['id']}",
            "-F",
            f"headRef=refs/heads/{target['headRefName']}",
        ],
        cwd=repo_root,
        gh_runner=gh_runner,
        label=f"authoritative PR node {target['id']} read",
    )
    data = node_result.get("data")
    node = data.get("node") if isinstance(data, dict) else None
    return {
        "node": _normalized_node(node),
        "pr": _normalized_pr(pr),
        "repository": _normalized_repository(repository),
    }


def _expected_pr(target: dict[str, Any], *, state: str) -> dict[str, Any]:
    expected = copy.deepcopy(target)
    expected["state"] = state
    expected["mergedAt"] = None
    expected["headRepository"]["nameWithOwner"] = REPOSITORY_NAME
    return expected


def _expected_head_ref(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": target["headRefName"],
        "prefix": "refs/heads/",
        "target": {"oid": target["headRefOid"], "type": "Commit"},
    }


def _remote_pr_shape_errors(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} is not an object"]
    expected_keys = {
        "baseRefName",
        "headRefName",
        "headRefOid",
        "headRepository",
        "id",
        "mergedAt",
        "number",
        "state",
    }
    errors: list[str] = []
    if set(value) != expected_keys:
        errors.append(f"{label} schema mismatch")
    head_repository = value.get("headRepository")
    if not isinstance(head_repository, dict) or set(head_repository) != {
        "id",
        "nameWithOwner",
        "owner",
    }:
        errors.append(f"{label} head repository schema mismatch")
    else:
        owner = head_repository.get("owner")
        if not isinstance(owner, dict) or set(owner) != {"id", "login"}:
            errors.append(f"{label} head owner schema mismatch")
    return errors


def _node_shape_errors(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} is not an object"]
    errors: list[str] = []
    if set(value) != {"headRef", "pullRequest", "repository", "type"}:
        errors.append(f"{label} schema mismatch")
    repository = value.get("repository")
    if not isinstance(repository, dict) or set(repository) != {"id", "nameWithOwner", "url"}:
        errors.append(f"{label} repository schema mismatch")
    errors.extend(_remote_pr_shape_errors(value.get("pullRequest"), label=f"{label} PR"))
    head_ref = value.get("headRef")
    if head_ref is not None:
        if not isinstance(head_ref, dict) or set(head_ref) != {"name", "prefix", "target"}:
            errors.append(f"{label} head-ref schema mismatch")
        else:
            target = head_ref.get("target")
            if not isinstance(target, dict) or set(target) != {"oid", "type"}:
                errors.append(f"{label} head-ref target schema mismatch")
    return errors


def _snapshot_shape_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["remote snapshot is not an object"]
    errors: list[str] = []
    if set(value) != {"node", "pr", "repository"}:
        errors.append("remote snapshot schema mismatch")
    repository = value.get("repository")
    if not isinstance(repository, dict) or set(repository) != {"id", "nameWithOwner", "url"}:
        errors.append("remote repository schema mismatch")
    errors.extend(_remote_pr_shape_errors(value.get("pr"), label="number-addressed PR"))
    errors.extend(_node_shape_errors(value.get("node"), label="node-addressed PR"))
    return errors


def _snapshot_errors(
    snapshot: Any,
    target: dict[str, Any],
    *,
    state: str,
) -> list[str]:
    errors = _snapshot_shape_errors(snapshot)
    if not isinstance(snapshot, dict):
        return errors
    expected_pr = _expected_pr(target, state=state)
    if not _json_exact_equal(snapshot.get("repository"), EXPECTED_REPOSITORY):
        errors.append("repository id/name/url drift")
    number_addressed_pr = snapshot.get("pr")
    expected_number_addressed_pr = copy.deepcopy(expected_pr)
    if isinstance(number_addressed_pr, dict):
        head_repository = number_addressed_pr.get("headRepository")
        if (
            isinstance(head_repository, dict)
            and head_repository.get("nameWithOwner") == ""
        ):
            # `gh pr view --json headRepository` can return an empty repository
            # name even when its ID and owner are present.  Accept only that
            # provider-specific omission here; the independently node-addressed
            # record below must still prove the exact nonempty name and full tuple.
            expected_number_addressed_pr["headRepository"]["nameWithOwner"] = ""
    if not _json_exact_equal(number_addressed_pr, expected_number_addressed_pr):
        errors.append("number-addressed PR immutable or expected-state drift")
    node = snapshot.get("node")
    if not isinstance(node, dict):
        errors.append("node-addressed PR snapshot is absent")
        return errors
    if node.get("type") != "PullRequest":
        errors.append("exact node is not a PullRequest")
    if not _json_exact_equal(node.get("repository"), EXPECTED_REPOSITORY):
        errors.append("node repository identity drift")
    if not _json_exact_equal(node.get("pullRequest"), expected_pr):
        errors.append("node-addressed PR immutable or expected-state drift")
    if not _json_exact_equal(node.get("headRef"), _expected_head_ref(target)):
        errors.append("head ref is missing, deleted, or rewritten")
    return errors


def _node_errors(
    node: Any,
    target: dict[str, Any],
    *,
    state: str,
) -> list[str]:
    errors = _node_shape_errors(node, label="terminal node response")
    if not isinstance(node, dict):
        return errors
    expected_pr = _expected_pr(target, state=state)
    if node.get("type") != "PullRequest":
        errors.append("terminal node type mismatch")
    if not _json_exact_equal(node.get("repository"), EXPECTED_REPOSITORY):
        errors.append("terminal repository identity drift")
    if not _json_exact_equal(node.get("pullRequest"), expected_pr):
        errors.append("terminal PR tuple mismatch")
    if not _json_exact_equal(node.get("headRef"), _expected_head_ref(target)):
        errors.append("terminal head ref is missing, deleted, or rewritten")
    return errors


def _close_exact_node(
    target: dict[str, Any],
    *,
    repo_root: Path,
    gh_runner: GhRunner,
) -> dict[str, Any]:
    result = _gh_json(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={_CLOSE_MUTATION}",
            "-F",
            f"id={target['id']}",
            "-F",
            f"headRef=refs/heads/{target['headRefName']}",
        ],
        cwd=repo_root,
        gh_runner=gh_runner,
        label=f"closePullRequest node mutation for PR #{target['number']}",
    )
    data = result.get("data")
    close = data.get("closePullRequest") if isinstance(data, dict) else None
    pr = close.get("pullRequest") if isinstance(close, dict) else None
    normalized = _normalized_node(pr)
    errors = _node_errors(normalized, target, state="CLOSED")
    if errors:
        raise ContractError(
            "closePullRequest returned contradictory terminal proof: "
            + "; ".join(errors)
        )
    return normalized


def _safe_remote_snapshot(
    target: dict[str, Any],
    *,
    repo_root: Path,
    gh_runner: GhRunner,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return (
            _read_remote_snapshot(target, repo_root=repo_root, gh_runner=gh_runner),
            None,
        )
    except Exception as exc:  # noqa: BLE001 - receipt must preserve ambiguity
        return None, f"{type(exc).__name__}: {exc}"


def _boundary_summary(boundary: Any) -> dict[str, Any]:
    source = boundary if isinstance(boundary, dict) else {}
    return {
        "action_error": source.get("action_error"),
        "action_invoked": source.get("action_invoked"),
        "action_succeeded": source.get("action_succeeded"),
        "authority_consumed": source.get("authority_consumed"),
        "decision": source.get("decision"),
        "operation_id": source.get("operation_id"),
        "reason": source.get("reason"),
    }


_RECEIPT_KEYS = {
    "after",
    "before",
    "comparison_commit",
    "intent",
    "intent_path",
    "manifest_sha256",
    "operation_id",
    "receipt_sha256",
    "reason",
    "repository",
    "schema_version",
    "status",
    "target",
    "terminal",
    "wave_id",
}


def _seal_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    if "receipt_sha256" in payload:
        raise ContractError("receipt payload was already sealed")
    sealed = copy.deepcopy(payload)
    sealed["receipt_sha256"] = _canonical_sha256(payload)
    return sealed


def _new_receipt(
    *,
    status: str,
    target: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
    operation_id: str | None,
    intent_path: Path | None,
    intent: dict[str, Any] | None,
    before: dict[str, Any] | None,
    terminal: dict[str, Any],
    after: dict[str, Any] | None,
    reason: str | None,
) -> dict[str, Any]:
    payload = {
        "after": copy.deepcopy(after),
        "before": copy.deepcopy(before),
        "comparison_commit": comparison_commit,
        "intent": copy.deepcopy(intent),
        "intent_path": str(intent_path) if intent_path is not None else None,
        "manifest_sha256": manifest_sha256,
        "operation_id": operation_id,
        "reason": reason,
        "repository": copy.deepcopy(EXPECTED_REPOSITORY),
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "status": status,
        "target": copy.deepcopy(target),
        "terminal": copy.deepcopy(terminal),
        "wave_id": WAVE_ID,
    }
    return _seal_receipt(payload)


def _read_receipt(path: Path) -> dict[str, Any]:
    receipt, _ = _read_canonical_json(path, label="PR disposition receipt")
    if set(receipt) != _RECEIPT_KEYS:
        raise ContractError(f"receipt has an unexpected schema: {path}")
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or _DIGEST_RE.fullmatch(claimed) is None:
        raise ContractError(f"receipt self-hash is invalid: {path}")
    unhashed = dict(receipt)
    del unhashed["receipt_sha256"]
    actual = _canonical_sha256(unhashed)
    if claimed != actual:
        raise ContractError(f"receipt self-hash mismatch: {path}")
    return receipt


def _is_error_observation(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"error"}
        and isinstance(value["error"], str)
        and bool(value["error"])
    )


_BOUNDARY_SUMMARY_KEYS = {
    "action_error",
    "action_invoked",
    "action_succeeded",
    "authority_consumed",
    "decision",
    "operation_id",
    "reason",
}


def _boundary_semantic_errors(
    value: Any,
    *,
    operation_id: str,
) -> list[str]:
    if not isinstance(value, dict):
        return ["boundary summary is not an object"]
    errors: list[str] = []
    if set(value) != _BOUNDARY_SUMMARY_KEYS:
        errors.append("boundary summary schema mismatch")
    if value.get("operation_id") != operation_id:
        errors.append("boundary operation id mismatch")
    decision = value.get("decision")
    if decision not in {
        "ACTION_COMPLETED",
        "ACTION_FAILED",
        "BOUNDARY_EXCEPTION",
        "HOLD",
    }:
        errors.append("boundary decision is invalid")
    for key in ("action_invoked", "action_succeeded", "authority_consumed"):
        if value.get(key) is not None and type(value.get(key)) is not bool:
            errors.append(f"boundary {key} is invalid")
    if value.get("action_invoked") is False and value.get("action_succeeded") is not None:
        errors.append("non-invoked boundary cannot report action success")
    if value.get("action_invoked") is True and value.get("authority_consumed") is not True:
        errors.append("invoked boundary lacks consumed authority")
    for key in ("action_error", "reason"):
        if value.get(key) is not None and not isinstance(value.get(key), str):
            errors.append(f"boundary {key} is invalid")
    tuple_value = (
        value.get("action_invoked"),
        value.get("action_succeeded"),
        value.get("authority_consumed"),
    )
    if decision == "ACTION_COMPLETED":
        if tuple_value != (True, True, True):
            errors.append("ACTION_COMPLETED boundary tuple is contradictory")
        if value.get("action_error") is not None or value.get("reason") is not None:
            errors.append("ACTION_COMPLETED boundary carries failure text")
    elif decision == "ACTION_FAILED":
        if tuple_value != (True, False, True):
            errors.append("ACTION_FAILED boundary tuple is contradictory")
        if not isinstance(value.get("action_error"), str) or not value.get("action_error"):
            errors.append("ACTION_FAILED boundary lacks action error")
        if not isinstance(value.get("reason"), str) or not value.get("reason"):
            errors.append("ACTION_FAILED boundary lacks reason")
    elif decision == "HOLD":
        if tuple_value != (False, None, False):
            errors.append("HOLD boundary tuple is contradictory")
        if not isinstance(value.get("reason"), str) or not value.get("reason"):
            errors.append("HOLD boundary lacks reason")
        if value.get("action_error") is not None:
            errors.append("HOLD boundary carries action error")
    elif decision == "BOUNDARY_EXCEPTION":
        if tuple_value != (None, False, None):
            errors.append("BOUNDARY_EXCEPTION tuple is contradictory")
        if not isinstance(value.get("action_error"), str) or not value.get("action_error"):
            errors.append("BOUNDARY_EXCEPTION lacks exception evidence")
        if not isinstance(value.get("reason"), str) or not value.get("reason"):
            errors.append("BOUNDARY_EXCEPTION lacks reason")
    return errors


def _observation_semantic_errors(
    value: Any,
    *,
    label: str,
    allow_none: bool,
    allow_error: bool,
) -> list[str]:
    if value is None:
        return [] if allow_none else [f"{label} observation is absent"]
    if _is_error_observation(value):
        return [] if allow_error else [f"{label} observation is only an error"]
    return [f"{label}: {item}" for item in _snapshot_shape_errors(value)]


def _receipt_semantic_errors(
    receipt: dict[str, Any],
    *,
    target: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
    repo_root: Path | None,
    common_dir: Path | None,
) -> list[str]:
    errors: list[str] = []
    common_expected = {
        "comparison_commit": comparison_commit,
        "manifest_sha256": manifest_sha256,
        "repository": EXPECTED_REPOSITORY,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "target": target,
        "wave_id": WAVE_ID,
    }
    for key, expected in common_expected.items():
        if not _json_exact_equal(receipt.get(key), expected):
            errors.append(f"receipt {key} mismatch")
    status = receipt.get("status")
    if status not in ALLOWED_STATUSES:
        errors.append("receipt status is invalid")
        return errors
    operation_id = receipt.get("operation_id")
    intent_path_value = receipt.get("intent_path")
    intent = receipt.get("intent")
    before = receipt.get("before")
    after = receipt.get("after")
    terminal = receipt.get("terminal")
    reason = receipt.get("reason")

    if status == "HOLD_SHARED_UNATTEMPTED":
        if any(value is not None for value in (operation_id, intent_path_value, intent, before, after)):
            errors.append("shared-unattempted receipt carries intent/action evidence")
        if not isinstance(reason, str) or not reason:
            errors.append("shared-unattempted receipt lacks reason")
        if not isinstance(terminal, dict) or set(terminal) != {
            "kind",
            "trigger_pr",
            "trigger_status",
        }:
            errors.append("shared-unattempted terminal schema mismatch")
        else:
            if terminal.get("kind") != "SHARED_UNATTEMPTED":
                errors.append("shared-unattempted terminal kind mismatch")
            trigger_pr = terminal.get("trigger_pr")
            if type(trigger_pr) is not int or trigger_pr not in EXPECTED_NUMBERS:
                errors.append("shared-unattempted trigger PR is invalid")
            if terminal.get("trigger_status") not in {
                "HOLD_REMOTE_DRIFT",
                "HOLD_ACTION_OR_POSTVERIFY",
            }:
                errors.append("shared-unattempted trigger status is invalid")
        return errors

    if not isinstance(operation_id, str) or _OPERATION_ID_RE.fullmatch(operation_id) is None:
        errors.append("attempted receipt operation id is invalid")
    if not isinstance(intent_path_value, str):
        errors.append("attempted receipt intent path is absent")
    else:
        path = Path(intent_path_value)
        suffix = (INTENT_ROOT_NAME, WAVE_ID, f"pr-{target['number']}.json")
        if not path.is_absolute() or tuple(path.parts[-3:]) != suffix:
            errors.append("attempted receipt intent path is not the exact PR path")
        if intent_path_value != os.path.normpath(intent_path_value) or intent_path_value != str(path):
            errors.append("attempted receipt intent path is not lexically canonical")
        if common_dir is not None and path != _intent_path(common_dir, target["number"]):
            errors.append("attempted receipt intent path is outside the active common dir")
    if not isinstance(intent, dict):
        errors.append("attempted receipt does not embed its intent")
    else:
        errors.extend(
            _intent_errors(
                intent,
                target=target,
                comparison_commit=comparison_commit,
                manifest_sha256=manifest_sha256,
                repo_root=repo_root,
                common_dir=common_dir,
            )
        )
        if intent.get("operation_id") != operation_id:
            errors.append("receipt and intent operation ids differ")
        identity = intent.get("terminal_target_identity")
        if isinstance(identity, dict):
            common_identity = identity.get("common_dir_identity")
            if isinstance(common_identity, dict) and isinstance(
                common_identity.get("path"), str
            ) and isinstance(intent_path_value, str):
                embedded_common = Path(common_identity["path"])
                embedded_expected = _intent_path(embedded_common, target["number"])
                if Path(intent_path_value) != embedded_expected:
                    errors.append("intent path is not bound to embedded common-dir identity")

    if status == "CLOSED":
        if reason is not None:
            errors.append("CLOSED receipt cannot carry a reason")
        errors.extend(f"before: {item}" for item in _snapshot_errors(before, target, state="OPEN"))
        errors.extend(f"after: {item}" for item in _snapshot_errors(after, target, state="CLOSED"))
        if not isinstance(terminal, dict) or set(terminal) != {
            "boundary",
            "close_response",
            "kind",
        }:
            errors.append("CLOSED terminal schema mismatch")
        else:
            if terminal.get("kind") != "CLOSE_CONFIRMED":
                errors.append("CLOSED terminal kind mismatch")
            errors.extend(
                f"terminal: {item}"
                for item in _node_errors(terminal.get("close_response"), target, state="CLOSED")
            )
            boundary = terminal.get("boundary")
            errors.extend(
                f"terminal: {item}"
                for item in _boundary_semantic_errors(
                    boundary, operation_id=str(operation_id)
                )
            )
            if not isinstance(boundary, dict) or (
                boundary.get("decision"),
                boundary.get("authority_consumed"),
                boundary.get("action_invoked"),
                boundary.get("action_succeeded"),
            ) != ("ACTION_COMPLETED", True, True, True):
                errors.append("CLOSED boundary state machine is contradictory")
        if isinstance(intent, dict):
            if intent.get("state") != "CLOSE_RESPONSE_OBSERVED":
                errors.append("CLOSED intent did not reach close-response state")
            if not _json_exact_equal(intent.get("callback_snapshot"), before):
                errors.append("CLOSED before proof differs from callback proof")
            if isinstance(terminal, dict) and not _json_exact_equal(
                intent.get("close_response"), terminal.get("close_response")
            ):
                errors.append("CLOSED terminal proof differs from intent proof")
    elif status == "CLOSED_RECONCILED":
        if reason is not None:
            errors.append("CLOSED_RECONCILED receipt cannot carry a reason")
        errors.extend(f"after: {item}" for item in _snapshot_errors(after, target, state="CLOSED"))
        if before is not None:
            errors.extend(
                f"before: {item}" for item in _snapshot_errors(before, target, state="OPEN")
            )
        if not isinstance(terminal, dict) or set(terminal) != {"intent_state", "kind"}:
            errors.append("CLOSED_RECONCILED terminal schema mismatch")
        else:
            if terminal.get("kind") != "RESTART_INTENT_RECONCILIATION":
                errors.append("CLOSED_RECONCILED terminal kind mismatch")
            if isinstance(intent, dict) and terminal.get("intent_state") != intent.get("state"):
                errors.append("reconciled terminal/intent state mismatch")
        if isinstance(intent, dict):
            expected_before = intent.get("callback_snapshot")
            if expected_before is not None and _snapshot_errors(
                expected_before, target, state="OPEN"
            ):
                expected_before = None
            if not _json_exact_equal(before, expected_before):
                errors.append("reconciled before proof differs from intent proof")
    elif status == "HOLD_REMOTE_DRIFT":
        if not isinstance(reason, str) or not reason:
            errors.append("remote-drift HOLD lacks reason")
        drift = _snapshot_errors(before, target, state="OPEN")
        if not drift:
            errors.append("remote-drift HOLD has an exact OPEN before snapshot")
        if not isinstance(terminal, dict) or set(terminal) != {
            "boundary",
            "drift",
            "kind",
        }:
            errors.append("remote-drift terminal schema mismatch")
        else:
            if terminal.get("kind") != "REMOTE_DRIFT_NO_ACTION":
                errors.append("remote-drift terminal kind mismatch")
            if not _json_exact_equal(terminal.get("drift"), drift):
                errors.append("remote-drift reasons do not match actual snapshot")
            boundary = terminal.get("boundary")
            errors.extend(
                f"terminal: {item}"
                for item in _boundary_semantic_errors(
                    boundary, operation_id=str(operation_id)
                )
            )
            if not isinstance(boundary, dict) or (
                boundary.get("decision"),
                boundary.get("authority_consumed"),
                boundary.get("action_invoked"),
                boundary.get("action_succeeded"),
            ) != ("ACTION_COMPLETED", True, True, True):
                errors.append("remote-drift boundary state machine is contradictory")
        if isinstance(intent, dict):
            if intent.get("state") != "REMOTE_DRIFT_NO_ACTION":
                errors.append("remote-drift intent state mismatch")
            if not _json_exact_equal(intent.get("callback_snapshot"), before):
                errors.append("remote-drift before proof differs from intent proof")
            if not _json_exact_equal(intent.get("callback_drift"), drift):
                errors.append("remote-drift intent reasons mismatch")
        if after is not None and not isinstance(after, dict):
            errors.append("remote-drift after observation is invalid")
        errors.extend(
            _observation_semantic_errors(
                after,
                label="remote-drift after",
                allow_none=False,
                allow_error=True,
            )
        )
    elif status == "HOLD_ACTION_OR_POSTVERIFY":
        if not isinstance(reason, str) or not reason:
            errors.append("action/postverify HOLD lacks reason")
        if not isinstance(terminal, dict) or terminal.get("kind") not in {
            "ACTION_OR_POSTVERIFY_HOLD",
            "RESTART_NO_REPLAY",
        }:
            errors.append("action/postverify HOLD terminal kind mismatch")
        elif terminal.get("kind") == "RESTART_NO_REPLAY":
            if set(terminal) != {"intent_state", "kind"}:
                errors.append("restart HOLD terminal schema mismatch")
            elif isinstance(intent, dict) and terminal.get("intent_state") != intent.get("state"):
                errors.append("restart HOLD terminal/intent state mismatch")
            if isinstance(after, dict) and not _snapshot_errors(after, target, state="CLOSED"):
                errors.append("restart exact CLOSED proof must be CLOSED_RECONCILED")
            if isinstance(intent, dict):
                expected_before = intent.get("callback_snapshot")
                if expected_before is not None and _snapshot_errors(
                    expected_before, target, state="OPEN"
                ):
                    expected_before = None
                if not _json_exact_equal(before, expected_before):
                    errors.append("restart before proof differs from intent proof")
        else:
            if set(terminal) != {"boundary", "callback", "kind", "postverify_error"}:
                errors.append("fresh action/postverify HOLD terminal schema mismatch")
            boundary = terminal.get("boundary")
            if not isinstance(boundary, dict):
                errors.append("fresh action/postverify HOLD lacks boundary summary")
            else:
                errors.extend(
                    f"terminal: {item}"
                    for item in _boundary_semantic_errors(
                        boundary, operation_id=str(operation_id)
                    )
                )
            callback = terminal.get("callback")
            postverify_error = terminal.get("postverify_error")
            if postverify_error is not None and not isinstance(postverify_error, str):
                errors.append("postverify error is invalid")
            if _is_error_observation(after):
                if postverify_error != after["error"]:
                    errors.append("postverify error does not match after observation")
            elif after is not None and postverify_error is not None:
                errors.append("successful postverify observation carries an error")
            if callback is not None:
                if not isinstance(callback, dict) or set(callback) != {
                    "close_response",
                    "kind",
                }:
                    errors.append("fresh action/postverify callback schema mismatch")
                elif callback.get("kind") != "CLOSE_INVOKED":
                    errors.append("fresh action/postverify callback kind mismatch")
                else:
                    errors.extend(
                        f"callback: {item}"
                        for item in _node_errors(
                            callback.get("close_response"), target, state="CLOSED"
                        )
                    )
            intent_state = intent.get("state") if isinstance(intent, dict) else None
            callback_is_close = (
                isinstance(callback, dict) and callback.get("kind") == "CLOSE_INVOKED"
            )
            if callback_is_close and intent_state not in {
                "CALLBACK_VALIDATED_CLOSE_PENDING",
                "CLOSE_RESPONSE_OBSERVED",
            }:
                errors.append("close callback contradicts durable intent state")
            if intent_state == "CLOSE_RESPONSE_OBSERVED":
                if not callback_is_close:
                    errors.append("close-observed intent lacks callback proof")
                elif not _json_exact_equal(
                    callback.get("close_response"), intent.get("close_response")
                ):
                    errors.append("callback close proof differs from intent proof")
            if intent_state in {
                "REMOTE_DRIFT_NO_ACTION",
                "CALLBACK_VALIDATED_CLOSE_PENDING",
                "CLOSE_RESPONSE_OBSERVED",
            } and not _json_exact_equal(before, intent.get("callback_snapshot")):
                errors.append("fresh HOLD before proof differs from intent proof")
            if isinstance(boundary, dict):
                decision = boundary.get("decision")
                if decision == "HOLD":
                    if callback is not None or before is not None:
                        errors.append("pre-callback boundary HOLD carries callback proof")
                    if isinstance(intent, dict) and intent.get("state") != "PREPARED":
                        errors.append("pre-callback boundary HOLD intent state is contradictory")
                elif decision == "ACTION_COMPLETED":
                    if not isinstance(callback, dict) or callback.get("kind") != "CLOSE_INVOKED":
                        errors.append("ACTION_COMPLETED HOLD lacks close callback proof")
                    if isinstance(intent, dict) and intent.get("state") != "CLOSE_RESPONSE_OBSERVED":
                        errors.append("ACTION_COMPLETED HOLD intent state is contradictory")
            if (
                isinstance(boundary, dict)
                and boundary.get("decision") == "ACTION_COMPLETED"
                and boundary.get("authority_consumed") is True
                and boundary.get("action_invoked") is True
                and boundary.get("action_succeeded") is True
                and isinstance(callback, dict)
                and callback.get("kind") == "CLOSE_INVOKED"
                and not _node_errors(callback.get("close_response"), target, state="CLOSED")
                and not _snapshot_errors(after, target, state="CLOSED")
            ):
                errors.append("confirmed close/postverify proof cannot remain HOLD")
        if before is not None and not isinstance(before, dict):
            errors.append("action/postverify before observation is invalid")
        if after is not None and not isinstance(after, dict):
            errors.append("action/postverify after observation is invalid")
        errors.extend(
            _observation_semantic_errors(
                before,
                label="action/postverify before",
                allow_none=True,
                allow_error=False,
            )
        )
        errors.extend(
            _observation_semantic_errors(
                after,
                label="action/postverify after",
                allow_none=False,
                allow_error=True,
            )
        )
    return errors


def _validate_receipt_for_target(
    path: Path,
    *,
    target: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
    repo_root: Path | None = None,
    common_dir: Path | None = None,
) -> dict[str, Any]:
    receipt = _read_receipt(path)
    errors = _receipt_semantic_errors(
        receipt,
        target=target,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
        repo_root=repo_root,
        common_dir=common_dir,
    )
    if errors:
        raise ContractError(f"invalid receipt {path}: " + "; ".join(errors))
    return receipt


def _shared_causality_errors(
    receipts_by_number: dict[int, dict[str, Any]],
) -> list[str]:
    """Require the canonical complete-prefix then one-root shared-stop shape."""
    errors: list[str] = []
    root: tuple[int, str] | None = None
    for number in EXPECTED_NUMBERS:
        receipt = receipts_by_number.get(number)
        if receipt is None:
            continue
        status = receipt.get("status")
        if root is None:
            if status == "HOLD_SHARED_UNATTEMPTED":
                errors.append(f"shared HOLD for PR #{number} has no earlier root HOLD")
            elif status in {"HOLD_REMOTE_DRIFT", "HOLD_ACTION_OR_POSTVERIFY"}:
                root = (number, str(status))
            continue
        if status != "HOLD_SHARED_UNATTEMPTED":
            errors.append(
                f"receipt for PR #{number} is attempted after shared-stop root PR #{root[0]}"
            )
            continue
        terminal = receipt.get("terminal")
        if not isinstance(terminal, dict) or (
            terminal.get("trigger_pr"), terminal.get("trigger_status")
        ) != root:
            errors.append(f"shared HOLD for PR #{number} contradicts the root HOLD")
    return errors


def verify_receipts(
    manifest_path: Path | str,
    *,
    comparison_commit: str,
    receipts_dir: Path | str,
    repository: str = REPOSITORY_NAME,
) -> dict[str, Any]:
    """Semantically verify one canonical receipt for each literal target."""
    if _SHA_RE.fullmatch(comparison_commit) is None:
        raise ContractError("comparison commit must be an exact lowercase 40-hex SHA")
    validated = validate_manifest_contract(manifest_path, repository=repository)
    manifest_sha256 = validated["manifest_sha256"]
    directory = Path(receipts_dir)
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        raise ContractError(f"cannot enumerate receipt directory {directory}: {exc}") from exc
    expected_names = {f"pr-{number}.json" for number in EXPECTED_NUMBERS}
    actual_names = {entry.name for entry in entries}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ContractError(
            f"receipt batch is not exactly eight targets; missing={missing}, extra={extra}"
        )
    receipts: list[dict[str, Any]] = []
    receipts_by_number: dict[int, dict[str, Any]] = {}
    operation_ids: set[str] = set()
    intent_paths: set[str] = set()
    batch_common_identity: dict[str, Any] | None = None
    for target in EXPECTED_TARGETS:
        path = _receipt_path(directory, target["number"])
        receipt = _validate_receipt_for_target(
            path,
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
        )
        operation_id = receipt["operation_id"]
        if operation_id is not None:
            if operation_id in operation_ids:
                raise ContractError(f"duplicate operation id in receipt batch: {operation_id}")
            operation_ids.add(operation_id)
            common_identity = receipt["intent"]["terminal_target_identity"][
                "common_dir_identity"
            ]
            if batch_common_identity is None:
                batch_common_identity = copy.deepcopy(common_identity)
            elif not _json_exact_equal(batch_common_identity, common_identity):
                raise ContractError(
                    "attempted receipts do not share one common-dir identity"
                )
        intent_path_value = receipt["intent_path"]
        if intent_path_value is not None:
            if intent_path_value in intent_paths:
                raise ContractError(
                    f"duplicate intent path in receipt batch: {intent_path_value}"
                )
            intent_paths.add(intent_path_value)
        receipts.append(receipt)
        receipts_by_number[target["number"]] = receipt
    causality_errors = _shared_causality_errors(receipts_by_number)
    if causality_errors:
        raise ContractError("invalid shared HOLD causality: " + "; ".join(causality_errors))
    holds = [receipt["target"]["number"] for receipt in receipts if receipt["status"] in HOLD_STATUSES]
    return {
        "decision": "VERIFIED",
        "has_hold": bool(holds),
        "hold_targets": holds,
        "manifest_sha256": manifest_sha256,
        "receipt_count": len(receipts),
        "repository": REPOSITORY_NAME,
        "statuses": {
            str(receipt["target"]["number"]): receipt["status"]
            for receipt in receipts
        },
        "wave_id": WAVE_ID,
    }


def requires_terminal_sweep(wave_id: str) -> bool:
    """Return whether *wave_id* is the consumed Apply-R2 landing carrier."""
    return str(wave_id or "").strip() == TERMINAL_SWEEP_WAVE_ID


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _path_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    info = resolved.stat()
    return {
        "device": int(info.st_dev),
        "inode": int(info.st_ino),
        "path": str(resolved),
    }


def _parse_worktree_porcelain(raw: str) -> list[dict[str, Any]]:
    worktrees: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in [*raw.splitlines(), ""]:
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value if value else True
    return sorted(worktrees, key=lambda item: str(item.get("worktree") or ""))


def _terminal_cleanup_snapshot(
    repo_root: Path,
    *,
    git_run: Callable[..., subprocess.CompletedProcess[Any]] = _default_git_run,
) -> dict[str, Any]:
    """Capture exact local refs/worktrees/stashes surrounding carrier cleanup."""
    branch_output = _git_stdout(
        [
            "git",
            "for-each-ref",
            "--format=%(refname)%00%(objectname)",
            "refs/heads",
        ],
        cwd=repo_root,
        git_run=git_run,
    )
    branches: dict[str, str] = {}
    for row in branch_output.splitlines():
        ref, separator, oid = row.partition("\0")
        if not separator or not ref or _SHA_RE.fullmatch(oid) is None:
            raise ContractError("local branch snapshot contains an invalid ref row")
        branches[ref] = oid

    worktree_output = _git_stdout(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        git_run=git_run,
    )
    stash_output = _git_stdout(
        ["git", "stash", "list", "--format=%H%x00%gs"],
        cwd=repo_root,
        git_run=git_run,
    )
    stashes: list[dict[str, str]] = []
    for row in stash_output.splitlines():
        oid, separator, subject = row.partition("\0")
        if not separator or _SHA_RE.fullmatch(oid) is None:
            raise ContractError("stash snapshot contains an invalid row")
        stashes.append({"oid": oid, "subject": subject})
    return {
        "branches": dict(sorted(branches.items())),
        "stashes": stashes,
        "worktrees": _parse_worktree_porcelain(worktree_output),
    }


def _terminal_evidence_contract(
    *,
    comparison_commit: str,
    manifest_path: Path,
    packet_path: Path,
    receipts_dir: Path,
    expected_packet_sha256: str,
    expected_candidate_sha256: str,
) -> dict[str, Any]:
    return {
        "comparison_commit": comparison_commit,
        "expected_candidate_sha256": expected_candidate_sha256,
        "expected_packet_sha256": expected_packet_sha256,
        "manifest_path": str(manifest_path),
        "packet_path": str(packet_path),
        "receipts_dir": str(receipts_dir),
        "source_wave_id": TERMINAL_SWEEP_WAVE_ID,
    }


def _collect_terminal_evidence(
    repo_root: Path,
    common_dir: Path,
    *,
    contract: dict[str, Any],
    candidate_sha256: str,
    include_remote: bool,
    gh_runner: GhRunner,
) -> tuple[dict[str, Any], list[str]]:
    """Collect fixed R2 artifacts/intents and optional fresh provider proof."""
    errors: list[str] = []
    comparison_commit = str(contract.get("comparison_commit") or "")
    manifest_path = Path(str(contract.get("manifest_path") or ""))
    packet_path = Path(str(contract.get("packet_path") or ""))
    receipts_dir = Path(str(contract.get("receipts_dir") or ""))
    expected_packet_sha256 = str(contract.get("expected_packet_sha256") or "")
    expected_candidate_sha256 = str(
        contract.get("expected_candidate_sha256") or ""
    )
    evidence: dict[str, Any] = {
        "candidate_sha256": candidate_sha256,
        "comparison_commit": comparison_commit,
        "intents": [],
        "manifest": None,
        "packet": None,
        "receipts": [],
        "remote_observations": [],
        "result": "HOLD",
        "target_numbers": list(EXPECTED_NUMBERS),
    }

    if _DIGEST_RE.fullmatch(candidate_sha256) is None:
        errors.append("R2 staged-candidate SHA-256 is missing or invalid")
    elif candidate_sha256 != expected_candidate_sha256:
        errors.append("R2 staged-candidate SHA-256 mismatch")

    manifest_sha256 = ""
    try:
        validated = validate_manifest_contract(manifest_path)
        manifest_sha256 = str(validated["manifest_sha256"])
        evidence["manifest"] = {
            "path": str(manifest_path),
            "raw_sha256": _sha256_bytes(validated["raw_bytes"]),
            "self_sha256": manifest_sha256,
        }
    except (ContractError, OSError) as exc:
        errors.append(f"manifest evidence failed: {exc}")

    try:
        packet_raw = _read_regular_bytes(packet_path, label="Apply R2 packet")
        packet_sha256 = _sha256_bytes(packet_raw)
        evidence["packet"] = {
            "path": str(packet_path),
            "sha256": packet_sha256,
        }
        if packet_sha256 != expected_packet_sha256:
            errors.append("Apply R2 packet SHA-256 mismatch")
    except ContractError as exc:
        errors.append(f"packet evidence failed: {exc}")

    if manifest_sha256:
        try:
            verified = verify_receipts(
                manifest_path,
                comparison_commit=comparison_commit,
                receipts_dir=receipts_dir,
            )
            if verified.get("has_hold") is not False:
                errors.append("Apply R2 receipt batch contains a HOLD")
            if verified.get("receipt_count") != len(EXPECTED_TARGETS):
                errors.append("Apply R2 receipt batch count mismatch")
        except ContractError as exc:
            errors.append(f"receipt batch verification failed: {exc}")

        for target in EXPECTED_TARGETS:
            number = target["number"]
            receipt_path = _receipt_path(receipts_dir, number)
            intent_path = _intent_path(common_dir, number)
            receipt: dict[str, Any] | None = None
            intent: dict[str, Any] | None = None
            binding_equivalent = False
            try:
                receipt_raw = _read_regular_bytes(
                    receipt_path, label=f"Apply R2 receipt PR #{number}"
                )
                receipt = _validate_receipt_for_target(
                    receipt_path,
                    target=target,
                    comparison_commit=comparison_commit,
                    manifest_sha256=manifest_sha256,
                    repo_root=None,
                    common_dir=common_dir,
                )
                if receipt.get("status") not in COMPLETE_STATUSES:
                    errors.append(f"PR #{number} receipt is not complete")
                evidence["receipts"].append(
                    {
                        "number": number,
                        "operation_id": receipt.get("operation_id"),
                        "path": str(receipt_path),
                        "receipt_sha256": receipt.get("receipt_sha256"),
                        "raw_sha256": _sha256_bytes(receipt_raw),
                        "status": receipt.get("status"),
                    }
                )
            except ContractError as exc:
                errors.append(f"PR #{number} receipt evidence failed: {exc}")

            try:
                intent, intent_raw = _read_canonical_json(
                    intent_path, label=f"Apply R2 intent PR #{number}"
                )
                intent_errors = _intent_errors(
                    intent,
                    target=target,
                    comparison_commit=comparison_commit,
                    manifest_sha256=manifest_sha256,
                    repo_root=None,
                    common_dir=common_dir,
                )
                if intent_errors:
                    raise ContractError("; ".join(intent_errors))
                binding_equivalent = bool(
                    receipt is not None
                    and receipt.get("intent_path") == str(intent_path)
                    and _json_exact_equal(receipt.get("intent"), intent)
                    and receipt.get("operation_id") == intent.get("operation_id")
                )
                if not binding_equivalent:
                    errors.append(
                        f"PR #{number} receipt/intent binding is not equivalent"
                    )
                evidence["intents"].append(
                    {
                        "binding_equivalent": binding_equivalent,
                        "number": number,
                        "operation_id": intent.get("operation_id"),
                        "path": str(intent_path),
                        "raw_sha256": _sha256_bytes(intent_raw),
                        "state": intent.get("state"),
                    }
                )
            except ContractError as exc:
                errors.append(f"PR #{number} intent evidence failed: {exc}")

            if include_remote:
                try:
                    snapshot = _read_remote_snapshot(
                        target, repo_root=repo_root, gh_runner=gh_runner
                    )
                    snapshot_errors = _snapshot_errors(
                        snapshot, target, state="CLOSED"
                    )
                    if snapshot_errors:
                        errors.extend(
                            f"PR #{number} terminal observation: {item}"
                            for item in snapshot_errors
                        )
                    evidence["remote_observations"].append(
                        {
                            "errors": snapshot_errors,
                            "number": number,
                            "snapshot": snapshot,
                        }
                    )
                except ContractError as exc:
                    errors.append(f"PR #{number} terminal observation failed: {exc}")

    if len(evidence["receipts"]) != len(EXPECTED_TARGETS):
        errors.append("terminal evidence does not contain exactly eight receipts")
    if len(evidence["intents"]) != len(EXPECTED_TARGETS):
        errors.append("terminal evidence does not contain exactly eight intents")
    if include_remote and len(evidence["remote_observations"]) != len(EXPECTED_TARGETS):
        errors.append("terminal evidence does not contain exactly eight fresh observations")
    if not errors:
        evidence["result"] = "PASS"
    return evidence, errors


def _terminal_receipt_path(common_dir: Path, wave_id: str, merge_sha: str) -> Path:
    return common_dir / TERMINAL_RECEIPT_ROOT_NAME / wave_id / f"{merge_sha}.json"


def _seal_terminal_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    sealed = copy.deepcopy(payload)
    sealed.pop("receipt_sha256", None)
    sealed["receipt_sha256"] = _canonical_sha256(sealed)
    return sealed


def _write_new_terminal_receipt(path: Path, payload: dict[str, Any]) -> None:
    try:
        _write_json_exclusive(path, payload)
    except FileExistsError as exc:
        raise ContractError(
            f"terminal receipt already exists and was not overwritten: {path}"
        ) from exc


def _owned_cleanup_stash(
    stash: dict[str, Any], *, wave_id: str, target_branch: str
) -> bool:
    subject = str(stash.get("subject") or "")
    return any(
        marker in subject
        for marker in (f"phase_b:{target_branch}:", f"phase_b:{wave_id}:")
    )


def _terminal_cleanup_errors(
    *,
    receipt: dict[str, Any],
    cleanup_result: Any,
    post_snapshot: Any,
) -> list[str]:
    errors: list[str] = []
    authority = receipt.get("cleanup_authority")
    if not isinstance(authority, dict):
        return ["cleanup authority is absent"]
    pre_snapshot = authority.get("pre_snapshot")
    if not isinstance(pre_snapshot, dict) or not isinstance(post_snapshot, dict):
        return ["cleanup snapshots are incomplete"]
    if not isinstance(cleanup_result, dict):
        return ["cleanup result is absent"]
    required_result_keys = {
        "branch_deleted",
        "stashes_dropped",
        "warnings",
        "worktree_removed",
    }
    if set(cleanup_result) != required_result_keys:
        errors.append("cleanup result schema mismatch")
    if cleanup_result.get("branch_deleted") is not True:
        errors.append("authorized carrier branch was not deleted")
    expected_worktree_remove = authority.get("remove_carrier_worktree") is True
    if cleanup_result.get("worktree_removed") is not expected_worktree_remove:
        errors.append("carrier worktree cleanup result mismatch")
    warnings = cleanup_result.get("warnings")
    if not isinstance(warnings, list) or warnings:
        errors.append("carrier cleanup reported warnings")

    target_ref = str(authority.get("target_ref") or "")
    pre_branches = pre_snapshot.get("branches")
    post_branches = post_snapshot.get("branches")
    if not isinstance(pre_branches, dict) or not isinstance(post_branches, dict):
        errors.append("branch cleanup snapshots are invalid")
    else:
        expected_branches = dict(pre_branches)
        expected_branches.pop(target_ref, None)
        if not _json_exact_equal(post_branches, expected_branches):
            errors.append("cleanup changed refs outside the authorized carrier ref")

    pre_worktrees = pre_snapshot.get("worktrees")
    post_worktrees = post_snapshot.get("worktrees")
    if not isinstance(pre_worktrees, list) or not isinstance(post_worktrees, list):
        errors.append("worktree cleanup snapshots are invalid")
    else:
        carrier_path = str(authority.get("carrier_root") or "")
        expected_worktrees = [
            item
            for item in pre_worktrees
            if not (
                expected_worktree_remove
                and isinstance(item, dict)
                and item.get("worktree") == carrier_path
            )
        ]
        if not _json_exact_equal(post_worktrees, expected_worktrees):
            errors.append("cleanup changed worktrees outside the authorized carrier")

    pre_stashes = pre_snapshot.get("stashes")
    post_stashes = post_snapshot.get("stashes")
    if not isinstance(pre_stashes, list) or not isinstance(post_stashes, list):
        errors.append("stash cleanup snapshots are invalid")
    else:
        expected_stashes = [
            stash
            for stash in pre_stashes
            if not _owned_cleanup_stash(
                stash,
                wave_id=str(receipt.get("wave_id") or ""),
                target_branch=str(authority.get("target_branch") or ""),
            )
        ]
        removed_count = len(pre_stashes) - len(expected_stashes)
        if cleanup_result.get("stashes_dropped") != removed_count:
            errors.append("wave-owned stash cleanup count mismatch")
        if not _json_exact_equal(post_stashes, expected_stashes):
            errors.append("cleanup changed stashes outside the wave-owned set")
    return errors


def prepare_terminal_sweep_receipt(
    repo_root: Path | str,
    *,
    carrier_root: Path | str,
    wave_id: str,
    merge_sha: str,
    carrier_commit_sha: str,
    target_branch: str,
    base_branch: str,
    candidate_sha256: str,
    manifest_path: Path | str | None = None,
    packet_path: Path | str | None = None,
    receipts_dir: Path | str | None = None,
    comparison_commit: str = TERMINAL_SWEEP_COMPARISON_COMMIT,
    expected_packet_sha256: str = TERMINAL_SWEEP_PACKET_SHA256,
    expected_candidate_sha256: str = TERMINAL_SWEEP_CANDIDATE_SHA256,
    git_run: Callable[..., subprocess.CompletedProcess[Any]] = _default_git_run,
    gh_runner: GhRunner | None = None,
) -> dict[str, Any]:
    """Persist PREPARED evidence before the Apply-R2 carrier is cleaned."""
    if not requires_terminal_sweep(wave_id):
        raise ContractError(f"terminal sweep is not authorized for wave {wave_id!r}")
    if _SHA_RE.fullmatch(merge_sha) is None:
        raise ContractError("terminal sweep merge SHA must be exact lowercase 40-hex")
    if _SHA_RE.fullmatch(carrier_commit_sha) is None:
        raise ContractError("terminal sweep carrier commit must be exact lowercase 40-hex")
    survivor = Path(repo_root).resolve(strict=True)
    carrier = Path(carrier_root).resolve(strict=True)
    common_dir = _resolve_common_git_dir(survivor, git_run=git_run)
    if _resolve_common_git_dir(carrier, git_run=git_run) != common_dir:
        raise ContractError("cleanup carrier and surviving root have different common Git dirs")

    manifest = Path(manifest_path) if manifest_path is not None else survivor / MANIFEST_RELATIVE_PATH
    packet = Path(packet_path) if packet_path is not None else survivor / TERMINAL_SWEEP_PACKET_RELATIVE_PATH
    receipt_root = Path(receipts_dir) if receipts_dir is not None else survivor / TERMINAL_SWEEP_RECEIPTS_RELATIVE_PATH
    contract = _terminal_evidence_contract(
        comparison_commit=comparison_commit,
        manifest_path=manifest.resolve(strict=False),
        packet_path=packet.resolve(strict=False),
        receipts_dir=receipt_root.resolve(strict=False),
        expected_packet_sha256=expected_packet_sha256,
        expected_candidate_sha256=expected_candidate_sha256,
    )
    errors: list[str] = []
    try:
        snapshot = _terminal_cleanup_snapshot(survivor, git_run=git_run)
    except ContractError as exc:
        snapshot = None
        errors.append(f"pre-cleanup snapshot failed: {exc}")

    target_ref = f"refs/heads/{target_branch}"
    branch_sha = (
        snapshot.get("branches", {}).get(target_ref)
        if isinstance(snapshot, dict)
        else None
    )
    if branch_sha != carrier_commit_sha:
        errors.append("authorized carrier ref does not match its exact commit")
    carrier_is_linked = (
        carrier != survivor and (carrier / ".git").is_file()
    )
    if carrier_is_linked and isinstance(snapshot, dict):
        matches = [
            entry
            for entry in snapshot.get("worktrees", [])
            if isinstance(entry, dict)
            and entry.get("worktree") == str(carrier)
            and entry.get("branch") == target_ref
            and entry.get("HEAD") == carrier_commit_sha
        ]
        if len(matches) != 1:
            errors.append("authorized linked carrier registration mismatch")

    evidence, evidence_errors = _collect_terminal_evidence(
        survivor,
        common_dir,
        contract=contract,
        candidate_sha256=candidate_sha256,
        include_remote=False,
        gh_runner=gh_runner or _default_gh_runner,
    )
    errors.extend(evidence_errors)
    now = datetime.now(timezone.utc).isoformat()
    payload = _seal_terminal_receipt(
        {
            "cleanup_authority": {
                "base_branch": base_branch,
                "carrier_commit_sha": carrier_commit_sha,
                "carrier_identity": _path_identity(carrier),
                "carrier_root": str(carrier),
                "pre_snapshot": snapshot,
                "remove_carrier_worktree": carrier_is_linked,
                "target_branch": target_branch,
                "target_ref": target_ref,
            },
            "cleanup_result": None,
            "cleanup_validation": {"errors": [], "result": "PENDING"},
            "common_git_dir_identity": _path_identity(common_dir),
            "completed_at_utc": None,
            "created_at_utc": now,
            "decision": "PREPARED",
            "errors": errors,
            "evidence_contract": contract,
            "merge_sha": merge_sha,
            "post_cleanup_evidence": None,
            "pre_cleanup_evidence": evidence,
            "route_candidate": None,
            "schema_version": TERMINAL_RECEIPT_SCHEMA_VERSION,
            "surviving_repo_root_identity": _path_identity(survivor),
            "wave_id": wave_id,
        }
    )
    path = _terminal_receipt_path(common_dir, wave_id, merge_sha)
    _write_new_terminal_receipt(path, payload)
    return {"receipt": payload, "receipt_path": str(path)}


def finalize_terminal_sweep_receipt(
    repo_root: Path | str,
    prepared: dict[str, Any],
    *,
    cleanup_result: dict[str, Any],
    git_run: Callable[..., subprocess.CompletedProcess[Any]] = _default_git_run,
    gh_runner: GhRunner | None = None,
) -> dict[str, Any]:
    """Run landed post-cleanup proof and atomically finalize PASS or HOLD."""
    survivor = Path(repo_root).resolve(strict=True)
    common_dir = _resolve_common_git_dir(survivor, git_run=git_run)
    path_value = prepared.get("receipt_path") if isinstance(prepared, dict) else None
    if not isinstance(path_value, str) or not path_value:
        raise ContractError("prepared terminal receipt path is absent")
    path = Path(path_value)
    expected_path = _terminal_receipt_path(
        common_dir,
        str(prepared.get("receipt", {}).get("wave_id") or ""),
        str(prepared.get("receipt", {}).get("merge_sha") or ""),
    )
    if path != expected_path:
        raise ContractError("prepared terminal receipt path/common-dir binding mismatch")
    current, _ = _read_canonical_json(path, label="prepared terminal receipt")
    if not _json_exact_equal(current, prepared.get("receipt")):
        raise ContractError("prepared terminal receipt changed before finalization")
    if current.get("decision") != "PREPARED":
        raise ContractError("terminal receipt is not PREPARED")

    errors = list(current.get("errors") or [])
    try:
        post_snapshot = _terminal_cleanup_snapshot(survivor, git_run=git_run)
    except ContractError as exc:
        post_snapshot = None
        errors.append(f"post-cleanup snapshot failed: {exc}")
    cleanup_errors = _terminal_cleanup_errors(
        receipt=current,
        cleanup_result=cleanup_result,
        post_snapshot=post_snapshot,
    )
    errors.extend(cleanup_errors)

    common_identity = current.get("common_git_dir_identity")
    if not isinstance(common_identity, dict) or not _json_exact_equal(
        common_identity, _path_identity(common_dir)
    ):
        errors.append("common Git directory identity changed across cleanup")
    survivor_identity = current.get("surviving_repo_root_identity")
    if not isinstance(survivor_identity, dict) or not _json_exact_equal(
        survivor_identity, _path_identity(survivor)
    ):
        errors.append("surviving landed repository identity changed across cleanup")

    contract = current.get("evidence_contract")
    if not isinstance(contract, dict):
        post_evidence = None
        errors.append("terminal evidence contract is absent")
    else:
        post_evidence, post_errors = _collect_terminal_evidence(
            survivor,
            common_dir,
            contract=contract,
            candidate_sha256=str(
                current.get("pre_cleanup_evidence", {}).get("candidate_sha256")
                if isinstance(current.get("pre_cleanup_evidence"), dict)
                else ""
            ),
            include_remote=True,
            gh_runner=gh_runner or _default_gh_runner,
        )
        errors.extend(post_errors)
        pre_evidence = current.get("pre_cleanup_evidence")
        if isinstance(pre_evidence, dict):
            for key in (
                "candidate_sha256",
                "comparison_commit",
                "intents",
                "manifest",
                "packet",
                "receipts",
                "target_numbers",
            ):
                if not _json_exact_equal(pre_evidence.get(key), post_evidence.get(key)):
                    errors.append(f"pre/post terminal evidence mismatch: {key}")
        else:
            errors.append("pre-cleanup terminal evidence is absent")

    decision = "PASS" if not errors else "HOLD"
    route_candidate = (
        TERMINAL_FLEET_CANDIDATE
        if decision == "PASS"
        else TERMINAL_RECONCILIATION_CANDIDATE
    )
    finalized = copy.deepcopy(current)
    finalized.update(
        {
            "cleanup_result": copy.deepcopy(cleanup_result),
            "cleanup_validation": {
                "errors": cleanup_errors,
                "post_snapshot": post_snapshot,
                "result": "PASS" if not cleanup_errors else "HOLD",
            },
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "errors": errors,
            "post_cleanup_evidence": post_evidence,
            "route_candidate": route_candidate,
        }
    )
    finalized = _seal_terminal_receipt(finalized)
    _atomic_replace_json(path, finalized)
    raw = _read_regular_bytes(path, label="final terminal receipt")
    binding = {
        "decision": decision,
        "merge_sha": finalized["merge_sha"],
        "path": str(path.relative_to(common_dir)),
        "sha256": _sha256_bytes(raw),
        "wave_id": finalized["wave_id"],
    }
    return {"binding": binding, "receipt": finalized, "receipt_path": str(path)}


_TERMINAL_RECEIPT_KEYS = {
    "cleanup_authority",
    "cleanup_result",
    "cleanup_validation",
    "common_git_dir_identity",
    "completed_at_utc",
    "created_at_utc",
    "decision",
    "errors",
    "evidence_contract",
    "merge_sha",
    "post_cleanup_evidence",
    "pre_cleanup_evidence",
    "receipt_sha256",
    "route_candidate",
    "schema_version",
    "surviving_repo_root_identity",
    "wave_id",
}
_TERMINAL_BINDING_KEYS = {"decision", "merge_sha", "path", "sha256", "wave_id"}


def _terminal_receipt_semantic_errors(receipt: Any) -> list[str]:
    if not isinstance(receipt, dict):
        return ["terminal receipt is not an object"]
    errors: list[str] = []
    if set(receipt) != _TERMINAL_RECEIPT_KEYS:
        errors.append("terminal receipt schema mismatch")
    claimed = receipt.get("receipt_sha256")
    unhashed = dict(receipt)
    unhashed.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or _DIGEST_RE.fullmatch(claimed) is None:
        errors.append("terminal receipt self-hash is invalid")
    elif claimed != _canonical_sha256(unhashed):
        errors.append("terminal receipt self-hash mismatch")
    if receipt.get("schema_version") != TERMINAL_RECEIPT_SCHEMA_VERSION:
        errors.append("terminal receipt schema version mismatch")
    if receipt.get("wave_id") != TERMINAL_SWEEP_WAVE_ID:
        errors.append("terminal receipt wave mismatch")
    if not isinstance(receipt.get("merge_sha"), str) or _SHA_RE.fullmatch(
        receipt.get("merge_sha", "")
    ) is None:
        errors.append("terminal receipt merge SHA is invalid")
    decision = receipt.get("decision")
    if decision not in {"PASS", "HOLD"}:
        errors.append("terminal receipt is not final")
    error_rows = receipt.get("errors")
    if not isinstance(error_rows, list) or not all(
        isinstance(item, str) and item for item in error_rows
    ):
        errors.append("terminal receipt errors field is invalid")
    elif decision == "PASS" and error_rows:
        errors.append("PASS terminal receipt contains errors")
    elif decision == "HOLD" and not error_rows:
        errors.append("HOLD terminal receipt lacks a reason")
    expected_route = (
        TERMINAL_FLEET_CANDIDATE
        if decision == "PASS"
        else TERMINAL_RECONCILIATION_CANDIDATE
    )
    if receipt.get("route_candidate") != expected_route:
        errors.append("terminal receipt route candidate contradicts its decision")
    for label, evidence in (
        ("pre", receipt.get("pre_cleanup_evidence")),
        ("post", receipt.get("post_cleanup_evidence")),
    ):
        if not isinstance(evidence, dict):
            errors.append(f"{label}-cleanup evidence is absent")
            continue
        if evidence.get("target_numbers") != list(EXPECTED_NUMBERS):
            errors.append(f"{label}-cleanup fixed target set mismatch")
        if decision == "PASS":
            if len(evidence.get("receipts") or []) != len(EXPECTED_TARGETS):
                errors.append(f"{label}-cleanup receipt count mismatch")
            intent_rows = evidence.get("intents")
            if not isinstance(intent_rows, list) or len(intent_rows) != len(
                EXPECTED_TARGETS
            ):
                errors.append(f"{label}-cleanup intent count mismatch")
            else:
                intent_numbers: list[Any] = []
                for intent_row in intent_rows:
                    if not isinstance(intent_row, dict):
                        errors.append(
                            f"{label}-cleanup intent binding evidence is invalid"
                        )
                        continue
                    number = intent_row.get("number")
                    intent_numbers.append(number)
                    if intent_row.get("binding_equivalent") is not True:
                        errors.append(
                            f"{label}-cleanup PR #{number} intent is not "
                            "binding-equivalent"
                        )
                if intent_numbers != list(EXPECTED_NUMBERS):
                    errors.append(f"{label}-cleanup intent target set mismatch")
            if label == "post" and len(
                evidence.get("remote_observations") or []
            ) != len(EXPECTED_TARGETS):
                errors.append("post-cleanup provider observation count mismatch")
            if evidence.get("result") != "PASS":
                errors.append(f"PASS receipt has nonpassing {label}-cleanup evidence")
    cleanup_validation = receipt.get("cleanup_validation")
    if not isinstance(cleanup_validation, dict):
        errors.append("cleanup validation is absent")
    elif decision == "PASS" and cleanup_validation.get("result") != "PASS":
        errors.append("PASS receipt has nonpassing cleanup validation")
    contract = receipt.get("evidence_contract")
    pre_evidence = receipt.get("pre_cleanup_evidence")
    if not isinstance(contract, dict):
        errors.append("terminal evidence contract is absent")
    elif isinstance(pre_evidence, dict):
        if decision == "PASS" and pre_evidence.get(
            "candidate_sha256"
        ) != contract.get("expected_candidate_sha256"):
            errors.append("terminal candidate digest binding mismatch")
        if pre_evidence.get("comparison_commit") != contract.get(
            "comparison_commit"
        ):
            errors.append("terminal comparison commit binding mismatch")
    return errors


def validate_terminal_receipt_authority(
    repo_root: Path | str,
    binding: Any,
    *,
    expected_merge_sha: str = "",
    expected_candidate: str = "",
) -> dict[str, Any]:
    """Validate a dispatcher binding without invoking GitHub or any mutation."""
    invalid = {"decision": "", "error": "", "receipt_path": "", "valid": False}
    if not isinstance(binding, dict) or set(binding) != _TERMINAL_BINDING_KEYS:
        return {**invalid, "error": "terminal receipt binding schema mismatch"}
    if binding.get("wave_id") != TERMINAL_SWEEP_WAVE_ID:
        return {**invalid, "error": "terminal receipt binding wave mismatch"}
    merge_sha = binding.get("merge_sha")
    if not isinstance(merge_sha, str) or _SHA_RE.fullmatch(merge_sha) is None:
        return {**invalid, "error": "terminal receipt binding merge SHA is invalid"}
    if expected_merge_sha and merge_sha != expected_merge_sha:
        return {**invalid, "error": "terminal receipt binding merge SHA mismatch"}
    decision = binding.get("decision")
    if decision not in {"PASS", "HOLD"}:
        return {**invalid, "error": "terminal receipt binding is not final"}
    expected_route = (
        TERMINAL_FLEET_CANDIDATE
        if decision == "PASS"
        else TERMINAL_RECONCILIATION_CANDIDATE
    )
    normalized_candidate = str(expected_candidate or "").strip().lower().replace("_", "-")
    if normalized_candidate and not (
        normalized_candidate == expected_route
        or normalized_candidate.startswith(f"{expected_route}-")
    ):
        return {**invalid, "error": "terminal receipt decision/candidate mismatch"}
    relative = binding.get("path")
    expected_relative = Path(
        TERMINAL_RECEIPT_ROOT_NAME, TERMINAL_SWEEP_WAVE_ID, f"{merge_sha}.json"
    )
    if not isinstance(relative, str) or Path(relative) != expected_relative:
        return {**invalid, "error": "terminal receipt binding path mismatch"}
    claimed_raw_sha = binding.get("sha256")
    if not isinstance(claimed_raw_sha, str) or _DIGEST_RE.fullmatch(claimed_raw_sha) is None:
        return {**invalid, "error": "terminal receipt binding SHA-256 is invalid"}
    try:
        root = Path(repo_root).resolve(strict=True)
        common_dir = _resolve_common_git_dir(root)
        path = common_dir / expected_relative
        receipt, raw = _read_canonical_json(path, label="terminal receipt authority")
    except (ContractError, OSError) as exc:
        return {**invalid, "error": f"terminal receipt is unavailable: {exc}"}
    if _sha256_bytes(raw) != claimed_raw_sha:
        return {
            **invalid,
            "error": "terminal receipt binding SHA-256 mismatch",
            "receipt_path": str(path),
        }
    semantic_errors = _terminal_receipt_semantic_errors(receipt)
    if semantic_errors:
        return {
            **invalid,
            "error": "; ".join(semantic_errors),
            "receipt_path": str(path),
        }
    for key in ("decision", "merge_sha", "wave_id"):
        if not _json_exact_equal(receipt.get(key), binding.get(key)):
            return {
                **invalid,
                "error": f"terminal receipt/binding {key} mismatch",
                "receipt_path": str(path),
            }
    return {
        "decision": decision,
        "error": "",
        "receipt_path": str(path),
        "valid": True,
    }


def _load_commit_executor_seams() -> tuple[Callable[..., Any], Callable[..., Any]]:
    script_dir = Path(__file__).resolve().parent
    inserted = False
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
        inserted = True
    try:
        module = importlib.import_module("commit_executor")
    finally:
        if inserted:
            try:
                sys.path.remove(str(script_dir))
            except ValueError:
                pass
    return module.bind_terminal_target_identity, module.execute_terminal_mutation_once


def _publish_new_receipt(path: Path, receipt: dict[str, Any]) -> None:
    try:
        _publish_receipt_atomic(path, receipt)
    except FileExistsError as exc:
        raise ContractError(f"receipt already exists and was not overwritten: {path}") from exc


def _reconcile_existing_intent(
    *,
    target: dict[str, Any],
    intent_path: Path,
    receipt_path: Path,
    comparison_commit: str,
    manifest_sha256: str,
    repo_root: Path,
    common_dir: Path,
    gh_runner: GhRunner,
) -> dict[str, Any]:
    """Never execute an operation whose outer intent survived without receipt."""
    intent = _read_intent(
        intent_path,
        target=target,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
        repo_root=repo_root,
        common_dir=common_dir,
    )
    after, observation_error = _safe_remote_snapshot(
        target, repo_root=repo_root, gh_runner=gh_runner
    )
    before = intent.get("callback_snapshot")
    if before is not None and _snapshot_errors(before, target, state="OPEN"):
        before = None
    if after is not None and not _snapshot_errors(after, target, state="CLOSED"):
        receipt = _new_receipt(
            status="CLOSED_RECONCILED",
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            operation_id=intent["operation_id"],
            intent_path=intent_path,
            intent=intent,
            before=before,
            terminal={
                "intent_state": intent["state"],
                "kind": "RESTART_INTENT_RECONCILIATION",
            },
            after=after,
            reason=None,
        )
    else:
        after_evidence = after if after is not None else {"error": observation_error}
        receipt = _new_receipt(
            status="HOLD_ACTION_OR_POSTVERIFY",
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            operation_id=intent["operation_id"],
            intent_path=intent_path,
            intent=intent,
            before=before,
            terminal={"intent_state": intent["state"], "kind": "RESTART_NO_REPLAY"},
            after=after_evidence,
            reason=(
                "pre-existing intent has no valid receipt; operation will never be "
                "executed again in this wave"
            ),
        )
    _publish_new_receipt(receipt_path, receipt)
    return receipt


def _shared_hold_receipt(
    *,
    target: dict[str, Any],
    comparison_commit: str,
    manifest_sha256: str,
    trigger_pr: int,
    trigger_status: str,
) -> dict[str, Any]:
    return _new_receipt(
        status="HOLD_SHARED_UNATTEMPTED",
        target=target,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
        operation_id=None,
        intent_path=None,
        intent=None,
        before=None,
        terminal={
            "kind": "SHARED_UNATTEMPTED",
            "trigger_pr": trigger_pr,
            "trigger_status": trigger_status,
        },
        after=None,
        reason=(
            f"shared batch stop after PR #{trigger_pr} produced {trigger_status}; "
            "no intent or action was attempted for this target"
        ),
    )


def _apply_new_target(
    *,
    target: dict[str, Any],
    intent_path: Path,
    receipt_path: Path,
    comparison_commit: str,
    manifest_sha256: str,
    repo_root: Path,
    common_dir: Path,
    gh_runner: GhRunner,
    bind_target_identity: Callable[..., Any],
    execute_terminal_once: Callable[..., Any],
    reserved_operation_ids: set[str],
    log: Callable[[str], Any],
) -> dict[str, Any]:
    identity = bind_target_identity(repo_root, base_branch="dev")
    identity_errors = _validate_terminal_identity(
        identity, repo_root=repo_root, common_dir=common_dir
    )
    if identity_errors:
        raise ContractError(
            "terminal identity binding failed before intent/action: "
            + "; ".join(identity_errors)
        )
    operation_id = identity["operation_id"]
    if operation_id in reserved_operation_ids:
        raise ContractError(
            f"terminal identity reused operation id before intent/action: {operation_id}"
        )
    reserved_operation_ids.add(operation_id)

    intent = _new_intent(
        target=target,
        identity=identity,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
    )
    try:
        _write_json_exclusive(intent_path, intent)
    except FileExistsError as exc:
        reserved_operation_ids.discard(operation_id)
        raise ContractError(
            "intent appeared despite the exclusive fixed-wave apply lock; "
            "refusing action and reconciliation in this process"
        ) from exc

    callback_outcome: dict[str, Any] | None = None
    callback_before: dict[str, Any] | None = None
    current_intent = intent

    def terminal_action() -> dict[str, Any]:
        nonlocal callback_outcome, callback_before, current_intent
        # These are the authoritative reads.  They intentionally occur only
        # after commit_executor has consumed one-shot authority and entered
        # this callback while holding the common-dir lock.
        callback_before = _read_remote_snapshot(
            target, repo_root=repo_root, gh_runner=gh_runner
        )
        drift = _snapshot_errors(callback_before, target, state="OPEN")
        if drift:
            current_intent = _advance_intent(
                intent_path,
                current_intent,
                expected_state="PREPARED",
                new_state="REMOTE_DRIFT_NO_ACTION",
                additions={
                    "callback_drift": drift,
                    "callback_snapshot": callback_before,
                },
                target=target,
                comparison_commit=comparison_commit,
                manifest_sha256=manifest_sha256,
                repo_root=repo_root,
                common_dir=common_dir,
            )
            callback_outcome = {
                "drift": drift,
                "kind": "REMOTE_DRIFT_NO_ACTION",
                "snapshot": callback_before,
            }
            return callback_outcome

        current_intent = _advance_intent(
            intent_path,
            current_intent,
            expected_state="PREPARED",
            new_state="CALLBACK_VALIDATED_CLOSE_PENDING",
            additions={"callback_snapshot": callback_before},
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            repo_root=repo_root,
            common_dir=common_dir,
        )
        close_response = _close_exact_node(
            target, repo_root=repo_root, gh_runner=gh_runner
        )
        callback_outcome = {
            "close_response": close_response,
            "kind": "CLOSE_INVOKED",
        }
        current_intent = _advance_intent(
            intent_path,
            current_intent,
            expected_state="CALLBACK_VALIDATED_CLOSE_PENDING",
            new_state="CLOSE_RESPONSE_OBSERVED",
            additions={"close_response": close_response},
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            repo_root=repo_root,
            common_dir=common_dir,
        )
        return callback_outcome

    try:
        boundary = execute_terminal_once(
            repo_root,
            identity,
            terminal_action=terminal_action,
            log=log,
        )
    except Exception as exc:  # noqa: BLE001 - an intent now forbids retry
        boundary = {
            "action_error": f"{type(exc).__name__}: {exc}",
            "action_invoked": None,
            "action_succeeded": False,
            "authority_consumed": None,
            "decision": "BOUNDARY_EXCEPTION",
            "operation_id": identity["operation_id"],
            "reason": "terminal boundary raised after durable outer intent",
        }
    # The callback may have replaced the intent and then failed during the
    # directory-fsync boundary.  Re-read durable truth rather than embedding a
    # stale in-memory predecessor in the receipt.  Failure here leaves only the
    # existing intent, which is the deliberate no-replay restart signal.
    current_intent = _read_intent(
        intent_path,
        target=target,
        comparison_commit=comparison_commit,
        manifest_sha256=manifest_sha256,
        repo_root=repo_root,
        common_dir=common_dir,
    )
    boundary_summary = _boundary_summary(boundary)
    after, postverify_error = _safe_remote_snapshot(
        target, repo_root=repo_root, gh_runner=gh_runner
    )

    if callback_outcome is not None and callback_outcome.get("kind") == "REMOTE_DRIFT_NO_ACTION":
        receipt = _new_receipt(
            status="HOLD_REMOTE_DRIFT",
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            operation_id=identity["operation_id"],
            intent_path=intent_path,
            intent=current_intent,
            before=callback_before,
            terminal={
                "boundary": boundary_summary,
                "drift": callback_outcome["drift"],
                "kind": "REMOTE_DRIFT_NO_ACTION",
            },
            after=after if after is not None else {"error": postverify_error},
            reason="callback-local authoritative read found remote drift; no close ran",
        )
    elif (
        isinstance(boundary, dict)
        and boundary.get("decision") == "ACTION_COMPLETED"
        and boundary.get("authority_consumed") is True
        and boundary.get("action_invoked") is True
        and boundary.get("action_succeeded") is True
        and callback_outcome is not None
        and callback_outcome.get("kind") == "CLOSE_INVOKED"
        and after is not None
        and not _snapshot_errors(after, target, state="CLOSED")
    ):
        receipt = _new_receipt(
            status="CLOSED",
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            operation_id=identity["operation_id"],
            intent_path=intent_path,
            intent=current_intent,
            before=callback_before,
            terminal={
                "boundary": boundary_summary,
                "close_response": callback_outcome["close_response"],
                "kind": "CLOSE_CONFIRMED",
            },
            after=after,
            reason=None,
        )
    else:
        receipt = _new_receipt(
            status="HOLD_ACTION_OR_POSTVERIFY",
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            operation_id=identity["operation_id"],
            intent_path=intent_path,
            intent=current_intent,
            before=callback_before,
            terminal={
                "boundary": boundary_summary,
                "callback": callback_outcome,
                "kind": "ACTION_OR_POSTVERIFY_HOLD",
                "postverify_error": postverify_error,
            },
            after=after if after is not None else {"error": postverify_error},
            reason=(
                "terminal authority was consumed or became ambiguous; post-state "
                "is not sufficient for a fresh CLOSED receipt and will not be retried"
            ),
        )
    _publish_new_receipt(receipt_path, receipt)
    return receipt


def _apply_dispositions_with_lock_held(
    manifest_path: Path | str,
    *,
    comparison_commit: str,
    repo_root: Path | str,
    receipts_dir: Path | str | None = None,
    repository: str = REPOSITORY_NAME,
    gh_runner: GhRunner | None = None,
    bind_target_identity: Callable[..., Any] | None = None,
    execute_terminal_once: Callable[..., Any] | None = None,
    git_run: Callable[..., subprocess.CompletedProcess[Any]] = _default_git_run,
    log: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Apply the literal batch while the caller owns the fixed-wave lock."""
    root = Path(repo_root).resolve(strict=True)
    manifest_file = Path(manifest_path)
    validated = validate_manifest_contract(manifest_file, repository=repository)
    _validate_manifest_comparison_ancestry(
        repo_root=root,
        manifest_path=manifest_file,
        manifest_bytes=validated["raw_bytes"],
        comparison_commit=comparison_commit,
        git_run=git_run,
    )
    common_dir = _resolve_common_git_dir(root, git_run=git_run)
    receipt_root = (
        Path(receipts_dir).resolve(strict=False)
        if receipts_dir is not None
        else common_dir / RECEIPT_ROOT_NAME / WAVE_ID
    )
    _ensure_durable_directory(receipt_root)
    expected_receipt_names = {
        f"pr-{number}.json" for number in EXPECTED_NUMBERS
    }
    unexpected = sorted(
        entry.name
        for entry in receipt_root.iterdir()
        if entry.name not in expected_receipt_names
    )
    if unexpected:
        raise ContractError(f"unexpected receipt files pre-exist: {unexpected}")

    manifest_sha256 = validated["manifest_sha256"]
    intent_root = common_dir / INTENT_ROOT_NAME / WAVE_ID
    if os.path.lexists(intent_root):
        intent_root_info = intent_root.lstat()
        if not stat.S_ISDIR(intent_root_info.st_mode):
            raise ContractError(f"intent root is not a real directory: {intent_root}")
        allowed_intent_names = {
            ".apply.lock",
            *(f"pr-{number}.json" for number in EXPECTED_NUMBERS),
        }
        unexpected_intents = sorted(
            entry.name
            for entry in intent_root.iterdir()
            if entry.name not in allowed_intent_names
        )
        if unexpected_intents:
            raise ContractError(
                f"unexpected fixed-wave intent files pre-exist: {unexpected_intents}"
            )

    # Validate every pre-existing receipt and intent, including cross-record
    # uniqueness, before the first possible terminal callback.  A corrupt
    # later record must not be discovered only after an earlier PR was closed.
    preexisting_receipts: dict[int, dict[str, Any]] = {}
    preexisting_intents: dict[int, dict[str, Any]] = {}
    reserved_by_operation: dict[str, int] = {}
    for target in EXPECTED_TARGETS:
        number = target["number"]
        receipt_file = _receipt_path(receipt_root, number)
        if not os.path.lexists(receipt_file):
            continue
        receipt = _validate_receipt_for_target(
            receipt_file,
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            repo_root=root,
            common_dir=common_dir,
        )
        preexisting_receipts[number] = receipt
        operation_id = receipt["operation_id"]
        if operation_id is not None:
            prior = reserved_by_operation.setdefault(operation_id, number)
            if prior != number:
                raise ContractError(
                    f"pre-existing records duplicate operation id {operation_id}"
                )

    for target in EXPECTED_TARGETS:
        number = target["number"]
        intent_file = _intent_path(common_dir, number)
        receipt = preexisting_receipts.get(number)
        if not os.path.lexists(intent_file):
            if receipt is not None and receipt["status"] != "HOLD_SHARED_UNATTEMPTED":
                raise ContractError(
                    f"attempted receipt lacks its durable intent: {intent_file}"
                )
            continue
        if receipt is not None and receipt["status"] == "HOLD_SHARED_UNATTEMPTED":
            raise ContractError(
                f"shared-unattempted receipt contradicts an existing intent: {intent_file}"
            )
        intent = _read_intent(
            intent_file,
            target=target,
            comparison_commit=comparison_commit,
            manifest_sha256=manifest_sha256,
            repo_root=root,
            common_dir=common_dir,
        )
        preexisting_intents[number] = intent
        if receipt is not None:
            if receipt["intent_path"] != str(intent_file) or not _json_exact_equal(
                receipt["intent"], intent
            ):
                raise ContractError(
                    f"receipt does not match its durable intent: {intent_file}"
                )
        operation_id = intent["operation_id"]
        prior = reserved_by_operation.setdefault(operation_id, number)
        if prior != number:
            raise ContractError(
                f"pre-existing records duplicate operation id {operation_id}"
            )

    preexisting_causality_errors = _shared_causality_errors(preexisting_receipts)
    if preexisting_causality_errors:
        raise ContractError(
            "invalid pre-existing shared HOLD causality: "
            + "; ".join(preexisting_causality_errors)
        )

    # The executor publishes records in manifest order.  Under the batch lock,
    # a gap followed by durable state, or state after a receiptless intent,
    # cannot be a valid interrupted prefix and must stop before any action.
    saw_gap = False
    saw_receiptless_intent = False
    for number in EXPECTED_NUMBERS:
        has_receipt = number in preexisting_receipts
        has_intent = number in preexisting_intents
        has_record = has_receipt or has_intent
        if not has_record:
            saw_gap = True
            continue
        if saw_gap:
            raise ContractError(
                f"pre-existing durable records are out of manifest order at PR #{number}"
            )
        if saw_receiptless_intent:
            raise ContractError(
                f"durable record follows an unresolved intent at PR #{number}"
            )
        if has_intent and not has_receipt:
            saw_receiptless_intent = True

    runner = gh_runner or _default_gh_runner
    if bind_target_identity is None or execute_terminal_once is None:
        default_bind, default_execute = _load_commit_executor_seams()
        bind_target_identity = bind_target_identity or default_bind
        execute_terminal_once = execute_terminal_once or default_execute
    logger = log or (lambda message: print(message, file=sys.stderr))
    receipts: dict[int, dict[str, Any]] = {}
    reserved_operation_ids = set(reserved_by_operation)
    shared_trigger: tuple[int, str] | None = None

    for target in EXPECTED_TARGETS:
        number = target["number"]
        receipt_file = _receipt_path(receipt_root, number)
        intent_file = _intent_path(common_dir, number)
        if os.path.lexists(receipt_file):
            receipt = _validate_receipt_for_target(
                receipt_file,
                target=target,
                comparison_commit=comparison_commit,
                manifest_sha256=manifest_sha256,
                repo_root=root,
                common_dir=common_dir,
            )
            receipts[number] = receipt
            if receipt["status"] in HOLD_STATUSES and shared_trigger is None:
                if receipt["status"] == "HOLD_SHARED_UNATTEMPTED":
                    shared_trigger = (
                        receipt["terminal"]["trigger_pr"],
                        receipt["terminal"]["trigger_status"],
                    )
                else:
                    shared_trigger = (number, receipt["status"])
            continue

        if shared_trigger is not None and not os.path.lexists(intent_file):
            receipt = _shared_hold_receipt(
                target=target,
                comparison_commit=comparison_commit,
                manifest_sha256=manifest_sha256,
                trigger_pr=shared_trigger[0],
                trigger_status=shared_trigger[1],
            )
            _publish_new_receipt(receipt_file, receipt)
            receipts[number] = receipt
            continue

        if os.path.lexists(intent_file):
            receipt = _reconcile_existing_intent(
                target=target,
                intent_path=intent_file,
                receipt_path=receipt_file,
                comparison_commit=comparison_commit,
                manifest_sha256=manifest_sha256,
                repo_root=root,
                common_dir=common_dir,
                gh_runner=runner,
            )
        elif shared_trigger is not None:
            receipt = _shared_hold_receipt(
                target=target,
                comparison_commit=comparison_commit,
                manifest_sha256=manifest_sha256,
                trigger_pr=shared_trigger[0],
                trigger_status=shared_trigger[1],
            )
            _publish_new_receipt(receipt_file, receipt)
        else:
            receipt = _apply_new_target(
                target=target,
                intent_path=intent_file,
                receipt_path=receipt_file,
                comparison_commit=comparison_commit,
                manifest_sha256=manifest_sha256,
                repo_root=root,
                common_dir=common_dir,
                gh_runner=runner,
                bind_target_identity=bind_target_identity,
                execute_terminal_once=execute_terminal_once,
                reserved_operation_ids=reserved_operation_ids,
                log=logger,
            )
        receipts[number] = receipt
        if receipt["status"] in HOLD_STATUSES and shared_trigger is None:
            shared_trigger = (number, receipt["status"])

    verified = verify_receipts(
        manifest_file,
        comparison_commit=comparison_commit,
        receipts_dir=receipt_root,
        repository=repository,
    )
    verified["receipts_dir"] = str(receipt_root)
    return verified


def apply_dispositions(
    manifest_path: Path | str,
    *,
    comparison_commit: str,
    repo_root: Path | str,
    receipts_dir: Path | str | None = None,
    repository: str = REPOSITORY_NAME,
    gh_runner: GhRunner | None = None,
    bind_target_identity: Callable[..., Any] | None = None,
    execute_terminal_once: Callable[..., Any] | None = None,
    git_run: Callable[..., subprocess.CompletedProcess[Any]] = _default_git_run,
    log: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Apply the literal eight-target batch with conservative no replay."""
    root = Path(repo_root).resolve(strict=True)
    manifest_file = Path(manifest_path)
    validated = validate_manifest_contract(manifest_file, repository=repository)
    _validate_manifest_comparison_ancestry(
        repo_root=root,
        manifest_path=manifest_file,
        manifest_bytes=validated["raw_bytes"],
        comparison_commit=comparison_commit,
        git_run=git_run,
    )
    common_dir = _resolve_common_git_dir(root, git_run=git_run)
    with _wave_apply_lock(common_dir):
        return _apply_dispositions_with_lock_held(
            manifest_file,
            comparison_commit=comparison_commit,
            repo_root=root,
            receipts_dir=receipts_dir,
            repository=repository,
            gh_runner=gh_runner,
            bind_target_identity=bind_target_identity,
            execute_terminal_once=execute_terminal_once,
            git_run=git_run,
            log=log,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fixed-set executor for the eight governed PR disposition targets"
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    contract_parser = subparsers.add_parser(
        "contract-check", help="validate only the exact self-hashed target manifest"
    )
    contract_parser.add_argument("--manifest", type=Path, required=True)
    contract_parser.add_argument("--repository", default=REPOSITORY_NAME)

    for mode in ("apply", "verify"):
        mode_parser = subparsers.add_parser(mode)
        mode_parser.add_argument("--manifest", type=Path, required=True)
        mode_parser.add_argument("--comparison-commit", required=True)
        mode_parser.add_argument("--repository", default=REPOSITORY_NAME)
        mode_parser.add_argument("--receipts-dir", type=Path, required=(mode == "verify"))
        if mode == "apply":
            mode_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.mode == "contract-check":
            result = contract_check(args.manifest, repository=args.repository)
        elif args.mode == "verify":
            result = verify_receipts(
                args.manifest,
                comparison_commit=args.comparison_commit,
                receipts_dir=args.receipts_dir,
                repository=args.repository,
            )
        else:
            result = apply_dispositions(
                args.manifest,
                comparison_commit=args.comparison_commit,
                repo_root=args.repo_root,
                receipts_dir=args.receipts_dir,
                repository=args.repository,
            )
    except ContractError as exc:
        print(json.dumps({"decision": "HOLD", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.mode == "apply" and result.get("has_hold"):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
