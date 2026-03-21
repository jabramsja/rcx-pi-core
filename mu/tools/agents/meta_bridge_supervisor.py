#!/usr/bin/env python3
"""Pre-commit convergence gate: consumes Claude's summary package, emits program-level decision.

This is the meta-bridge supervisor (Slice 1). It runs AFTER the per-job bridge loop
converges but BEFORE commit is allowed. Codex acts as adversarial reviewer with
investigative authority but no direct implementation authority.

See: .scratch/meta_bridge_supervisor_slice1_plan.md
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from string import Template
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bridge_adapters import get_adapter, load_bridge_config, run_adapter

# Namespace isolation: meta-bridge uses .agent_bus/meta/ subdirectory
META_BUS_DIR_NAME = ".agent_bus/meta"
META_DB_NAME = "meta_bridge.db"
META_LOCK_NAME = "meta_bridge.lock"

# Paths ignored in dirty-state comparison (transient artifacts)
DIRTY_STATE_IGNORE_PREFIXES = (
    ".agent_bus/",
    ".scratch/",
    ".git/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "node_modules/",
)

# State ignore prefixes for repo state hashing (matches bridge_supervisor.py)
STATE_IGNORE_PREFIXES = (
    ".agent_bus/",
    ".git/",
    ".scratch/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "node_modules/",
)


class MetaBridgeState(Enum):
    """Slice 1 state machine states.

    NOTE: Slice 1 uses in-memory state only. State persistence (crash recovery,
    resume, audit trail) is deferred to Slice 2+. Current state transitions are
    implicit in the control flow, not persisted to .agent_bus/meta/.
    """
    IDLE = "IDLE"
    AWAITING_CLAUDE_SUMMARY = "AWAITING_CLAUDE_SUMMARY"
    AWAITING_META_REVIEW = "AWAITING_META_REVIEW"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT = "TIMEOUT"
    ABORT = "ABORT"
    COMPLETED = "COMPLETED"


class Decision(Enum):
    """Slice 1 authoritative decision vocabulary."""
    # Success tokens
    COMMIT_GO = "COMMIT_GO"
    COMMIT_GO_HOLD_PUSH = "COMMIT_GO_HOLD_PUSH"
    NO_ACTION = "NO_ACTION"
    # Redirect tokens
    NEEDS_PHASE_A = "NEEDS_PHASE_A"
    NEEDS_PHASE_B = "NEEDS_PHASE_B"
    STOP_FOR_FOUNDER = "STOP_FOR_FOUNDER"
    STOP_FOR_TRIAGE_DISCUSSION = "STOP_FOR_TRIAGE_DISCUSSION"
    # Error tokens
    ERROR_PACKAGE_INVALID = "ERROR_PACKAGE_INVALID"
    ERROR_CODEX_TIMEOUT = "ERROR_CODEX_TIMEOUT"
    ERROR_CODEX_ABORT = "ERROR_CODEX_ABORT"
    ERROR_VALIDATION_FAILED = "ERROR_VALIDATION_FAILED"
    ERROR_REPO_CHANGED = "ERROR_REPO_CHANGED"
    ERROR_INTERNAL = "ERROR_INTERNAL"
    RETRY_SUGGESTED = "RETRY_SUGGESTED"


# Required package fields (11 total)
REQUIRED_PACKAGE_FIELDS = {
    "task_id",
    "wave_name",
    "lane",
    "changed_files",
    "scope_items",
    "fixes_implemented",
    "deferred_items",
    "bridge_status",
    "evidence_handles",
    "blocker_report_paths",
    "current_judgment",
}


class MetaBridgeError(RuntimeError):
    """Raised when meta-bridge execution cannot continue."""


class _MetaBridgeLock:
    """Exclusive file lock for single-supervisor enforcement."""

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._fp: Any = None

    def __enter__(self) -> "_MetaBridgeLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self._lock_path, "w")
        try:
            fcntl.flock(self._fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            self._fp.close()
            raise MetaBridgeError(
                "Another meta-bridge supervisor is running. "
                "Wait or remove .agent_bus/meta/meta_bridge.lock if stale."
            )
        return self

    def __exit__(self, *exc: object) -> bool:
        if self._fp:
            fcntl.flock(self._fp, fcntl.LOCK_UN)
            self._fp.close()
        return False


@dataclass(frozen=True)
class MetaBridgePaths:
    repo_root: Path
    bus_dir: Path
    db_path: Path
    lock_path: Path


@dataclass(frozen=True)
class RepoState:
    head_sha: str
    staged_sha: str
    unstaged_sha: str
    untracked_sha: str
    state_sha: str


@dataclass
class ValidationResult:
    name: str
    passed: bool
    error: str = ""


@dataclass
class MetaBridgeResponse:
    status: str  # "success", "error", "partial"
    decision: str
    summary: str
    validations_passed: list[str] = field(default_factory=list)
    validations_failed: list[dict[str, str]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    request_for_claude: str = ""
    error_code: str = ""
    error_detail: str = ""
    recovery_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "decision": self.decision,
            "summary": self.summary,
        }
        if self.status == "success" or self.status == "partial":
            d["validations_passed"] = self.validations_passed
            d["validations_failed"] = self.validations_failed
            d["findings"] = self.findings
            d["request_for_claude"] = self.request_for_claude
        if self.status == "error":
            d["error_code"] = self.error_code
            d["error_detail"] = self.error_detail
            if self.recovery_hint:
                d["recovery_hint"] = self.recovery_hint
        return d


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def meta_bridge_paths(repo_root: Path) -> MetaBridgePaths:
    bus_dir = repo_root / META_BUS_DIR_NAME
    return MetaBridgePaths(
        repo_root=repo_root,
        bus_dir=bus_dir,
        db_path=bus_dir / META_DB_NAME,
        lock_path=bus_dir / META_LOCK_NAME,
    )


def ensure_runtime_dirs(paths: MetaBridgePaths) -> None:
    paths.bus_dir.mkdir(parents=True, exist_ok=True)


def git_output(repo_root: Path, args: list[str], *, text: bool = True) -> str | bytes:
    result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise MetaBridgeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    if text:
        return result.stdout.decode("utf-8", errors="replace")
    return result.stdout


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _iter_untracked_files(repo_root: Path) -> list[Path]:
    output = git_output(repo_root, ["ls-files", "--others", "--exclude-standard"])
    paths: list[Path] = []
    for raw in str(output).splitlines():
        raw = raw.strip()
        if not raw:
            continue
        normalized = raw.replace("\\", "/")
        if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in STATE_IGNORE_PREFIXES):
            continue
        path = repo_root / raw
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def compute_repo_state(repo_root: Path) -> RepoState:
    """Compute repo state hash (matches bridge_supervisor.py protocol)."""
    head_sha = str(git_output(repo_root, ["rev-parse", "HEAD"])).strip()
    staged_sha = _hash_bytes(git_output(repo_root, ["diff", "--cached", "--binary"], text=False))  # type: ignore
    unstaged_sha = _hash_bytes(git_output(repo_root, ["diff", "--binary"], text=False))  # type: ignore

    hasher = hashlib.sha256()
    for path in _iter_untracked_files(repo_root):
        rel = path.relative_to(repo_root).as_posix().encode("utf-8")
        hasher.update(rel)
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    untracked_sha = hasher.hexdigest()

    state_sha = hashlib.sha256(
        f"{head_sha}|{staged_sha}|{unstaged_sha}|{untracked_sha}".encode("utf-8")
    ).hexdigest()
    return RepoState(
        head_sha=head_sha,
        staged_sha=staged_sha,
        unstaged_sha=unstaged_sha,
        untracked_sha=untracked_sha,
        state_sha=state_sha,
    )


def parse_dirty_state(repo_root: Path) -> dict[str, set[str]]:
    """Parse git status --porcelain=v1 -z output.

    Returns dict with keys:
      - modified: set of modified/added/deleted file paths
      - renamed: set of (new_path, old_path) tuples (new first per git output)
      - all_paths: set of all paths mentioned

    Per git docs, rename records in -z mode output: R new\0old\0
    """
    raw = git_output(repo_root, ["status", "--porcelain=v1", "-z"], text=False)
    result: dict[str, set[str]] = {"modified": set(), "renamed": set(), "all_paths": set()}

    # Split on NUL, filter empties
    parts = [p for p in bytes(raw).split(b"\0") if p]  # type: ignore

    i = 0
    while i < len(parts):
        record = parts[i].decode("utf-8", errors="replace")
        if len(record) < 3:
            i += 1
            continue

        status = record[:2]
        path = record[3:]

        # Skip ignored paths
        normalized = path.replace("\\", "/")
        if any(normalized.startswith(prefix) for prefix in DIRTY_STATE_IGNORE_PREFIXES):
            # For renames, also skip the next part (old path)
            if status.startswith("R"):
                i += 2
            else:
                i += 1
            continue

        if status.startswith("R"):
            # Rename: this record has new path, next record has old path
            new_path = path
            if i + 1 < len(parts):
                old_path = parts[i + 1].decode("utf-8", errors="replace")
                result["renamed"].add(f"{new_path}|{old_path}")
                result["all_paths"].add(new_path)
                result["all_paths"].add(old_path)
                i += 2
            else:
                result["all_paths"].add(new_path)
                i += 1
        else:
            result["modified"].add(path)
            result["all_paths"].add(path)
            i += 1

    return result


def validate_package_schema(package: Any) -> tuple[bool, list[str]]:
    """Validate package has all 11 required fields with correct types."""
    # Package must be a JSON object (dict), not an array or primitive
    if not isinstance(package, dict):
        return False, [f"Package must be a JSON object, got {type(package).__name__}"]

    missing = REQUIRED_PACKAGE_FIELDS - set(package.keys())
    if missing:
        return False, [f"Missing required field: {f}" for f in sorted(missing)]

    # Validate field types for all 11 required fields
    errors = []

    # String fields that must be non-empty
    string_fields = ["task_id", "wave_name", "lane", "current_judgment"]
    for field in string_fields:
        val = package.get(field)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"{field} must be a non-empty string")

    # fixes_implemented can be string OR list (seeded corpus uses list)
    fixes = package.get("fixes_implemented")
    if not isinstance(fixes, (str, list)):
        errors.append("fixes_implemented must be a string or list")

    # List fields with element type validation
    list_fields = ["changed_files", "scope_items", "deferred_items", "blocker_report_paths"]
    for field in list_fields:
        val = package.get(field)
        if not isinstance(val, list):
            errors.append(f"{field} must be a list")
        else:
            # Validate element types: changed_files and blocker_report_paths must be strings
            if field in ("changed_files", "blocker_report_paths"):
                for i, elem in enumerate(val):
                    if not isinstance(elem, str):
                        errors.append(f"{field}[{i}] must be a string, got {type(elem).__name__}")

    # Object fields
    object_fields = ["bridge_status", "evidence_handles"]
    for field in object_fields:
        if not isinstance(package.get(field), dict):
            errors.append(f"{field} must be an object")

    # Validate current_judgment is a known token
    valid_judgments = {d.value for d in Decision}
    judgment = package.get("current_judgment", "")
    if judgment and judgment not in valid_judgments:
        errors.append(f"current_judgment '{judgment}' is not a valid decision token")

    return len(errors) == 0, errors


def check_tasks_authorization(repo_root: Path, task_id: str) -> ValidationResult:
    """Gate 8: Check task_id is in active NOW or NEXT section of TASKS.md."""
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return ValidationResult("TASKS.md auth", False, "TASKS.md not found")

    content = tasks_path.read_text(encoding="utf-8")

    # Extract NOW and NEXT sections (sections may have parenthetical descriptions)
    now_match = re.search(r"## NOW.*?\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    next_match = re.search(r"## NEXT.*?\n(.*?)(?=\n## |\Z)", content, re.DOTALL)

    active_section = ""
    if now_match:
        active_section += now_match.group(1)
    if next_match:
        active_section += next_match.group(1)

    # Filter out struck-through lines
    # Format: ~~**[TASK-ID] description...**~~ (struck-through task with bold)
    # The closing **~~ may come after description text, not right after the task ID
    active_lines = []
    for line in active_section.splitlines():
        # Skip struck-through task IDs: ~~**[...]...**~~ pattern
        # This matches lines where the task ID block is struck through
        if re.search(r"~~\*\*\[.*?\].*?\*\*~~", line):
            continue
        active_lines.append(line)

    active_text = "\n".join(active_lines)

    # Check if task_id appears as a bracketed task ID token
    # Task IDs MUST be bracketed like [META-BRIDGE-S1] - arbitrary prose is NOT authorized
    # The task_id field should already include brackets; if not, reject it
    if not (task_id.startswith("[") and task_id.endswith("]")):
        return ValidationResult(
            "TASKS.md auth",
            False,
            f"task_id must be bracketed (e.g., [TASK-ID]), got: {task_id}"
        )

    # Match task_id with optional bold markers (e.g., **[META-BRIDGE-S1]**)
    # Only match the exact bracketed token, not prose containing similar text
    escaped_id = re.escape(task_id)
    # Pattern requires the bracketed token to appear as-is (with optional bold)
    pattern = rf"(?:\*\*)?{escaped_id}(?:\*\*)?"
    if re.search(pattern, active_text):
        return ValidationResult("TASKS.md auth", True)

    return ValidationResult(
        "TASKS.md auth",
        False,
        f"task_id {task_id} not found in active NOW or NEXT sections"
    )


def check_deferred_blockers(repo_root: Path, blocker_report_paths: list[str]) -> ValidationResult:
    """Gate 7: Check for unresolved blockers in reports/deferred/blocking/.

    Per rollout packet and template contract:
    - blocker_report_paths MUST acknowledge ALL reports/deferred/blocking/ packets (hard fail)
    - OPEN items are LOGGED as warnings but do NOT block if packet is acknowledged
    - This allows pre-existing "background truth" blockers to not gate unrelated work
    - Codex meta-reviewer can still escalate to STOP_FOR_FOUNDER if OPEN items are concerning
    """
    blocking_dir = repo_root / "reports" / "deferred" / "blocking"
    if not blocking_dir.exists():
        return ValidationResult("deferred_blockers", True)

    # Get blocking packet files (exclude README.md which is documentation)
    blocking_files = [f for f in blocking_dir.glob("*.md") if f.name.lower() != "readme.md"]
    if not blocking_files:
        return ValidationResult("deferred_blockers", True)

    errors = []
    warnings = []
    acknowledged_paths = set(blocker_report_paths)

    # First: verify ALL blocking packets are acknowledged (HARD FAIL if missing)
    for bf in blocking_files:
        rel_path = bf.relative_to(repo_root).as_posix()
        if rel_path not in acknowledged_paths:
            errors.append(
                f"Blocking packet {rel_path} exists but is NOT acknowledged in blocker_report_paths"
            )

    # Second: check acknowledged packets for OPEN items (WARN, do not fail)
    # Per rollout packet: pre-existing findings are "background truth" that don't block
    # the immediate implementation target
    for bf in blocking_files:
        rel_path = bf.relative_to(repo_root).as_posix()
        content = bf.read_text(encoding="utf-8")

        # Check if this is an ACTIVE BLOCKERS packet with OPEN items
        if "**Status:** ACTIVE BLOCKERS" in content:
            open_count = content.count("**Status:** OPEN")
            if open_count > 0:
                warnings.append(
                    f"Blocking packet {rel_path} has {open_count} OPEN items (acknowledged, not blocking)"
                )

    # Only fail on unacknowledged packets, not on OPEN items in acknowledged packets
    if errors:
        return ValidationResult("deferred_blockers", False, "; ".join(errors))

    # Pass with warnings if all packets are acknowledged
    if warnings:
        return ValidationResult("deferred_blockers", True, "; ".join(warnings))
    return ValidationResult("deferred_blockers", True)


def check_dirty_state(repo_root: Path, claimed_files: list[str], *, verbose: bool = False) -> ValidationResult:
    """Gate 1: Compare package changed_files against actual git status.

    Note: git status collapses untracked directories to `?? directory/`, so files
    inside untracked directories won't appear individually. We handle this by:
    1. Checking if claimed file's parent directory appears as untracked
    2. Verifying claimed file actually exists on disk (prevents fabrication)
    3. Checking if untracked directory markers are covered by claimed children
    """
    dirty = parse_dirty_state(repo_root)
    claimed_set = set(claimed_files)
    actual_paths = dirty["all_paths"]

    # Missing dirty: package claims files not in porcelain → ERROR (package stale)
    # But allow files inside untracked directories IF the file actually exists
    # IMPORTANT: Reject raw directory markers - packages must enumerate actual files
    missing = set()
    for claimed in claimed_set:
        # Reject directory markers: they can hide child files
        # A directory marker ends with / or is an actual directory on disk
        claimed_full = repo_root / claimed
        if claimed.endswith("/") or claimed_full.is_dir():
            missing.add(f"{claimed} (directory markers not allowed; enumerate actual files)")
            continue
        if claimed in actual_paths:
            continue
        # Check if any parent directory appears as untracked
        parts = Path(claimed).parts
        found_parent = False
        for i in range(len(parts)):
            parent_path = "/".join(parts[:i+1])
            # Untracked directories appear with trailing slash or just the dir name
            if parent_path in actual_paths or f"{parent_path}/" in actual_paths:
                # Parent is untracked - but verify the claimed file ACTUALLY EXISTS
                # This prevents fabricated child paths from bypassing the gate
                claimed_full_path = repo_root / claimed
                if claimed_full_path.exists():
                    found_parent = True
                # else: fabricated path, will be flagged as missing
                break
        if not found_parent:
            missing.add(claimed)

    if missing:
        return ValidationResult(
            "dirty_state",
            False,
            f"Package claims files not in git status (stale package or fabricated): {sorted(missing)}"
        )

    # Extra dirty: git has files not in package → FAIL (dirty-worktree drift)
    # This prevents underreported packages from clearing gates
    extra = actual_paths - claimed_set
    if extra:
        # Filter out transient paths that are always ignored
        # Use exact prefix matching (with trailing slash) to avoid
        # filtering out real paths like .gitignore or .github/
        filtered_extra = set()
        for p in extra:
            is_ignored = False
            for prefix in DIRTY_STATE_IGNORE_PREFIXES:
                # Exact directory prefix match (e.g., ".agent_bus/" matches ".agent_bus/foo")
                if p.startswith(prefix):
                    is_ignored = True
                    break
                # Directory itself without trailing slash
                if p == prefix.rstrip("/"):
                    is_ignored = True
                    break
            if not is_ignored:
                filtered_extra.add(p)

        # For renames, the old path is in extra but the new path is in claimed
        # This is valid - filter out rename old paths
        rename_old_paths = dirty.get("renamed", set())
        for rename_pair in rename_old_paths:
            if "|" in rename_pair:
                _, old_path = rename_pair.split("|", 1)
                filtered_extra.discard(old_path)

        # Handle untracked directory markers: if git status shows `?? dir/`,
        # but all actual files under that directory are claimed, remove the marker
        dir_markers_covered = set()
        for p in list(filtered_extra):
            # Check if this is a directory marker (ends with / or is a directory)
            if p.endswith("/") or (repo_root / p).is_dir():
                dir_path = p.rstrip("/")
                # Check if ALL actual files under this directory are claimed
                dir_full = repo_root / dir_path
                if dir_full.is_dir():
                    all_covered = True
                    for file_path in dir_full.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(repo_root).as_posix()
                            if rel_path not in claimed_set:
                                all_covered = False
                                break
                    if all_covered:
                        dir_markers_covered.add(p)
        filtered_extra -= dir_markers_covered

        if filtered_extra:
            return ValidationResult(
                "dirty_state",
                False,
                f"Dirty-worktree drift: {len(filtered_extra)} files outside package scope: {sorted(filtered_extra)[:5]}"
            )

    return ValidationResult("dirty_state", True)


def run_validation_command(repo_root: Path, command: list[str]) -> tuple[int, str]:
    """Run a validation command and return (exit_code, output)."""
    try:
        env = {**os.environ, "PYTHONHASHSEED": "0"}
        proc = subprocess.run(
            command,
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        output = (proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
        return proc.returncode, output
    except FileNotFoundError:
        return 127, f"[error] command not found: {command[0]}"
    except OSError as exc:
        return 126, f"[error] failed to execute: {exc}"


def run_validation_gates(
    repo_root: Path,
    package: dict[str, Any],
    verbose: bool = False,
) -> tuple[list[ValidationResult], bool]:
    """Run all 8 validation gates from Section 10.

    Returns (results, all_passed).
    """
    results: list[ValidationResult] = []

    # Gate 1: Dirty-state comparison
    if verbose:
        print("[meta-bridge] Gate 1: dirty-state comparison...")
    r1 = check_dirty_state(repo_root, package.get("changed_files", []), verbose=verbose)
    results.append(r1)

    # Gate 2: L4 execution contract (with explicit file list)
    if verbose:
        print("[meta-bridge] Gate 2: L4 execution contract...")
    enforcer = repo_root / "tools" / "checks" / "enforce_l4_execution_contract.py"
    if enforcer.exists():
        changed = package.get("changed_files", [])
        if changed:
            # Use --files with explicit file list from package
            exit_code, output = run_validation_command(
                repo_root,
                ["python3", "tools/checks/enforce_l4_execution_contract.py", "--files"] + changed
            )
            if exit_code == 0:
                results.append(ValidationResult("L4 contract", True))
            else:
                results.append(ValidationResult("L4 contract", False, output[:200]))
        else:
            results.append(ValidationResult("L4 contract", True))
    else:
        results.append(ValidationResult("L4 contract", True))

    # Gate 3: Host semantics ratchet
    if verbose:
        print("[meta-bridge] Gate 3: host semantics ratchet...")
    exit_code, output = run_validation_command(
        repo_root,
        ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"]
    )
    if exit_code == 0:
        results.append(ValidationResult("host_semantics_ratchet", True))
    else:
        results.append(ValidationResult("host_semantics_ratchet", False, output[:200]))

    # Gate 4: Host authority inventory ratchet
    if verbose:
        print("[meta-bridge] Gate 4: host authority inventory ratchet...")
    exit_code, output = run_validation_command(
        repo_root,
        ["python3", "tools/checks/check_host_authority_inventory_ratchet.py"]
    )
    if exit_code == 0:
        results.append(ValidationResult("host_authority_ratchet", True))
    else:
        results.append(ValidationResult("host_authority_ratchet", False, output[:200]))

    # Gate 5: Docs consistency
    if verbose:
        print("[meta-bridge] Gate 5: docs consistency...")
    exit_code, output = run_validation_command(
        repo_root,
        ["bash", "tools/checks/check_docs_consistency.sh"]
    )
    if exit_code == 0:
        results.append(ValidationResult("docs_consistency", True))
    else:
        results.append(ValidationResult("docs_consistency", False, output[:200]))

    # Gate 6: Attestation
    if verbose:
        print("[meta-bridge] Gate 6: attestation...")
    attest_script = repo_root / "tools" / "session" / "founder_session_attest.sh"
    if attest_script.exists():
        exit_code, output = run_validation_command(
            repo_root,
            ["bash", "tools/session/founder_session_attest.sh", "redteam"]
        )
        if exit_code == 0:
            results.append(ValidationResult("attestation", True))
        else:
            results.append(ValidationResult("attestation", False, output[:200]))
    else:
        results.append(ValidationResult("attestation", True))

    # Gate 7: Deferred blockers
    if verbose:
        print("[meta-bridge] Gate 7: deferred blockers...")
    r7 = check_deferred_blockers(repo_root, package.get("blocker_report_paths", []))
    results.append(r7)

    # Gate 8: TASKS.md authorization
    if verbose:
        print("[meta-bridge] Gate 8: TASKS.md authorization...")
    r8 = check_tasks_authorization(repo_root, package.get("task_id", ""))
    results.append(r8)

    all_passed = all(r.passed for r in results)
    return results, all_passed


def build_meta_reviewer_prompt(
    package: dict[str, Any],
    validation_results: list[ValidationResult],
    repo_root: Path,
) -> str:
    """Build the Codex meta-reviewer prompt."""
    template_path = SCRIPT_DIR / "templates" / "meta_bridge_task.txt"
    if not template_path.exists():
        raise MetaBridgeError(
            f"Meta-bridge template not found: {template_path}. "
            "Cannot proceed without the full prompt template."
        )
    template = Template(template_path.read_text(encoding="utf-8"))

    validation_summary = "\n".join(
        f"- {r.name}: {'PASS' if r.passed else 'FAIL'}" +
        (f" ({r.error[:100]})" if r.error else "")
        for r in validation_results
    )

    payload = {
        "package_json": json.dumps(package, indent=2),
        "validation_summary": validation_summary,
        "repo_root": str(repo_root),
        "task_id": package.get("task_id", "unknown"),
        "wave_name": package.get("wave_name", "unknown"),
        "lane": package.get("lane", "unknown"),
    }
    return template.safe_substitute(payload)


META_ENVELOPE_RE = re.compile(
    r"BEGIN_META_ENVELOPE\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```\s*)?END_META_ENVELOPE",
    re.DOTALL,
)


# Template-authorized decisions (what Codex can emit via the template)
# These are the only tokens the meta-reviewer is authorized to return
TEMPLATE_AUTHORIZED_DECISIONS = {
    "COMMIT_GO",
    "COMMIT_GO_HOLD_PUSH",
    "NO_ACTION",
    "NEEDS_PHASE_A",
    "NEEDS_PHASE_B",
    "STOP_FOR_FOUNDER",
    "STOP_FOR_TRIAGE_DISCUSSION",
    "ERROR_VALIDATION_FAILED",
}


def parse_meta_envelope(output: str) -> dict[str, Any]:
    """Parse the meta-reviewer's JSON envelope."""
    match = META_ENVELOPE_RE.search(output)
    if not match:
        raise MetaBridgeError("Meta-reviewer output missing BEGIN_META_ENVELOPE / END_META_ENVELOPE block")
    try:
        envelope = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise MetaBridgeError(f"Meta-envelope is not valid JSON: {exc}") from exc

    required = {"decision", "summary"}
    missing = required - set(envelope.keys())
    if missing:
        raise MetaBridgeError(f"Meta-envelope missing keys: {sorted(missing)}")

    # Validate decision is in template-authorized vocabulary only
    # (ERROR_* and RETRY_SUGGESTED are internal supervisor tokens, not Codex-emittable)
    if envelope["decision"] not in TEMPLATE_AUTHORIZED_DECISIONS:
        raise MetaBridgeError(
            f"Invalid decision token: {envelope['decision']}. "
            f"Template-authorized tokens: {sorted(TEMPLATE_AUTHORIZED_DECISIONS)}"
        )

    return envelope


def run_meta_review(
    paths: MetaBridgePaths,
    package: dict[str, Any],
    validation_results: list[ValidationResult],
    *,
    verbose: bool = False,
    timeout_s: int = 1200,
) -> dict[str, Any]:
    """Run Codex meta-reviewer and return parsed envelope."""
    import uuid
    prompt = build_meta_reviewer_prompt(package, validation_results, paths.repo_root)

    # Load adapter config
    config = load_bridge_config(paths.repo_root / ".agent_bus" / "bridge_config.json")
    adapter_name = "codex"

    if verbose:
        print(f"[meta-bridge] Running Codex meta-review (timeout: {timeout_s}s)...")

    # Generate job/turn IDs for this meta-review
    job_id = f"meta-{package.get('task_id', 'unknown')}-{uuid.uuid4().hex[:8]}"
    turn_id = f"{job_id}--r1-meta"

    # Write prompt to file for adapter
    prompt_dir = paths.bus_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"{turn_id}.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    # Raw output path for persistence
    raw_dir = paths.bus_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_output_path = raw_dir / f"{turn_id}.txt"

    try:
        # get_adapter(config, adapter_name) - config first, then name
        adapter = get_adapter(config, adapter_name)
        output = run_adapter(
            adapter,
            prompt_text=prompt,
            prompt_path=prompt_path,
            repo_root=paths.repo_root,
            job_id=job_id,
            turn_id=turn_id,
            agent_role="meta-reviewer",
            stream=True,
            raw_output_path=raw_output_path,
        )
    except Exception as exc:
        raise MetaBridgeError(f"Codex adapter failed: {exc}") from exc

    return parse_meta_envelope(output)


def run_meta_bridge(
    package_path: Path,
    *,
    verbose: bool = False,
    dry_run: bool = False,
) -> MetaBridgeResponse:
    """Main entry point: run meta-bridge supervisor on a package file.

    Returns MetaBridgeResponse with decision and details.
    """
    # Resolve repo_root from git toplevel, anchored to the package file location
    # This handles: (1) subdirectory invocation, (2) outside-repo invocation with absolute path
    package_dir = package_path.resolve().parent
    try:
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
            cwd=str(package_dir)  # Run git from package directory, not caller's cwd
        ).stdout.strip()
        repo_root = Path(toplevel)
    except subprocess.CalledProcessError:
        # Fall back to package directory if not in a git repo
        repo_root = package_dir
    paths = meta_bridge_paths(repo_root)
    ensure_runtime_dirs(paths)

    # Load and validate package
    if verbose:
        print(f"[meta-bridge] Loading package: {package_path}")

    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return MetaBridgeResponse(
            status="error",
            decision=Decision.ERROR_PACKAGE_INVALID.value,
            summary="Package is not valid JSON",
            error_code="INVALID_JSON",
            error_detail=str(exc),
            recovery_hint="Resubmit package as valid JSON",
        )
    except (OSError, IOError) as exc:
        # Handle file I/O errors: directory instead of file, file not found, permission denied, etc.
        return MetaBridgeResponse(
            status="error",
            decision=Decision.ERROR_PACKAGE_INVALID.value,
            summary="Package file cannot be read",
            error_code="FILE_READ_ERROR",
            error_detail=f"{type(exc).__name__}: {exc}",
            recovery_hint="Ensure package_path is a valid file path, not a directory",
        )

    # Schema validation
    valid, errors = validate_package_schema(package)
    if not valid:
        return MetaBridgeResponse(
            status="error",
            decision=Decision.ERROR_PACKAGE_INVALID.value,
            summary="Package failed schema validation",
            error_code="MISSING_REQUIRED_FIELD",
            error_detail="; ".join(errors),
            recovery_hint="Resubmit package with all 11 required fields",
        )

    # Capture repo state at start
    try:
        if verbose:
            print("[meta-bridge] Capturing repo state...")
        state_start = compute_repo_state(repo_root)

        # Run validation gates
        if verbose:
            print("[meta-bridge] Running validation gates...")
        validation_results, all_passed = run_validation_gates(repo_root, package, verbose=verbose)
    except KeyboardInterrupt:
        # Handle SIGINT during state capture or validation
        return MetaBridgeResponse(
            status="error",
            decision=Decision.ERROR_CODEX_ABORT.value,
            summary="Meta-bridge aborted by user during validation (SIGINT)",
            error_code="ABORT",
            error_detail="User interrupted validation phase with Ctrl+C or SIGINT",
            recovery_hint="Re-run meta-bridge when ready to complete validation",
        )

    passed = [r.name for r in validation_results if r.passed]
    failed = [{"name": r.name, "error": r.error} for r in validation_results if not r.passed]

    if not all_passed:
        return MetaBridgeResponse(
            status="partial",
            decision=Decision.ERROR_VALIDATION_FAILED.value,
            summary=f"{len(passed)} of {len(validation_results)} validations passed",
            validations_passed=passed,
            validations_failed=failed,
            request_for_claude="Address validation failures before retry",
        )

    if dry_run:
        return MetaBridgeResponse(
            status="success",
            decision=Decision.NO_ACTION.value,
            summary="Dry run: validations passed, Codex review skipped",
            validations_passed=passed,
            validations_failed=[],
            request_for_claude="Run without --dry-run for full meta-review",
        )

    # Run Codex meta-review
    with _MetaBridgeLock(paths.lock_path):
        try:
            envelope = run_meta_review(paths, package, validation_results, verbose=verbose)
        except KeyboardInterrupt:
            # Handle SIGINT gracefully with structured response
            return MetaBridgeResponse(
                status="error",
                decision=Decision.ERROR_CODEX_ABORT.value,
                summary="Meta-review aborted by user (SIGINT)",
                error_code="ABORT",
                error_detail="User interrupted meta-review with Ctrl+C or SIGINT",
                recovery_hint="Re-run meta-bridge when ready to complete review",
            )
        except MetaBridgeError as exc:
            if "timeout" in str(exc).lower():
                return MetaBridgeResponse(
                    status="error",
                    decision=Decision.ERROR_CODEX_TIMEOUT.value,
                    summary="Codex meta-review timed out",
                    error_code="TIMEOUT",
                    error_detail=str(exc),
                    recovery_hint="Retry with longer timeout or simpler package",
                )
            return MetaBridgeResponse(
                status="error",
                decision=Decision.ERROR_INTERNAL.value,
                summary="Codex meta-review failed",
                error_code="ADAPTER_ERROR",
                error_detail=str(exc),
            )

    # Check for staleness
    state_end = compute_repo_state(repo_root)
    if state_start.state_sha != state_end.state_sha:
        return MetaBridgeResponse(
            status="error",
            decision=Decision.ERROR_REPO_CHANGED.value,
            summary="Repo state changed during meta-review",
            error_code="STALE",
            error_detail=f"State SHA changed: {state_start.state_sha[:8]} → {state_end.state_sha[:8]}",
            recovery_hint="Re-run meta-bridge with fresh package (repo changed during review)",
        )

    # Build response from Codex envelope
    decision = envelope.get("decision", Decision.ERROR_INTERNAL.value)
    return MetaBridgeResponse(
        status="success",
        decision=decision,
        summary=envelope.get("summary", ""),
        validations_passed=passed,
        validations_failed=[],
        findings=envelope.get("findings", []),
        request_for_claude=envelope.get("request_for_claude", ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Meta-bridge supervisor: pre-commit convergence gate",
    )
    parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Path to Claude's pre-commit package JSON file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validations only, skip Codex review",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    # Helper to output error in JSON format when --json is set
    def output_error(error_msg: str, error_code: str) -> int:
        error_response = MetaBridgeResponse(
            status="error",
            decision=Decision.ERROR_PACKAGE_INVALID.value,
            summary=error_msg,
            error_code=error_code,
            error_detail=str(args.package),
            recovery_hint="Provide a valid package file path",
        )
        if args.json:
            print(json.dumps(error_response.to_dict(), indent=2))
        else:
            print(f"[error] {error_msg}: {args.package}", file=sys.stderr)
        return 1

    if not args.package.exists():
        return output_error("Package file not found", "FILE_NOT_FOUND")

    try:
        response = run_meta_bridge(
            args.package,
            verbose=args.verbose,
            dry_run=args.dry_run,
        )
    except MetaBridgeError as exc:
        error_response = MetaBridgeResponse(
            status="error",
            decision=Decision.ERROR_INTERNAL.value,
            summary="Meta-bridge internal error",
            error_code="INTERNAL_ERROR",
            error_detail=str(exc),
            recovery_hint="Check logs and retry",
        )
        if args.json:
            print(json.dumps(error_response.to_dict(), indent=2))
        else:
            print(f"[error] {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(response.to_dict(), indent=2))
    else:
        print(f"Decision: {response.decision}")
        print(f"Summary: {response.summary}")
        if response.validations_passed:
            print(f"Validations passed: {', '.join(response.validations_passed)}")
        if response.validations_failed:
            print("Validations failed:")
            for f in response.validations_failed:
                print(f"  - {f['name']}: {f['error']}")
        if response.request_for_claude:
            print(f"Request for Claude: {response.request_for_claude}")

    # Exit code based on decision
    if response.decision == Decision.COMMIT_GO.value:
        return 0
    elif response.decision == Decision.COMMIT_GO_HOLD_PUSH.value:
        return 0
    elif response.decision == Decision.NO_ACTION.value:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
