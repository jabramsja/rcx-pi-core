#!/usr/bin/env python3
"""Commit executor: 15-step mechanical commit pipeline.

Same command every time. Script infers state. No caller memory.
Bounded post-commit continuation only; no separate caller-managed resume mode.

Steps:
 1  validate_inputs           All handoff fields present + correct types
 2  ensure_feature_branch     Create or verify target branch
 3  ensure_tracker_note       Append tracker note to TASKS.md if missing
 4  stage_files               git add files_to_stage + force_add_files
 5  collect_and_stage_indicator  Run indicator collector, force-add artifact
 6  build_and_run_supervisor  Build 11-field package, run supervisor
 7  validate_receipt          Read receipt JSON, check decision
 8  run_pre_commit_script     Explicit pre-commit-doc-check + targeted pytest gate
 9  git_commit                git commit -m <message>
10  hold_check                COMMIT_GO_HOLD_PUSH = terminal stop
11  run_pre_push_script       Explicit pre-push-fast run
12  git_push                  Push to origin
13  ensure_pr                 Create or reuse PR
14  wait_ci                   gh pr checks --watch --required
15  ensure_review_clear_and_merge  Query reviews, merge if clear

See: reports/control_plane/commit_pipeline_automation_plan_2026-03-22.md
"""

from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import (
        DEFAULT_EXECUTOR_CONFIG,
        MAX_WAVE_ID_LEN,
        WAVE_ID_RE,
        agent_bus_path,
        agent_bus_relpath,
        bridge_config_path,
        ensure_bridge_config_path,
        is_agent_bus_runtime_path,
        load_executor_config,
        normalize_wave_id,
        packet_status_is_completed,
        read_control_plane_packet_status,
        resolve_agent_bus_dir,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        emit_pipeline_agent_event,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    DEFAULT_EXECUTOR_CONFIG = _mod.DEFAULT_EXECUTOR_CONFIG
    MAX_WAVE_ID_LEN = _mod.MAX_WAVE_ID_LEN
    WAVE_ID_RE = _mod.WAVE_ID_RE
    agent_bus_path = _mod.agent_bus_path
    agent_bus_relpath = _mod.agent_bus_relpath
    bridge_config_path = _mod.bridge_config_path
    ensure_bridge_config_path = _mod.ensure_bridge_config_path
    is_agent_bus_runtime_path = _mod.is_agent_bus_runtime_path
    load_executor_config = _mod.load_executor_config
    normalize_wave_id = _mod.normalize_wave_id
    packet_status_is_completed = _mod.packet_status_is_completed
    read_control_plane_packet_status = _mod.read_control_plane_packet_status
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError
    emit_pipeline_agent_event = _mod.emit_pipeline_agent_event

_ACTIVE_BUS_DIR: ContextVar[Path | None] = ContextVar("commit_executor_bus_dir", default=None)


def _active_bus_dir() -> Path | None:
    return _ACTIVE_BUS_DIR.get()

_bridge_adapters = None
_bridge_import_error = None
try:
    _agents_dir = str(Path(__file__).resolve().parent.parent / "agents")
    if _agents_dir not in sys.path:
        sys.path.insert(0, _agents_dir)
    import bridge_adapters as _bridge_adapters
except ImportError as _exc:
    _bridge_import_error = _exc

_tracker_sync_note = None
_tracker_sync_import_error = None
try:
    _executors_dir = str(SCRIPT_DIR)
    if _executors_dir not in sys.path:
        sys.path.insert(0, _executors_dir)
    import tracker_sync_note as _tracker_sync_note
except ImportError as _exc:
    _tracker_sync_import_error = _exc

BRANCH_PREFIX_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
TARGET_BRANCH_SUFFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,190}$")
TARGET_GATE_ID_RE = re.compile(r"^G[1-8]$")
PACKET_TARGET_GATE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(?:Target Gate|Target gate|target_gate_id)"
    r"(?:\*\*)?\s*:\s*`?([A-Za-z0-9][A-Za-z0-9._-]*)`?",
    re.IGNORECASE,
)

FORCE_ADD_DENYLIST = tuple(d.lower() for d in (".git/", ".env", ".agent_bus/"))

REQUIRED_HANDOFF_FIELDS = {
    "wave_id", "wave_class", "target_gate_id", "branch_prefix",
    "tracker_note_text", "fixes_implemented", "files_to_stage",
    "force_add_files", "commit_message", "pr_title", "pr_body",
    "base_branch", "pre_commit_receipt_path", "task_id", "caller",
}
OPTIONAL_HANDOFF_FIELDS = {
    "target_branch",
    "tracked_packet",
    "supervisor_lane",
    "deferred_items",
    "bridge_status",
    "scope_items",
    "evidence_handles",
}

VALID_CALLERS = {"phase_b", "phase_a", "update_tracker_only", "standalone"}

# Fields that may be empty/missing when caller is "standalone"
STANDALONE_OPTIONAL_FIELDS = {"pre_commit_receipt_path"}
_STANDALONE_RECOVERY_TERMINAL_STATUSES = frozenset({
    "success",
    "held",
    "question_for_founder",
    "max_rounds_reached",
    "supervisor_rejected",
})
_STANDALONE_RECOVERY_STATUSES = frozenset({
    "bot_findings_pending",
    "pre_push_failed",
    "stage_failed",
    "implementer_error",
    "bridge_error",
    "l4_contract_violation",
})
_STANDALONE_RECOVERY_ERROR_STEPS = frozenset({
    "run_pre_push_script",
    "run_pre_commit_script",
    "private_attr_gate",
    "stage_files",
    "implementer",
    "implementer_bridge_fix",
    "implementer_reentry",
    "pytest_fix",
    "bridge_subprocess",
    "reentry_bridge_subprocess",
})


@contextmanager
def _prepend_sys_path(path: Path | str):
    """Temporarily prepend a path for a bounded import without leaking it globally."""
    entry = str(path)
    inserted = False
    if entry and entry not in sys.path:
        sys.path.insert(0, entry)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass


def _load_repo_meta_bridge_client(repo_root: Path) -> tuple[Any, Any]:
    """Import the repo-local meta_bridge_client without leaving temp agent paths on sys.path."""
    try:
        from meta_bridge_client import run_meta_bridge_package, MetaBridgeClientError
    except ImportError:
        with _prepend_sys_path(repo_root / "mu" / "tools" / "agents"):
            from meta_bridge_client import run_meta_bridge_package, MetaBridgeClientError
    return run_meta_bridge_package, MetaBridgeClientError


def _load_repo_recovery_symbols(repo_root: Path) -> tuple[Any, Any]:
    """Import standalone recovery helpers without leaking repo_root onto sys.path."""
    try:
        from mu.tools.executors.recovery_gate import attempt_recovery
        from mu.tools.executors.executor_common import normalize_wave_id
    except ImportError:
        with _prepend_sys_path(repo_root):
            from mu.tools.executors.recovery_gate import attempt_recovery
            from mu.tools.executors.executor_common import normalize_wave_id
    return attempt_recovery, normalize_wave_id


def _should_attempt_standalone_recovery(result: dict[str, Any]) -> bool:
    """Return true when a standalone non-success result is recoverable."""
    status = str(result.get("status", "") or "").strip().lower()
    if status in _STANDALONE_RECOVERY_TERMINAL_STATUSES:
        return False
    if status in _STANDALONE_RECOVERY_STATUSES:
        return True
    step = str(result.get("step", "") or "").strip().lower()
    return status in {"error", "failed", "timeout", "stale"} and (
        step in _STANDALONE_RECOVERY_ERROR_STEPS
    )

# GraphQL query for PR review state
PR_REVIEW_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      headRefOid
      reviewDecision
      latestReviews(first: 20) {
        nodes {
          author { login }
          body
          state
          submittedAt
          commit { oid }
        }
      }
      reviewThreads(first: 100) {
        nodes {
          isResolved
          isOutdated
          comments(last: 20) {
            nodes {
              author { login }
              body
              path
              line
              createdAt
            }
          }
        }
      }
      comments(last: 30) {
        nodes {
          databaseId
          author { login }
          body
          createdAt
        }
      }
    }
  }
}
"""

BOT_REVIEW_LOGIN = "chatgpt-codex-connector"
BOT_REVIEW_TRIGGER_COMMENT = "@codex review"
BOT_REVIEW_WAIT_SECONDS = 45
BOT_REVIEW_ACK_WAIT_SECONDS = 60
BOT_REVIEW_POLL_SECONDS = 5
BOT_REVIEW_ACK_REACTION = "eyes"
CI_CHECK_REGISTRATION_WAIT_SECONDS = 120
CI_CHECK_REGISTRATION_POLL_SECONDS = 5
CI_REQUIRED_PASSING_BUCKETS = {"pass", "skipping"}
CI_REQUIRED_FAILING_BUCKETS = {"fail", "cancel"}
CI_REQUIRED_PENDING_BUCKETS = {"pending"}
CI_REQUIRED_PASSING_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}
CI_REQUIRED_FAILING_STATES = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
CI_REQUIRED_PENDING_STATES = {"PENDING", "IN_PROGRESS", "QUEUED", "REQUESTED", "WAITING", "EXPECTED"}
_COMMIT_EXECUTOR_CONFIG = load_executor_config(SCRIPT_DIR.parent.parent.parent)
_COMMIT_EXECUTOR_TIMEOUTS = _COMMIT_EXECUTOR_CONFIG.get("timeouts", {})
COMMIT_EXECUTOR_OUTER_BUDGET_S = _COMMIT_EXECUTOR_TIMEOUTS.get(
    "commit_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_executor"]
)
PRE_PUSH_FAST_TIMEOUT_S = _COMMIT_EXECUTOR_TIMEOUTS.get("pre_push_fast", 900)
BOT_NO_ISSUES_COMMENT_RE = re.compile(
    r"Codex Review:\s*.*did(?:n't| not) find any major issues",
    re.IGNORECASE | re.DOTALL,
)
BOT_USAGE_LIMIT_COMMENT_RE = re.compile(
    r"reached your Codex usage limits",
    re.IGNORECASE,
)
BOT_BLOCKING_REVIEW_BADGE_RE = re.compile(
    r"!\[\s*P[0-2]\s+Badge\s*\]\(|badge/P[0-2]-",
    re.IGNORECASE,
)
COMMIT_CONTINUATION_VERSION = 1
CONTINUATION_ACTIVE_STATUS = "post_commit_pending"
TRANSIENT_STATUS_PREFIXES = (".agent_bus/", ".scratch/")
COMMIT_PATH_REFRESH_START = "<!-- COMMIT_PATH_TRUTH_REFRESH:start -->"
COMMIT_PATH_REFRESH_END = "<!-- COMMIT_PATH_TRUTH_REFRESH:end -->"
DEFERRED_AUTH_REFRESH_START = "<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->"
DEFERRED_AUTH_REFRESH_END = "<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->"

BOT_REMEDIATION_MAX_ROUNDS = 2
_COMMIT_EXECUTOR_BACKENDS = _COMMIT_EXECUTOR_CONFIG.get("backends", {})
BOT_REMEDIATION_ADAPTER = _COMMIT_EXECUTOR_BACKENDS.get(
    "bot_remediation", DEFAULT_EXECUTOR_CONFIG["backends"]["bot_remediation"]
)
BOT_REMEDIATION_TIMEOUT_S = _COMMIT_EXECUTOR_TIMEOUTS.get("bot_remediation", 600)
BOT_REMEDIATION_STALE_TIMEOUT_S = 300.0


def _is_transient_status_path(path: str) -> bool:
    return bool(path) and (
        is_agent_bus_runtime_path(path)
        or any(path.startswith(prefix) for prefix in TRANSIENT_STATUS_PREFIXES)
    )


def _runtime_bus_artifact_match(path: str) -> str | None:
    return ".agent_bus*" if is_agent_bus_runtime_path(path) else None

# Validate sub-timeouts fit within outer budget at import time
for _sub_name, _sub_val in [
    ("pre_push_fast", PRE_PUSH_FAST_TIMEOUT_S),
    ("bot_remediation", BOT_REMEDIATION_TIMEOUT_S),
]:
    if _sub_val > COMMIT_EXECUTOR_OUTER_BUDGET_S:
        raise ExecutorCommonError(
            f"commit_executor sub-timeout {_sub_name}={_sub_val}s exceeds "
            f"outer budget commit_executor={COMMIT_EXECUTOR_OUTER_BUDGET_S}s"
        )


def _extract_founder_override_token(text: str) -> str:
    """Extract a bounded FOUNDER_OVERRIDE token from untrusted text."""
    if not text:
        return ""
    match = re.search(r"FOUNDER_OVERRIDE:\s*(\S+)", text)
    if not match:
        return ""
    return match.group(1).strip().rstrip("`.,;")


def _extract_founder_override_from_tracker_note(text: str) -> str:
    """Extract wave-bound FOUNDER_OVERRIDE token from stored tracker-note text."""
    return _extract_founder_override_token(text)


def _normalize_founder_override_token(token: str | None) -> str:
    """Canonicalize bare or prefixed override input to the bare token id."""
    if not isinstance(token, str):
        return ""
    clean = token.strip()
    if not clean:
        return ""
    extracted = _extract_founder_override_token(clean)
    if extracted:
        return extracted
    return clean.split()[0].strip().rstrip("`.,;")


def _wave_class_allows_founder_override(wave_class: Any) -> bool:
    """Return true only for wave classes allowed to carry founder override tokens."""
    return str(wave_class or "").strip() in ("L4_ENABLER", "MAINTENANCE")


def _extract_maintenance_bypass_fields_from_text(text: str) -> tuple[str, str]:
    """Extract optional consecutive-maintenance bypass fields from text."""
    if not text:
        return "", ""
    unblocks_wave_id = ""
    unblocks_runtime_blocker = ""
    unblocks_wave_pattern = re.compile(
        r"(?<![A-Za-z0-9_])(?:Unblocks wave id:|unblocks_wave_id:)\s*([A-Za-z0-9_-]+)"
    )
    unblocks_runtime_blocker_pattern = re.compile(
        r"(?<![A-Za-z0-9_])(?:Unblocks runtime blocker:|unblocks_runtime_blocker:)\s*(.+?)(?:\.\s|$)"
    )
    for raw_line in text.splitlines():
        clean = str(raw_line or "").strip()
        if not unblocks_wave_id:
            match = unblocks_wave_pattern.search(clean)
            if match:
                unblocks_wave_id = match.group(1).strip().strip("`").rstrip(".,;")
        if not unblocks_runtime_blocker:
            match = unblocks_runtime_blocker_pattern.search(clean)
            if match:
                unblocks_runtime_blocker = match.group(1).strip().strip("`").rstrip(".,;")
        if unblocks_wave_id and unblocks_runtime_blocker:
            return unblocks_wave_id, unblocks_runtime_blocker
    return unblocks_wave_id, unblocks_runtime_blocker


def _dedupe_repo_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw_path in paths:
        normalized = _normalize_repo_relpath(raw_path)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _current_staged_diff_paths(repo_root: Path) -> list[str]:
    try:
        proc = _run(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    except subprocess.CalledProcessError:
        return []
    return _dedupe_repo_paths(proc.stdout.splitlines())


def _canonicalize_stage_path(repo_root: Path, raw_path: str) -> str:
    """Resolve repo-local symlink aliases before passing paths to git add."""
    normalized = _normalize_repo_relpath(raw_path)
    if not normalized:
        return normalized
    if _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return normalized
    try:
        repo_resolved = repo_root.resolve()
        resolved = (repo_root / normalized).resolve(strict=False)
        return resolved.relative_to(repo_resolved).as_posix()
    except (OSError, RuntimeError, ValueError):
        return normalized


def _canonicalize_stage_paths(repo_root: Path, paths: list[str]) -> list[str]:
    return _dedupe_repo_paths([
        _canonicalize_stage_path(repo_root, path)
        for path in paths
        if isinstance(path, str)
    ])


def _path_deleted_in_branch_history(repo_root: Path, relpath: str) -> bool:
    upstream = _run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    upstream_ref = upstream.stdout.strip()
    if upstream.returncode != 0 or not upstream_ref:
        return False

    merge_base = _run(
        ["git", "merge-base", upstream_ref, "HEAD"],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    base_sha = merge_base.stdout.strip()
    if merge_base.returncode != 0 or not base_sha:
        return False

    committed_delete = _run(
        [
            "git", "diff", "--name-only", "--diff-filter=D",
            f"{base_sha}..HEAD", "--", relpath,
        ],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    return committed_delete.returncode == 0 and bool(committed_delete.stdout.strip())


def _stage_handoff_paths(
    repo_root: Path,
    *,
    files_to_stage: list[str],
    force_files: list[str],
) -> tuple[list[str], list[str]]:
    canonical_files = _canonicalize_stage_paths(repo_root, files_to_stage)
    canonical_force = _canonicalize_stage_paths(repo_root, force_files)
    existing_files: list[str] = []
    missing_files: list[str] = []
    for relpath in canonical_files:
        path = repo_root / relpath
        if path.exists() or path.is_symlink():
            existing_files.append(relpath)
        else:
            missing_files.append(relpath)
    if existing_files:
        _run(["git", "add", "--", *existing_files], cwd=repo_root)
    for relpath in missing_files:
        staged_delete = _run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=D", "--", relpath],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
        if staged_delete.returncode == 0 and staged_delete.stdout.strip():
            continue
        deleted = _run(
            ["git", "ls-files", "--deleted", "--", relpath],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
        if deleted.returncode == 0 and deleted.stdout.strip():
            _run(["git", "add", "-u", "--", relpath], cwd=repo_root)
        else:
            committed_delete = _run(
                [
                    "git", "diff", "--name-only", "--diff-filter=D",
                    "HEAD^..HEAD", "--", relpath,
                ],
                cwd=repo_root,
                check=False,
                timeout=30,
            )
            if committed_delete.returncode == 0 and committed_delete.stdout.strip():
                continue
            if _path_deleted_in_branch_history(repo_root, relpath):
                continue
            _run(["git", "add", "--", relpath], cwd=repo_root)
    if canonical_force:
        _run(["git", "add", "-f", "--", *canonical_force], cwd=repo_root)
    return canonical_files, canonical_force


def _git_index_contains_repo_path(repo_root: Path, relpath: str) -> bool:
    """Return true when relpath is bound to Git's tracked/staged index."""
    normalized = _normalize_repo_relpath(str(relpath or ""))
    if not normalized or _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return False
    try:
        result = _run(
            ["git", "ls-files", "--error-unmatch", "--", normalized],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _git_index_text_for_repo_path(repo_root: Path, relpath: str) -> str | None:
    """Read relpath from Git's index instead of the mutable working tree."""
    normalized = _normalize_repo_relpath(str(relpath or ""))
    if not normalized or _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return None
    if not _git_index_contains_repo_path(repo_root, normalized):
        return None
    try:
        result = _run(
            ["git", "show", f":{normalized}"],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _tracked_packet_paths_from_record(record: dict[str, Any]) -> list[str]:
    paths: list[str] = []

    def add_candidate(raw_path: Any) -> None:
        tracked_packet = _normalize_repo_relpath(str(raw_path or ""))
        if not tracked_packet:
            return
        if _is_absolute_untrusted_path(tracked_packet) or _has_path_traversal(tracked_packet):
            return
        if tracked_packet not in paths:
            paths.append(tracked_packet)

    add_candidate(record.get("tracked_packet"))
    candidates = record.get("next_candidates")
    if not isinstance(candidates, list):
        return paths
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        add_candidate(candidate.get("tracked_packet"))
    return paths


def _tracked_packet_text_from_record(record: dict[str, Any], repo_root: Path) -> str:
    repo_root_resolved = repo_root.resolve()
    for tracked_packet in _tracked_packet_paths_from_record(record):
        packet_path = (repo_root / tracked_packet).resolve()
        if repo_root_resolved not in packet_path.parents:
            continue
        packet_text = _git_index_text_for_repo_path(repo_root, tracked_packet)
        if packet_text is not None:
            return packet_text
    return ""


def _tracked_packet_path_from_record(record: dict[str, Any]) -> str:
    paths = _tracked_packet_paths_from_record(record)
    return paths[0] if paths else ""


def _normalize_target_gate_id(value: Any) -> str:
    gate = str(value or "").strip().strip("`.,;")
    return gate if TARGET_GATE_ID_RE.fullmatch(gate) else ""


def _extract_target_gate_id_from_text(text: str) -> str:
    for line in str(text or "").splitlines():
        match = PACKET_TARGET_GATE_RE.match(line)
        if match:
            gate = _normalize_target_gate_id(match.group(1))
            if gate:
                return gate
    return ""


def _resolve_target_gate_id(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
) -> str:
    for value in (
        (embedded_handoff or {}).get("target_gate_id"),
        record.get("target_gate_id"),
    ):
        gate = _normalize_target_gate_id(value)
        if gate:
            return gate
    gate = _extract_target_gate_id_from_text(_tracked_packet_text_from_record(record, repo_root))
    return gate or "G8"


def _extract_founder_override_from_routing_record(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
) -> str:
    for key in ("founder_override_token", "founder_override"):
        token = _normalize_founder_override_token(record.get(key))
        if token:
            return token
    for text in [
        str(record.get("tracker_note_text") or ""),
        str((embedded_handoff or {}).get("tracker_note_text") or ""),
        _tracked_packet_text_from_record(record, repo_root),
    ]:
        token = _extract_founder_override_token(text)
        if token:
            return token
    return ""


def _extract_same_wave_founder_override_from_tasks(repo_root: Path, wave_id: str) -> str:
    """Return a same-wave founder override already staged or written in TASKS.md."""
    normalized_wave_id = normalize_wave_id(wave_id)
    if not normalized_wave_id:
        return ""

    candidates: list[str] = []
    staged_tasks = _git_index_text_for_repo_path(repo_root, "TASKS.md")
    if staged_tasks is not None:
        candidates.append(staged_tasks)
    try:
        working_tasks = (repo_root / "TASKS.md").read_text(encoding="utf-8")
    except OSError:
        working_tasks = ""
    if working_tasks and working_tasks not in candidates:
        candidates.append(working_tasks)

    for text in candidates:
        for line in text.splitlines():
            token = _extract_founder_override_token(line)
            if token and normalize_wave_id(token) == normalized_wave_id:
                return token
    return ""


def _packet_declares_same_wave_id(packet_text: str, normalized_wave_id: str) -> bool:
    """Return true when packet metadata declares exactly normalized_wave_id."""
    if not packet_text or not normalized_wave_id:
        return False
    wave_id_pattern = re.compile(
        r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:Wave ID|wave_id)(?:\*\*)?\s*:\s*`?([A-Za-z0-9][A-Za-z0-9._-]*)`?",
        re.IGNORECASE,
    )
    for line in packet_text.splitlines():
        match = wave_id_pattern.match(line)
        if not match:
            continue
        if normalize_wave_id(match.group(1)) == normalized_wave_id:
            return True
    return False


_CONTROL_SURFACE_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])control-surface(?![A-Za-z0-9_-])"
)
_NEGATED_CONTROL_SURFACE_RE = re.compile(
    r"(?i)\b(?:anti|no|non|not|without)[-\s]+control-surface\b"
)
_PACKET_LANE_RE = re.compile(
    r"(?i)^\s*(?:[-*]\s*)?(?:\*\*)?Lane(?:\*\*)?\s*:\s*(.+?)\s*$"
)
_PACKET_AUTHORIZATION_RE = re.compile(
    r"(?i)^\s*(?:[-*]\s*)?(?:\*\*)?(?:Founder authorization|Authorization|Authority)"
    r"(?:\*\*)?\s*:\s*(.+?)\s*$"
)
_NEGATED_AUTHORIZATION_RE = re.compile(
    r"(?i)\b(?:authorization\s+(?:is\s+)?(?:denied|not|rejected|revoked)|"
    r"denied|not\s+(?:authorized|approved|granted)|no\s+(?:standing\s+pipeline-bug-fix\s+)?"
    r"authorization|rejected|revoked|without\s+authorization)\b"
)
_STANDING_PIPELINE_BUG_FIX_AUTHORIZATION_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])standing pipeline-bug-fix authorization(?![A-Za-z0-9_-])"
)
_AUTHORIZED_CONTROL_SURFACE_L4_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])authorized\s+control-surface\s+l4[_ -]?enabler"
    r"(?![A-Za-z0-9_-])"
)


def _packet_declares_positive_control_surface_lane(packet_text: str) -> bool:
    for line in packet_text.splitlines():
        lane_match = _PACKET_LANE_RE.match(line)
        if not lane_match:
            continue
        lane = lane_match.group(1)
        if _NEGATED_CONTROL_SURFACE_RE.search(lane):
            continue
        if _CONTROL_SURFACE_TOKEN_RE.search(lane):
            return True
    return False


def _packet_contains_negative_authorization(packet_text: str) -> bool:
    return any(_NEGATED_AUTHORIZATION_RE.search(line) for line in packet_text.splitlines())


def _packet_declares_explicit_control_surface_l4_authorization(packet_text: str) -> bool:
    for line in packet_text.splitlines():
        if _NEGATED_AUTHORIZATION_RE.search(line):
            continue
        if _AUTHORIZED_CONTROL_SURFACE_L4_RE.search(line):
            return True
    return False


def _packet_declares_positive_standing_authorization(packet_text: str) -> bool:
    for line in packet_text.splitlines():
        if _NEGATED_AUTHORIZATION_RE.search(line):
            continue
        auth_match = _PACKET_AUTHORIZATION_RE.match(line)
        if not auth_match:
            continue
        if _STANDING_PIPELINE_BUG_FIX_AUTHORIZATION_RE.search(auth_match.group(1)):
            return True
    return False


def _packet_authorizes_control_surface_l4(packet_text: str) -> bool:
    if _packet_contains_negative_authorization(packet_text):
        return False
    if _packet_declares_explicit_control_surface_l4_authorization(packet_text):
        return True
    return (
        _packet_declares_positive_control_surface_lane(packet_text)
        and _packet_declares_positive_standing_authorization(packet_text)
    )


def _control_surface_packet_authorized(
    record: dict[str, Any],
    repo_root: Path,
    *,
    wave_id: str,
) -> bool:
    """Return true only when packet content declares control-surface authority."""
    normalized_wave_id = normalize_wave_id(wave_id or str(record.get("wave_name") or record.get("wave_id") or ""))
    if not normalized_wave_id:
        return False
    repo_resolved = repo_root.resolve()
    for tracked_packet in _tracked_packet_paths_from_record(record):
        if not tracked_packet.startswith("reports/control_plane/"):
            continue
        packet_path = (repo_root / tracked_packet).resolve()
        if repo_resolved not in packet_path.parents:
            continue
        packet_text = _git_index_text_for_repo_path(repo_root, tracked_packet)
        if packet_text is None:
            continue
        if not _packet_declares_same_wave_id(packet_text, normalized_wave_id):
            continue
        if _packet_authorizes_control_surface_l4(packet_text):
            return True
    return False


def _is_authorized_control_surface_l4_enabler(
    record: dict[str, Any],
    *,
    embedded_handoff: dict[str, Any] | None,
    wave_id: str,
    wave_class: str,
    repo_root: Path,
) -> bool:
    if str(wave_class or "").strip() != "L4_ENABLER":
        return False
    _ = embedded_handoff
    return _control_surface_packet_authorized(record, repo_root, wave_id=str(wave_id or ""))


def _resolve_control_surface_founder_override_token(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
    wave_id: str,
    wave_class: str,
) -> str:
    token = _extract_founder_override_from_routing_record(
        record,
        repo_root,
        embedded_handoff=embedded_handoff,
    )
    if token:
        return token if _wave_class_allows_founder_override(wave_class) else ""
    if _is_authorized_control_surface_l4_enabler(
        record,
        embedded_handoff=embedded_handoff,
        wave_id=wave_id,
        wave_class=wave_class,
        repo_root=repo_root,
    ):
        return normalize_wave_id(wave_id)
    return ""


def _missing_founder_override_error(wave_id: str) -> str:
    return (
        "Missing FOUNDER_OVERRIDE token for standalone L4_ENABLER commit handoff "
        f"before supervisor Step 6 (wave_id={wave_id}). Expected source: "
        "routing_record.tracker_note_text, embedded handoff tracker_note_text, "
        "tracked packet text, or authorized reports/control_plane packet text "
        "declaring same-wave control-surface authorization that permits deriving "
        "FOUNDER_OVERRIDE:<wave_id>."
    )


def _resolve_standalone_founder_override_token(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None,
    wave_id: str,
    wave_class: str,
) -> tuple[str, str | None]:
    token = _resolve_control_surface_founder_override_token(
        record,
        repo_root,
        embedded_handoff=embedded_handoff,
        wave_id=wave_id,
        wave_class=wave_class,
    )
    if token:
        return token, None
    token = _extract_same_wave_founder_override_from_tasks(repo_root, wave_id)
    if token and _wave_class_allows_founder_override(wave_class):
        return token, None
    if str(wave_class or "").strip() == "L4_ENABLER":
        return "", _missing_founder_override_error(wave_id)
    return "", None


def _extract_maintenance_bypass_from_routing_record(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
) -> tuple[str, str]:
    unblocks_wave_id = str(record.get("unblocks_wave_id") or "").strip().strip("`").rstrip(".,;")
    unblocks_runtime_blocker = (
        str(record.get("unblocks_runtime_blocker") or "").strip().strip("`").rstrip(".,;")
    )
    for text in [
        str(record.get("tracker_note_text") or ""),
        str((embedded_handoff or {}).get("tracker_note_text") or ""),
        _tracked_packet_text_from_record(record, repo_root),
    ]:
        extracted_wave_id, extracted_runtime_blocker = _extract_maintenance_bypass_fields_from_text(text)
        if extracted_wave_id and not unblocks_wave_id:
            unblocks_wave_id = extracted_wave_id
        if extracted_runtime_blocker and not unblocks_runtime_blocker:
            unblocks_runtime_blocker = extracted_runtime_blocker
        if unblocks_wave_id and unblocks_runtime_blocker:
            break
    return unblocks_wave_id, unblocks_runtime_blocker


def _summarize_path_preview(paths: list[str]) -> str:
    preview = ", ".join(paths[:3])
    remainder = len(paths) - min(len(paths), 3)
    if remainder > 0:
        preview = f"{preview}, +{remainder} more"
    return preview


def _build_standalone_staged_diff_fixes(paths: list[str]) -> list[str]:
    preview = _summarize_path_preview(paths)
    return [f"Resume standalone continuation for current staged diff: {preview}."]


def _build_standalone_commit_message(wave_id: str) -> str:
    return f"chore: continue {wave_id} staged diff"


def _is_wave_bound_target_branch(
    target_branch: str,
    *,
    branch_prefix: str,
    wave_id: str,
) -> bool:
    """Allow only the canonical wave branch or its restart descendants."""
    if not target_branch or not branch_prefix or not wave_id:
        return False
    prefix = f"{branch_prefix}/"
    if not target_branch.startswith(prefix):
        return False
    suffix = target_branch[len(prefix):]
    if not TARGET_BRANCH_SUFFIX_RE.fullmatch(suffix):
        return False
    return (
        suffix == wave_id
        or suffix == f"{wave_id}-restart"
        or suffix.startswith(f"{wave_id}-restart-")
    )


def _handoff_plan_path(handoff: dict[str, Any]) -> str | None:
    tracked_packet = handoff.get("tracked_packet")
    if isinstance(tracked_packet, str) and tracked_packet.strip():
        return _normalize_repo_relpath(tracked_packet)
    scope_items = handoff.get("scope_items")
    if not isinstance(scope_items, list):
        return None
    for item in scope_items:
        text = str(item or "").strip()
        if text.endswith(".md"):
            return text
    return None


def _path_field_error(field_name: str, path: str) -> str | None:
    if not path:
        return f"{field_name} is required"
    if _is_absolute_untrusted_path(path):
        return f"{field_name} must be repo-relative: {path}"
    if _has_path_traversal(path):
        return f"Path traversal in {field_name}: {path}"
    return None


def _commit_refresh_packet_path(handoff: dict[str, Any]) -> tuple[str, str | None]:
    """Resolve the builder-owned control-plane packet path from the canonical handoff."""
    tracked_packet = handoff.get("tracked_packet")
    if tracked_packet is not None:
        if not isinstance(tracked_packet, str) or not tracked_packet.strip():
            return "", "tracked_packet must be a non-empty string when provided"
        packet = _normalize_repo_relpath(tracked_packet)
        error = _path_field_error("tracked_packet", packet)
        if error:
            return "", error
        if not packet.startswith("reports/control_plane/") or not packet.endswith(".md"):
            return "", f"tracked_packet must name a reports/control_plane/*.md packet: {packet}"
        return packet, None

    return "", None


def _tracker_marker_value(note: str, marker: str) -> str:
    marker_names = [
        "Class",
        "target_gate_id",
        "no_op_proof",
        "defer_reason_code",
        "evidence_command",
        "evidence_delta",
        "progress_proof_before",
        "progress_proof_after",
        "primary_blocker_class",
        "primary_invariant_id",
        "indicator_artifact_ref",
        "indicator_collection_command",
        "bootstrap_endgame_policy",
        "boot0_track_id",
        "boot0_progress_state",
        "FOUNDER_OVERRIDE",
        "unblocks_wave_id",
        "unblocks_runtime_blocker",
    ]
    other_markers = "|".join(re.escape(name) for name in marker_names if name != marker)
    pattern = re.compile(
        rf"(?:^|\s){re.escape(marker)}:\s*"
        rf"(.+?)(?=\s(?:{other_markers}):|$)"
    )
    match = pattern.search(note or "")
    if not match:
        return ""
    return match.group(1).strip().rstrip()


def _refresh_tracker_note_wave_file_count(note: str, file_count: int) -> str:
    """Align generated tracker-note file counts with the rebuilt staged scope."""
    if file_count < 0:
        return note

    replacements = [
        (
            r"Routed commit handoff scopes \d+ wave-owned file\(s\)",
            f"Routed commit handoff scopes {file_count} wave-owned file(s)",
        ),
        (
            r"handoff for ([^.;]+?) is now bound to \d+ wave-owned file\(s\)",
            rf"handoff for \1 is now bound to {file_count} wave-owned file(s)",
        ),
        (
            r"handoff for ([^.;]+?) now carries \d+ wave-owned file\(s\)",
            rf"handoff for \1 now carries {file_count} wave-owned file(s)",
        ),
        (
            r"handoff now carries \d+ wave-owned file\(s\)",
            f"handoff now carries {file_count} wave-owned file(s)",
        ),
        (
            r"Phase B emitted a commit-ready handoff for ([^.;]+?) with \d+ wave-owned file\(s\)",
            rf"Phase B emitted a commit-ready handoff for \1 with {file_count} wave-owned file(s)",
        ),
    ]
    refreshed = note
    for pattern, replacement in replacements:
        refreshed = re.sub(pattern, replacement, refreshed)
    return refreshed


def _refresh_tracker_note_bridge_rounds(
    note: str,
    bridge_status: dict[str, Any] | None,
) -> str:
    """Align generated tracker-note bridge rounds with the supervisor package."""
    if not isinstance(bridge_status, dict):
        return note
    rounds = max(
        _bridge_status_round_value(bridge_status.get("rounds")),
        _bridge_status_round_value(bridge_status.get("total_rounds")),
    )
    if rounds <= 0:
        return note
    return re.sub(r"bridge rounds=\d+", f"bridge rounds={rounds}", note)


def _refresh_tracker_note_test_evidence(note: str, staged_paths: list[str]) -> str:
    """Align generated tracker-note pytest evidence with the rebuilt staged scope."""
    test_files = _collect_wave_test_files(staged_paths)
    if not test_files:
        return note
    evidence_command = (
        "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
        + " ".join(test_files)
        + "`"
    )
    refreshed = re.sub(
        r"evidence_command:\s*`PYTHONHASHSEED=0 python3 -m pytest -x --tb=short [^`]+`",
        evidence_command,
        note,
    )
    refreshed = re.sub(
        r"Final pytest gate covered \d+ test file\(s\)",
        f"Final pytest gate covered {len(test_files)} test file(s)",
        refreshed,
    )
    refreshed = re.sub(
        r"Evidence gate exercises \d+ wave-owned test module\(s\)",
        f"Evidence gate exercises {len(test_files)} wave-owned test module(s)",
        refreshed,
    )
    refreshed = re.sub(
        r", \d+ wave-owned test module\(s\),",
        f", {len(test_files)} wave-owned test module(s),",
        refreshed,
    )
    return refreshed


def _render_commit_path_truth_refresh_block(
    *,
    wave_id: str,
    active_packet_path: str,
    tracker_note_text: str,
    staged_paths: list[str],
    indicator_path: str,
    commit_status: str,
    evidence_handles: dict[str, str],
    pre_commit_receipt_path: str,
) -> str:
    tracker_note_sha = hashlib.sha256(tracker_note_text.encode("utf-8")).hexdigest()
    evidence_command = _tracker_marker_value(tracker_note_text, "evidence_command")
    evidence_delta = _tracker_marker_value(tracker_note_text, "evidence_delta")
    lines = [
        COMMIT_PATH_REFRESH_START,
        "## Commit Path Truth Refresh",
        "",
        f"- Refresh wave: `{wave_id}`",
        f"- Active packet: `{active_packet_path}`",
        f"- Commit status: `{commit_status}`",
        f"- Tracker note sha256: `{tracker_note_sha}`",
        f"- Indicator artifact: `{indicator_path}`",
    ]
    if pre_commit_receipt_path:
        lines.append(f"- Pre-commit receipt handle: `{pre_commit_receipt_path}`")
    if evidence_command:
        lines.append(f"- Evidence command: {evidence_command}")
    if evidence_delta:
        lines.append(f"- Evidence delta: {evidence_delta}")
    lines.append("- Evidence handles:")
    if evidence_handles:
        for key in sorted(evidence_handles):
            lines.append(f"  - `{key}`: `{evidence_handles[key]}`")
    else:
        lines.append("  - none")
    lines.append("- Current staged files:")
    for path in staged_paths:
        lines.append(f"  - `{path}`")
    lines.append(COMMIT_PATH_REFRESH_END)
    return "\n".join(lines) + "\n"


def _replace_commit_path_truth_refresh_block(packet_text: str, block: str) -> str:
    start = packet_text.find(COMMIT_PATH_REFRESH_START)
    end = packet_text.find(COMMIT_PATH_REFRESH_END)
    if start != -1 and end != -1 and end > start:
        end += len(COMMIT_PATH_REFRESH_END)
        trailing_newline = "\n" if end < len(packet_text) and packet_text[end:end + 1] != "\n" else ""
        return packet_text[:start].rstrip() + "\n\n" + block.rstrip() + trailing_newline + packet_text[end:]
    if start != -1 or end != -1:
        raise ValueError("existing Commit Path Truth Refresh markers are unbalanced")
    return packet_text.rstrip() + "\n\n" + block


def _same_wave_deferred_non_blocking_paths(wave_id: str, paths: list[str]) -> list[str]:
    normalized_wave = normalize_wave_id(str(wave_id or ""))
    if not normalized_wave:
        return []
    expected = f"reports/deferred/non_blocking/{normalized_wave}_bridge_nonblockers.md"
    return [expected] if expected in set(_dedupe_repo_paths(paths)) else []


def _render_same_wave_deferred_authorization_block(wave_id: str, paths: list[str]) -> str:
    lines = [
        DEFERRED_AUTH_REFRESH_START,
        "## Same-Wave Deferred Non-Blocking Authorization",
        "",
        f"- Refresh wave: `{wave_id}`",
        "- Purpose: Phase B and commit automation may stage the same-wave "
        "non-blocking bridge findings packet as deferred follow-up instead of "
        "blocking an otherwise commit-ready wave.",
        "- Authorized deferred packet(s):",
    ]
    for path in paths:
        lines.append(f"  - `{path}`")
    lines.extend([
        "- Scope binding: the packet(s) above are in scope only as generated "
        "same-wave non-blocking bridge findings packets.",
        "- Acceptance binding: the final touched-file set may include the packet(s) "
        "above when they are also present in `deferred_items` or current staged files.",
        DEFERRED_AUTH_REFRESH_END,
    ])
    return "\n".join(lines) + "\n"


def _replace_same_wave_deferred_authorization_block(packet_text: str, block: str) -> str:
    start = packet_text.find(DEFERRED_AUTH_REFRESH_START)
    end = packet_text.find(DEFERRED_AUTH_REFRESH_END)
    if start != -1 and end != -1 and end > start:
        end += len(DEFERRED_AUTH_REFRESH_END)
        trailing_newline = "\n" if end < len(packet_text) and packet_text[end:end + 1] != "\n" else ""
        return packet_text[:start].rstrip() + "\n\n" + block.rstrip() + trailing_newline + packet_text[end:]
    if start != -1 or end != -1:
        raise ValueError("existing Same-Wave Deferred Non-Blocking Authorization markers are unbalanced")
    commit_refresh_start = packet_text.find(COMMIT_PATH_REFRESH_START)
    if commit_refresh_start != -1:
        return (
            packet_text[:commit_refresh_start].rstrip()
            + "\n\n"
            + block.rstrip()
            + "\n\n"
            + packet_text[commit_refresh_start:]
        )
    return packet_text.rstrip() + "\n\n" + block


def _section_bounds(lines: list[str], heading: str) -> tuple[int, int] | None:
    start = next((idx for idx, line in enumerate(lines) if line.strip() == heading), None)
    if start is None:
        return None
    end = next(
        (idx for idx in range(start + 1, len(lines)) if lines[idx].startswith("## ")),
        len(lines),
    )
    return start, end


def _append_paths_to_bounded_packet_line(line: str, paths: list[str]) -> str:
    missing = [path for path in paths if f"`{path}`" not in line]
    if not missing:
        return line
    addition = ", " + ", ".join(f"`{path}`" for path in missing)
    for anchor in (
        ", or a canonical",
        ", and the same-wave canonical",
        ", or returns",
        " or returns",
    ):
        if anchor in line:
            return line.replace(anchor, addition + anchor, 1)
    return line.rstrip(".") + addition + "."


def _refresh_same_wave_deferred_packet_authorization(
    packet_text: str,
    *,
    wave_id: str,
    deferred_paths: list[str],
) -> str:
    paths = _same_wave_deferred_non_blocking_paths(wave_id, deferred_paths)
    if not paths:
        return packet_text

    had_final_newline = packet_text.endswith("\n")
    lines = packet_text.splitlines()
    scope_bounds = _section_bounds(lines, "## Scope")
    if scope_bounds is not None:
        scope_start, scope_end = scope_bounds
        scope_text = "\n".join(lines[scope_start:scope_end])
        scope_bullets: list[str] = []
        for path in paths:
            if f"`{path}`" in scope_text:
                continue
            scope_bullets.extend([
                f"- `{path}`",
                "  - Same-wave Phase B/commit generated deferred non-blocking "
                "bridge findings packet only; no unrelated deferred report is "
                "authorized by this wave.",
            ])
        if scope_bullets:
            insert_at = next(
                (
                    idx
                    for idx in range(scope_start + 1, scope_end)
                    if lines[idx].startswith("Only files under ")
                ),
                scope_end,
            )
            if insert_at > 0 and lines[insert_at - 1].strip():
                scope_bullets.insert(0, "")
            if insert_at < len(lines) and lines[insert_at].strip():
                scope_bullets.append("")
            lines[insert_at:insert_at] = scope_bullets

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- The required fix resolves to files outside "):
            lines[idx] = _append_paths_to_bounded_packet_line(line, paths)
        elif stripped.startswith("- The final touched-file set stays within "):
            lines[idx] = _append_paths_to_bounded_packet_line(line, paths)

    refreshed = "\n".join(lines)
    if had_final_newline:
        refreshed += "\n"
    block = _render_same_wave_deferred_authorization_block(wave_id, paths)
    return _replace_same_wave_deferred_authorization_block(refreshed, block)


def _commit_refresh_evidence_handles(
    handoff: dict[str, Any],
    *,
    indicator_path: str,
    include_pre_commit_receipt: bool = True,
) -> dict[str, str]:
    evidence_handles: dict[str, str] = {}
    raw = handoff.get("evidence_handles")
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "pre_commit_receipt" and not include_pre_commit_receipt:
                continue
            if isinstance(key, str) and isinstance(value, str):
                evidence_handles[key] = value
    evidence_handles.setdefault("indicator", indicator_path)
    receipt = handoff.get("pre_commit_receipt_path")
    if include_pre_commit_receipt and isinstance(receipt, str) and receipt.strip():
        evidence_handles.setdefault("pre_commit_receipt", receipt.strip())
    return evidence_handles


_PENDING_PRE_COMMIT_RECEIPT_RE = re.compile(
    r"\.agent_bus(?:-[A-Za-z0-9_.-]+)?/meta/pre_commit_receipts/[^\s`]+?\.json"
)


def _mark_tracker_note_pre_commit_receipt_pending(tracker_note_text: str) -> str:
    """Remove stale exact receipt claims while pre-commit supervisor is pending."""
    receipt_path = _PENDING_PRE_COMMIT_RECEIPT_RE.pattern
    refreshed = tracker_note_text.replace(
        "commit-ready Phase B handoff",
        "pre-commit supervisor package refresh",
    )
    refreshed = re.sub(
        r"Phase B emitted a commit-ready handoff for ([^.;]+?) with (\d+) wave-owned file\(s\)",
        r"Phase B refreshed the pre-commit supervisor package for \1 with \2 wave-owned file(s)",
        refreshed,
    )
    refreshed = re.sub(
        rf"\(3\)\s+Commit handoff carries explicit receipt authority at\s+{receipt_path}\.*",
        "(3) Pre-commit supervisor receipt remains pending for the current staged package.",
        refreshed,
    )
    refreshed = re.sub(
        rf"\(2\)\s+Commit handoff carries (\d+) wave-owned file\(s\) with explicit "
        rf"receipt authority at\s+{receipt_path}\.*",
        r"(2) Commit handoff carries \1 wave-owned file(s) with pre-commit supervisor "
        r"receipt pending for the current staged package.",
        refreshed,
    )
    refreshed = refreshed.replace(
        "explicit receipt authority, and an L4-compliant tracker note.",
        "package-bound L4 authority pending pre-commit supervisor validation.",
    )
    return refreshed


def _rebuild_handoff_after_packet_truth_refresh(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    active_packet_path: str,
    staged_paths: list[str],
    evidence_handles: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    scope_items = handoff.get("scope_items")
    rebuilt_scope_items = _dedupe_repo_paths([
        *(scope_items if isinstance(scope_items, list) else []),
        active_packet_path,
    ])
    bridge_status = _effective_commit_bridge_status(
        repo_root=repo_root,
        handoff=handoff,
        active_packet_path=active_packet_path,
    )
    return build_commit_handoff(
        wave_id=str(handoff.get("wave_id") or ""),
        task_id=str(handoff.get("task_id") or ""),
        files_to_stage=staged_paths,
        commit_message=str(handoff.get("commit_message") or ""),
        fixes_implemented=list(handoff.get("fixes_implemented") or []),
        wave_class=str(handoff.get("wave_class") or "L4_ENABLER"),
        target_gate_id=str(handoff.get("target_gate_id") or "G8"),
        caller=str(handoff.get("caller") or "phase_b"),
        base_branch=str(handoff.get("base_branch") or "dev"),
        branch_prefix=str(handoff.get("branch_prefix") or "jabramsja"),
        target_branch=handoff.get("target_branch") if isinstance(handoff.get("target_branch"), str) else None,
        force_add_files=[],
        pr_title=str(handoff.get("pr_title") or ""),
        pr_body=str(handoff.get("pr_body") or ""),
        tracker_note_text=_refresh_tracker_note_wave_file_count(
            str(handoff.get("tracker_note_text") or ""),
            len(staged_paths),
        ),
        supervisor_lane=(
            str(handoff.get("supervisor_lane"))
            if isinstance(handoff.get("supervisor_lane"), str)
            else None
        ),
        deferred_items=(
            list(handoff.get("deferred_items"))
            if isinstance(handoff.get("deferred_items"), list)
            else None
        ),
        bridge_status=bridge_status,
        scope_items=rebuilt_scope_items,
        evidence_handles=evidence_handles,
        pre_commit_receipt_path=(
            str(handoff.get("pre_commit_receipt_path") or "")
            if "pre_commit_receipt_path" in handoff
            else None
        ),
        repo_root=repo_root,
        tracked_packet=active_packet_path,
    )


def _bridge_status_round_value(raw_value: Any) -> int:
    try:
        return max(int(raw_value or 0), 0)
    except (TypeError, ValueError):
        return 0


_BRIDGE_ROUND_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_BRIDGE_ROUND_WORD_PATTERN = "|".join(
    sorted((re.escape(word) for word in _BRIDGE_ROUND_WORDS), key=len, reverse=True)
)
_BRIDGE_ROUND_ILLUSTRATIVE_PREFIX_RE = re.compile(
    r"\b(?:such\s+as|for\s+example|e\.g\.|examples?\s*(?:include|:)|sample)\b",
    flags=re.IGNORECASE,
)


def _documented_bridge_round_value(raw_value: str) -> int:
    normalized = raw_value.strip().lower()
    if normalized.isdigit():
        return int(normalized)
    return _BRIDGE_ROUND_WORDS.get(normalized, 0)


def _bridge_round_match_is_illustrative(text: str, match_start: int) -> bool:
    line_start = text.rfind("\n", 0, match_start) + 1
    prefix = text[line_start:match_start]
    return bool(_BRIDGE_ROUND_ILLUSTRATIVE_PREFIX_RE.search(prefix))


def _documented_bridge_round_floor_from_text(text: str) -> int:
    round_floor = 0
    for match in re.finditer(r"\bBridge\s+Round\s+(\d+)\b", text, flags=re.IGNORECASE):
        if _bridge_round_match_is_illustrative(text, match.start()):
            continue
        round_floor = max(round_floor, int(match.group(1)))
    for match in re.finditer(
        rf"\b(\d+|{_BRIDGE_ROUND_WORD_PATTERN})\s+"
        r"(?:Phase\s+[AB]\s+)?bridge\s+rounds?\b",
        text,
        flags=re.IGNORECASE,
    ):
        if _bridge_round_match_is_illustrative(text, match.start()):
            continue
        round_floor = max(round_floor, _documented_bridge_round_value(match.group(1)))
    return round_floor


def _same_wave_document_bridge_round_floor(
    repo_root: Path,
    *,
    wave_id: str,
    active_packet_path: str,
    handoff: dict[str, Any],
) -> int:
    """Return highest same-wave Bridge Round mention in packet/deferred truth."""
    candidate_paths = _dedupe_repo_paths(
        [
            active_packet_path,
            *(
                list(handoff.get("deferred_items"))
                if isinstance(handoff.get("deferred_items"), list)
                else []
            ),
        ]
    )
    round_floor = 0
    for rel_path in candidate_paths:
        if not rel_path or rel_path.startswith("<") or not rel_path.endswith(".md"):
            continue
        full_path = (repo_root / rel_path).resolve()
        try:
            if not full_path.is_relative_to(repo_root.resolve()):
                continue
            text = full_path.read_text(encoding="utf-8")
        except OSError:
            continue
        normalized_wave_id = normalize_wave_id(wave_id)
        same_wave = (
            rel_path == active_packet_path
            and _packet_declares_same_wave_id(text, normalized_wave_id)
        ) or bool(
            re.search(
                rf"(?im)^\s*(?:Wave|Wave ID):\s*{re.escape(normalized_wave_id)}\s*$",
                text,
            )
        )
        if not same_wave:
            continue
        round_floor = max(round_floor, _documented_bridge_round_floor_from_text(text))
    return round_floor


def _effective_commit_bridge_status(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    active_packet_path: str,
) -> dict[str, Any] | None:
    raw_status = handoff.get("bridge_status")
    if not isinstance(raw_status, dict):
        raw_status = {}
    current_rounds = max(
        _bridge_status_round_value(raw_status.get("rounds")),
        _bridge_status_round_value(raw_status.get("total_rounds")),
    )
    documented_rounds = _same_wave_document_bridge_round_floor(
        repo_root,
        wave_id=str(handoff.get("wave_id") or ""),
        active_packet_path=active_packet_path,
        handoff=handoff,
    )
    effective_rounds = max(current_rounds, documented_rounds)
    if effective_rounds == 0 and not raw_status:
        return None
    refreshed = dict(raw_status)
    refreshed["rounds"] = effective_rounds
    refreshed["total_rounds"] = max(
        effective_rounds,
        _bridge_status_round_value(raw_status.get("total_rounds")),
    )
    return refreshed


def _persist_phase_b_handoff_for_commit_path(
    repo_root: Path,
    handoff: dict[str, Any],
) -> str | None:
    """Persist the Phase B handoff after commit-path rebinding.

    The commit executor may refresh the in-memory handoff from current staged
    truth before supervisor review. Keep the durable Phase B handoff in sync so
    retry/review surfaces do not read stale files_to_stage or receipt authority.
    """
    if str(handoff.get("caller") or "") != "phase_b":
        return None
    handoff_path = agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "executors",
        "phase_b_handoff.json",
    )
    try:
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return f"failed to persist refreshed Phase B handoff at {handoff_path}: {exc}"
    return None


def _can_rekey_continuation_to_refreshed_handoff(handoff: dict[str, Any]) -> bool:
    """Return true when reruns read a refreshed handoff persisted by this executor."""
    return str(handoff.get("caller") or "") == "phase_b"


def _refresh_tasks_tracker_note_after_packet_truth(
    repo_root: Path,
    *,
    wave_id: str,
    tracker_note_text: str,
) -> str | None:
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return None

    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return None

    matching_tracker_indices = _matching_tracker_note_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical_tracker_indices = [
        idx
        for idx in matching_tracker_indices
        if _is_canonical_tracker_note_line(lines[idx].rstrip("\n"), wave_id)
    ]
    if len(canonical_tracker_indices) > 1:
        return (
            f"wave_id '{wave_id}' has {len(canonical_tracker_indices)} canonical "
            "tracker notes in TASKS.md during commit packet truth refresh"
        )
    if not canonical_tracker_indices:
        return None

    note_line = tracker_note_text if tracker_note_text.endswith("\n") else tracker_note_text + "\n"
    canonical_idx = canonical_tracker_indices[0]
    if lines[canonical_idx] == note_line:
        return None

    lines[canonical_idx] = note_line
    tasks_path.write_text("".join(lines), encoding="utf-8")
    try:
        _run(["git", "add", "--", "TASKS.md"], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        retry, detail = _git_index_lock_self_cleared_without_owner(repo_root, stderr)
        if not retry:
            return f"git add failed for refreshed TASKS.md tracker note ({detail}): {stderr}"
        try:
            _run(["git", "add", "--", "TASKS.md"], cwd=repo_root)
        except subprocess.CalledProcessError as retry_exc:
            return (
                "git add failed for refreshed TASKS.md tracker note after "
                f"self-cleared index.lock retry ({detail}): {retry_exc.stderr.strip()}"
            )
    return None


def refresh_tasks_tracker_note_after_packet_truth(
    repo_root: Path,
    *,
    wave_id: str,
    tracker_note_text: str,
) -> str | None:
    """Public seam for commit-packet truth refresh tests and callers."""
    return _refresh_tasks_tracker_note_after_packet_truth(
        repo_root,
        wave_id=wave_id,
        tracker_note_text=tracker_note_text,
    )


def _git_index_lock_candidates_from_diagnostic(repo_root: Path, diagnostic: str) -> list[Path]:
    """Return candidate index.lock paths mentioned by git diagnostics."""
    candidates: list[Path] = []

    def add(raw: str) -> None:
        text = raw.strip().strip("'\"`:,.;")
        if not text or "index.lock" not in text:
            return
        path = Path(text)
        if not path.is_absolute():
            path = repo_root / path
        resolved = path.resolve(strict=False)
        if resolved not in candidates:
            candidates.append(resolved)

    for match in re.finditer(r"['\"]([^'\"]*index\.lock)['\"]", diagnostic):
        add(match.group(1))
    for match in re.finditer(r"(?<!\S)(\S*index\.lock)(?!\S)", diagnostic):
        add(match.group(1))
    add(str(repo_root / ".git" / "index.lock"))
    return candidates


def _path_contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _looks_like_git_process(command: str) -> bool:
    if not command:
        return False
    argv0 = command.strip().split(None, 1)[0]
    base = Path(argv0).name
    return base == "git" or base.startswith("git-")


def _process_cwd(pid: int) -> tuple[Path | None, str | None]:
    proc_cwd = Path("/proc") / str(pid) / "cwd"
    if proc_cwd.exists():
        try:
            return proc_cwd.resolve(strict=True), None
        except FileNotFoundError:
            return None, None
        except OSError as exc:
            return None, str(exc)

    try:
        proc = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except FileNotFoundError:
        return None, "lsof unavailable"
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, str(exc)

    if proc.returncode != 0 and not proc.stdout:
        return None, None
    for line in proc.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return Path(line[1:]).resolve(strict=False), None
    return None, None


def _git_owner_processes_for_repo(repo_root: Path) -> list[str]:
    """Return live git processes that appear to own the current repo."""
    repo = repo_root.resolve(strict=False)
    git_dir = (repo / ".git").resolve(strict=False)
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return [f"git owner process probe unavailable: {exc}"]
    if proc.returncode != 0:
        return [f"git owner process probe failed: {(proc.stderr or '').strip() or proc.returncode}"]

    owners: list[str] = []
    current_pid = os.getpid()
    for line in proc.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        parts = text.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid == current_pid:
            continue
        command = parts[1]
        if not _looks_like_git_process(command):
            continue
        if str(repo) in command or str(git_dir) in command:
            owners.append(f"pid={pid} command={command[:180]}")
            continue
        cwd, cwd_error = _process_cwd(pid)
        if cwd is not None:
            cwd = cwd.resolve(strict=False)
            if _path_contains(repo, cwd):
                owners.append(f"pid={pid} cwd={cwd} command={command[:180]}")
            continue
        if cwd_error:
            owners.append(f"pid={pid} cwd_probe_error={cwd_error} command={command[:180]}")
    return owners


def _git_index_lock_self_cleared_without_owner(
    repo_root: Path,
    diagnostic: str,
) -> tuple[bool, str]:
    """Classify git-add index.lock failures without touching .git internals.

    Git's index writer owns the lock by keeping index.lock present. Retry is
    allowed only when the failure named index.lock and every candidate lock path
    has already disappeared before recovery code runs.
    """
    if "index.lock" not in diagnostic:
        return False, "git add failure did not name index.lock"

    candidates = _git_index_lock_candidates_from_diagnostic(repo_root, diagnostic)
    existing = [str(path) for path in candidates if path.exists()]
    if existing:
        return (
            False,
            "index.lock still exists or an active git owner remains: "
            + ", ".join(existing),
        )
    owners = _git_owner_processes_for_repo(repo_root)
    if owners:
        return (
            False,
            "index.lock self-cleared but active git owner remains: "
            + "; ".join(owners[:3]),
        )
    return True, "index.lock self-cleared before retry; no lock owner remained"


def refresh_commit_path_packet_truth(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    indicator_path: str,
    commit_status: str,
) -> tuple[dict[str, Any], list[str], str | None]:
    """Refresh the wave packet from current commit-path facts before supervisor review."""
    active_packet_path, packet_error = _commit_refresh_packet_path(handoff)
    if packet_error:
        return handoff, [], packet_error
    if not active_packet_path:
        return handoff, _current_staged_diff_paths(repo_root), None

    if str(handoff.get("wave_class") or "").strip() != "L4_ENABLER":
        return handoff, _current_staged_diff_paths(repo_root), None

    tracker_note_text = str(handoff.get("tracker_note_text") or "")
    if not tracker_note_text.strip():
        return handoff, [], "tracker_note_text is required for commit packet truth refresh"
    if not indicator_path:
        return handoff, [], "indicator_path is required for commit packet truth refresh"

    packet_full = (repo_root / active_packet_path).resolve()
    repo_resolved = repo_root.resolve()
    if repo_resolved not in packet_full.parents:
        return handoff, [], f"active packet escapes repo root: {active_packet_path}"
    if not packet_full.exists():
        return handoff, [], f"active packet not found for commit packet truth refresh: {active_packet_path}"
    packet_text = packet_full.read_text(encoding="utf-8")
    original_packet_text = packet_text
    wave_id = str(handoff.get("wave_id") or "")
    if not _packet_declares_same_wave_id(packet_text, normalize_wave_id(wave_id)):
        return handoff, [], (
            "active packet missing matching Wave ID for commit packet truth refresh: "
            f"{active_packet_path} (wave_id={wave_id})"
        )

    staged_paths_before = sorted(_current_staged_diff_paths(repo_root))
    if indicator_path not in staged_paths_before:
        return handoff, [], (
            "indicator artifact is not staged before commit packet truth refresh: "
            f"{indicator_path}"
        )
    staged_paths_for_block = sorted(_dedupe_repo_paths([*staged_paths_before, active_packet_path]))
    effective_bridge_status = _effective_commit_bridge_status(
        repo_root=repo_root,
        handoff=handoff,
        active_packet_path=active_packet_path,
    )
    refreshed_tracker_note_text = _refresh_tracker_note_wave_file_count(
        tracker_note_text,
        len(staged_paths_for_block),
    )
    refreshed_tracker_note_text = _refresh_tracker_note_bridge_rounds(
        refreshed_tracker_note_text,
        effective_bridge_status,
    )
    refreshed_tracker_note_text = _refresh_tracker_note_test_evidence(
        refreshed_tracker_note_text,
        staged_paths_for_block,
    )
    pending_pre_commit_supervisor = commit_status == "pre_commit_supervisor_pending"
    if pending_pre_commit_supervisor:
        refreshed_tracker_note_text = _mark_tracker_note_pre_commit_receipt_pending(
            refreshed_tracker_note_text
        )
    tracker_refresh_error = _refresh_tasks_tracker_note_after_packet_truth(
        repo_root,
        wave_id=wave_id,
        tracker_note_text=refreshed_tracker_note_text,
    )
    if tracker_refresh_error:
        return handoff, [], tracker_refresh_error
    # TASKS.md may have been staged by the tracker refresh; render from
    # the settled scope.
    staged_paths_before = sorted(_current_staged_diff_paths(repo_root))
    staged_paths_for_block = sorted(_dedupe_repo_paths([*staged_paths_before, active_packet_path]))
    tracker_note_after_staging = _refresh_tracker_note_wave_file_count(
        refreshed_tracker_note_text,
        len(staged_paths_for_block),
    )
    tracker_note_after_staging = _refresh_tracker_note_bridge_rounds(
        tracker_note_after_staging,
        effective_bridge_status,
    )
    tracker_note_after_staging = _refresh_tracker_note_test_evidence(
        tracker_note_after_staging,
        staged_paths_for_block,
    )
    if pending_pre_commit_supervisor:
        tracker_note_after_staging = _mark_tracker_note_pre_commit_receipt_pending(
            tracker_note_after_staging
        )
    if tracker_note_after_staging != refreshed_tracker_note_text:
        refreshed_tracker_note_text = tracker_note_after_staging
        tracker_refresh_error = _refresh_tasks_tracker_note_after_packet_truth(
            repo_root,
            wave_id=wave_id,
            tracker_note_text=refreshed_tracker_note_text,
        )
        if tracker_refresh_error:
            return handoff, [], tracker_refresh_error
        staged_paths_before = sorted(_current_staged_diff_paths(repo_root))
        staged_paths_for_block = sorted(_dedupe_repo_paths([*staged_paths_before, active_packet_path]))
    if refreshed_tracker_note_text != tracker_note_text:
        handoff = {**handoff, "tracker_note_text": refreshed_tracker_note_text}
        tracker_note_text = refreshed_tracker_note_text
    evidence_handles = _commit_refresh_evidence_handles(
        handoff,
        indicator_path=indicator_path,
        include_pre_commit_receipt=not pending_pre_commit_supervisor,
    )
    block = _render_commit_path_truth_refresh_block(
        wave_id=wave_id,
        active_packet_path=active_packet_path,
        tracker_note_text=tracker_note_text,
        staged_paths=staged_paths_for_block,
        indicator_path=indicator_path,
        commit_status=commit_status,
        evidence_handles=evidence_handles,
        pre_commit_receipt_path=(
            ""
            if pending_pre_commit_supervisor
            else str(handoff.get("pre_commit_receipt_path") or "")
        ),
    )
    try:
        deferred_path_candidates = [
            *staged_paths_for_block,
            *(
                list(handoff.get("deferred_items"))
                if isinstance(handoff.get("deferred_items"), list)
                else []
            ),
        ]
        packet_text = _refresh_same_wave_deferred_packet_authorization(
            packet_text,
            wave_id=wave_id,
            deferred_paths=deferred_path_candidates,
        )
        refreshed_text = _replace_commit_path_truth_refresh_block(packet_text, block)
    except ValueError as exc:
        return handoff, [], str(exc)
    packet_changed = refreshed_text != original_packet_text
    if packet_changed:
        packet_full.write_text(refreshed_text, encoding="utf-8")
    try:
        _run(["git", "add", "--", active_packet_path], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        return handoff, [], f"git add failed for refreshed packet {active_packet_path}: {exc.stderr.strip()}"

    final_staged_paths = sorted(_current_staged_diff_paths(repo_root))
    if not final_staged_paths:
        return handoff, [], "staged file set empty after commit packet truth refresh"
    if packet_changed and active_packet_path not in final_staged_paths:
        return handoff, [], f"refreshed packet is not staged: {active_packet_path}"
    if indicator_path not in final_staged_paths:
        return handoff, [], f"indicator artifact is not staged after commit packet truth refresh: {indicator_path}"

    refreshed_handoff, errors = _rebuild_handoff_after_packet_truth_refresh(
        handoff,
        repo_root=repo_root,
        active_packet_path=active_packet_path,
        staged_paths=final_staged_paths,
        evidence_handles=evidence_handles,
    )
    if errors:
        return handoff, [], "rebuilt commit handoff invalid after packet truth refresh: " + "; ".join(errors)
    return refreshed_handoff, final_staged_paths, None


def _emit_commit_ready_event(
    repo_root: Path,
    *,
    handoff: dict[str, Any],
    receipt_path_from_supervisor: str,
    receipt_decision: str,
    handoff_receipt_rel: str,
) -> dict[str, Any]:
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=_active_bus_dir(),
        event_type="commit_ready",
        wave_id=str(handoff.get("wave_id") or "").strip(),
        task_id=str(handoff.get("task_id") or "[COMMIT-EXECUTOR]").strip(),
        plan_path=_handoff_plan_path(handoff),
        phase="commit_executor",
        state="commit_ready",
        transition_key=receipt_path_from_supervisor,
        summary=f"Commit path reached {receipt_decision}",
        reason=f"Commit-ready receipt validated at {receipt_path_from_supervisor}",
        artifact_paths={
            "supervisor_receipt": receipt_path_from_supervisor,
            "handoff_receipt": handoff_receipt_rel,
        },
    )


def _emit_commit_lifecycle_event(
    repo_root: Path,
    *,
    handoff: dict[str, Any],
    event_type: str,
    state: str,
    transition_key: str,
    summary: str,
    artifact_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=_active_bus_dir(),
        event_type=event_type,
        wave_id=str(handoff.get("wave_id") or "").strip(),
        task_id=str(handoff.get("task_id") or "[COMMIT-EXECUTOR]").strip(),
        plan_path=_handoff_plan_path(handoff),
        phase="commit_executor",
        state=state,
        transition_key=transition_key,
        summary=summary,
        reason=summary,
        artifact_paths=artifact_paths,
    )


def _emit_pre_commit_supervisor_lifecycle_event(
    repo_root: Path,
    package_path: Path,
    *,
    event_type: str,
    state: str,
    decision: str = "pending",
    summary: str | None = None,
) -> dict[str, Any]:
    """Emit the structured pre-commit supervisor lifecycle from package facts."""
    package: dict[str, Any] = {}
    try:
        loaded = json.loads(package_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            package = loaded
    except (json.JSONDecodeError, OSError):
        package = {}

    try:
        rel_package = str(package_path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        rel_package = str(package_path)

    try:
        package_digest = hashlib.sha256(package_path.read_bytes()).hexdigest()
    except OSError:
        package_digest = package_path.name

    wave_id = normalize_wave_id(str(package.get("wave_name") or package_path.stem))
    task_id = str(package.get("task_id") or "[PRE-COMMIT-SUPERVISOR]").strip()
    event_summary = summary or (
        f"Pre-commit supervisor {state}"
        if decision == "pending"
        else f"Pre-commit supervisor {state}: {decision}"
    )
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=_active_bus_dir(),
        event_type=event_type,
        wave_id=wave_id,
        task_id=task_id,
        plan_path=rel_package,
        phase="pre_commit_supervisor",
        state=state,
        transition_key=f"pre-commit-supervisor:{package_digest}:{state}:{decision}",
        summary=event_summary,
        reason=event_summary,
        artifact_paths={"package": rel_package},
    )


def _safe_emit_pre_commit_supervisor_lifecycle_event(
    repo_root: Path,
    package_path: Path,
    *,
    event_type: str,
    state: str,
    decision: str = "pending",
    summary: str | None = None,
) -> dict[str, Any]:
    try:
        return _emit_pre_commit_supervisor_lifecycle_event(
            repo_root,
            package_path,
            event_type=event_type,
            state=state,
            decision=decision,
            summary=summary,
        )
    except Exception as exc:
        return {"enabled": False, "error": str(exc)}


def _commit_outcome_event_type(status: str) -> str:
    if status == "success":
        return "commit_succeeded"
    if status == "held":
        return "commit_held"
    return "commit_failed"


def _commit_lifecycle_pager_enabled(repo_root: Path) -> bool:
    try:
        config = load_executor_config(repo_root)
    except Exception:
        return False
    return bool(config.get("pipeline_agent_pager", {}).get("enabled", False))


def _run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess with sanitized env."""
    run_env = env
    if run_env is None:
        run_env = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=check,
        timeout=timeout, env=run_env,
    )


def _commit_subprocess_env(*, skip_receipt_check: bool = False) -> dict[str, str] | None:
    """Build subprocess env for commit hooks while preserving active bus authority."""
    active_bus_dir = _active_bus_dir()
    if active_bus_dir is None and not skip_receipt_check:
        return None
    run_env = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
    if active_bus_dir is not None:
        run_env["RCX_AGENT_BUS_DIR"] = str(active_bus_dir)
    if skip_receipt_check:
        run_env["RCX_SKIP_RECEIPT_CHECK"] = "1"
    return run_env


def _tail_failure_excerpt(text: str, *, limit: int = 1000, max_lines: int = 20) -> str:
    """Keep the actionable tail of noisy hook output."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    lines = [line for line in cleaned.splitlines() if line.strip()]
    tail = "\n".join(lines[-max_lines:]).strip() if lines else cleaned
    if len(tail) <= limit:
        return tail
    return tail[-limit:]


def _is_test_file(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith("mu/tests/")
        or normalized.startswith("tests/")
        or "/test_" in normalized
        or normalized.endswith("_test.py")
    )


def _canonical_repo_test_path(repo_root: Path, path: str) -> str:
    """Canonicalize repo-relative test paths so symlink mirrors dedupe cleanly."""
    normalized = path.replace("\\", "/")
    try:
        resolved = (repo_root / normalized).resolve(strict=False)
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return normalized


def _collect_commit_test_files(repo_root: Path, staged_files: list[str]) -> list[str]:
    """Collect staged test files and mirrored test files for staged Python code."""
    candidates: set[str] = set()
    for path in staged_files:
        normalized = path.replace("\\", "/")
        if _is_test_file(normalized) and normalized.endswith(".py"):
            candidates.add(_canonical_repo_test_path(repo_root, normalized))
            continue
        if not normalized.endswith(".py"):
            continue
        stem = Path(normalized).stem
        for test_root in ("mu/tests", "tests"):
            root_path = repo_root / test_root
            if not root_path.is_dir():
                continue
            for match in root_path.rglob(f"test_{stem}*.py"):
                if match.is_file():
                    candidates.add(
                        _canonical_repo_test_path(
                            repo_root,
                            match.relative_to(repo_root).as_posix(),
                        )
                    )
    return sorted(candidates)


def _collect_private_attr_gate_files(repo_root: Path, staged_files: list[str]) -> list[str]:
    """Return staged Python test files that should trigger the private-attr gate."""
    candidates: set[str] = set()
    for path in staged_files:
        normalized = path.replace("\\", "/")
        if _is_test_file(normalized) and normalized.endswith(".py"):
            candidates.add(_canonical_repo_test_path(repo_root, normalized))
    return sorted(candidates)


def run_private_attr_test_gate(
    repo_root: Path,
    staged_files: list[str],
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run the repo's private-attribute checker when staged Python tests changed."""
    gate_files = _collect_private_attr_gate_files(repo_root, staged_files)
    if not gate_files:
        return {
            "passed": True,
            "skipped": True,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": [],
        }
    checker = repo_root / "tools" / "checks" / "linters" / "check_private_attr_access.py"
    if not checker.exists():
        checker = SCRIPT_DIR.parents[2] / "tools" / "checks" / "linters" / "check_private_attr_access.py"
    if not checker.exists():
        return {
            "passed": False,
            "skipped": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"private-attr checker not found: {checker}",
            "test_files": gate_files,
        }
    try:
        completed = subprocess.run(
            [sys.executable, str(checker), str(repo_root)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "passed": completed.returncode == 0,
            "skipped": False,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "test_files": gate_files,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "skipped": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"private-attr checker timed out after {timeout}s",
            "test_files": gate_files,
        }


def _private_attr_gate_error(gate_result: dict[str, Any]) -> str:
    detail = _tail_failure_excerpt(
        "\n".join(
            part
            for part in (
                str(gate_result.get("stdout") or ""),
                str(gate_result.get("stderr") or ""),
            )
            if part
        ),
        limit=1500,
        max_lines=30,
    )
    test_files = gate_result.get("test_files") or []
    file_summary = ", ".join(str(path) for path in test_files[:8])
    if len(test_files) > 8:
        file_summary += f", ... (+{len(test_files) - 8} more)"
    message = (
        "private-attr test-integrity gate failed before local commit creation "
        f"(exit={gate_result.get('exit_code')})"
    )
    if file_summary:
        message += f" for staged test file(s): {file_summary}"
    if detail:
        message += f": {detail}"
    return message


def _run_pytest_on_files(
    repo_root: Path,
    test_files: list[str],
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run pytest on specific test files. Returns exit_code and output."""
    if not test_files:
        return {"exit_code": 0, "stdout": "", "stderr": "", "passed": True}
    # Control-plane executor tests are integration-heavy. The real 2-file gate
    # for `test_phase_b_executor.py test_recovery_gate.py` took 198.857s on
    # 2026-04-21, and the same commit gate exhausted the old 300s budget on
    # 2026-05-05. Keep enough slack that the gate fails on test truth, not an
    # undersized commit-executor budget.
    effective_timeout = max(timeout, 240 * len(test_files))
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-x",
                "--tb=short",
                "--import-mode=importlib",
                *test_files,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=effective_timeout,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"pytest timed out after {effective_timeout}s",
            "passed": False,
        }


def _parse_worktree_list(output: str) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain` into entry dicts."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                entries.append(current)
                current = {}
            current["worktree"] = value
            continue
        current[key] = value or "true"
    if current:
        entries.append(current)
    return entries


def _find_linked_worktree_for_branch(repo_root: Path, branch: str) -> Path | None:
    """Return the linked worktree path for `branch`, if exactly one exists."""
    try:
        worktree_proc = _run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None
    if worktree_proc.returncode != 0:
        return None
    target_ref = f"refs/heads/{branch}"
    matches = [
        Path(entry["worktree"])
        for entry in _parse_worktree_list(worktree_proc.stdout)
        if entry.get("worktree")
        and entry.get("bare") != "true"
        and entry.get("prunable") is None
        and entry.get("branch") == target_ref
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _resolve_post_merge_verify_root(repo_root: Path, base_branch: str, *, log: Any) -> Path:
    """Choose a safe worktree for post-merge verification of the base branch."""
    current_after = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
    ).stdout.strip()
    if current_after == base_branch:
        return repo_root
    branch_worktree = _find_linked_worktree_for_branch(repo_root, base_branch)
    if branch_worktree is not None and branch_worktree != repo_root:
        log(
            f"Step 15: using linked {base_branch} worktree for verification: {branch_worktree}"
        )
        return branch_worktree
    _run(["git", "checkout", base_branch], cwd=repo_root)
    return repo_root


def _preferred_branch_creation_base(repo_root: Path, base_branch: str) -> str:
    """Prefer the fetched remote base for new feature branches when available."""
    try:
        fetch_proc = _run(
            ["git", "fetch", "origin", base_branch],
            cwd=repo_root,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return base_branch
    if fetch_proc.returncode != 0:
        return base_branch
    remote_ref = f"refs/remotes/origin/{base_branch}"
    remote_check = _run(
        ["git", "rev-parse", "--verify", remote_ref],
        cwd=repo_root,
        check=False,
    )
    if remote_check.returncode == 0:
        return f"origin/{base_branch}"
    return base_branch


def _collect_branch_rebind_dirty_scope(
    repo_root: Path,
    *,
    handoff: dict[str, Any],
) -> tuple[set[str], set[str], list[str]]:
    """Return tracked, untracked, and out-of-scope dirty paths for branch rebinding."""
    allowed_pathspecs = [
        path for path in [
            *handoff.get("files_to_stage", []),
            *handoff.get("force_add_files", []),
        ]
        if isinstance(path, str) and path.strip()
    ]
    tracked_dirty = {
        path for path in _tracked_dirty_paths(repo_root)
        if not _is_transient_status_path(path)
    }
    untracked_dirty = {
        path for path in _untracked_worktree_paths(repo_root)
        if not _is_transient_status_path(path)
    }
    dirty_paths = tracked_dirty | untracked_dirty
    # Handoff scope entries are Git pathspecs, not just literal file paths.
    # Re-resolve dirty files through Git so `.` and directory pathspecs are
    # treated as in-scope during branch rebinding the same way staging does.
    scoped_dirty = set()
    if allowed_pathspecs:
        scoped_dirty = {
            path for path in (
                _tracked_dirty_paths(repo_root, pathspecs=allowed_pathspecs)
                | _untracked_worktree_paths(repo_root, pathspecs=allowed_pathspecs)
            )
            if not _is_transient_status_path(path)
        }
    outside_scope = sorted(dirty_paths - scoped_dirty)
    return tracked_dirty, untracked_dirty, outside_scope


def _probe_feature_branch_existence(repo_root: Path, target_branch: str) -> tuple[bool, bool]:
    """Return local/remote existence for the canonical target branch."""
    local_check = _run(
        ["git", "rev-parse", "--verify", f"refs/heads/{target_branch}"],
        cwd=repo_root,
        check=False,
    )
    remote_check = _run(
        ["git", "ls-remote", "--heads", "origin", target_branch],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    return local_check.returncode == 0, bool(remote_check.stdout.strip())


def _tracked_dirty_paths(repo_root: Path, pathspecs: list[str] | None = None) -> set[str]:
    """Return tracked paths that differ from HEAD."""
    dirty: set[str] = set()
    cmd = ["git", "diff", "--name-only", "HEAD"]
    if pathspecs:
        cmd.extend(["--", *pathspecs])
    diff_proc = _run(cmd, cwd=repo_root, check=False)
    if diff_proc.returncode == 0:
        dirty.update(
            path.strip()
            for path in diff_proc.stdout.splitlines()
            if path.strip()
        )
    return dirty


def _untracked_worktree_paths(repo_root: Path, pathspecs: list[str] | None = None) -> set[str]:
    """Return untracked repo-relative paths."""
    dirty: set[str] = set()
    cmd = ["git", "ls-files", "--others", "--exclude-standard"]
    if pathspecs:
        cmd.extend(["--", *pathspecs])
    untracked_proc = _run(cmd, cwd=repo_root, check=False)
    if untracked_proc.returncode == 0:
        dirty.update(
            path.strip()
            for path in untracked_proc.stdout.splitlines()
            if path.strip()
        )
    return dirty


def _dirty_worktree_paths(repo_root: Path) -> set[str]:
    """Return repo-relative dirty/untracked paths, excluding transient executor state."""
    dirty = _tracked_dirty_paths(repo_root) | _untracked_worktree_paths(repo_root)
    return {
        path for path in dirty
        if path and not _is_transient_status_path(path)
    }


def _capture_scope_snapshot(
    repo_root: Path,
    pathspecs: list[str],
 ) -> dict[str, bytes | None]:
    """Capture exact worktree bytes for dirty wave-owned files."""
    snapshot: dict[str, bytes | None] = {}
    for path in pathspecs:
        full_path = repo_root / path
        if full_path.exists():
            snapshot[path] = full_path.read_bytes()
        else:
            snapshot[path] = None
    return snapshot


def _clear_scope_for_branch_rebind(
    repo_root: Path,
    *,
    tracked_paths: list[str],
    untracked_paths: list[str],
) -> None:
    """Temporarily clear a bounded dirty scope so the target checkout can proceed."""
    if tracked_paths:
        _run(
            ["git", "restore", "--source=HEAD", "--staged", "--worktree", "--", *tracked_paths],
            cwd=repo_root,
            timeout=120,
        )
    for path in untracked_paths:
        full_path = repo_root / path
        if full_path.exists():
            full_path.unlink()


def _restore_scope_snapshot(repo_root: Path, snapshot: dict[str, bytes | None]) -> None:
    """Restore the captured bounded scope onto the rebound branch."""
    for path, payload in snapshot.items():
        full_path = repo_root / path
        if payload is None:
            if full_path.exists():
                full_path.unlink()
            continue
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(payload)


def _restore_scope_snapshot_on_branch_failure(
    repo_root: Path,
    *,
    snapshot: dict[str, bytes | None],
    expected_branch: str,
) -> None:
    """Restore a captured bounded scope when checkout failed before branch switch."""
    if not snapshot:
        return
    current_after_failure = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
        check=False,
    ).stdout.strip()
    if current_after_failure != expected_branch:
        return
    try:
        _restore_scope_snapshot(repo_root, snapshot)
    except subprocess.CalledProcessError:
        pass


def _handoff_sha(handoff: dict[str, Any]) -> str:
    canonical = json.dumps(handoff, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _collect_wave_test_files(paths: list[str]) -> list[str]:
    """Return deduplicated pytest-style module paths from staged wave files."""
    test_files: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        if not isinstance(raw_path, str):
            continue
        normalized = raw_path.replace("\\", "/")
        if not normalized.endswith(".py"):
            continue
        if not (normalized.startswith("mu/tests/") or normalized.startswith("tests/")):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        test_files.append(normalized)
    return test_files


def _normalize_repo_relpath(path: str) -> str:
    return str(path or "").replace("\\", "/").strip()


def _is_tracker_relevant_path(path: str) -> bool:
    normalized = _normalize_repo_relpath(path)
    if not normalized or normalized in {"STATUS.md", "TASKS.md"}:
        return False
    if normalized.startswith("mu/tools/agents/"):
        return True
    if normalized.startswith("rcx_pi/selfhost/"):
        return True
    if normalized.startswith("mu/"):
        return not normalized.startswith(
            ("mu/docs/", "mu/tools/", "mu/scripts/", "mu/tests/")
        )
    return False


def _tracker_relevant_paths_for_handoff(
    files_to_stage: list[str],
    force_add_files: list[str] | None = None,
) -> list[str]:
    seen: set[str] = set()
    tracker_paths: list[str] = []
    for raw_path in [*(files_to_stage or []), *((force_add_files or []))]:
        if not isinstance(raw_path, str):
            continue
        normalized = _normalize_repo_relpath(raw_path)
        if not _is_tracker_relevant_path(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        tracker_paths.append(normalized)
    return tracker_paths


def _build_tracker_followup_note(*, wave_id: str, tracker_paths: list[str]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    preview = ", ".join(tracker_paths[:3])
    remainder = len(tracker_paths) - min(len(tracker_paths), 3)
    if remainder > 0:
        preview = f"{preview}, +{remainder} more"
    return (
        f"- Tracker sync follow-up ({stamp}, {wave_id}): same-wave follow-up commit touched "
        f"tracker-relevant file(s) without phase/task-state change: {preview}.\n"
    )


def _append_founder_override_to_tracker_note(
    note: Any,
    founder_override_token: str | None,
) -> Any:
    if not isinstance(note, str):
        return note
    token = _normalize_founder_override_token(founder_override_token)
    if not token:
        return note
    if _extract_founder_override_from_tracker_note(note):
        return note
    return note.rstrip() + (
        f" FOUNDER_OVERRIDE:{token} (standing pipeline-bug-fix authorization "
        "per memory feedback_autonomous_executor_fix.md; auto-appended by "
        "build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)"
    )


def _build_default_tracker_note_text(
    *,
    wave_id: str,
    wave_class: str,
    target_gate_id: str,
    commit_message: str,
    files_to_stage: list[str],
    founder_override_token: str | None = None,
    unblocks_wave_id: str = "",
    unblocks_runtime_blocker: str = "",
) -> str:
    """Render a contract-complete tracker note for ad hoc commit handoffs.

    When ``founder_override_token`` is provided (non-empty string), the token
    is auto-appended to the rendered note as
    ``FOUNDER_OVERRIDE:<token> (reason)`` so pre-push-fast L4 adjacency/rolling
    caps + supervisor Gate 8 can consume it without callers hand-crafting the
    append. Mirrors the manual-append pattern used repeatedly during
    2026-04-20 standalone commit work; mechanizes the skip-pattern.
    """
    summary = (commit_message or "").splitlines()[0].strip() or f"update {wave_id}"
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    indicator_cmd = (
        f"python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
        f"--output {indicator_path}"
    )
    wave_files = [path for path in files_to_stage if isinstance(path, str)]
    test_files = _collect_wave_test_files(wave_files)

    if wave_class == "MAINTENANCE":
        if _tracker_sync_note is not None:
            fields = _tracker_sync_note.TrackerSyncNoteFields(
                wave_id=wave_id,
                title=summary,
                wave_class=wave_class,
                target_gate_id=target_gate_id,
                no_op_proof=(
                    "control-surface/docs/test-only wave-owned scope; no runtime/substrate files "
                    "declared in this handoff"
                ),
                defer_reason_code="PIPELINE_HARDENING",
                primary_blocker_class="INTEGRATION",
                primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
                indicator_artifact_ref=indicator_path,
                indicator_collection_command=indicator_cmd,
                unblocks_wave_id=(unblocks_wave_id or "").strip(),
                unblocks_runtime_blocker=(unblocks_runtime_blocker or "").strip(),
            )
            return _append_founder_override_to_tracker_note(
                _tracker_sync_note.render_tracker_sync_note(fields),
                founder_override_token,
            )
        note = (
            f"- Tracker sync note ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}, {wave_id}): "
            f"**{summary}.**. Class: {wave_class}. target_gate_id: {target_gate_id}. "
            "no_op_proof: control-surface/docs/test-only wave-owned scope; no runtime/substrate files "
            "declared in this handoff. defer_reason_code: PIPELINE_HARDENING. "
        )
        if unblocks_wave_id:
            note += f"unblocks_wave_id: {unblocks_wave_id}. "
        if unblocks_runtime_blocker:
            note += f"unblocks_runtime_blocker: {unblocks_runtime_blocker}. "
        note += (
            "primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: {indicator_path}. indicator_collection_command: {indicator_cmd}. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )
        return _append_founder_override_to_tracker_note(note, founder_override_token)

    if test_files:
        evidence_command = (
            "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short " + " ".join(test_files)
        )
        evidence_delta = (
            f"(1) Routed commit handoff scopes {len(wave_files)} wave-owned file(s). "
            f"(2) Evidence gate exercises {len(test_files)} wave-owned test module(s). "
            f"(3) Indicator artifact binds the wave to {indicator_path}."
        )
    else:
        evidence_command = indicator_cmd
        evidence_delta = (
            f"(1) Routed commit handoff scopes {len(wave_files)} wave-owned file(s). "
            "(2) No wave-owned pytest module was staged in this ad hoc handoff, so indicator collection is "
            "the mechanical evidence surface. "
            f"(3) Indicator artifact binds the wave to {indicator_path}."
        )
    progress_before = (
        "The routed commit handoff had not yet been bound to a contract-complete tracker note, so "
        "downstream L4 governance could fail during pre-push."
    )
    progress_after = (
        f"The routed commit handoff for {wave_id} is now bound to {len(wave_files)} wave-owned file(s), "
        f"{len(test_files)} wave-owned test module(s), and a canonical indicator artifact."
    )

    if _tracker_sync_note is not None:
        fields = _tracker_sync_note.TrackerSyncNoteFields(
            wave_id=wave_id,
            title=summary,
            wave_class="L4_ENABLER" if wave_class == "MAINTENANCE" else wave_class,
            target_gate_id=target_gate_id,
            evidence_command=evidence_command,
            evidence_delta=evidence_delta,
            progress_proof_before=progress_before,
            progress_proof_after=progress_after,
            primary_blocker_class="INTEGRATION",
            primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
            indicator_artifact_ref=indicator_path,
            indicator_collection_command=indicator_cmd,
        )
        return _append_founder_override_to_tracker_note(
            _tracker_sync_note.render_tracker_sync_note(fields),
            founder_override_token,
        )

    return _append_founder_override_to_tracker_note(
        f"- Tracker sync note ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}, {wave_id}): "
        f"**{summary}.**. Class: {wave_class}. target_gate_id: {target_gate_id}. "
        f"evidence_command: `{evidence_command}`. evidence_delta: {evidence_delta}. "
        f"progress_proof_before: {progress_before}. progress_proof_after: {progress_after}. "
        "primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
        f"indicator_artifact_ref: {indicator_path}. indicator_collection_command: {indicator_cmd}. "
        "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
        "boot0_track_id: V1. boot0_progress_state: HOLD.",
        founder_override_token,
    )


def _validate_tracker_note_text(
    *,
    tracker_note_text: str,
    wave_id: str,
    wave_class: str,
    target_gate_id: str,
) -> list[str]:
    """Reject incomplete tracker notes before the executor makes a local commit."""
    errors: list[str] = []
    note = tracker_note_text.strip()
    header_re = re.compile(
        rf"^- Tracker sync note \([^,]+,\s*{re.escape(wave_id)}\):"
    )
    if not header_re.search(note):
        errors.append(f"tracker_note_text must start with a canonical tracker note header for wave_id '{wave_id}'")

    required_literals = [
        "Class:",
        f"target_gate_id: {target_gate_id}",
        "primary_blocker_class:",
        "primary_invariant_id:",
        "indicator_artifact_ref:",
        "indicator_collection_command:",
        "bootstrap_endgame_policy:",
        "boot0_track_id:",
        "boot0_progress_state:",
    ]
    if wave_class in ("L4_ENABLER", "L4_STRUCTURAL"):
        required_literals.extend([
            "evidence_command:",
            "evidence_delta:",
            "progress_proof_before:",
            "progress_proof_after:",
        ])
    elif wave_class == "MAINTENANCE":
        required_literals.extend([
            "no_op_proof:",
            "defer_reason_code:",
        ])

    for literal in required_literals:
        if literal not in note:
            errors.append(f"tracker_note_text missing required field marker: {literal}")

    return errors


def _continuation_record_path(repo_root: Path, wave_id: str) -> Path:
    return agent_bus_path(repo_root, _active_bus_dir(), "executors", f"commit_executor_{wave_id}.json")


def _write_continuation_record(
    path: Path,
    *,
    handoff_sha: str,
    target_branch: str,
    commit_sha: str,
    receipt_decision: str,
    steps_completed: list[str],
    pr_number: str | None = None,
    bot_review_request_sha: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_payload = _read_continuation_record(path) or {}
    payload: dict[str, Any] = {
        "version": COMMIT_CONTINUATION_VERSION,
        "status": CONTINUATION_ACTIVE_STATUS,
        "handoff_sha": handoff_sha,
        "target_branch": target_branch,
        "commit_sha": commit_sha,
        "receipt_decision": receipt_decision,
        "steps_completed": list(steps_completed),
        "updated_at_unix": int(time.time()),
    }
    if pr_number:
        payload["pr_number"] = pr_number
    preserved_bot_review_request_sha = existing_payload.get("bot_review_request_sha")
    preserved_commit_sha = existing_payload.get("commit_sha")
    if bot_review_request_sha:
        payload["bot_review_request_sha"] = bot_review_request_sha
    elif (
        preserved_commit_sha == commit_sha
        and isinstance(preserved_bot_review_request_sha, str)
        and preserved_bot_review_request_sha
    ):
        payload["bot_review_request_sha"] = preserved_bot_review_request_sha
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _clear_continuation_record(path: Path) -> None:
    if path.exists():
        path.unlink()


def _read_continuation_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _load_post_commit_continuation(
    path: Path,
    *,
    repo_root: Path,
    handoff_sha: str,
    target_branch: str,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _read_continuation_record(path)
    if payload is None:
        return None
    if payload.get("version") != COMMIT_CONTINUATION_VERSION:
        return None
    if payload.get("status") != CONTINUATION_ACTIVE_STATUS:
        return None
    if payload.get("handoff_sha") != handoff_sha:
        return None
    if payload.get("target_branch") != target_branch:
        return None

    commit_sha = payload.get("commit_sha")
    if not isinstance(commit_sha, str) or not commit_sha.strip():
        return None
    receipt_decision = payload.get("receipt_decision")
    if receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        return None
    steps_completed = payload.get("steps_completed")
    if not isinstance(steps_completed, list) or "git_commit" not in steps_completed:
        return None

    try:
        head_sha = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        branch_name = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
        ).stdout.strip()
        status_output = _run(["git", "status", "--short"], cwd=repo_root).stdout.splitlines()
    except subprocess.CalledProcessError:
        return None

    if branch_name != target_branch:
        return None
    if head_sha != commit_sha:
        # HEAD may have moved forward from remediation commits.
        # Accept if commit_sha is an ancestor of current HEAD.
        try:
            merge_base = _run(
                ["git", "merge-base", "--is-ancestor", commit_sha, head_sha],
                cwd=repo_root, check=False,
            )
            if merge_base.returncode != 0:
                return None
            payload["commit_sha"] = head_sha
            reset_steps = _continuation_steps_for_new_commit(steps_completed)
            if reset_steps is None:
                return None
            payload["steps_completed"] = reset_steps
            payload.pop("bot_review_request_sha", None)
        except subprocess.CalledProcessError:
            return None
    non_transient_status = []
    for line in status_output:
        path_text = line[3:] if len(line) > 3 else line
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        if _is_transient_status_path(path_text):
            continue
        non_transient_status.append(line)
    if non_transient_status:
        return None

    return payload


def _checkpoint_post_commit_progress(
    result: dict[str, Any],
    *,
    continuation_path: Path,
    target_branch: str,
) -> None:
    commit_sha = result.get("commit_sha")
    receipt_decision = result.get("receipt_decision")
    handoff_sha = result.get("handoff_sha")
    steps_completed = result.get("steps_completed")
    if not isinstance(commit_sha, str) or not commit_sha:
        return
    if receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        return
    if not isinstance(handoff_sha, str) or not handoff_sha:
        return
    if not isinstance(steps_completed, list) or "git_commit" not in steps_completed:
        return

    pr_number_val = result.get("pr_number")
    pr_number = str(pr_number_val) if pr_number_val else None
    bot_review_request_sha = result.get("bot_review_request_sha")
    _write_continuation_record(
        continuation_path,
        handoff_sha=handoff_sha,
        target_branch=target_branch,
        commit_sha=commit_sha,
        receipt_decision=receipt_decision,
        steps_completed=steps_completed,
        pr_number=pr_number,
        bot_review_request_sha=bot_review_request_sha if isinstance(bot_review_request_sha, str) else None,
    )


def _continuation_steps_for_new_commit(steps_completed: Any) -> list[str] | None:
    """Return the bounded-resume baseline for a newly created local HEAD."""
    if not isinstance(steps_completed, list):
        return None
    try:
        git_commit_idx = steps_completed.index("git_commit")
    except ValueError:
        return None
    return list(steps_completed[:git_commit_idx + 1])


def _parse_porcelain_status_line(line: str) -> tuple[str, str] | None:
    raw_line = line.rstrip("\n")
    if not raw_line.strip():
        return None
    if len(raw_line) < 4:
        return None
    status_code = raw_line[:2]
    path_text = raw_line[3:]
    if " -> " in path_text:
        path_text = path_text.split(" -> ", 1)[1]
    if not path_text:
        return None
    return status_code, path_text


def _discard_worktree_path(
    repo_root: Path,
    *,
    status_code: str,
    file_path: str,
) -> None:
    if status_code == "??":
        _run(
            ["git", "clean", "-fd", "--", file_path],
            cwd=repo_root,
            timeout=10,
            check=False,
        )
        return
    _run(
        ["git", "checkout", "--", file_path],
        cwd=repo_root,
        timeout=10,
        check=False,
    )


def _decode_untrusted_path(path_str: str) -> str | None:
    """Decode percent escapes and normalize compatibility characters."""
    normalized = path_str.replace("\\", "/")
    for _ in range(4):
        if "%" not in normalized:
            break
        try:
            next_normalized = unquote(normalized, errors="strict")
        except UnicodeDecodeError:
            return None
        if next_normalized == normalized:
            break
        normalized = next_normalized
    return unicodedata.normalize("NFKC", normalized)


def _is_absolute_untrusted_path(path_str: str) -> bool:
    """Reject absolute POSIX, UNC, or Windows drive-rooted paths."""
    normalized = _decode_untrusted_path(path_str)
    if normalized is None:
        return True
    if "\x00" in normalized:
        return True
    normalized = normalized.replace("\\", "/")
    if normalized.startswith("//"):
        return True
    if normalized.startswith("/"):
        return True
    return bool(re.match(r"^[A-Za-z]:/", normalized))


def _has_path_traversal(path_str: str) -> bool:
    """Check for decoded traversal components and hostile separators."""
    normalized = _decode_untrusted_path(path_str)
    if normalized is None:
        return True
    if "\x00" in normalized:
        return True
    parts = Path(normalized.replace("\\", "/")).parts
    return ".." in parts


def _count_exact_wave_id_mentions(text: str, wave_id: str) -> int:
    """Count lines containing an exact wave_id without substring false positives."""
    pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(wave_id)}(?![a-z0-9-])")
    return sum(1 for line in text.splitlines() if pattern.search(line))


def _is_canonical_tracker_note_line(line: str, wave_id: str) -> bool:
    """Return True when *line* is a parseable canonical tracker note for *wave_id*."""
    return bool(re.match(
        rf"^- Tracker sync note \(([^,]+),\s*{re.escape(wave_id)}\):\s*\*\*[^*]+\*\*.*\bClass:\s*",
        line,
    ))


def _is_tracker_followup_note_line(line: str, wave_id: str) -> bool:
    return bool(re.match(
        rf"^- Tracker sync follow-up \(([^,]+),\s*{re.escape(wave_id)}\):",
        line,
    ))


def _matching_tracker_note_indices(lines: list[str], wave_id: str) -> list[int]:
    """Return line indices for tracker-note-shaped lines that reference *wave_id*."""
    pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(wave_id)}(?![a-z0-9-])")
    indices: list[int] = []
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("- Tracker sync note"):
            continue
        if pattern.search(line):
            indices.append(i)
    return indices


def _matching_tracker_note_indices_in_range(
    lines: list[str],
    wave_id: str,
    *,
    start_idx: int,
    end_idx: int,
) -> list[int]:
    """Return tracker-note-shaped line indices for *wave_id* inside one section."""
    return [
        idx for idx in _matching_tracker_note_indices(lines, wave_id)
        if start_idx <= idx < end_idx
    ]


def _matching_tracker_followup_indices_in_range(
    lines: list[str],
    wave_id: str,
    *,
    start_idx: int,
    end_idx: int,
) -> list[int]:
    return [
        idx
        for idx in range(start_idx, end_idx)
        if _is_tracker_followup_note_line(lines[idx].rstrip("\n"), wave_id)
    ]


def _find_ra_section_range(lines: list[str]) -> tuple[int | None, int | None]:
    """Return [start, end) indices for the active ## Ra section."""
    ra_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## Ra"):
            ra_idx = i
            break
    if ra_idx is None:
        return None, None

    ra_end_idx = len(lines)
    for i in range(ra_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped == "---" and i > ra_idx + 1:
            ra_end_idx = i
            break
        if stripped.startswith("## ") and i > ra_idx:
            ra_end_idx = i
            break
    return ra_idx, ra_end_idx


def _force_add_denied_match(path_str: str) -> str | None:
    """Return the denylist token matched by a force-add path, if any."""
    normalized = path_str.replace("\\", "/")
    lowered = normalized.lower()
    parts = [part.lower() for part in Path(normalized).parts]
    if ".git" in parts:
        return ".git/"
    if any(
        part == ".env"
        or part == ".envrc"
        or part.startswith(".env.")
        or part.startswith(".envrc.")
        for part in parts
    ):
        return ".env*"
    if ".agent_bus" in parts:
        return ".agent_bus/"
    if is_agent_bus_runtime_path(normalized):
        return ".agent_bus-*"
    for denied in FORCE_ADD_DENYLIST:
        if lowered.startswith(denied):
            return denied
    return None


def _parse_origin_owner_repo(repo_root: Path) -> tuple[str, str]:
    remote_url = _run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_root,
    ).stdout.strip()
    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    parts = remote_url.rstrip("/").split("/")
    repo_owner = parts[-2]
    repo_name = parts[-1]
    if ":" in repo_owner:
        repo_owner = repo_owner.split(":")[-1]
    return repo_owner, repo_name


def _query_pr_review_state(
    repo_root: Path,
    *,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
) -> dict[str, Any]:
    review_result = _run(
        ["gh", "api", "graphql", "-f",
         f"query={PR_REVIEW_QUERY}",
         "-F", f"owner={repo_owner}",
         "-F", f"repo={repo_name}",
         "-F", f"number={pr_number}"],
        cwd=repo_root,
        timeout=30,
    )
    review_data = json.loads(review_result.stdout)
    pr_data = review_data.get("data", {}).get("repository", {}).get("pullRequest", {})
    if not isinstance(pr_data, dict):
        raise ValueError("PR review query returned no pullRequest object")
    return pr_data


def _pr_head_matches_expected(pr_data: dict[str, Any], head_sha: str) -> bool:
    pr_head = pr_data.get("headRefOid", "")
    return isinstance(pr_head, str) and pr_head == head_sha


def _assert_expected_pr_head(pr_data: dict[str, Any], head_sha: str) -> None:
    pr_head = pr_data.get("headRefOid", "")
    if not isinstance(pr_head, str) or not pr_head:
        raise ValueError("PR review query missing headRefOid")
    if pr_head != head_sha:
        raise ValueError(
            f"PR head moved from expected {head_sha[:8]} to {pr_head[:8]} "
            f"while waiting for {BOT_REVIEW_LOGIN}"
        )


def _has_fresh_connector_review(pr_data: dict[str, Any], head_sha: str) -> bool:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return False
    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    if not isinstance(latest_reviews, list):
        return False
    for review in latest_reviews:
        if not isinstance(review, dict):
            continue
        author = review.get("author", {}).get("login", "")
        commit_oid = review.get("commit", {}).get("oid", "")
        if _is_connector_review_author(author) and commit_oid == head_sha:
            return True
    return False


def _iter_pr_issue_comments(pr_data: dict[str, Any]) -> list[dict[str, Any]]:
    comments = pr_data.get("comments", {}).get("nodes", [])
    if not isinstance(comments, list):
        return []
    return [comment for comment in comments if isinstance(comment, dict)]


def _latest_bot_review_request_comment(pr_data: dict[str, Any]) -> dict[str, Any] | None:
    latest_request: dict[str, Any] | None = None
    for comment in _iter_pr_issue_comments(pr_data):
        author = comment.get("author", {}).get("login", "")
        body = (comment.get("body") or "").strip()
        created_at = comment.get("createdAt", "")
        if _is_bot_review_author(author):
            continue
        if body != BOT_REVIEW_TRIGGER_COMMENT:
            continue
        if not isinstance(created_at, str) or not created_at:
            continue
        if latest_request is None or created_at > latest_request.get("createdAt", ""):
            latest_request = comment
    return latest_request


def _latest_bot_review_request_timestamp(pr_data: dict[str, Any]) -> str | None:
    latest_request = _latest_bot_review_request_comment(pr_data)
    if latest_request is None:
        return None
    created_at = latest_request.get("createdAt", "")
    if not isinstance(created_at, str) or not created_at:
        return None
    return created_at


def _latest_current_head_connector_review_timestamp(
    pr_data: dict[str, Any],
    head_sha: str,
) -> str | None:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return None
    latest_timestamp: str | None = None
    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    if not isinstance(latest_reviews, list):
        return None
    for review in latest_reviews:
        if not isinstance(review, dict):
            continue
        author = review.get("author", {}).get("login", "")
        commit_oid = review.get("commit", {}).get("oid", "")
        submitted_at = review.get("submittedAt", "")
        if not _is_connector_review_author(author) or commit_oid != head_sha:
            continue
        if not isinstance(submitted_at, str) or not submitted_at:
            continue
        if latest_timestamp is None or submitted_at > latest_timestamp:
            latest_timestamp = submitted_at
    return latest_timestamp


def _current_review_cycle_floor_timestamp(
    pr_data: dict[str, Any],
    head_sha: str,
) -> str | None:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return None
    latest_request_at = _latest_bot_review_request_timestamp(pr_data)
    latest_review_at = _latest_current_head_connector_review_timestamp(pr_data, head_sha)
    if latest_request_at is None:
        return latest_review_at
    if latest_review_at is None:
        return latest_request_at
    request_seconds = _parse_github_timestamp_seconds(latest_request_at)
    review_seconds = _parse_github_timestamp_seconds(latest_review_at)
    if request_seconds is None or review_seconds is None:
        return latest_review_at if latest_review_at >= latest_request_at else latest_request_at
    return latest_review_at if review_seconds >= request_seconds else latest_request_at


def _parse_github_timestamp_seconds(timestamp: str) -> float | None:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _is_bot_no_issues_issue_comment(body: str) -> bool:
    return bool(BOT_NO_ISSUES_COMMENT_RE.search(body or ""))


def _is_blocking_connector_review_body(body: str) -> bool:
    return bool(BOT_BLOCKING_REVIEW_BADGE_RE.search(body or ""))


def _latest_relevant_thread_comment(
    thread: dict[str, Any],
    *,
    floor_timestamp: str | None,
) -> dict[str, Any] | None:
    comments = thread.get("comments", {}).get("nodes", [])
    if not isinstance(comments, list):
        return None
    floor_seconds = _parse_github_timestamp_seconds(floor_timestamp or "")
    latest_comment: dict[str, Any] | None = None
    latest_seconds: float | None = None
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        created_at = comment.get("createdAt", "")
        created_seconds = _parse_github_timestamp_seconds(created_at)
        if floor_seconds is not None and (created_seconds is None or created_seconds < floor_seconds):
            continue
        if latest_comment is None:
            latest_comment = comment
            latest_seconds = created_seconds
            continue
        if created_seconds is None:
            continue
        if latest_seconds is None or created_seconds >= latest_seconds:
            latest_comment = comment
            latest_seconds = created_seconds
    return latest_comment


def _current_head_connector_issue_comment_outcome(
    pr_data: dict[str, Any],
    head_sha: str,
) -> dict[str, Any] | None:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return None
    floor_timestamp = _current_review_cycle_floor_timestamp(pr_data, head_sha)
    if floor_timestamp is None:
        return None

    latest_bot_comment: dict[str, Any] | None = None
    for comment in _iter_pr_issue_comments(pr_data):
        author = comment.get("author", {}).get("login", "")
        created_at = comment.get("createdAt", "")
        if not _is_connector_review_author(author):
            continue
        if not isinstance(created_at, str) or not created_at or created_at <= floor_timestamp:
            continue
        if latest_bot_comment is None or created_at > latest_bot_comment.get("createdAt", ""):
            latest_bot_comment = comment

    if latest_bot_comment is None:
        return None

    body = latest_bot_comment.get("body", "") or ""
    if BOT_USAGE_LIMIT_COMMENT_RE.search(body):
        kind = "usage_limit"
    elif _is_bot_no_issues_issue_comment(body):
        kind = "clear"
    else:
        kind = "other"

    return {
        "kind": kind,
        "author": latest_bot_comment.get("author", {}).get("login", ""),
        "body": body,
        "createdAt": latest_bot_comment.get("createdAt", ""),
    }


def _bot_review_request_acknowledged(
    repo_root: Path,
    *,
    repo_owner: str,
    repo_name: str,
    pr_data: dict[str, Any],
) -> bool:
    latest_request = _latest_bot_review_request_comment(pr_data)
    if latest_request is None:
        return False
    comment_id = latest_request.get("databaseId")
    if not isinstance(comment_id, int) or comment_id <= 0:
        return False
    try:
        response = _run(
            ["gh", "api", f"repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}/reactions"],
            cwd=repo_root,
            timeout=30,
        )
        reactions = json.loads(response.stdout or "[]")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    if not isinstance(reactions, list):
        return False
    for reaction in reactions:
        if not isinstance(reaction, dict):
            continue
        content = reaction.get("content", "")
        author = reaction.get("user", {}).get("login", "")
        if content == BOT_REVIEW_ACK_REACTION and _is_connector_review_author(author):
            return True
    return False


def _normalize_bot_login(author: str) -> str:
    if author.endswith("[bot]"):
        return author[:-5]
    return author


def _is_connector_review_author(author: str) -> bool:
    if not author:
        return False
    return _normalize_bot_login(author) == BOT_REVIEW_LOGIN


def _is_bot_review_author(author: str) -> bool:
    if not author:
        return False
    normalized = _normalize_bot_login(author)
    return (
        normalized == BOT_REVIEW_LOGIN
        or author.endswith("[bot]")
        or author.endswith("-bot")
    )


def _wait_for_bot_review_freshness(
    query_pr_state: Any,
    *,
    head_sha: str,
    wait_seconds: int = BOT_REVIEW_WAIT_SECONDS,
    request_acknowledged: Any = None,
    acknowledged_wait_seconds: int = BOT_REVIEW_ACK_WAIT_SECONDS,
    poll_interval: int = BOT_REVIEW_POLL_SECONDS,
    log: Any = None,
) -> dict[str, Any]:
    start_time = time.time()
    deadline = start_time + wait_seconds
    last_pr_data: dict[str, Any] | None = None
    acknowledgement_logged = False
    while True:
        pr_data = query_pr_state()
        last_pr_data = pr_data
        _assert_expected_pr_head(pr_data, head_sha)
        if _has_fresh_connector_review(pr_data, head_sha):
            if log is not None:
                log(f"Fresh {BOT_REVIEW_LOGIN} review observed for {head_sha[:8]}")
            return pr_data
        issue_comment_outcome = _current_head_connector_issue_comment_outcome(pr_data, head_sha)
        if issue_comment_outcome is not None:
            if log is not None:
                if issue_comment_outcome["kind"] == "clear":
                    log(
                        f"Fresh {BOT_REVIEW_LOGIN} no-issues issue comment observed "
                        f"for {head_sha[:8]}"
                    )
                else:
                    log(
                        f"Fresh {BOT_REVIEW_LOGIN} issue comment observed for "
                        f"{head_sha[:8]} ({issue_comment_outcome['kind']})"
                    )
            return pr_data
        if request_acknowledged is not None and request_acknowledged(pr_data):
            acknowledged_deadline = start_time + acknowledged_wait_seconds
            request_started = _parse_github_timestamp_seconds(
                _latest_bot_review_request_timestamp(pr_data) or ""
            )
            if request_started is not None:
                acknowledged_deadline = request_started + acknowledged_wait_seconds
            deadline = max(deadline, acknowledged_deadline)
            if log is not None and not acknowledgement_logged:
                log(
                    f"{BOT_REVIEW_LOGIN} acknowledged the current-head review request "
                    f"for {head_sha[:8]}; extending wait to {acknowledged_wait_seconds}s"
                )
            acknowledgement_logged = True
        if time.time() >= deadline:
            effective_wait_seconds = int(max(wait_seconds, deadline - start_time))
            raise TimeoutError(
                f"No current-head {BOT_REVIEW_LOGIN} review or issue-comment clearance "
                f"for {head_sha[:8]} within {effective_wait_seconds}s"
            )
        if log is not None:
            log(
                f"Waiting for {BOT_REVIEW_LOGIN} review signal on {head_sha[:8]} "
                f"({poll_interval}s poll)"
            )
        time.sleep(poll_interval)


def _maybe_request_current_head_bot_review(
    repo_root: Path,
    *,
    pr_number: str,
    head_sha: str,
    continuation_path: Path,
    log: Any = None,
) -> bool:
    continuation = _read_continuation_record(continuation_path)
    if continuation and continuation.get("bot_review_request_sha") == head_sha:
        # Re-request if the original request is older than the wait timeout —
        # the connector may have dropped the webhook and a fresh comment gives
        # the delivery system another chance.
        updated_at = continuation.get("updated_at_unix", 0)
        if time.time() - updated_at < BOT_REVIEW_WAIT_SECONDS:
            return False
    _run(
        ["gh", "pr", "comment", pr_number, "--body", BOT_REVIEW_TRIGGER_COMMENT],
        cwd=repo_root,
        timeout=30,
    )
    if continuation:
        continuation["bot_review_request_sha"] = head_sha
        continuation["updated_at_unix"] = int(time.time())
        continuation_path.write_text(json.dumps(continuation, indent=2) + "\n", encoding="utf-8")
    if log is not None:
        log(
            f"Requested current-head {BOT_REVIEW_LOGIN} review for {head_sha[:8]} "
            f"via PR comment"
        )
    return True


def _has_recorded_current_head_bot_request(
    continuation_path: Path,
    head_sha: str,
) -> bool:
    continuation = _read_continuation_record(continuation_path)
    return bool(
        isinstance(continuation, dict)
        and continuation.get("bot_review_request_sha") == head_sha
    )


def _mint_bot_remediation_receipt(
    *,
    repo_root: Path,
    findings_addressed: list[dict[str, str]],
    scoped_files: list[str],
    round_num: int,
    wave_id: str,
) -> Path:
    """Mint a type-B (bot remediation) pre-commit receipt for the current staged state.

    Writes both the canonical hook-compatible receipt and a per-invocation
    receipt.  The hook checks decision + staged_sha — both are present.
    The receipt_type field distinguishes this from a full supervisor receipt
    (type A) for audit purposes.
    """
    staged_diff = subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        capture_output=True, cwd=repo_root, check=True,
    ).stdout
    staged_sha = hashlib.sha256(staged_diff).hexdigest()

    receipt = {
        "decision": "COMMIT_GO",
        "staged_sha": staged_sha,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "receipt_type": "bot_remediation",
        "wave_id": wave_id,
        "remediation_round": round_num,
        "findings_addressed": findings_addressed,
        "scoped_files": scoped_files,
    }

    meta_dir = agent_bus_path(repo_root, _active_bus_dir(), "meta")
    meta_dir.mkdir(parents=True, exist_ok=True)

    # Write canonical hook-compatible receipt
    canonical = meta_dir / "pre_commit_receipt.json"
    canonical.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    # Write per-invocation receipt for audit trail
    receipts_dir = meta_dir / "pre_commit_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = receipt["timestamp_utc"].replace(":", "-").replace("+", "p")
    unique_suffix = uuid.uuid4().hex[:8]
    per_invocation = receipts_dir / f"receipt_{ts_slug}_{unique_suffix}.json"
    per_invocation.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    return per_invocation


def _extract_review_findings(
    pr_data: dict[str, Any],
    head_sha: str,
    *,
    result: dict[str, Any],
    pr_number: str,
) -> dict[str, Any]:
    """Extract bot review findings from PR data.

    Returns dict with 'outcome' key:
      'clean'        — no findings, safe to merge
      'bot_findings' — bot findings found (includes 'bot_findings' list)
      'error'        — hard error (includes 'response' dict)
    """
    _assert_expected_pr_head(pr_data, head_sha)
    issue_comment_outcome = _current_head_connector_issue_comment_outcome(
        pr_data, head_sha,
    )
    if issue_comment_outcome is not None:
        if issue_comment_outcome["kind"] == "usage_limit":
            return {"outcome": "error", "response": {
                "status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"{BOT_REVIEW_LOGIN} issue comment reported usage-limit exhaustion"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}}
        if issue_comment_outcome["kind"] == "other":
            return {"outcome": "bot_findings", "bot_findings": [{
                "author": issue_comment_outcome["author"],
                "body": issue_comment_outcome["body"][:500],
                "path": "", "line": None,
            }]}

    review_decision = pr_data.get("reviewDecision", "")
    if review_decision == "CHANGES_REQUESTED":
        return {"outcome": "error", "response": {
            "status": "error", "step": "ensure_review_clear_and_merge",
            "errors": ["reviewDecision is CHANGES_REQUESTED"],
            "steps_completed": result["steps_completed"],
            "pr_number": pr_number}}

    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    bot_review_findings: list[dict[str, Any]] = []
    for review in latest_reviews:
        author = review.get("author", {}).get("login", "")
        state = review.get("state", "")
        is_bot = _is_bot_review_author(author)
        commit_oid = review.get("commit", {}).get("oid", "")
        body = str(review.get("body") or "")
        if is_bot and commit_oid == head_sha and _is_blocking_connector_review_body(body):
            bot_review_findings.append({
                "author": author,
                "body": body[:500],
                "path": "", "line": None,
            })
        if not is_bot and state == "CHANGES_REQUESTED":
            return {"outcome": "error", "response": {
                "status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Human reviewer {author} requested changes"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}}
    if bot_review_findings:
        return {"outcome": "bot_findings", "bot_findings": bot_review_findings}

    threads = pr_data.get("reviewThreads", {}).get("nodes", [])
    current_review_cycle_floor = _current_review_cycle_floor_timestamp(
        pr_data, head_sha,
    )
    bot_findings: list[dict[str, Any]] = []
    for thread in threads:
        if thread.get("isResolved"):
            continue
        latest_comment = _latest_relevant_thread_comment(
            thread, floor_timestamp=current_review_cycle_floor,
        )
        if latest_comment is None:
            continue
        author = latest_comment.get("author", {}).get("login", "")
        is_bot = _is_bot_review_author(author)
        if not is_bot:
            return {"outcome": "error", "response": {
                "status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Unresolved human review thread from {author}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}}
        if thread.get("isOutdated"):
            continue
        bot_findings.append({
            "author": author,
            "body": latest_comment.get("body", "")[:500],
            "path": latest_comment.get("path", ""),
            "line": latest_comment.get("line"),
        })

    if bot_findings:
        return {"outcome": "bot_findings", "bot_findings": bot_findings}
    return {"outcome": "clean"}


def _extract_timeout_verified_current_head_findings(
    pr_data: dict[str, Any],
    head_sha: str,
    *,
    result: dict[str, Any],
    pr_number: str,
) -> dict[str, Any]:
    """Extract findings after review-wait timeout only with current-head proof."""
    _assert_expected_pr_head(pr_data, head_sha)
    issue_comment_outcome = _current_head_connector_issue_comment_outcome(
        pr_data, head_sha,
    )
    has_current_head_bot_signal = (
        _has_fresh_connector_review(pr_data, head_sha)
        or issue_comment_outcome is not None
    )
    findings_result = _extract_review_findings(
        pr_data, head_sha, result=result, pr_number=pr_number,
    )
    if (
        not has_current_head_bot_signal
        and findings_result["outcome"] == "bot_findings"
    ):
        return {"outcome": "unverified"}
    return findings_result


def _build_bot_remediation_prompt(
    bot_findings: list[dict[str, Any]],
    *,
    wave_id: str,
    pr_number: str,
    remediation_round: int,
) -> str:
    """Build a prompt for the bridge adapter to fix bot review findings."""
    lines = [
        f"You are a code-fix agent. A bot reviewer found issues on PR #{pr_number} "
        f"(wave: {wave_id}). Fix each issue directly in the files.",
        "",
        "Rules:",
        "- Edit the files mentioned in the findings. You may also create new files",
        "  in the SAME directories as the finding paths if the fix requires a helper.",
        "  Do NOT create files in unrelated directories — the staging guard will reject them.",
        "- Do NOT run git commands, tests, or hooks. Just edit files.",
        f"- This is remediation round {remediation_round}/{BOT_REMEDIATION_MAX_ROUNDS}.",
        "",
        "## Findings",
        "",
    ]
    for i, finding in enumerate(bot_findings, 1):
        path = finding.get("path", "(unknown)")
        line = finding.get("line")
        body = finding.get("body", "")
        loc = f"{path}:{line}" if line else path
        lines.append(f"### Finding {i}: `{loc}`")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def _check_pr_conflict_state(
    repo_root: Path,
    *,
    pr_number: str,
    log: Any = None,
) -> str | None:
    """Return a human-readable conflict indicator if PR is CONFLICTING/DIRTY.

    2026-04-17 learning: when a PR has ``mergeable: CONFLICTING`` or
    ``mergeStateStatus: DIRTY``, GitHub Actions silently skips
    ``pull_request``-triggered workflows (no merge-ref computable), so the
    required-checks list is permanently incomplete. Polling such a PR
    wastes the full CI timeout without a chance of success.

    Returns a short conflict-state string (``"CONFLICTING"`` or
    ``"mergeStateStatus=DIRTY"``) when the PR cannot complete CI until
    dev is merged in; returns ``None`` when the PR is either mergeable or
    in a transient state that should be polled normally. Fails open on
    any ``gh`` error so that the normal Step 14 path still runs: the
    pre-check is a performance optimization, not a correctness guard.
    """
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "mergeable,mergeStateStatus"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        if log is not None:
            log(f"Step 14 pre-check: gh pr view error ({exc}); skipping")
        return None
    if proc.returncode != 0:
        if log is not None:
            log(
                f"Step 14 pre-check: gh pr view exit={proc.returncode}; "
                "skipping"
            )
        return None
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        if log is not None:
            log("Step 14 pre-check: malformed gh pr view JSON; skipping")
        return None
    mergeable = data.get("mergeable")
    merge_state = data.get("mergeStateStatus")
    if mergeable == "CONFLICTING":
        return "mergeable=CONFLICTING"
    if merge_state == "DIRTY":
        return "mergeStateStatus=DIRTY"
    return None


def _resolve_tasks_md_tracker_note_conflict(path: Path) -> bool:
    """Resolve a TASKS.md merge conflict IFF every conflict block contains
    only tracker-note lines on both sides.

    Returns ``True`` if the file was successfully resolved (all conflict
    markers removed; both sides' tracker-note lines preserved in
    chronological order: origin block first, HEAD block second — matches
    the 2026-04-17 learning recipe "keeping both notes in chronological
    merge order; merged-first wave's note first, then this wave's").

    Returns ``False`` WITHOUT modifying the file if any conflict block
    contains non-tracker-note content or if conflict markers are
    malformed (nested / dangling). Caller must abort the merge in that
    case.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "<<<<<<<" not in text:
        return True  # no conflict to resolve
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    head_buf: list[str] = []
    origin_buf: list[str] = []
    state = "normal"  # 'normal' | 'head' | 'origin'
    for line in lines:
        if line.startswith("<<<<<<<"):
            if state != "normal":
                return False  # nested / malformed
            head_buf = []
            origin_buf = []
            state = "head"
            continue
        if line.startswith("=======") and state == "head":
            state = "origin"
            continue
        if line.startswith(">>>>>>>"):
            if state != "origin":
                return False
            if not _is_tracker_note_only(head_buf) or not _is_tracker_note_only(
                origin_buf
            ):
                return False
            new_lines.extend(origin_buf)
            new_lines.extend(head_buf)
            state = "normal"
            continue
        if state == "head":
            head_buf.append(line)
        elif state == "origin":
            origin_buf.append(line)
        else:
            new_lines.append(line)
    if state != "normal":
        return False  # dangling conflict marker
    path.write_text("".join(new_lines), encoding="utf-8")
    return True


def _is_tracker_note_only(buf: list[str]) -> bool:
    """Every non-blank line in *buf* must be a tracker-sync-note line.

    Tracker-sync-note lines start with ``- Tracker sync note (`` or
    ``- ~~Tracker sync note (`` (strike-through closed notes). Leading
    whitespace is allowed (indented continuation lines inside a note).
    """
    for raw in buf:
        stripped = raw.rstrip("\n").strip()
        if not stripped:
            continue
        if not (
            stripped.startswith("- Tracker sync note (")
            or stripped.startswith("- ~~Tracker sync note (")
        ):
            return False
    return True


def _try_auto_resolve_pr_conflict(
    repo_root: Path,
    *,
    pr_number: str,
    base_branch: str,
    branch_name: str,
    log: Any = None,
) -> dict[str, Any]:
    """Attempt automatic merge-base resolution for a CONFLICTING/DIRTY PR.

    2026-04-17 learning recipe mechanized: on detection of a conflicting
    PR, fetch the base branch, merge it in, resolve a TASKS.md tracker-
    note conflict chronologically if that is the only conflict, commit
    via ``RCX_SKIP_RECEIPT_CHECK=1``, and push. Any non-TASKS.md
    conflict, non-tracker-note TASKS.md conflict, or subprocess error
    aborts the merge and returns an error for the caller to surface.

    Returns a dict:
      resolved: bool — True if no conflict OR auto-resolve succeeded + pushed
      action: str — 'no_action' | 'clean_merge' | 'tasks_md_resolved' | 'aborted'
      detail: str — human-readable explanation
    """
    conflict_state = _check_pr_conflict_state(
        repo_root, pr_number=pr_number, log=log
    )
    if conflict_state is None:
        return {
            "resolved": True,
            "action": "no_action",
            "detail": "PR not in CONFLICTING/DIRTY state",
        }
    if log is not None:
        log(
            f"Step 14 auto-resolve: PR #{pr_number} {conflict_state}; "
            f"attempting merge of origin/{base_branch} into {branch_name}"
        )
    try:
        subprocess.run(
            ["git", "fetch", "origin", base_branch],
            cwd=repo_root,
            check=True,
            timeout=60,
            capture_output=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"git fetch origin {base_branch} failed: {exc}",
        }
    try:
        merge_proc = subprocess.run(
            ["git", "merge", f"origin/{base_branch}", "--no-edit"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"git merge origin/{base_branch} subprocess error: {exc}",
        }
    if merge_proc.returncode == 0:
        push_ok, push_err = _push_branch(repo_root, branch_name)
        if push_ok:
            if log is not None:
                log(
                    f"Step 14 auto-resolve: clean merge of origin/{base_branch} + pushed"
                )
            return {
                "resolved": True,
                "action": "clean_merge",
                "detail": f"merged origin/{base_branch} cleanly and pushed",
            }
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"clean merge but push failed: {push_err}",
        }
    try:
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        _abort_merge(repo_root, log=log)
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"git diff failed after merge conflict: {exc}",
        }
    conflicted = [
        line.strip() for line in diff_proc.stdout.splitlines() if line.strip()
    ]
    if conflicted != ["TASKS.md"]:
        _abort_merge(repo_root, log=log)
        return {
            "resolved": False,
            "action": "aborted",
            "detail": (
                f"conflict in non-TASKS.md files: {conflicted}; "
                "manual recovery required"
            ),
        }
    if not _resolve_tasks_md_tracker_note_conflict(repo_root / "TASKS.md"):
        _abort_merge(repo_root, log=log)
        return {
            "resolved": False,
            "action": "aborted",
            "detail": (
                "TASKS.md conflict includes non-tracker-note content; "
                "manual recovery required"
            ),
        }
    try:
        subprocess.run(
            ["git", "add", "TASKS.md"],
            cwd=repo_root,
            check=True,
            timeout=20,
            capture_output=True,
        )
        commit_env = {**os.environ, "RCX_SKIP_RECEIPT_CHECK": "1"}
        subprocess.run(
            ["git", "commit", "--no-edit"],
            cwd=repo_root,
            check=True,
            timeout=60,
            capture_output=True,
            env=commit_env,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        _abort_merge(repo_root, log=log)
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"TASKS.md resolved but commit failed: {exc}",
        }
    push_ok, push_err = _push_branch(repo_root, branch_name)
    if not push_ok:
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"merge + resolve succeeded but push failed: {push_err}",
        }
    if log is not None:
        log(
            "Step 14 auto-resolve: merged origin/"
            + base_branch
            + " + resolved TASKS.md tracker-note conflict chronologically + pushed"
        )
    return {
        "resolved": True,
        "action": "tasks_md_resolved",
        "detail": (
            f"merged origin/{base_branch}, resolved TASKS.md chronologically, "
            "committed with RCX_SKIP_RECEIPT_CHECK, pushed"
        ),
    }


def _abort_merge(repo_root: Path, *, log: Any = None) -> None:
    """Best-effort `git merge --abort` — swallows errors."""
    try:
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=repo_root,
            timeout=20,
            capture_output=True,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        pass
    if log is not None:
        log("Step 14 auto-resolve: merge aborted")


def _push_branch(repo_root: Path, branch_name: str) -> tuple[bool, str]:
    """`git push --no-verify origin <branch>` with error capture."""
    # --no-verify: same rationale as step 12 — pre-push gate already ran in step 11.
    try:
        subprocess.run(
            ["git", "push", "--no-verify", "origin", branch_name],
            cwd=repo_root,
            check=True,
            timeout=120,
            capture_output=True,
        )
        return True, ""
    except subprocess.CalledProcessError as exc:
        return False, f"exit={exc.returncode}: {exc.stderr.decode('utf-8', errors='replace') if exc.stderr else ''}"
    except (subprocess.SubprocessError, OSError) as exc:
        return False, str(exc)


def _extract_ci_failure_excerpt(text: str, *, max_lines: int = 12) -> str:
    """Return compact failure lines from GitHub Actions log text."""
    interesting: list[str] = []
    markers = (
        "assertionerror",
        "failed ",
        " failures ",
        "==== failures",
        "##[error]",
        "error:",
        "traceback",
    )
    for raw_line in (text or "").splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", raw_line).strip()
        lowered = line.lower()
        if not line or not any(marker in lowered for marker in markers):
            continue
        interesting.append(line[-500:])
    return "\n".join(interesting[-max_lines:])


def _summarize_required_ci_failures(repo_root: Path, pr_number: str) -> dict[str, Any]:
    """Gather failed required check names and short GitHub Actions failure excerpts."""
    summary: dict[str, Any] = {"checks_output": "", "failures": []}
    try:
        checks = _run(
            ["gh", "pr", "checks", pr_number, "--required"],
            cwd=repo_root,
            check=False,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        summary["checks_output"] = f"gh pr checks failed while summarizing CI: {exc}"
        return summary

    checks_output = (checks.stdout or checks.stderr or "").strip()
    summary["checks_output"] = checks_output
    failing_names: list[str] = []
    for line in checks_output.splitlines():
        fields = [field.strip() for field in line.split("\t") if field.strip()]
        lowered = line.lower()
        if len(fields) >= 2 and fields[1].lower() in {"fail", "failed", "failure"}:
            failing_names.append(fields[0])
        elif any(token in lowered for token in ("\tfail\t", "\tfailed\t", "\tfailure\t")) and fields:
            failing_names.append(fields[0])

    try:
        view = _run(
            ["gh", "pr", "view", pr_number, "--json", "statusCheckRollup"],
            cwd=repo_root,
            check=False,
            timeout=60,
        )
        payload = json.loads(view.stdout or "{}")
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        payload = {}

    failures: list[dict[str, str]] = []
    for check in payload.get("statusCheckRollup", []) or []:
        if not isinstance(check, dict):
            continue
        conclusion = str(check.get("conclusion") or "").upper()
        name = str(check.get("name") or "")
        if conclusion not in {"FAILURE", "TIMED_OUT", "CANCELLED"}:
            continue
        if failing_names and name and name not in failing_names:
            continue
        details_url = str(check.get("detailsUrl") or "")
        failure = {
            "name": name,
            "workflow": str(check.get("workflowName") or ""),
            "conclusion": conclusion,
            "details_url": details_url,
            "excerpt": "",
        }
        match = re.search(r"/actions/runs/(\d+)", details_url)
        if match:
            try:
                run_log = _run(
                    ["gh", "run", "view", match.group(1), "--log-failed"],
                    cwd=repo_root,
                    check=False,
                    timeout=90,
                )
                failure["excerpt"] = _extract_ci_failure_excerpt(run_log.stdout or run_log.stderr or "")
            except (subprocess.SubprocessError, OSError):
                failure["excerpt"] = ""
        failures.append(failure)

    if not failures:
        failures = [
            {"name": name, "workflow": "", "conclusion": "FAILURE", "details_url": "", "excerpt": ""}
            for name in failing_names
        ]
    summary["failures"] = failures
    if failures:
        compact = []
        for failure in failures[:3]:
            line = failure.get("name", "") or "unknown-check"
            if failure.get("workflow"):
                line = f"{line} ({failure['workflow']})"
            excerpt = str(failure.get("excerpt") or "").splitlines()
            if excerpt:
                line = f"{line}: {excerpt[-1]}"
            compact.append(line)
        summary["summary"] = "Failed required CI: " + "; ".join(compact)
    elif checks_output:
        summary["summary"] = "Required CI failed; gh pr checks output: " + checks_output.replace("\n", " | ")[:1000]
    else:
        summary["summary"] = "Required CI failed; no failed check details available"
    return summary


def _wait_ci_failure_class(ci_failure: dict[str, Any]) -> str:
    failures = ci_failure.get("failures", [])
    if not isinstance(failures, list):
        return "unknown_error"
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        conclusion = str(failure.get("conclusion") or "").upper()
        if conclusion == "FAILURE" or failure.get("excerpt"):
            return "test_failure"
    return "unknown_error"


def _wait_for_pr_ci(
    repo_root: Path,
    *,
    pr_number: str,
    result: dict[str, Any],
    continuation_path: Path,
    target_branch: str,
    log: Any = None,
    step_label: str = "Step 14",
) -> dict[str, Any] | None:
    """Wait for required CI checks and checkpoint `wait_ci` once."""
    if log is not None:
        log(f"{step_label}: waiting for CI on PR #{pr_number}...")
    try:
        _wait_for_required_checks_to_register(
            repo_root,
            pr_number=pr_number,
            log=log,
        )
        _run(
            ["gh", "pr", "checks", pr_number, "--watch", "--required"],
            cwd=repo_root, timeout=600,
        )
        if not _wait_for_required_checks_to_pass(repo_root, pr_number, timeout=900, log=log):
            ci_failure = _summarize_required_ci_failures(repo_root, pr_number)
            return {
                "status": "error",
                "step": "wait_ci",
                "failure_class": _wait_ci_failure_class(ci_failure),
                "errors": [
                    "Required CI checks did not reach green after gh watch returned. "
                    + str(ci_failure.get("summary", ""))
                ],
                "ci_failures": ci_failure.get("failures", []),
                "ci_checks_output": ci_failure.get("checks_output", ""),
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number,
            }
        if "wait_ci" not in result["steps_completed"]:
            result["steps_completed"].append("wait_ci")
            _checkpoint_post_commit_progress(
                result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
        if log is not None:
            log(f"{step_label}: CI passed")
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, TimeoutError) as exc:
        if log is not None:
            log(
                f"{step_label}: gh pr checks exited ({exc.__class__.__name__}), "
                "polling CI as fallback"
            )
        if not _poll_ci_checks_fallback(repo_root, pr_number, timeout=900, log=log):
            ci_failure = _summarize_required_ci_failures(repo_root, pr_number)
            return {
                "status": "error",
                "step": "wait_ci",
                "failure_class": _wait_ci_failure_class(ci_failure),
                "errors": [
                    f"CI checks failed (confirmed by polling): {exc}. "
                    + str(ci_failure.get("summary", ""))
                ],
                "ci_failures": ci_failure.get("failures", []),
                "ci_checks_output": ci_failure.get("checks_output", ""),
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number,
            }
        if not _wait_for_required_checks_to_pass(repo_root, pr_number, timeout=900, log=log):
            ci_failure = _summarize_required_ci_failures(repo_root, pr_number)
            return {
                "status": "error",
                "step": "wait_ci",
                "failure_class": _wait_ci_failure_class(ci_failure),
                "errors": [
                    f"Required CI checks did not reach green after fallback polling: {exc}. "
                    + str(ci_failure.get("summary", ""))
                ],
                "ci_failures": ci_failure.get("failures", []),
                "ci_checks_output": ci_failure.get("checks_output", ""),
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number,
            }
        if "wait_ci" not in result["steps_completed"]:
            result["steps_completed"].append("wait_ci")
            _checkpoint_post_commit_progress(
                result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
        if log is not None:
            log(f"{step_label}: CI passed (confirmed by polling fallback)")
        return None


def _prepare_result_for_late_conflict_retry(
    repo_root: Path,
    *,
    result: dict[str, Any],
    continuation_path: Path,
    target_branch: str,
) -> None:
    """Refresh continuation state after a late auto-resolve push changes HEAD."""
    result["commit_sha"] = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
    result["steps_completed"] = [
        step for step in result["steps_completed"] if step != "wait_ci"
    ]
    result.pop("bot_review_request_sha", None)
    _checkpoint_post_commit_progress(
        result,
        continuation_path=continuation_path,
        target_branch=target_branch,
    )


def _poll_ci_checks_fallback(
    repo_root: Path,
    pr_number: str,
    *,
    timeout: int = 900,
    poll_interval: int = 15,
    log: Any = None,
) -> bool:
    """Fallback CI poll when ``gh pr checks --watch`` exits prematurely.

    ``gh pr checks --watch --required`` exits 1 when checks are still
    pending (not started or in progress), which the caller interprets as
    CI failure.  This function polls ``gh pr view --json statusCheckRollup``
    until every check has a conclusion, then returns True iff none FAILED.
    """
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        try:
            out = subprocess.run(
                ["gh", "pr", "view", pr_number, "--json", "statusCheckRollup"],
                cwd=repo_root, capture_output=True, text=True, timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            _time.sleep(poll_interval)
            continue
        if out.returncode != 0:
            _time.sleep(poll_interval)
            continue
        try:
            checks = json.loads(out.stdout).get("statusCheckRollup", [])
        except (json.JSONDecodeError, ValueError):
            _time.sleep(poll_interval)
            continue
        if not checks:
            _time.sleep(poll_interval)
            continue
        # Treat non-passing conclusions as failed.  GitHub considers SUCCESS,
        # SKIPPED and NEUTRAL as passing for required-check purposes.
        _PASSING = {"SUCCESS", "SKIPPED", "NEUTRAL"}
        _non_success = [
            c for c in checks
            if c.get("conclusion") and c["conclusion"] not in _PASSING
        ]
        if _non_success:
            if log:
                failed_names = [f"{c.get('name', '?')}={c['conclusion']}" for c in _non_success]
                log(f"CI check(s) not successful: {', '.join(failed_names)}")
            return False
        all_done = all(c.get("conclusion") for c in checks)
        if all_done:
            return True
        _time.sleep(poll_interval)
    if log:
        log(f"CI poll timed out after {timeout}s")
    return False


def _required_check_label(check: dict[str, Any]) -> str:
    name = str(check.get("name") or check.get("workflow") or "unknown")
    state = str(check.get("state") or "").upper()
    bucket = str(check.get("bucket") or "").lower()
    status = state or bucket or "unknown"
    return f"{name}={status}"


def _required_checks_green_snapshot(repo_root: Path, pr_number: str) -> tuple[bool, str, str]:
    result = _run(
        [
            "gh", "pr", "checks", pr_number,
            "--required",
            "--json", "name,state,bucket",
        ],
        cwd=repo_root,
        timeout=30,
        check=False,
    )
    if result.returncode not in (0, 8):
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    try:
        checks = json.loads(result.stdout or "[]")
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"required-check JSON decode failed: {exc}") from exc
    if not isinstance(checks, list):
        raise ValueError("required-check JSON was not a list")
    if not checks:
        return False, "pending", "no required checks reported"

    pending: list[str] = []
    failing: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            pending.append(str(check))
            continue
        bucket = str(check.get("bucket") or "").lower()
        state = str(check.get("state") or "").upper()
        label = _required_check_label(check)
        if bucket in CI_REQUIRED_FAILING_BUCKETS or state in CI_REQUIRED_FAILING_STATES:
            failing.append(label)
        elif bucket in CI_REQUIRED_PASSING_BUCKETS or state in CI_REQUIRED_PASSING_STATES:
            continue
        elif bucket in CI_REQUIRED_PENDING_BUCKETS or state in CI_REQUIRED_PENDING_STATES or not state:
            pending.append(label)
        else:
            pending.append(label)

    if failing:
        return False, "failed", "failing required check(s): " + ", ".join(failing)
    if pending:
        return False, "pending", "pending required check(s): " + ", ".join(pending)
    return True, "passed", "all required checks green"


def _wait_for_required_checks_to_pass(
    repo_root: Path,
    pr_number: str,
    *,
    timeout: int = 900,
    poll_interval: int = 15,
    log: Any = None,
) -> bool:
    """Verify current required PR checks are green after gh's watch command exits."""
    deadline = time.monotonic() + timeout
    last_detail = ""
    while True:
        green, status, detail = _required_checks_green_snapshot(repo_root, pr_number)
        last_detail = detail
        if green:
            return True
        if status == "failed":
            if log:
                log(f"Required checks failed for PR #{pr_number}: {detail}")
            return False
        if time.monotonic() >= deadline:
            if log:
                log(
                    f"Required checks did not pass for PR #{pr_number} "
                    f"within {timeout}s: {last_detail}"
                )
            return False
        if log:
            log(f"Waiting for required checks to pass on PR #{pr_number}: {detail}")
        time.sleep(poll_interval)


def _auto_defer_bot_findings(
    repo_root: Path,
    findings: list[dict[str, Any]],
    wave_id: str,
    pr_number: str,
    repo_owner: str,
    repo_name: str,
    log: Any,
) -> None:
    """Auto-defer bot findings when the remediation adapter produces no changes.

    Writes a deferred non-blocking report and resolves PR comment threads
    so the merge can proceed without manual intervention.
    """
    from datetime import datetime, timezone

    # 1. Write deferred report
    deferred_dir = repo_root / "reports" / "deferred" / "non_blocking"
    deferred_dir.mkdir(parents=True, exist_ok=True)
    report_name = f"pr{pr_number}_bot_auto_deferred_{wave_id}.md"
    report_path = deferred_dir / report_name
    lines = [
        f"# PR #{pr_number} Bot Findings (Auto-Deferred)\n\n",
        f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n",
        f"Wave: {wave_id}\n",
        "Classification: NON-BLOCKING (auto-deferred — remediation adapter produced no changes)\n\n",
    ]
    for i, finding in enumerate(findings, 1):
        body = finding.get("body", "")
        path = finding.get("path", "unknown")
        lines.append(f"## Finding {i}: `{path}`\n\n")
        lines.append(f"{body[:500]}\n\n")
    report_path.write_text("".join(lines), encoding="utf-8")
    log(f"Step 15: deferred report written to {report_name}")

    # 2. Resolve PR comment threads so merge is not blocked
    try:
        query = (
            f'{{"query":"query{{repository(owner:\\"{repo_owner}\\",name:\\"{repo_name}\\")'
            f'{{pullRequest(number:{pr_number}){{reviewThreads(first:50){{nodes{{id isResolved comments(first:1){{nodes{{author{{login}}}}}}}}}}}}}}}}"}}'
        )
        query_result = subprocess.run(
            ["gh", "api", "graphql", "--input", "-"],
            input=query, capture_output=True, text=True, timeout=30,
        )
        if query_result.returncode == 0:
            data = json.loads(query_result.stdout)
            threads = (
                data.get("data", {})
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads", {})
                .get("nodes", [])
            )
            resolved_count = 0
            for thread in threads:
                if not thread.get("isResolved"):
                    # Only resolve bot-authored threads — human threads must
                    # remain unresolved for manual review.
                    first_comments = thread.get("comments", {}).get("nodes", [])
                    if first_comments:
                        thread_author = first_comments[0].get("author", {}).get("login", "")
                        if not _is_bot_review_author(thread_author):
                            continue
                    tid = thread["id"]
                    mutation = (
                        f'{{"query":"mutation{{resolveReviewThread(input:{{threadId:\\"{tid}\\"}})'
                        f'{{thread{{isResolved}}}}}}"}}'
                    )
                    subprocess.run(
                        ["gh", "api", "graphql", "--input", "-"],
                        input=mutation, capture_output=True, text=True, timeout=30,
                    )
                    resolved_count += 1
            if resolved_count:
                log(f"Step 15: resolved {resolved_count} PR comment thread(s)")
    except Exception as exc:
        log(f"Step 15: failed to resolve comment threads (non-fatal): {exc}")


def _attempt_bot_finding_remediation(
    bot_findings: list[dict[str, Any]],
    *,
    repo_root: Path,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
    target_branch: str,
    head_sha: str,
    wave_id: str,
    continuation_path: Path,
    result: dict[str, Any],
    log: Any,
) -> dict[str, Any] | None:
    """Attempt to fix bot findings via bridge adapter.

    Returns None on success (caller proceeds to merge).
    Returns a response dict on failure (bot_findings_pending or error).
    """
    if _bridge_adapters is None:
        log("Step 15: bridge_adapters unavailable, skipping remediation")
        return {
            "status": "bot_findings_pending",
            "bot_findings": bot_findings,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
        }

    config_path = bridge_config_path(repo_root, _active_bus_dir())
    # Auto-heal: fresh worktrees created by `git worktree add` lack bus runtime
    # directories because .gitignore excludes them. Seed the active bus from a
    # trusted bridge_config.json source, including the canonical default bus for
    # namespaced runs. Preserves load_bridge_config's fail-closed contract: if
    # no trusted source exists, load_bridge_config raises BridgeAdapterError
    # unchanged.
    if not config_path.exists():
        try:
            config_path = ensure_bridge_config_path(repo_root, _active_bus_dir())
            if config_path.exists():
                relpath = agent_bus_relpath(_active_bus_dir(), "bridge_config.json")
                log(f"Step 15: auto-copied bridge_config.json into {relpath}")
        except Exception as heal_exc:
            log(f"Step 15: bridge_config.json auto-heal failed: {heal_exc}")
    try:
        config = _bridge_adapters.load_bridge_config(config_path)
        adapter = _bridge_adapters.get_adapter(config, BOT_REMEDIATION_ADAPTER)
    except Exception as exc:
        log(f"Step 15: cannot load bridge adapter: {exc}")
        return {
            "status": "bot_findings_pending",
            "bot_findings": bot_findings,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
        }

    current_findings = bot_findings
    current_head = head_sha

    for round_num in range(1, BOT_REMEDIATION_MAX_ROUNDS + 1):
        log(f"Step 15: bot-finding remediation round {round_num}/{BOT_REMEDIATION_MAX_ROUNDS}")

        prompt = _build_bot_remediation_prompt(
            current_findings,
            wave_id=wave_id,
            pr_number=pr_number,
            remediation_round=round_num,
        )

        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        job_id = f"bot-fix-{uuid.uuid4().hex[:8]}"
        prompt_path = scratch_dir / f"bot_remediation_prompt_r{round_num}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        raw_output_path = scratch_dir / f"bot_remediation_output_{job_id}.txt"

        final_adapter = _bridge_adapters.AdapterSpec(
            name=adapter.name,
            cmd=adapter.cmd,
            timeout_s=BOT_REMEDIATION_TIMEOUT_S,
            prompt_via_stdin=adapter.prompt_via_stdin,
            env=adapter.env,
            mode=adapter.mode,
        )

        try:
            _bridge_adapters.run_adapter(
                final_adapter,
                prompt_text=prompt,
                prompt_path=prompt_path,
                repo_root=repo_root,
                job_id=job_id,
                turn_id=f"bot-fix-r{round_num}",
                agent_role="bot_remediation",
                raw_output_path=raw_output_path,
                stale_timeout_s=BOT_REMEDIATION_STALE_TIMEOUT_S,
                bus_dir=_active_bus_dir(),
            )
        except _bridge_adapters.BridgeAdapterError as exc:
            log(f"Step 15: adapter error in round {round_num}: {exc}")
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
            }

        # Check if adapter produced changes
        status_out = _run(
            ["git", "status", "--porcelain"],
            cwd=repo_root, timeout=30,
        ).stdout
        if not status_out.strip():
            # Check if any finding is P0 or P1 (blocking) — these with no
            # adapter fix must still fail-close.  Only P2+ get auto-deferred.
            blocking_findings = [
                f for f in current_findings
                if any(
                    sev in f.get("body", "") or sev in f.get("severity", "")
                    for sev in ("P0", "P1")
                )
            ]
            if blocking_findings:
                log(
                    f"Step 15: adapter produced no changes in round {round_num} — "
                    f"{len(blocking_findings)} P0/P1 finding(s) remain, routing to recovery agent"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "p1_unresolved": True,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                }
            # Critical-path guard: findings on hooks, executors, checks, or
            # preflight are ALWAYS blocking regardless of P-level — the bot's
            # severity badge measures code quality, not pipeline impact.
            _CRITICAL_PATH_PREFIXES = (
                ".claude/hooks/", ".claude/skills/preflight/", "mu/tools/executors/",
                "mu/tools/checks/", "tools/checks/", "mu/tools/hooks/",
            )
            critical_findings = [
                f for f in current_findings
                if any(f.get("path", "").startswith(pfx) for pfx in _CRITICAL_PATH_PREFIXES)
            ]
            if critical_findings:
                log(
                    f"Step 15: adapter produced no changes in round {round_num} — "
                    f"{len(critical_findings)} finding(s) on critical-path files, routing to recovery"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "p1_unresolved": True,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                }
            log(f"Step 15: adapter produced no changes in round {round_num} — auto-deferring {len(current_findings)} non-blocking finding(s)")
            _auto_defer_bot_findings(
                repo_root, current_findings, wave_id, pr_number,
                repo_owner, repo_name, log,
            )
            # Stage + amend the deferred report into the commit so it's not
            # lost on merge (PR #760 bot finding 5).
            try:
                deferred_dir = repo_root / "reports" / "deferred" / "non_blocking"
                report_name = f"pr{pr_number}_bot_auto_deferred_{wave_id}.md"
                report_path = deferred_dir / report_name
                if report_path.exists():
                    _run(["git", "add", "-f", "--", str(report_path.relative_to(repo_root))],
                         cwd=repo_root, timeout=30)
                    _run(["git", "commit", "--amend", "--no-edit"], cwd=repo_root, timeout=30)
                    _run(["git", "push", "--force-with-lease"], cwd=repo_root, timeout=60)
                    log(f"Step 15: deferred report amended into commit and pushed")
            except subprocess.CalledProcessError as exc:
                log(f"Step 15: failed to amend deferred report (non-fatal): {exc}")
            return None  # success — caller proceeds to merge

        # Stage finding-scoped files + same-directory helpers, fail closed on rest.
        # The remediation prompt allows creating helper files in the same
        # directories as finding paths, so the staging guard must match.
        finding_paths = {f.get("path") for f in current_findings if f.get("path")}
        allowed_dirs = {str(Path(p).parent) for p in finding_paths if p}
        allowed_paths = set(finding_paths)  # exact finding paths always allowed

        def _is_same_dir_helper(fp: str) -> bool:
            """Return True if fp is a new file in a finding's directory."""
            return any(str(Path(fp).parent) == d for d in allowed_dirs)
        changed_lines = [ln for ln in status_out.splitlines() if ln.strip()]
        scoped_entries: list[tuple[str, str]] = []
        out_of_scope_entries: list[tuple[str, str]] = []
        for ln in changed_lines:
            parsed_line = _parse_porcelain_status_line(ln)
            if parsed_line is None:
                log(f"Step 15: cannot parse git status line: {ln!r}")
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                }
            status_code, file_path = parsed_line
            if file_path in allowed_paths or _is_same_dir_helper(file_path):
                scoped_entries.append((status_code, file_path))
            elif not _is_transient_status_path(file_path):
                out_of_scope_entries.append((status_code, file_path))
        scoped_files = [file_path for _, file_path in scoped_entries]
        out_of_scope = [file_path for _, file_path in out_of_scope_entries]

        if out_of_scope:
            log(f"Step 15: out-of-scope changes detected: {out_of_scope}")
            # Discard only the scoped + out-of-scope files, not unrelated work
            for status_code, file_path in scoped_entries + out_of_scope_entries:
                _discard_worktree_path(
                    repo_root,
                    status_code=status_code,
                    file_path=file_path,
                )
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
            }

        if not scoped_files:
            log(f"Step 15: no in-scope file changes in round {round_num}")
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
            }

        try:
            # Split .claude/ paths into individual staging to avoid the git
            # multi-path pathspec resolver false-positive (learning.md 2026-04-11).
            _claude_files = [f for f in scoped_files if f.startswith(".claude/")]
            _other_files = [f for f in scoped_files if not f.startswith(".claude/")]
            if _other_files:
                _run(["git", "add", "--"] + _other_files, cwd=repo_root, timeout=30)
            for _cf in _claude_files:
                _run(["git", "add", "--", _cf], cwd=repo_root, timeout=30)

            # Mint bot-remediation receipt (type B) so the pre-commit hook
            # sees a valid receipt for this staged state.  This is a
            # lightweight alternative to a full supervisor round-trip.
            bot_receipt = _mint_bot_remediation_receipt(
                repo_root=repo_root,
                findings_addressed=[
                    {"path": f.get("path", ""), "body": f.get("body", "")[:200]}
                    for f in current_findings
                ],
                scoped_files=scoped_files,
                round_num=round_num,
                wave_id=wave_id,
            )
            log(f"Step 15: bot-remediation receipt minted: {bot_receipt.name}")

            msg = (
                f"fix: address bot review findings (round {round_num})\n\n"
                f"Co-Authored-By: Codex <noreply@openai.com>"
            )
            _run(["git", "commit", "-m", msg], cwd=repo_root, timeout=60)
            current_head = _run(
                ["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=10,
            ).stdout.strip()
            result["commit_sha"] = current_head
            remediation_checkpoint = dict(result)
            remediation_checkpoint["steps_completed"] = (
                _continuation_steps_for_new_commit(result.get("steps_completed"))
                or list(result.get("steps_completed", []))
            )
            remediation_checkpoint.pop("bot_review_request_sha", None)
            _checkpoint_post_commit_progress(
                remediation_checkpoint,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
            # --no-verify on push: same rationale as step 12 — pre-push gate
            # was already proven on the original wave commit.
            _run(
                ["git", "push", "--no-verify", "origin", target_branch],
                cwd=repo_root, timeout=300,
            )
        except subprocess.CalledProcessError as exc:
            failure_detail = _tail_failure_excerpt(
                "\n".join(part for part in (exc.stderr, exc.stdout) if part),
                limit=1200,
            )
            if failure_detail:
                log(
                    f"Step 15: git operation failed in round {round_num}: "
                    f"{failure_detail}"
                )
            else:
                log(f"Step 15: git operation failed in round {round_num}: {exc}")
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
            }

        log(f"Step 15: remediation round {round_num} pushed ({current_head[:8]})")

        ci_response = _wait_for_pr_ci(
            repo_root,
            pr_number=pr_number,
            result=result,
            continuation_path=continuation_path,
            target_branch=target_branch,
            log=log,
            step_label=f"Step 15 remediation round {round_num}",
        )
        if ci_response is not None:
            log(f"Step 15: CI did not pass after remediation round {round_num}: {ci_response.get('errors', [])}")
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
                "ci_failure": ci_response.get("errors", []),
            }
        log(f"Step 15: CI passed on remediation commit {current_head[:8]}")

        # Request fresh bot review and wait
        try:
            _maybe_request_current_head_bot_review(
                repo_root, pr_number=pr_number, head_sha=current_head,
                continuation_path=continuation_path, log=log,
            )
            pr_data = _wait_for_bot_review_freshness(
                lambda: _query_pr_review_state(
                    repo_root, repo_owner=repo_owner,
                    repo_name=repo_name, pr_number=pr_number),
                head_sha=current_head,
                request_acknowledged=lambda pd: _bot_review_request_acknowledged(
                    repo_root, repo_owner=repo_owner,
                    repo_name=repo_name, pr_data=pd),
                log=log,
            )
        except TimeoutError as exc:
            # The remediation commit at current_head is already pushed and CI
            # passed at step 14 before we got here. The bot simply did not post
            # a fresh review/clearance within the wait window. Old findings
            # cannot be auto-deferred unless a current-head bot review or
            # current-head connector issue comment proves they still apply.
            # Per feedback_bot_comments_not_gates.md: "Bot comments are signal,
            # not gates." A timeout with no current-head proof skips report
            # creation and proceeds without manufacturing stale evidence. Closes
            # reports/deferred/blocking/commit_executor_bot_findings_false_positive_2026-04-17.md.
            #
            # SAFETY NOTE (hotfix 2026-04-17, closes bot P1 on PR #789):
            # ONLY TimeoutError is safe to auto-defer. Other exception types
            # (CalledProcessError, TimeoutExpired, JSONDecodeError,
            # ValueError from _assert_expected_pr_head) indicate genuine
            # state uncertainty (PR head changed, gh API failed, malformed
            # JSON, etc.) where auto-merging could land unreviewed code or
            # new commits pushed during remediation. Those fall through to
            # the catch-all below which preserves the prior safe bail-out to
            # bot_findings_pending.
            log(f"Step 15: review wait failed after round {round_num}: {exc}")
            try:
                timeout_pr_data = _query_pr_review_state(
                    repo_root,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                )
                timeout_findings_result = (
                    _extract_timeout_verified_current_head_findings(
                        timeout_pr_data,
                        current_head,
                        result=result,
                        pr_number=pr_number,
                    )
                )
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
            ) as state_exc:
                log(
                    f"Step 15: review-wait-timeout recheck failed with "
                    f"{type(state_exc).__name__}: {state_exc}; "
                    f"falling back to bot_findings_pending"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                    "review_wait_timeout": True,
                    "review_wait_failure_class": type(state_exc).__name__,
                }

            if timeout_findings_result["outcome"] == "error":
                timeout_response = timeout_findings_result["response"]
                timeout_response["review_wait_timeout"] = True
                return timeout_response

            if timeout_findings_result["outcome"] == "unverified":
                log(
                    f"Step 15: remediation commit {current_head[:8]} already pushed + "
                    f"CI green at step 14; no current-head bot review/comment "
                    f"proved findings still apply after timeout, so skipping "
                    f"auto-defer report and proceeding to merge"
                )
                return None

            if timeout_findings_result["outcome"] != "bot_findings":
                log(
                    f"Step 15: remediation commit {current_head[:8]} already pushed + "
                    f"CI green at step 14; current-head review snapshot is clean "
                    f"after timeout, so skipping auto-defer report and proceeding "
                    f"to merge"
                )
                return None

            verified_findings = timeout_findings_result["bot_findings"]
            log(
                f"Step 15: remediation commit {current_head[:8]} already pushed + "
                f"CI green at step 14; current-head review snapshot still has "
                f"{len(verified_findings)} bot finding(s), auto-deferring verified "
                f"current-head findings"
            )
            try:
                _auto_defer_bot_findings(
                    repo_root=repo_root,
                    findings=verified_findings,
                    wave_id=wave_id,
                    pr_number=pr_number,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    log=log,
                )
            except Exception as defer_exc:
                log(
                    f"Step 15: auto-defer after review-wait-timeout failed "
                    f"({defer_exc}); falling back to bot_findings_pending"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": verified_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                    "review_wait_timeout": True,
                }
            log(
                f"Step 15: auto-defer succeeded after review-wait-timeout; "
                f"verified current-head findings written to "
                f"reports/deferred/non_blocking/ and bot threads resolved. "
                f"Proceeding to merge."
            )
            return None
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            # Non-timeout failures (gh API error, subprocess hang, bad JSON,
            # PR head moved) indicate state uncertainty — bail safely to
            # bot_findings_pending so a human can verify the PR state before
            # merge. Do NOT auto-defer these; doing so risks merging
            # unreviewed/new code. Preserves the pre-hotfix bail-out shape.
            log(
                f"Step 15: review wait failed after round {round_num} with "
                f"non-timeout exception {type(exc).__name__}: {exc} — "
                f"bailing to bot_findings_pending (do not auto-defer on "
                f"state-uncertainty failures)"
            )
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
                "review_wait_failure_class": type(exc).__name__,
            }

        # Re-check findings
        findings_result = _extract_review_findings(
            pr_data, current_head, result=result, pr_number=pr_number,
        )
        if findings_result["outcome"] == "error":
            return findings_result["response"]
        if findings_result["outcome"] == "clean":
            log(f"Step 15: bot findings resolved after {round_num} remediation round(s)")
            return None
        current_findings = findings_result["bot_findings"]

    log(f"Step 15: bot findings remain after {BOT_REMEDIATION_MAX_ROUNDS} remediation rounds")
    return {
        "status": "bot_findings_pending",
        "bot_findings": current_findings,
        "pr_number": pr_number,
        "steps_completed": result["steps_completed"],
        "remediation_rounds_attempted": BOT_REMEDIATION_MAX_ROUNDS,
    }


def _wait_for_required_checks_to_register(
    repo_root: Path,
    *,
    pr_number: str,
    wait_seconds: int = CI_CHECK_REGISTRATION_WAIT_SECONDS,
    poll_interval: int = CI_CHECK_REGISTRATION_POLL_SECONDS,
    log: Any = None,
) -> None:
    deadline = time.time() + wait_seconds
    while True:
        result = _run(
            ["gh", "pr", "checks", pr_number, "--required"],
            cwd=repo_root,
            timeout=30,
            check=False,
        )
        detail = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
        if "no checks reported" not in detail.lower():
            if result.returncode not in (0, 8):
                raise subprocess.CalledProcessError(
                    result.returncode,
                    result.args,
                    output=result.stdout,
                    stderr=result.stderr,
                )
            return
        if time.time() >= deadline:
            raise TimeoutError(
                f"Required checks did not register for PR #{pr_number} within {wait_seconds}s"
            )
        if log is not None:
            log(
                f"Waiting for required checks to register on PR #{pr_number} "
                f"({poll_interval}s poll)"
            )
        time.sleep(poll_interval)


def prepare_handoff_from_routing_record(
    record: dict[str, Any],
    repo_root: Path,
    *,
    standalone: bool = False,
    bus_dir: str | Path | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Prepare a commit handoff from a routing record.

    Used when the dispatcher routes UPDATE_TRACKER_ONLY or COMMIT_GO
    to commit_executor without a pre-prepared handoff file.

    The routing record must contain enough information to build a valid
    handoff. Returns (handoff_dict, errors). If errors is non-empty,
    handoff_dict is None.
    """
    errors: list[str] = []

    wave_name = record.get("wave_name") or record.get("wave_id", "")
    if not wave_name:
        errors.append("Routing record missing wave_name/wave_id")

    summary = record.get("summary", "")
    if not summary:
        errors.append("Routing record missing summary")

    decision = record.get("decision", "")

    # Look for handoff fields in the record itself (supervisor may embed them)
    embedded_handoff = record.get("handoff")
    if isinstance(embedded_handoff, dict):
        embedded_copy = copy.deepcopy(embedded_handoff)
        valid, handoff_errors = validate_handoff(embedded_copy)
        if valid and not standalone:
            return embedded_copy, []
        if not valid:
            return None, [f"Embedded handoff invalid: {err}" for err in handoff_errors]
    else:
        embedded_copy = None

    # COMMIT_GO / COMMIT_GO_HOLD_PUSH require a pre-prepared handoff with
    # an exact Phase B receipt chain.  The supervisor receipt (written in
    # step 6) is the runtime commit-decision authority; the Phase B handoff
    # receipt provides provenance traceability.  Synthesizing a handoff here
    # would lack both, so only embedded handoffs (validated above) are accepted.
    if not standalone and decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        return None, [
            f"{decision} requires a pre-prepared Phase B handoff (or valid "
            f"embedded handoff). Cannot synthesize a handoff from a routing "
            f"record — the receipt chain would be broken."
        ]

    # For UPDATE_TRACKER_ONLY: construct a minimal tracker-only handoff
    candidates = record.get("next_candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    files_to_stage = record.get("files_to_stage", [])
    tracker_note = record.get("tracker_note_text", "")

    def has_nonblank_list_item(value: Any) -> bool:
        return isinstance(value, list) and any(str(item).strip() for item in value)

    candidate_has_scope = any(
        isinstance(c, dict)
        and (
            str(c.get("tracked_packet") or "").strip()
            or has_nonblank_list_item(c.get("files"))
        )
        for c in candidates
    )
    if (
        decision == "UPDATE_TRACKER_ONLY"
        and not standalone
        and not (isinstance(tracker_note, str) and tracker_note.strip())
        and not has_nonblank_list_item(files_to_stage)
        and not has_nonblank_list_item(record.get("force_add_files"))
        and not candidate_has_scope
    ):
        return None, [
            "UPDATE_TRACKER_ONLY routing record has no actionable tracker scope "
            "(tracker_note_text, files_to_stage, force_add_files, tracked_packet, "
            "or candidate files). Refusing to synthesize a TASKS.md-only handoff."
        ]

    # Try to derive files_to_stage from candidates if not directly provided
    if not files_to_stage:
        for c in candidates:
            cf = c.get("files", [])
            if cf:
                files_to_stage.extend(cf)

    if not files_to_stage:
        # Default to TASKS.md for tracker-only updates
        if decision == "UPDATE_TRACKER_ONLY":
            files_to_stage = ["TASKS.md"]
        elif not standalone:
            errors.append("Cannot derive files_to_stage from routing record")

    if errors:
        return None, errors

    # Normalize wave_id for branch naming
    wave_id = normalize_wave_id(wave_name)
    wave_class = record.get("wave_class", "MAINTENANCE")
    target_gate_id = _resolve_target_gate_id(
        record,
        repo_root,
        embedded_handoff=embedded_copy,
    )
    default_commit_message = (
        f"chore: {summary}\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    )
    commit_message = record.get("commit_message", default_commit_message)
    if commit_message is None:
        commit_message = default_commit_message
    elif not isinstance(commit_message, str):
        commit_message = str(commit_message)
    raw_force_add_files = record.get("force_add_files")
    force_add_files = [] if raw_force_add_files is None else raw_force_add_files

    if standalone:
        staged_files = _current_staged_diff_paths(repo_root)
        if not staged_files:
            return None, [
                "Standalone routing-record regeneration requires a non-empty staged diff"
            ]
        standalone_target_branch = (embedded_copy or {}).get("target_branch")
        if not isinstance(standalone_target_branch, str) or not standalone_target_branch.strip():
            standalone_target_branch = record.get("target_branch")
        unblocks_wave_id, unblocks_runtime_blocker = _extract_maintenance_bypass_from_routing_record(
            record,
            repo_root,
            embedded_handoff=embedded_copy,
        )
        wave_id = normalize_wave_id(
            str(
                (embedded_copy or {}).get("wave_id")
                or wave_name
            )
        )
        standalone_wave_class = str((embedded_copy or {}).get("wave_class") or wave_class)
        founder_override_token, override_error = _resolve_standalone_founder_override_token(
            record,
            repo_root,
            embedded_handoff=embedded_copy,
            wave_id=wave_id,
            wave_class=standalone_wave_class,
        )
        if override_error:
            return None, [override_error]
        commit_message = _build_standalone_commit_message(wave_id)
        handoff, build_errors = build_commit_handoff(
            wave_id=wave_id,
            task_id=str((embedded_copy or {}).get("task_id") or record.get("task_id", f"[{wave_name}]")),
            files_to_stage=staged_files,
            commit_message=commit_message,
            fixes_implemented=_build_standalone_staged_diff_fixes(staged_files),
            wave_class=standalone_wave_class,
            target_gate_id=target_gate_id,
            caller="standalone",
            base_branch=str((embedded_copy or {}).get("base_branch") or "dev"),
            branch_prefix=str((embedded_copy or {}).get("branch_prefix") or "jabramsja"),
            pr_title=commit_message[:70],
            pr_body=None,
            tracker_note_text=None,
            tracked_packet=_tracked_packet_path_from_record(record) or None,
            supervisor_lane=(embedded_copy or {}).get("supervisor_lane"),
            deferred_items=(embedded_copy or {}).get("deferred_items"),
            bridge_status=(embedded_copy or {}).get("bridge_status"),
            scope_items=staged_files,
            evidence_handles=None,
            pre_commit_receipt_path="",
            target_branch=(
                standalone_target_branch.strip()
                if isinstance(standalone_target_branch, str) and standalone_target_branch.strip()
                else None
            ),
            repo_root=repo_root,
            bus_dir=bus_dir,
            founder_override_token=founder_override_token,
            unblocks_wave_id=unblocks_wave_id,
            unblocks_runtime_blocker=unblocks_runtime_blocker,
        )
        if build_errors:
            return None, build_errors
        return handoff, []

    # UPDATE_TRACKER_ONLY routing records may omit tracker_note_text. In that
    # case, synthesize the same contract-complete note shape that validate_handoff
    # now requires instead of the older one-line fallback.
    founder_override_token = ""
    unblocks_wave_id = ""
    unblocks_runtime_blocker = ""
    if decision == "UPDATE_TRACKER_ONLY" and not tracker_note:
        founder_override_token = _extract_founder_override_from_routing_record(
            record,
            repo_root,
        )
        if not founder_override_token:
            founder_override_token = _extract_same_wave_founder_override_from_tasks(
                repo_root,
                wave_id,
            )
        unblocks_wave_id, unblocks_runtime_blocker = _extract_maintenance_bypass_from_routing_record(
            record,
            repo_root,
        )

    handoff, build_errors = build_commit_handoff(
        wave_id=wave_id,
        task_id=str(record.get("task_id", f"[{wave_name}]")),
        files_to_stage=files_to_stage,
        commit_message=commit_message,
        fixes_implemented=record.get("fixes_implemented", [summary]),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        caller="update_tracker_only" if decision == "UPDATE_TRACKER_ONLY" else "phase_b",
        base_branch="dev",
        branch_prefix="jabramsja",
        force_add_files=force_add_files,
        pr_title=record.get("pr_title", f"chore: {summary}"[:70]),
        pr_body=record.get("pr_body", f"## Summary\n\n- {summary}"),
        tracker_note_text=tracker_note or None,
        tracked_packet=_tracked_packet_path_from_record(record) or None,
        pre_commit_receipt_path=str(agent_bus_relpath(bus_dir, "meta", "pre_commit_receipt.json")),
        repo_root=repo_root,
        bus_dir=bus_dir,
        founder_override_token=founder_override_token or None,
        unblocks_wave_id=unblocks_wave_id,
        unblocks_runtime_blocker=unblocks_runtime_blocker,
    )
    if build_errors:
        return None, build_errors
    return handoff, []


def build_commit_handoff(
    *,
    wave_id: str,
    task_id: str,
    files_to_stage: list[str],
    commit_message: str,
    fixes_implemented: list[str],
    wave_class: str = "L4_ENABLER",
    target_gate_id: str = "G8",
    caller: str = "phase_b",
    base_branch: str = "dev",
    branch_prefix: str = "jabramsja",
    target_branch: str | None = None,
    force_add_files: list[str] | None = None,
    pr_title: str | None = None,
    pr_body: str | None = None,
    tracker_note_text: str | None = None,
    tracked_packet: str | None = None,
    supervisor_lane: str | None = None,
    deferred_items: list[str] | None = None,
    bridge_status: dict[str, Any] | None = None,
    scope_items: list[str] | None = None,
    evidence_handles: dict[str, str] | None = None,
    pre_commit_receipt_path: str | None = None,
    repo_root: Path | None = None,
    founder_override_token: str | None = None,
    unblocks_wave_id: str = "",
    unblocks_runtime_blocker: str = "",
    bus_dir: str | Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build a validated commit handoff from essential fields.

    Fills in defaults for optional fields, auto-detects .gitignored files
    for force_add_files, finds the latest COMMIT_GO receipt if not provided,
    and validates the result against the handoff schema.

    Returns (handoff_dict, errors). If errors is non-empty, the handoff is invalid.
    """
    errors: list[str] = []

    if not wave_id:
        errors.append("wave_id is required")
    if not task_id:
        errors.append("task_id is required")
    if not files_to_stage:
        errors.append("files_to_stage is required")
    if not commit_message:
        errors.append("commit_message is required")
    if not fixes_implemented:
        errors.append("fixes_implemented is required")
    if errors:
        return {}, errors

    # Auto-detect .gitignored files and move to force_add_files
    effective_files = list(files_to_stage)
    effective_force = list(force_add_files or [])
    if repo_root:
        effective_files = _canonicalize_stage_paths(repo_root, effective_files)
        effective_force = _canonicalize_stage_paths(repo_root, effective_force)
        for f in list(effective_files):
            try:
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", f],
                    cwd=repo_root, capture_output=True, timeout=5,
                )
                if result.returncode == 0:
                    effective_files.remove(f)
                    if f not in effective_force:
                        effective_force.append(f)
            except (subprocess.SubprocessError, OSError):
                pass

    # 2026-04-11 git multi-path .claude pathspec resolver workaround
    # (PR pipeline-followups-2026-04-11):
    # Move any `.claude/...` paths that slipped past the check-ignore probe
    # above into `force_add_files`. This works around a git quirk where
    # multi-path `git add -- .claude/hooks/foo.sh mu/tools/bar.py` fails
    # with "The following paths are ignored by one of your .gitignore
    # files: .claude" even though `git check-ignore -q .claude/hooks/foo.sh`
    # returns NOT ignored (the negation rule `!.claude/hooks/` at line 106
    # of .gitignore is honored by single-path add but the multi-path
    # resolver short-circuits at the parent `.claude/` ignore rule at line
    # 104 before walking the negation chain). `git add -f` bypasses the
    # short-circuit, and commit_executor's Step 4 uses `git add -f` for
    # `force_add_files`, so moving these paths there avoids the issue.
    #
    # Verified 2026-04-11 via 3 controlled tests in worktree
    # workingrcx_hook_denylist_1775885905:
    #   `git add -- .claude/hooks/check-reasoning-depth.sh` → exit 0
    #   `git add -- mu/tools/runners/run_review.py mu/tests/tools/test_run_review.py` → exit 0
    #   `git add -- .claude/hooks/check-reasoning-depth.sh mu/tools/runners/run_review.py` → exit 1
    #   `git add -f -- .claude/hooks/check-reasoning-depth.sh mu/tools/runners/run_review.py` → exit 0
    #
    # The fix is minimal: only `.claude/...` paths are affected (other
    # negation-rule directories under an ignored parent could have the
    # same issue but this is the only one currently in use). If the bug
    # is ever fixed in git or the project's .gitignore structure changes,
    # this workaround is safe to leave in place (force_add_files uses
    # `git add -f` which is a superset of `git add`).
    for f in list(effective_files):
        if f.startswith(".claude/") or f.startswith("./.claude/"):
            effective_files.remove(f)
            if f not in effective_force:
                effective_force.append(f)
    effective_files = _dedupe_repo_paths(effective_files)
    effective_force = _dedupe_repo_paths(effective_force)

    # Auto-find latest COMMIT_GO receipt if not provided
    # Use the canonical receipt path — no directory-sort discovery.
    # The commit executor's Step 6 runs the supervisor and gets a fresh
    # per-invocation receipt. This handoff receipt is provenance only.
    if caller == "standalone" and pre_commit_receipt_path == "":
        effective_receipt = ""
    else:
        effective_receipt = pre_commit_receipt_path or str(
            agent_bus_relpath(bus_dir, "meta", "pre_commit_receipt.json")
        )

    effective_founder_override_token = _normalize_founder_override_token(founder_override_token)
    if not effective_founder_override_token and isinstance(tracker_note_text, str):
        effective_founder_override_token = _extract_founder_override_from_tracker_note(
            tracker_note_text
        )
    if (
        not effective_founder_override_token
        and tracked_packet
        and repo_root is not None
        and str(wave_class or "").strip() == "L4_ENABLER"
    ):
        effective_founder_override_token = _resolve_control_surface_founder_override_token(
            {
                "wave_id": wave_id,
                "wave_name": wave_id,
                "tracked_packet": tracked_packet,
                "tracker_note_text": tracker_note_text or "",
            },
            repo_root,
            wave_id=wave_id,
            wave_class=wave_class,
        )

    if (
        caller == "standalone"
        and str(wave_class or "").strip() == "L4_ENABLER"
        and not effective_founder_override_token
    ):
        return {}, [_missing_founder_override_error(wave_id)]

    effective_tracker_note = tracker_note_text or _build_default_tracker_note_text(
        wave_id=wave_id,
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        commit_message=commit_message,
        files_to_stage=effective_files + effective_force,
        founder_override_token=effective_founder_override_token,
        unblocks_wave_id=unblocks_wave_id,
        unblocks_runtime_blocker=unblocks_runtime_blocker,
    )
    effective_tracker_note = _append_founder_override_to_tracker_note(
        effective_tracker_note,
        effective_founder_override_token,
    )

    handoff = {
        "wave_id": wave_id,
        "task_id": task_id,
        "wave_class": wave_class,
        "target_gate_id": target_gate_id,
        "caller": caller,
        "branch_prefix": branch_prefix,
        "tracker_note_text": effective_tracker_note,
        "fixes_implemented": fixes_implemented,
        "files_to_stage": effective_files,
        "force_add_files": effective_force,
        "commit_message": commit_message,
        "pr_title": pr_title or commit_message[:70],
        "pr_body": pr_body or f"## Summary\n\n" + "\n".join(f"- {f}" for f in fixes_implemented),
        "base_branch": base_branch,
        "pre_commit_receipt_path": effective_receipt,
    }

    # Add optional fields if provided
    if supervisor_lane:
        handoff["supervisor_lane"] = supervisor_lane
    if deferred_items is not None:
        handoff["deferred_items"] = deferred_items
    if bridge_status is not None:
        handoff["bridge_status"] = bridge_status
    if scope_items:
        handoff["scope_items"] = scope_items
    if evidence_handles:
        handoff["evidence_handles"] = evidence_handles
    if tracked_packet:
        handoff["tracked_packet"] = _normalize_repo_relpath(tracked_packet)
    if isinstance(target_branch, str) and target_branch.strip():
        handoff["target_branch"] = target_branch.strip()

    # Validate against schema
    valid, validation_errors = validate_handoff(handoff)
    if not valid:
        return handoff, validation_errors

    return handoff, []


def validate_handoff(handoff: dict[str, Any]) -> tuple[bool, list[str]]:
    """Step 1: Validate all handoff fields."""
    if not isinstance(handoff, dict):
        return False, ["Handoff must be a JSON object"]

    errors: list[str] = []

    allowed_fields = REQUIRED_HANDOFF_FIELDS | OPTIONAL_HANDOFF_FIELDS
    unexpected = sorted(set(handoff.keys()) - allowed_fields)
    if unexpected:
        errors.extend(f"Unexpected field: {field}" for field in unexpected)

    # Required fields (standalone caller relaxes some fields)
    is_standalone = handoff.get("caller") == "standalone"
    effective_required = REQUIRED_HANDOFF_FIELDS - (STANDALONE_OPTIONAL_FIELDS if is_standalone else set())
    missing = effective_required - set(handoff.keys())
    if missing:
        errors.extend(f"Missing field: {f}" for f in sorted(missing))
        return False, errors

    # base_branch must be dev
    if handoff.get("base_branch") != "dev":
        errors.append(f"base_branch must be 'dev', got '{handoff.get('base_branch')}'")

    # wave_id regex
    wave_id = handoff.get("wave_id", "")
    if not isinstance(wave_id, str) or not WAVE_ID_RE.fullmatch(wave_id):
        errors.append(f"wave_id must match {WAVE_ID_RE.pattern}, got '{wave_id}'")

    # pre_commit_receipt_path: must be string, relative, within repo
    # Standalone caller may omit this (supervisor is skipped, no receipt needed)
    receipt_path_val = handoff.get("pre_commit_receipt_path")
    if is_standalone and (not receipt_path_val or receipt_path_val == ""):
        pass  # standalone: receipt path not required
    elif not isinstance(receipt_path_val, str):
        errors.append(f"pre_commit_receipt_path must be a string, got {type(receipt_path_val).__name__}")
    elif not receipt_path_val.strip():
        errors.append("pre_commit_receipt_path must be non-empty")
    else:
        if os.path.isabs(receipt_path_val):
            errors.append(f"pre_commit_receipt_path must be relative, got absolute: {receipt_path_val}")
        elif _is_absolute_untrusted_path(receipt_path_val):
            errors.append(f"pre_commit_receipt_path must stay within repo, got absolute-like path: {receipt_path_val}")
        if _has_path_traversal(receipt_path_val):
            errors.append(f"Path traversal in pre_commit_receipt_path: {receipt_path_val}")

    # files_to_stage must be a list. It can be EMPTY only when
    # force_add_files is non-empty (e.g. a `.claude/`-only commit
    # where build_commit_handoff's auto-move routed every path to
    # force_add_files via the string-startswith check). A commit with
    # zero total files (both lists empty) is still an error.
    #
    # Rationale: `git add -f` at commit_executor Step 4 correctly
    # handles force_add_files entries regardless of whether
    # files_to_stage is also populated. Requiring files_to_stage
    # non-empty INDEPENDENTLY would forbid an otherwise-valid class
    # of commits — any wave whose entire scope lives under `.claude/`
    # (hook/config/skill hardening waves). This was diagnosed during
    # the block-protected-branch-lexer follow-up wave 2026-04-11 when
    # the 3-file `.claude/hooks/*` commit could not produce a valid
    # handoff despite the dirty files being semantically commit-ready.
    fts = handoff.get("files_to_stage")
    _faf_preview = handoff.get("force_add_files")
    _has_force_add = isinstance(_faf_preview, list) and len(_faf_preview) > 0
    if not isinstance(fts, list):
        errors.append("files_to_stage must be a list")
    elif not fts and not _has_force_add:
        errors.append(
            "files_to_stage or force_add_files must be non-empty "
            "(commit must have at least one file)"
        )
    elif fts and not all(isinstance(f, str) for f in fts):
        errors.append("files_to_stage entries must be strings")
    else:
        for f in fts:
            if _is_absolute_untrusted_path(f):
                errors.append(f"Absolute path in files_to_stage: {f}")
            if _has_path_traversal(f):
                errors.append(f"Path traversal in files_to_stage: {f}")
            denied = _runtime_bus_artifact_match(f)
            if denied:
                errors.append(f"files_to_stage denied: {f} (matches {denied})")

    # force_add_files validation + denylist (case-insensitive for macOS)
    faf = handoff.get("force_add_files", [])
    if not isinstance(faf, list):
        errors.append("force_add_files must be a list")
    else:
        for f in faf:
            if not isinstance(f, str):
                errors.append("force_add_files entries must be strings")
                continue
            if _is_absolute_untrusted_path(f):
                errors.append(f"Absolute path in force_add_files: {f}")
            if _has_path_traversal(f):
                errors.append(f"Path traversal in force_add_files: {f}")
            denied = _force_add_denied_match(f)
            if denied:
                errors.append(f"force_add_files denied: {f} (matches {denied})")

    supervisor_lane = handoff.get("supervisor_lane")
    if supervisor_lane is not None:
        if not isinstance(supervisor_lane, str) or not supervisor_lane.strip():
            errors.append("supervisor_lane must be a non-empty string when provided")

    deferred_items = handoff.get("deferred_items")
    if deferred_items is not None:
        if not isinstance(deferred_items, list):
            errors.append("deferred_items must be a list when provided")
        else:
            for item in deferred_items:
                if not isinstance(item, str):
                    errors.append("deferred_items entries must be strings")
                    continue
                if _is_absolute_untrusted_path(item):
                    errors.append(f"Absolute path in deferred_items: {item}")
                if _has_path_traversal(item):
                    errors.append(f"Path traversal in deferred_items: {item}")

    bridge_status = handoff.get("bridge_status")
    if bridge_status is not None and not isinstance(bridge_status, dict):
        errors.append("bridge_status must be an object when provided")

    scope_items = handoff.get("scope_items")
    if scope_items is not None:
        if not isinstance(scope_items, list):
            errors.append("scope_items must be a list when provided")
        else:
            for item in scope_items:
                if not isinstance(item, str):
                    errors.append("scope_items entries must be strings")
                    continue
                if _is_absolute_untrusted_path(item):
                    errors.append(f"Absolute path in scope_items: {item}")
                if _has_path_traversal(item):
                    errors.append(f"Path traversal in scope_items: {item}")

    evidence_handles = handoff.get("evidence_handles")
    if evidence_handles is not None:
        if not isinstance(evidence_handles, dict):
            errors.append("evidence_handles must be an object when provided")
        else:
            for key, value in evidence_handles.items():
                if not isinstance(key, str) or not key.strip():
                    errors.append("evidence_handles keys must be non-empty strings")
                if not isinstance(value, str):
                    errors.append(f"evidence_handles['{key}'] must be a string")

    tracked_packet = handoff.get("tracked_packet")
    if tracked_packet is not None:
        if not isinstance(tracked_packet, str) or not tracked_packet.strip():
            errors.append("tracked_packet must be a non-empty string when provided")
        else:
            normalized_packet = _normalize_repo_relpath(tracked_packet)
            if _is_absolute_untrusted_path(normalized_packet):
                errors.append(f"Absolute path in tracked_packet: {tracked_packet}")
            if _has_path_traversal(normalized_packet):
                errors.append(f"Path traversal in tracked_packet: {tracked_packet}")
            if not normalized_packet.startswith("reports/control_plane/") or not normalized_packet.endswith(".md"):
                errors.append(
                    "tracked_packet must name a reports/control_plane/*.md packet, "
                    f"got: {tracked_packet}"
                )

    # tracker_note_text must be non-empty string
    tnt = handoff.get("tracker_note_text", "")
    if not isinstance(tnt, str) or not tnt.strip():
        errors.append("tracker_note_text must be a non-empty string")
    else:
        errors.extend(
            _validate_tracker_note_text(
                tracker_note_text=tnt,
                wave_id=str(handoff.get("wave_id", "")),
                wave_class=str(handoff.get("wave_class", "")),
                target_gate_id=str(handoff.get("target_gate_id", "")),
            )
        )

    # fixes_implemented must be non-empty list of strings
    fi = handoff.get("fixes_implemented")
    if not isinstance(fi, list) or not fi:
        errors.append("fixes_implemented must be a non-empty list")
    elif not all(isinstance(f, str) for f in fi):
        errors.append("fixes_implemented entries must be strings")

    # String fields
    for fld in ("commit_message", "pr_title", "pr_body", "task_id", "caller",
                "branch_prefix", "wave_class", "target_gate_id"):
        val = handoff.get(fld)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"{fld} must be a non-empty string")
    target_gate_id = handoff.get("target_gate_id")
    if isinstance(target_gate_id, str) and target_gate_id.strip():
        normalized_gate = _normalize_target_gate_id(target_gate_id)
        if not normalized_gate:
            errors.append(f"target_gate_id must match G1-G8, got: {target_gate_id}")

    branch_prefix = handoff.get("branch_prefix", "")
    if isinstance(branch_prefix, str) and branch_prefix and not BRANCH_PREFIX_RE.fullmatch(branch_prefix):
        errors.append(f"branch_prefix contains unsafe characters: {branch_prefix}")
    target_branch = handoff.get("target_branch")
    if target_branch is not None:
        if not isinstance(target_branch, str) or not target_branch.strip():
            errors.append("target_branch must be a non-empty string when provided")
        else:
            normalized_target_branch = target_branch.strip()
            if not _is_wave_bound_target_branch(
                normalized_target_branch,
                branch_prefix=str(branch_prefix or ""),
                wave_id=str(wave_id or ""),
            ):
                errors.append(
                    "target_branch must equal the canonical wave branch or a "
                    f"restart branch derived from wave_id '{wave_id}': {normalized_target_branch}"
                )

    # Caller validation
    caller = handoff.get("caller", "")
    if caller and caller not in VALID_CALLERS:
        errors.append(f"caller must be one of {sorted(VALID_CALLERS)}, got: {caller}")

    return len(errors) == 0, errors


_STASH_REF_RE = re.compile(r"^stash@\{(\d+)\}")


def _post_merge_cleanup(
    *,
    cleanup_root: Path,
    repo_root: Path,
    target_branch: str,
    base_branch: str,
    wave_id: str,
    log: Any,
) -> dict[str, Any]:
    """Best-effort cleanup after a PR merge succeeds.

    Runs from *cleanup_root* (main repo after ff-only to origin/base_branch).
    Deletes the merged local branch, removes the wave worktree if distinct,
    and drops any stashes whose description references *wave_id*.

    All failures are logged and swallowed; the merge has already succeeded
    and cleanup must never regress the pipeline.

    Returns a dict with the per-substep outcomes (for test assertions).
    """
    outcome: dict[str, Any] = {
        "branch_deleted": False,
        "worktree_removed": False,
        "stashes_dropped": 0,
        "warnings": [],
    }

    try:
        cleanup_branch = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cleanup_root
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        outcome["warnings"].append(f"cannot resolve cleanup_root HEAD: {exc}")
        return outcome

    if cleanup_branch != base_branch:
        outcome["warnings"].append(
            f"cleanup_root {cleanup_root} is on '{cleanup_branch}', expected "
            f"'{base_branch}'; skipping cleanup to avoid deleting the wrong branch"
        )
        return outcome

    # 16b: remove worktree FIRST so the branch it holds is unlocked for 16a.
    # git rejects `branch -D` on a branch checked out by any linked worktree.
    try:
        repo_root_real = repo_root.resolve()
    except OSError:
        repo_root_real = repo_root
    try:
        cleanup_root_real = cleanup_root.resolve()
    except OSError:
        cleanup_root_real = cleanup_root
    # Refuse to touch the main worktree. Git refuses `worktree remove` on the
    # primary worktree, and attempting it would leave the branch checked out
    # so the subsequent `branch -D` also fails. Main worktree's `.git` is a
    # DIRECTORY; a linked worktree's `.git` is a FILE pointing at
    # `<main>/.git/worktrees/<name>/`. Only attempt removal when the path is
    # a linked worktree AND distinct from cleanup_root.
    repo_git_path = repo_root_real / ".git"
    is_linked_worktree = repo_git_path.is_file()
    if (
        repo_root_real != cleanup_root_real
        and repo_root_real.exists()
        and is_linked_worktree
    ):
        try:
            _run(
                ["git", "worktree", "remove", "--force", str(repo_root_real)],
                cwd=cleanup_root, timeout=30,
            )
            outcome["worktree_removed"] = True
            log(f"Step 16b: removed worktree {repo_root_real}")
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            outcome["warnings"].append(f"worktree remove: {detail[:200]}")
            log(f"Step 16b worktree remove warning: {detail[:200]}")
        except subprocess.TimeoutExpired:
            outcome["warnings"].append("worktree remove timed out")
            log("Step 16b worktree remove timed out")

    # 16a: delete the merged local branch (now unlocked if step 16b ran)
    try:
        _run(["git", "branch", "-D", target_branch], cwd=cleanup_root, timeout=30)
        outcome["branch_deleted"] = True
        log(f"Step 16a: deleted local branch {target_branch}")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        outcome["warnings"].append(f"branch delete: {detail[:200]}")
        log(f"Step 16a branch delete warning: {detail[:200]}")
    except subprocess.TimeoutExpired:
        outcome["warnings"].append("branch delete timed out")
        log("Step 16a branch delete timed out")

    # 16c: drop any stashes whose description references the wave_id.
    # Drop highest-index first so remaining refs stay stable during loop.
    if wave_id:
        try:
            stash_out = _run(
                ["git", "stash", "list"], cwd=cleanup_root, timeout=30
            ).stdout
            refs_to_drop: list[tuple[int, str]] = []
            for line in stash_out.splitlines():
                if wave_id not in line:
                    continue
                ref = line.split(":", 1)[0]
                m = _STASH_REF_RE.match(ref)
                if m is None:
                    continue
                refs_to_drop.append((int(m.group(1)), ref))
            refs_to_drop.sort(reverse=True)
            for _idx, ref in refs_to_drop:
                try:
                    _run(["git", "stash", "drop", ref], cwd=cleanup_root, timeout=30)
                    outcome["stashes_dropped"] += 1
                except subprocess.CalledProcessError as exc:
                    detail = (exc.stderr or exc.stdout or str(exc)).strip()
                    outcome["warnings"].append(f"stash drop {ref}: {detail[:200]}")
                    log(f"Step 16c stash drop {ref} warning: {detail[:200]}")
                except subprocess.TimeoutExpired:
                    outcome["warnings"].append(f"stash drop {ref} timed out")
                    log(f"Step 16c stash drop {ref} timed out")
            if outcome["stashes_dropped"]:
                log(
                    f"Step 16c: dropped {outcome['stashes_dropped']} stash(es) "
                    f"referencing {wave_id}"
                )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            outcome["warnings"].append(f"stash list: {detail[:200]}")
            log(f"Step 16c stash list warning: {detail[:200]}")
        except subprocess.TimeoutExpired:
            outcome["warnings"].append("stash list timed out")
            log("Step 16c stash list timed out")

    return outcome


def _queue_entry_backtick_value(line: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*`([^`]+)`", line)
    return match.group(1).strip() if match else ""


def _tracker_note_wave_id(line: str) -> str:
    match = re.search(r"Tracker sync note\s*\([^,]+,\s*([^)]+)\)", line)
    return match.group(1).strip() if match else ""


def _routed_tracker_queue_entries(
    repo_root: Path,
    *,
    existing_wave_ids: set[str],
) -> list[dict[str, Any]]:
    tasks_path = repo_root / "TASKS.md"
    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    entries: list[dict[str, Any]] = []
    for line in lines:
        if "Tracker sync note" not in line or "Packet:" not in line:
            continue
        wave_id = normalize_wave_id(_tracker_note_wave_id(line))
        if not wave_id or wave_id in existing_wave_ids:
            continue
        packet = _queue_entry_backtick_value(line, "Packet")
        if not packet:
            continue
        status = read_control_plane_packet_status(repo_root, packet)
        status_upper = str(status or "").upper()
        if not status_upper.startswith("ROUTED - PHASE A"):
            continue
        category_match = re.search(r"Category:\s*([^.`]+)", line)
        line_upper = line.upper()
        entries.append(
            {
                "label": wave_id.upper(),
                "state": str(status or "Routed tracker note"),
                "wave_id": wave_id,
                "category": (
                    category_match.group(1).strip()
                    if category_match
                    else "routed remediation"
                ),
                "packet": packet,
                "source_packet": "",
                "status": status,
                "hard_stop": "HARD STOP" in line_upper or "HARD STOP" in status_upper,
            }
        )
        existing_wave_ids.add(wave_id)
    return entries


def _founder_ordered_queue_entries(repo_root: Path) -> list[dict[str, Any]]:
    tasks_path = repo_root / "TASKS.md"
    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    entries: list[dict[str, Any]] = []
    seen_wave_ids: set[str] = set()
    for line in lines:
        if "FOUNDER-ORDERED-REDTEAM-" not in line:
            continue
        if "Wave ID:" not in line or "Packet:" not in line:
            continue
        label_match = re.match(
            r"^\s*\d+\.\s+\*\*\[(?P<label>[^\]]+)\]\s*(?P<state>.*?)\*\*",
            line,
        )
        if not label_match:
            continue
        wave_id = _queue_entry_backtick_value(line, "Wave ID")
        packet = _queue_entry_backtick_value(line, "Packet")
        if not wave_id or not packet:
            continue
        normalized_wave_id = normalize_wave_id(wave_id)
        category_match = re.search(r"Category:\s*([^.`]+)", line)
        source_packet = _queue_entry_backtick_value(line, "Source audit packet")
        status = read_control_plane_packet_status(repo_root, packet)
        line_upper = line.upper()
        status_upper = str(status or "").upper()
        seen_wave_ids.add(normalized_wave_id)
        entries.append(
            {
                "label": label_match.group("label").strip(),
                "state": label_match.group("state").strip(),
                "wave_id": normalized_wave_id,
                "category": (
                    category_match.group(1).strip()
                    if category_match
                    else "founder-ordered redteam"
                ),
                "packet": packet,
                "source_packet": source_packet,
                "status": status,
                "hard_stop": "HARD STOP" in line_upper or "HARD STOP" in status_upper,
            }
        )
    entries.extend(
        _routed_tracker_queue_entries(repo_root, existing_wave_ids=seen_wave_ids)
    )
    return entries


def _next_open_founder_ordered_queue_entry(repo_root: Path) -> dict[str, Any] | None:
    open_entries: list[dict[str, Any]] = []
    for entry in _founder_ordered_queue_entries(repo_root):
        if packet_status_is_completed(entry.get("status")):
            continue
        if packet_status_is_completed(entry.get("state")):
            continue
        open_entries.append(entry)
    for entry in open_entries:
        if not entry.get("hard_stop"):
            return entry
    return open_entries[0] if open_entries else None


def _post_merge_blocker_report_paths(repo_root: Path) -> list[str]:
    blocking_dir = repo_root / "reports" / "deferred" / "blocking"
    if not blocking_dir.is_dir():
        return []
    return sorted(
        p.relative_to(repo_root).as_posix()
        for p in blocking_dir.glob("*.md")
        if p.name != "README.md"
    )


def _post_merge_request_for_queue_entry(entry: dict[str, Any]) -> str:
    packet = str(entry.get("packet") or "")
    source_packet = str(entry.get("source_packet") or "")
    category = str(entry.get("category") or "founder-ordered redteam")
    read_targets = [packet]
    if source_packet:
        read_targets.append(source_packet)
    target_text = " and ".join(read_targets)
    if entry.get("hard_stop"):
        return (
            "Hard stop before implementation. The next open founder-ordered "
            f"candidate is {packet}; report that /mu structural work is queued "
            "and do not dispatch Phase A, Phase B, or commit implementation."
        )
    return (
        f"Use the full dispatcher pipeline for this {category} remediation wave: "
        "post-merge supervisor -> Phase A -> Phase B -> commit executor. "
        f"Read {target_text}. Do not edit Claude-related files. Stop if the "
        "packet requires /mu structural work or founder input."
    )


def _refresh_post_merge_package_for_next_open_queue(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    result: dict[str, Any],
    merge_sha: str,
    log: Any,
) -> dict[str, Any]:
    """Write a fresh post-merge package from the founder-ordered queue state."""
    entry = _next_open_founder_ordered_queue_entry(repo_root)
    queue_task_id = "[NEXT-CODEX-POST-REDTEAM]"
    pr_number_raw = result.get("pr_number")
    try:
        merged_pr = int(pr_number_raw)
    except (TypeError, ValueError):
        merged_pr = 0

    package_path = agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "meta",
        "post_merge_package.json",
    )

    if entry is None:
        package = {
            "task_id": queue_task_id,
            "merged_pr": merged_pr,
            "merge_sha": merge_sha,
            "wave_name": "founder-ordered-post-merge-queue-empty",
            "lane": "founder-ordered remediation queue complete",
            "rollout_packet_path": "reports/control_plane/post_redteam_structural_queue_2026-03-20.md",
            "deferred_items": [],
            "tracker_state_summary": (
                "Post-merge package refreshed mechanically after commit merge. "
                "No open founder-ordered queue packets remain."
            ),
            "next_candidates": [],
            "blocker_report_paths": _post_merge_blocker_report_paths(repo_root),
        }
        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
        result["post_merge_package_path"] = str(package_path.relative_to(repo_root))
        result["post_merge_next_wave"] = None
        result["post_merge_next_hard_stop"] = False
        result["post_merge_queue_empty"] = True
        log(
            "Step 15b: refreshed post-merge package with no open "
            "founder-ordered queue entry"
        )
        return package

    deferred_items = [
        p
        for p in (entry.get("source_packet"), entry.get("packet"))
        if isinstance(p, str) and p.strip()
    ]
    next_candidates: list[dict[str, Any]] = []
    if not entry.get("hard_stop"):
        next_candidates.append(
            {
                "candidate": entry["wave_id"],
                "bounded": True,
                "tracked_packet": entry["packet"],
                "summary": (
                    f"Implement the queued {entry['category']} remediation packet only."
                ),
                "request_for_claude": _post_merge_request_for_queue_entry(entry),
            }
        )

    package = {
        "task_id": queue_task_id,
        "merged_pr": merged_pr,
        "merge_sha": merge_sha,
        "wave_name": entry["wave_id"],
        "lane": f"{entry['category']} remediation",
        "rollout_packet_path": "reports/control_plane/post_redteam_structural_queue_2026-03-20.md",
        "deferred_items": deferred_items,
        "tracker_state_summary": (
            "Post-merge package refreshed mechanically after commit merge. "
            + (
                f"Next open queue packet is a hard stop: {entry['packet']}."
                if entry.get("hard_stop")
                else f"Next open queue packet: {entry['packet']}."
            )
        ),
        "next_candidates": next_candidates,
        "blocker_report_paths": _post_merge_blocker_report_paths(repo_root),
    }
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    result["post_merge_package_path"] = str(package_path.relative_to(repo_root))
    result["post_merge_next_wave"] = entry["wave_id"]
    result["post_merge_next_hard_stop"] = bool(entry.get("hard_stop"))
    result["post_merge_queue_empty"] = False
    log(
        "Step 15b: refreshed post-merge package for "
        f"{entry['wave_id']}"
        + (" (hard stop)" if entry.get("hard_stop") else "")
    )
    return package


def _run_post_commit_pipeline(
    *,
    handoff: dict[str, Any],
    repo_root: Path,
    result: dict[str, Any],
    target_branch: str,
    base_branch: str,
    continuation_path: Path,
    log: Any,
) -> dict[str, Any]:
    pr_number = str(result.get("pr_number") or "")
    late_conflict_retry_used = bool(result.pop("_late_conflict_retry_used", False))

    # ── Step 11: run_pre_push_script ──────────────────────────────────
    if "run_pre_push_script" not in result["steps_completed"]:
        pre_push_script = repo_root / "mu" / "tools" / "hooks" / "pre-push-fast"
        if pre_push_script.exists():
            try:
                _run(["bash", str(pre_push_script)], cwd=repo_root, timeout=PRE_PUSH_FAST_TIMEOUT_S)
            except subprocess.CalledProcessError as exc:
                detail = _tail_failure_excerpt(
                    exc.stderr or exc.stdout or "",
                    limit=4000,
                    max_lines=80,
                )
                if not detail:
                    detail = f"exit {exc.returncode}"
                return {"status": "error", "step": "run_pre_push_script",
                        "errors": [f"pre-push-fast failed: {detail}"],
                        "steps_completed": result["steps_completed"]}
            except subprocess.TimeoutExpired:
                return {"status": "error", "step": "run_pre_push_script",
                        "errors": ["pre-push-fast timed out"],
                        "steps_completed": result["steps_completed"]}
        result["steps_completed"].append("run_pre_push_script")
        _checkpoint_post_commit_progress(
            result,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )
        log("Step 11: pre-push script passed")
    else:
        log("Step 11: pre-push script already passed, skipping")

    # ── Step 12: git_push ─────────────────────────────────────────────
    if "git_push" not in result["steps_completed"]:
        try:
            _run(
                # Step 11 already ran the exact pre-push gate for this local head.
                ["git", "push", "--no-verify", "-u", "origin", target_branch],
                cwd=repo_root, timeout=300,
            )
            result["steps_completed"].append("git_push")
            _checkpoint_post_commit_progress(
                result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
            log(f"Step 12: pushed to origin/{target_branch}")
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "git_push",
                    "errors": [f"git push failed: {exc.stderr.strip()}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "git_push",
                    "errors": ["git push timed out"],
                    "steps_completed": result["steps_completed"]}
    else:
        log(f"Step 12: push already completed for {target_branch}, skipping")

    # ── Step 13: ensure_pr ────────────────────────────────────────────
    if "ensure_pr" not in result["steps_completed"]:
        try:
            existing_prs = _run(
                ["gh", "pr", "list", "--head", target_branch, "--base", base_branch,
                 "--state", "open", "--json", "number"],
                cwd=repo_root, timeout=30,
            ).stdout.strip()
            pr_list = json.loads(existing_prs) if existing_prs else []
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pr_list = []

        if len(pr_list) > 1:
            return {"status": "error", "step": "ensure_pr",
                    "errors": [f"Multiple open PRs for {target_branch}: {[p['number'] for p in pr_list]}"],
                    "steps_completed": result["steps_completed"]}

        if len(pr_list) == 1:
            pr_number = str(pr_list[0]["number"])
            if not pr_number.isdigit():
                return {"status": "error", "step": "ensure_pr",
                        "errors": [f"PR number non-numeric: {pr_number}"],
                        "steps_completed": result["steps_completed"]}
            try:
                _run(
                    ["gh", "pr", "edit", pr_number,
                     "--title", handoff["pr_title"],
                     "--body", handoff["pr_body"]],
                    cwd=repo_root, timeout=30,
                )
                log(f"Step 13: reused PR #{pr_number}, synced metadata")
            except subprocess.CalledProcessError as exc:
                log(f"Step 13: PR edit warning: {exc.stderr.strip()[:200]}")
        else:
            try:
                pr_create_result = _run(
                    ["gh", "pr", "create",
                     "--base", base_branch,
                     "--head", target_branch,
                     "--title", handoff["pr_title"],
                     "--body", handoff["pr_body"]],
                    cwd=repo_root, timeout=30,
                )
                pr_url = pr_create_result.stdout.strip()
                pr_number = pr_url.rstrip("/").split("/")[-1]
                if not pr_number.isdigit():
                    return {"status": "error", "step": "ensure_pr",
                            "errors": [f"PR number non-numeric from URL: {pr_url}"],
                            "steps_completed": result["steps_completed"]}
                log(f"Step 13: created PR #{pr_number}")
            except subprocess.CalledProcessError as exc:
                return {"status": "error", "step": "ensure_pr",
                        "errors": [f"gh pr create failed: {exc.stderr.strip()}"],
                        "steps_completed": result["steps_completed"]}
            except subprocess.TimeoutExpired:
                return {"status": "error", "step": "ensure_pr",
                        "errors": ["gh pr create timed out"],
                        "steps_completed": result["steps_completed"]}

        result["pr_number"] = pr_number
        result["steps_completed"].append("ensure_pr")
        _checkpoint_post_commit_progress(
            result,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )
    else:
        pr_number = str(result.get("pr_number") or pr_number)
        log(f"Step 13: PR #{pr_number or 'unknown'} already ensured, skipping")

    # ── Step 14: wait_ci ──────────────────────────────────────────────
    if "wait_ci" not in result["steps_completed"]:
        # Auto-resolve CONFLICTING/DIRTY PRs before polling CI (2026-04-17
        # learning mechanized). On clean merge: fetch base + merge + push.
        # On TASKS.md-only tracker-note conflict: fetch + merge + resolve
        # chronologically + commit (RCX_SKIP_RECEIPT_CHECK=1) + push. Any
        # other conflict OR non-tracker-note TASKS.md conflict aborts the
        # merge and returns a structured fail-fast error pointing to the
        # manual recovery recipe.
        resolve_result = _try_auto_resolve_pr_conflict(
            repo_root,
            pr_number=pr_number,
            base_branch=base_branch,
            branch_name=target_branch,
            log=log,
        )
        if not resolve_result.get("resolved"):
            action = resolve_result.get("action", "aborted")
            detail = resolve_result.get("detail", "unknown")
            return {
                "status": "error",
                "step": "wait_ci",
                "errors": [
                    f"PR #{pr_number} CONFLICTING/DIRTY and auto-resolve "
                    f"action={action}: {detail}. Manual recovery required: "
                    f"`cd <worktree> && git fetch origin {base_branch} && "
                    f"git merge origin/{base_branch} --no-edit` (resolve "
                    f"conflicts manually if any) + "
                    f"`RCX_SKIP_RECEIPT_CHECK=1 git commit --no-edit` + "
                    f"`git push origin {target_branch}` + relaunch commit_executor."
                ],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number,
                "failure_class": "pr_conflicting",
                "auto_resolve_action": action,
            }
        ci_response = _wait_for_pr_ci(
            repo_root,
            pr_number=pr_number,
            result=result,
            continuation_path=continuation_path,
            target_branch=target_branch,
            log=log,
            step_label="Step 14",
        )
        if ci_response is not None:
            return ci_response
    else:
        log(f"Step 14: required checks already passed for PR #{pr_number}, skipping")

    # ── Step 15: ensure_review_clear_and_merge ────────────────────────
    log(f"Step 15: checking review state for PR #{pr_number}...")

    try:
        repo_owner, repo_name = _parse_origin_owner_repo(repo_root)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError):
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["Cannot determine repo owner/name from git remote"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    review_wait_timed_out: TimeoutError | None = None
    try:
        head_sha_before_merge = _run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
        ).stdout.strip()
        pr_data = _query_pr_review_state(
            repo_root,
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
        )
        _assert_expected_pr_head(pr_data, head_sha_before_merge)
        existing_issue_comment_outcome = None
        if _has_recorded_current_head_bot_request(continuation_path, head_sha_before_merge):
            existing_issue_comment_outcome = _current_head_connector_issue_comment_outcome(
                pr_data,
                head_sha_before_merge,
            )
        if (
            not _has_fresh_connector_review(pr_data, head_sha_before_merge)
            and existing_issue_comment_outcome is None
        ):
            _maybe_request_current_head_bot_review(
                repo_root,
                pr_number=pr_number,
                head_sha=head_sha_before_merge,
                continuation_path=continuation_path,
                log=log,
            )
            pr_data = _wait_for_bot_review_freshness(
                lambda: _query_pr_review_state(
                    repo_root,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                ),
                head_sha=head_sha_before_merge,
                request_acknowledged=lambda pr_data: _bot_review_request_acknowledged(
                    repo_root,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    pr_data=pr_data,
                ),
                log=log,
            )
    except TimeoutError as exc:
        # Bot review timed out. Refresh PR state before merge evaluation so
        # human reviews/threads that appeared during the wait window cannot be
        # missed by stale pre-wait data.
        review_wait_timed_out = exc
        log(f"Step 15: bot review timed out ({exc}), refreshing PR state before merge")
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Review query failed: {exc}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    if review_wait_timed_out is not None:
        try:
            pr_data = _query_pr_review_state(
                repo_root,
                repo_owner=repo_owner,
                repo_name=repo_name,
                pr_number=pr_number,
            )
            _assert_expected_pr_head(pr_data, head_sha_before_merge)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"Review refresh after timeout failed: {exc}"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}

    findings_result = _extract_review_findings(
        pr_data, head_sha_before_merge, result=result, pr_number=pr_number,
    )
    if findings_result["outcome"] == "error":
        return findings_result["response"]

    # Inject sweep findings from prior merged PRs (merge_pr.sh --sweep writes
    # .agent_bus/meta/sweep_findings.json with unresolved bot finding content).
    sweep_file = agent_bus_path(repo_root, _active_bus_dir(), "meta", "sweep_findings.json")
    if sweep_file.exists():
        try:
            sweep_lines = [ln.strip() for ln in sweep_file.read_text().splitlines() if ln.strip()]
            sweep_findings = [json.loads(ln) for ln in sweep_lines]
            if sweep_findings:
                existing = findings_result.get("bot_findings", [])
                for sf in sweep_findings:
                    existing.append({
                        "author": "chatgpt-codex-connector[bot]",
                        "path": sf.get("path", ""),
                        "body": sf.get("body", "")[:500],
                        "source": f"sweep-pr-{sf.get('pr', '?')}",
                    })
                findings_result["bot_findings"] = existing
                if findings_result["outcome"] != "bot_findings":
                    findings_result["outcome"] = "bot_findings"
                log(f"Step 15: injected {len(sweep_findings)} sweep finding(s) from prior PRs")
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            log(f"Step 15: failed to load sweep findings (non-fatal): {exc}")

    if findings_result["outcome"] == "bot_findings" and review_wait_timed_out is None:
        # Only remediate bot findings if the bot actually reviewed the
        # current HEAD.  On timeout, stale threads from previous commits
        # are advisory — they get deferred, not remediated.
        remediation_response = _attempt_bot_finding_remediation(
            findings_result["bot_findings"],
            repo_root=repo_root,
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
            target_branch=target_branch,
            head_sha=head_sha_before_merge,
            wave_id=handoff["wave_id"],
            continuation_path=continuation_path,
            result=result,
            log=log,
        )
        if remediation_response is not None:
            return remediation_response

    pre_merge_ci_response = _wait_for_pr_ci(
        repo_root,
        pr_number=pr_number,
        result=result,
        continuation_path=continuation_path,
        target_branch=target_branch,
        log=log,
        step_label="Step 15 pre-merge",
    )
    if pre_merge_ci_response is not None:
        return pre_merge_ci_response

    merge_script = repo_root / "mu" / "tools" / "hooks" / "merge_pr.sh"
    if not merge_script.exists():
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["merge_pr.sh not found"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    try:
        _run(
            ["bash", str(merge_script), pr_number, "--sweep"],
            cwd=repo_root.parent, timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        if not late_conflict_retry_used:
            resolve_result = _try_auto_resolve_pr_conflict(
                repo_root,
                pr_number=pr_number,
                base_branch=base_branch,
                branch_name=target_branch,
                log=log,
            )
            if resolve_result.get("resolved") and resolve_result.get("action") != "no_action":
                result["_late_conflict_retry_used"] = True
                try:
                    _prepare_result_for_late_conflict_retry(
                        repo_root,
                        result=result,
                        continuation_path=continuation_path,
                        target_branch=target_branch,
                    )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as retry_exc:
                    return {
                        "status": "error",
                        "step": "ensure_review_clear_and_merge",
                        "errors": [f"Late auto-resolve refresh failed: {retry_exc}"],
                        "steps_completed": result["steps_completed"],
                        "pr_number": pr_number,
                    }
                ci_response = _wait_for_pr_ci(
                    repo_root,
                    pr_number=pr_number,
                    result=result,
                    continuation_path=continuation_path,
                    target_branch=target_branch,
                    log=log,
                    step_label="Step 15 late auto-resolve",
                )
                if ci_response is not None:
                    return ci_response
                return _run_post_commit_pipeline(
                    handoff=handoff,
                    repo_root=repo_root,
                    result=result,
                    target_branch=target_branch,
                    base_branch=base_branch,
                    continuation_path=continuation_path,
                    log=log,
                )
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"merge_pr.sh failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    try:
        verify_root = _resolve_post_merge_verify_root(repo_root, base_branch, log=log)
        _run(["git", "fetch", "origin", base_branch], cwd=verify_root, timeout=60)
        pre_verify_status = _run(["git", "status", "--short"], cwd=verify_root).stdout.strip()
        pre_verify_dirty = _dirty_worktree_paths(verify_root) if pre_verify_status else set()
        if pre_verify_dirty:
            head_sha = _run(
                ["git", "rev-parse", f"origin/{base_branch}"], cwd=verify_root
            ).stdout.strip()
            status_output = pre_verify_status or "\n".join(sorted(pre_verify_dirty))
            result["merge_sha"] = head_sha
            if "ensure_review_clear_and_merge" not in result["steps_completed"]:
                result["steps_completed"].append("ensure_review_clear_and_merge")
            _clear_continuation_record(continuation_path)
            log(
                f"Step 15: WARN post-merge verify root {verify_root} was already dirty "
                f"before ff-only sync; using origin/{base_branch}={head_sha[:8]} as "
                f"merged tip and continuing to step 16:\n{status_output}"
            )
            result["post_merge_verify_warning"] = status_output
            log(f"Step 15: merged, HEAD={head_sha[:8]} (pre-verify dirty, continuing to step 16)")
        else:
            _run(["git", "merge", "--ff-only", f"origin/{base_branch}"], cwd=verify_root, timeout=60)
            head_sha = _run(["git", "rev-parse", "HEAD"], cwd=verify_root).stdout.strip()
            status_output = _run(["git", "status", "--short"], cwd=verify_root).stdout.strip()
            result["merge_sha"] = head_sha
            if "ensure_review_clear_and_merge" not in result["steps_completed"]:
                result["steps_completed"].append("ensure_review_clear_and_merge")
            _clear_continuation_record(continuation_path)
            if status_output:
                # Soft-warn on dirty verify instead of fail-closing the pipeline.
                # Step 16 cleanup is wave-scoped (worktree + branch + wave-named
                # stash) and does NOT depend on main-repo dirty state. Fail-closing
                # here previously blocked step 16 cleanup in parallel multi-wave
                # sessions when the main repo held transient dirt from an in-flight
                # sibling wave (observed 2026-04-17 PR #784 Wave B: step 16
                # prevented from running because PR #783 Wave A shadow files were
                # uncommitted in main repo). Closes
                # reports/deferred/blocking/commit_executor_step16_cascade_block_2026-04-17.md
                # (candidate #2: skip-cleanup-on-verify-fail — preserve signal via
                # warning, don't block wave-scoped cleanup).
                log(
                    f"Step 15: WARN post-merge verify found dirty tree at "
                    f"{verify_root} (not wave-owned; cleanup will still proceed):\n"
                    f"{status_output}"
                )
                result["post_merge_verify_warning"] = status_output
                log(f"Step 15: merged, HEAD={head_sha[:8]} (verify dirty, continuing to step 16)")
            else:
                log(f"Step 15: merged, HEAD={head_sha[:8]}, clean tree verified at {verify_root}")
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Post-merge verify failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    _refresh_post_merge_package_for_next_open_queue(
        repo_root=verify_root,
        handoff=handoff,
        result=result,
        merge_sha=str(result.get("merge_sha") or ""),
        log=log,
    )

    # ── Step 16: post_merge_cleanup ────────────────────────────────────
    # Best-effort cleanup of wave-local state that would otherwise
    # accumulate: local branch ref, linked worktree, wave-scoped stashes.
    # Failures are logged and swallowed — the merge already succeeded and
    # this step MUST NOT regress the pipeline.
    cleanup_outcome = _post_merge_cleanup(
        cleanup_root=verify_root,
        repo_root=repo_root,
        target_branch=target_branch,
        base_branch=base_branch,
        wave_id=str(handoff.get("wave_id") or ""),
        log=log,
    )
    result["post_merge_cleanup"] = cleanup_outcome
    result["steps_completed"].append("post_merge_cleanup")

    return result


def _run_commit_pipeline_impl(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool = False,
    skip_supervisor: bool = False,
) -> dict[str, Any]:
    """Execute the 15-step commit pipeline.

    Same command every time. Automatic bounded continuation after a local
    commit is allowed; no extra resume flags.

    Args:
        skip_supervisor: Historical direct-bypass flag. It is retained only for
            API compatibility and now fails closed before supervisor authority.
    """
    try:
        ensure_not_agent_review_mode("commit_executor.run_commit_pipeline")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "step": "review_mode_guard",
            "errors": [str(exc)],
            "steps_completed": [],
        }
    if skip_supervisor:
        return {
            "status": "error",
            "step": "skip_supervisor_forbidden",
            "errors": [
                "--skip-supervisor is disabled: commit execution requires "
                "pre-commit supervisor review and receipt validation"
            ],
            "steps_completed": [],
        }

    result: dict[str, Any] = {
        "status": "success",
        "steps_completed": [],
        "pr_number": None,
        "merge_sha": None,
    }

    # Tee log to file for pipeline monitor observability
    _log_path = repo_root / ".scratch" / "commit_executor_live.log"
    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _log_fp = open(_log_path, "w", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[commit-executor] {msg}"
        if verbose:
            print(line, flush=True)
        try:
            _log_fp.write(line + "\n")
            _log_fp.flush()
        except (OSError, ValueError):
            pass

    # ── Step 1: validate_inputs ──────────────────────────────────────
    valid, errors = validate_handoff(handoff)
    if not valid:
        return {"status": "error", "step": "validate_inputs", "errors": errors}
    result["steps_completed"].append("validate_inputs")
    log("Step 1: inputs validated")

    wave_id = handoff["wave_id"]
    branch_prefix = handoff["branch_prefix"]
    founder_override_token = _resolve_control_surface_founder_override_token(
        {
            "wave_id": wave_id,
            "wave_name": wave_id,
            "tracked_packet": handoff.get("tracked_packet", ""),
            "tracker_note_text": handoff.get("tracker_note_text", ""),
        },
        repo_root,
        embedded_handoff=handoff,
        wave_id=wave_id,
        wave_class=str(handoff.get("wave_class") or ""),
    )
    if founder_override_token:
        tracker_note_text = _append_founder_override_to_tracker_note(
            handoff.get("tracker_note_text", ""),
            founder_override_token,
        )
        if tracker_note_text != handoff.get("tracker_note_text", ""):
            handoff = {**handoff, "tracker_note_text": tracker_note_text}
            valid, errors = validate_handoff(handoff)
            if not valid:
                return {"status": "error", "step": "validate_inputs", "errors": errors}
            log(
                "Step 1b: founder override derived from authorized tracked packet "
                f"for {wave_id}"
            )
    explicit_target_branch = handoff.get("target_branch")
    if isinstance(explicit_target_branch, str) and explicit_target_branch.strip():
        target_branch = explicit_target_branch.strip()
    else:
        target_branch = f"{branch_prefix}/{wave_id}"
    base_branch = handoff["base_branch"]
    # Continuation records bind to the caller-supplied handoff. Step 5c can
    # rebuild the in-memory handoff for supervisor packaging, but a rerun still
    # reloads the original --handoff payload.
    handoff_sha = _handoff_sha(handoff)
    result["handoff_sha"] = handoff_sha
    continuation_path = _continuation_record_path(repo_root, wave_id)
    continuation = _load_post_commit_continuation(
        continuation_path,
        repo_root=repo_root,
        handoff_sha=handoff_sha,
        target_branch=target_branch,
    )
    if continuation:
        result["steps_completed"] = list(continuation.get("steps_completed", []))
        result["commit_sha"] = continuation["commit_sha"]
        result["pr_number"] = continuation.get("pr_number")
        log(
            "Resuming post-commit pipeline from local commit "
            f"{continuation['commit_sha'][:8]}"
        )
        # If resuming after COMMIT_GO_HOLD_PUSH, skip directly to
        # post-commit pipeline (steps 11-15).  Steps 1-10 already ran.
        if "hold_check" in result["steps_completed"]:
            result["receipt_decision"] = continuation.get("receipt_decision", "COMMIT_GO")
            log("Prior run held at COMMIT_GO_HOLD_PUSH — continuing to push (steps 11-15)")
            return _run_post_commit_pipeline(
                handoff=handoff,
                repo_root=repo_root,
                result=result,
                target_branch=target_branch,
                base_branch=base_branch,
                continuation_path=continuation_path,
                log=log,
            )

    # ── Step 2: ensure_feature_branch ────────────────────────────────
    try:
        current = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root).stdout.strip()
    except subprocess.CalledProcessError:
        return {"status": "error", "step": "ensure_feature_branch",
                "errors": ["Cannot determine current branch"],
                "steps_completed": result["steps_completed"]}

    try:
        local_target_exists, remote_target_exists = _probe_feature_branch_existence(
            repo_root,
            target_branch,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "step": "ensure_feature_branch",
                "errors": ["Timeout checking target branch collisions"],
                "steps_completed": result["steps_completed"]}
    branch_start_ref = _preferred_branch_creation_base(repo_root, base_branch)
    start_from_remote_base = branch_start_ref != base_branch

    if current == base_branch:
        if local_target_exists:
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": [f"Local branch {target_branch} already exists"],
                    "steps_completed": result["steps_completed"]}
        if remote_target_exists:
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": [f"Remote branch {target_branch} already exists"],
                    "steps_completed": result["steps_completed"]}
        try:
            if start_from_remote_base:
                tracked_dirty, untracked_dirty, outside_scope = _collect_branch_rebind_dirty_scope(
                    repo_root,
                    handoff=handoff,
                )
                if outside_scope:
                    preview = ", ".join(outside_scope[:10])
                    if len(outside_scope) > 10:
                        preview += ", ..."
                    return {"status": "error", "step": "ensure_feature_branch",
                            "errors": [
                                "Refusing branch creation from fetched base because dirty paths outside "
                                f"the wave scope are present: {preview}"
                            ],
                            "steps_completed": result["steps_completed"]}
                scoped_dirty = sorted((tracked_dirty | untracked_dirty) - set(outside_scope))
                snapshot: dict[str, bytes | None] = {}
                if scoped_dirty:
                    snapshot = _capture_scope_snapshot(repo_root, scoped_dirty)
                    _clear_scope_for_branch_rebind(
                        repo_root,
                        tracked_paths=sorted(tracked_dirty),
                        untracked_paths=sorted(untracked_dirty),
                    )
                _run(["git", "checkout", "-b", target_branch, branch_start_ref], cwd=repo_root)
                if snapshot:
                    _restore_scope_snapshot(repo_root, snapshot)
                log(f"Step 2: created branch {target_branch} from {branch_start_ref}")
            else:
                _run(["git", "checkout", "-b", target_branch], cwd=repo_root)
                log(f"Step 2: created branch {target_branch}")
        except subprocess.CalledProcessError as exc:
            _restore_scope_snapshot_on_branch_failure(
                repo_root,
                snapshot=locals().get("snapshot", {}),
                expected_branch=current,
            )
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": [f"git checkout -b failed: {exc.stderr.strip()}"],
                    "steps_completed": result["steps_completed"]}
    elif current == target_branch:
        log(f"Step 2: already on {target_branch}")
    else:
        if local_target_exists or remote_target_exists:
            collisions: list[str] = []
            if local_target_exists:
                collisions.append(f"local branch {target_branch}")
            if remote_target_exists:
                collisions.append(f"remote branch origin/{target_branch}")
            collision_text = " and ".join(collisions)
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": [
                        f"On branch {current}, expected {base_branch} or {target_branch}. "
                        f"Refusing auto-rebind because {collision_text} already exists"
                    ],
                    "steps_completed": result["steps_completed"]}
        tracked_dirty, untracked_dirty, outside_scope = _collect_branch_rebind_dirty_scope(
            repo_root,
            handoff=handoff,
        )
        if outside_scope:
            preview = ", ".join(outside_scope[:10])
            if len(outside_scope) > 10:
                preview += ", ..."
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": [
                        "Refusing auto-rebind because dirty paths outside the wave scope are present: "
                        f"{preview}"
                    ],
                    "steps_completed": result["steps_completed"]}
        scoped_dirty = sorted((tracked_dirty | untracked_dirty) - set(outside_scope))
        snapshot: dict[str, bytes | None] = {}
        try:
            # When dev has diverged on wave-owned files, a raw checkout can fail
            # closed with "would be overwritten by checkout". Snapshot only the
            # bounded dirty scope, clear it, rebind to the fresh target branch
            # from dev, then restore the exact bytes onto the canonical branch.
            if scoped_dirty:
                snapshot = _capture_scope_snapshot(
                    repo_root,
                    scoped_dirty,
                )
                _clear_scope_for_branch_rebind(
                    repo_root,
                    tracked_paths=sorted(tracked_dirty),
                    untracked_paths=sorted(untracked_dirty),
                )
            _run(["git", "checkout", "-b", target_branch, branch_start_ref], cwd=repo_root)
            if snapshot:
                _restore_scope_snapshot(repo_root, snapshot)
            log(
                "Step 2: rebound worktree from "
                f"{current} to {target_branch} using {branch_start_ref} as base"
            )
        except subprocess.CalledProcessError as exc:
            _restore_scope_snapshot_on_branch_failure(
                repo_root,
                snapshot=snapshot,
                expected_branch=current,
            )
            failed_cmd = exc.cmd if isinstance(exc.cmd, list) else []
            detail = (exc.stderr or exc.stdout or "").strip()
            cmd_text = " ".join(str(part) for part in failed_cmd) or "step-2 rebind helper"
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": [f"Step 2 rebind failed while running `{cmd_text}`: {detail}"],
                    "steps_completed": result["steps_completed"]}

    if "ensure_feature_branch" not in result["steps_completed"]:
        result["steps_completed"].append("ensure_feature_branch")

    if continuation:
        result["receipt_decision"] = continuation["receipt_decision"]
        if continuation["receipt_decision"] == "COMMIT_GO_HOLD_PUSH":
            _clear_continuation_record(continuation_path)
            return {
                "status": "held",
                "commit_sha": continuation["commit_sha"],
                "steps_completed": result["steps_completed"],
                "message": "Committed locally. Pipeline held before push per COMMIT_GO_HOLD_PUSH.",
            }
        log("Continuation record valid; skipping steps 3-10 and resuming at push")
        return _run_post_commit_pipeline(
            handoff=handoff,
            repo_root=repo_root,
            result=result,
            target_branch=target_branch,
            base_branch=base_branch,
            continuation_path=continuation_path,
            log=log,
        )

    # ── Step 3: ensure_tracker_note ──────────────────────────────────
    tracker_note_text = handoff["tracker_note_text"]
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": ["TASKS.md not found"],
                "steps_completed": result["steps_completed"]}

    tasks_content = tasks_path.read_text(encoding="utf-8")
    lines = tasks_content.splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": ["## Ra section not found in TASKS.md"],
                "steps_completed": result["steps_completed"]}

    ra_content = "".join(lines[ra_idx:ra_end_idx])
    ra_wave_id_count = _count_exact_wave_id_mentions(ra_content, wave_id)
    matching_tracker_indices = _matching_tracker_note_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical_tracker_indices = [
        idx for idx in matching_tracker_indices
        if _is_canonical_tracker_note_line(lines[idx].rstrip("\n"), wave_id)
    ]
    tracker_followup_indices = _matching_tracker_followup_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    tracker_relevant_paths = _tracker_relevant_paths_for_handoff(
        list(handoff["files_to_stage"]),
        list(handoff.get("force_add_files", [])),
    )
    note_line = tracker_note_text if tracker_note_text.endswith("\n") else tracker_note_text + "\n"

    if ra_wave_id_count > 1 and not matching_tracker_indices:
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": [f"wave_id '{wave_id}' appears {ra_wave_id_count} times in active ## Ra section of TASKS.md (duplicate)"],
                "steps_completed": result["steps_completed"]}
    if len(canonical_tracker_indices) > 1:
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": [f"wave_id '{wave_id}' has {len(canonical_tracker_indices)} canonical tracker notes in TASKS.md (duplicate)"],
                "steps_completed": result["steps_completed"]}

    tasks_modified = False
    if canonical_tracker_indices:
        canonical_idx = canonical_tracker_indices[0]
        if lines[canonical_idx] != note_line:
            lines[canonical_idx] = note_line
            tasks_path.write_text("".join(lines), encoding="utf-8")
            tasks_modified = True
            log(f"Step 3: tracker note updated for {wave_id}")
        else:
            log(f"Step 3: tracker note for {wave_id} already present, skipping")
            tracker_file_staged = any(
                path in {"TASKS.md", "STATUS.md"}
                for path in [*handoff["files_to_stage"], *handoff.get("force_add_files", [])]
                if isinstance(path, str)
            )
            if tracker_relevant_paths and not tracker_file_staged:
                followup_line = _build_tracker_followup_note(
                    wave_id=wave_id,
                    tracker_paths=tracker_relevant_paths,
                )
                if len(tracker_followup_indices) > 1:
                    return {
                        "status": "error",
                        "step": "ensure_tracker_note",
                        "errors": [
                            f"wave_id '{wave_id}' has {len(tracker_followup_indices)} tracker follow-up notes in TASKS.md (duplicate)"
                        ],
                        "steps_completed": result["steps_completed"],
                    }
                if tracker_followup_indices:
                    followup_idx = tracker_followup_indices[0]
                    if lines[followup_idx] != followup_line:
                        lines[followup_idx] = followup_line
                        tasks_modified = True
                        log(f"Step 3: tracker follow-up refreshed for {wave_id}")
                else:
                    lines.insert(canonical_idx + 1, followup_line)
                    tasks_modified = True
                    log(f"Step 3: tracker follow-up inserted for {wave_id}")
                if tasks_modified:
                    tasks_path.write_text("".join(lines), encoding="utf-8")
    elif matching_tracker_indices:
        # Insert after the last tracker note in Ra, or repair a single malformed
        # tracker-note-shaped line for this wave in place.
        last_tracker_idx = None
        for i in range(ra_idx + 1, ra_end_idx):
            if lines[i].strip().startswith("- Tracker sync note"):
                last_tracker_idx = i

        if len(matching_tracker_indices) == 1:
            lines[matching_tracker_indices[0]] = note_line
            log(f"Step 3: tracker note repaired for {wave_id}")
        else:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": [f"wave_id '{wave_id}' has {len(matching_tracker_indices)} malformed tracker notes in TASKS.md (duplicate)"],
                    "steps_completed": result["steps_completed"]}
        tasks_path.write_text("".join(lines), encoding="utf-8")

        # Verify
        verify_content = tasks_path.read_text(encoding="utf-8")
        if _count_exact_wave_id_mentions(verify_content, wave_id) == 0:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": ["wave_id not found in TASKS.md after write"],
                    "steps_completed": result["steps_completed"]}
        tasks_modified = True
    elif ra_wave_id_count == 1:
        log(f"Step 3: wave_id {wave_id} already referenced outside tracker notes, skipping")
    else:
        # Insert after the last tracker note in Ra section
        last_tracker_idx = None
        for i in range(ra_idx + 1, ra_end_idx):
            if lines[i].strip().startswith("- Tracker sync note"):
                last_tracker_idx = i

        if last_tracker_idx is not None:
            insert_idx = last_tracker_idx + 1
        else:
            # No tracker notes yet — insert after Ra header + description
            insert_idx = ra_idx + 2 if ra_end_idx and ra_end_idx > ra_idx + 2 else ra_idx + 1

        lines.insert(insert_idx, note_line)
        tasks_path.write_text("".join(lines), encoding="utf-8")

        verify_content = tasks_path.read_text(encoding="utf-8")
        if _count_exact_wave_id_mentions(verify_content, wave_id) == 0:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": ["wave_id not found in TASKS.md after write"],
                    "steps_completed": result["steps_completed"]}
        tasks_modified = True
        log(f"Step 3: tracker note inserted for {wave_id}")

    result["steps_completed"].append("ensure_tracker_note")

    # ── Step 4: stage_files ──────────────────────────────────────────
    files_to_stage = _canonicalize_stage_paths(repo_root, list(handoff["files_to_stage"]))
    force_files = _canonicalize_stage_paths(repo_root, list(handoff.get("force_add_files", [])))
    handoff = {
        **handoff,
        "files_to_stage": files_to_stage,
        "force_add_files": force_files,
    }

    # Auto-add TASKS.md if modified in step 3
    if tasks_modified and "TASKS.md" not in files_to_stage:
        files_to_stage.append("TASKS.md")
        handoff["files_to_stage"] = files_to_stage

    runtime_bus_paths = [
        path for path in [*files_to_stage, *force_files]
        if isinstance(path, str) and is_agent_bus_runtime_path(path)
    ]
    if runtime_bus_paths:
        return {
            "status": "error",
            "step": "stage_files",
            "errors": [
                "Runtime agent bus paths cannot be staged or force-added: "
                + ", ".join(sorted(runtime_bus_paths))
            ],
            "steps_completed": result["steps_completed"],
        }

    try:
        files_to_stage, force_files = _stage_handoff_paths(
            repo_root,
            files_to_stage=files_to_stage,
            force_files=force_files,
        )
        handoff = {
            **handoff,
            "files_to_stage": files_to_stage,
            "force_add_files": force_files,
        }
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "stage_files",
                "errors": [f"git add failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"]}

    # Verify something is staged (do NOT auto-add indicator — step 5 handles)
    try:
        staged_output = _run(["git", "diff", "--cached", "--name-only"], cwd=repo_root).stdout.strip()
    except subprocess.CalledProcessError:
        staged_output = ""

    if not staged_output:
        return {"status": "error", "step": "stage_files",
                "errors": ["Nothing staged after git add (nothing to commit)"],
                "steps_completed": result["steps_completed"]}
    staged_runtime_bus = [
        path for path in staged_output.splitlines()
        if is_agent_bus_runtime_path(path)
    ]
    if staged_runtime_bus:
        return {
            "status": "error",
            "step": "stage_files",
            "errors": [
                "Runtime agent bus paths are staged and cannot be committed: "
                + ", ".join(sorted(staged_runtime_bus))
            ],
            "steps_completed": result["steps_completed"],
        }

    result["steps_completed"].append("stage_files")
    log(f"Step 4: staged {len(staged_output.splitlines())} files")

    # ── Step 5: collect_and_stage_indicator ───────────────────────────
    indicator_script = repo_root / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py"
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"

    if indicator_script.exists():
        try:
            _run(
                ["python3", str(indicator_script), "--wave-id", wave_id,
                 "--output", indicator_path],
                cwd=repo_root, timeout=30,
            )
            indicator_full = repo_root / indicator_path
            if not indicator_full.exists():
                return {"status": "error", "step": "collect_and_stage_indicator",
                        "errors": [f"Indicator artifact not created: {indicator_path}"],
                        "steps_completed": result["steps_completed"]}
            _run(["git", "add", "-f", "--", indicator_path], cwd=repo_root)
            result["steps_completed"].append("collect_and_stage_indicator")
            log(f"Step 5: indicator collected and staged at {indicator_path}")
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "collect_and_stage_indicator",
                    "errors": [f"Indicator collection failed: {exc.stderr.strip()[:300]}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "collect_and_stage_indicator",
                    "errors": ["Indicator collection timed out"],
                    "steps_completed": result["steps_completed"]}
    else:
        return {"status": "error", "step": "collect_and_stage_indicator",
                "errors": [f"Indicator collector script not found: {indicator_script}"],
                "steps_completed": result["steps_completed"]}

    # ── Step 5b: reconcile indicator_artifact_ref in TASKS.md ─────────
    # The tracker note (Step 3) may reference a speculative indicator path.
    # After Step 5 stages the real indicator, verify and patch the reference
    # so the supervisor sees a consistent staged state (Bug 2/9 fix, 2026-04-06).
    tasks_path = repo_root / "TASKS.md"
    if tasks_path.exists() and indicator_path:
        tasks_text = tasks_path.read_text(encoding="utf-8")
        expected_ref = f"indicator_artifact_ref: {indicator_path}"
        if wave_id in tasks_text and expected_ref not in tasks_text:
            # Find and patch the indicator_artifact_ref for this wave's tracker note
            import re as _re
            # Match indicator_artifact_ref lines near this wave_id's tracker note
            pattern = _re.compile(
                rf"(- Tracker sync note \([^)]*{_re.escape(wave_id)}[^)]*\).*?"
                rf"indicator_artifact_ref: )\S+",
                _re.DOTALL,
            )
            patched = pattern.sub(rf"\g<1>{indicator_path}", tasks_text)
            if patched != tasks_text:
                tasks_path.write_text(patched, encoding="utf-8")
                _run(["git", "add", "--", "TASKS.md"], cwd=repo_root)
                log("Step 5b: reconciled indicator_artifact_ref in TASKS.md")

    # ── Step 5c: refresh packet truth + rebound handoff scope ────────
    refreshed_handoff, refreshed_staged_paths, refresh_error = refresh_commit_path_packet_truth(
        repo_root=repo_root,
        handoff=handoff,
        indicator_path=indicator_path,
        commit_status="pre_commit_supervisor_pending",
    )
    if refresh_error:
        return {
            "status": "error",
            "step": "refresh_commit_packet_truth",
            "errors": [refresh_error],
            "steps_completed": result["steps_completed"],
        }
    if refreshed_handoff is not handoff:
        handoff = refreshed_handoff
        refreshed_handoff_sha = _handoff_sha(handoff)
        result["refreshed_handoff_sha"] = refreshed_handoff_sha
        if _can_rekey_continuation_to_refreshed_handoff(handoff):
            handoff_sha = refreshed_handoff_sha
            result["handoff_sha"] = handoff_sha
        try:
            refreshed_files, refreshed_force = _stage_handoff_paths(
                repo_root,
                files_to_stage=list(handoff["files_to_stage"]),
                force_files=list(handoff.get("force_add_files", [])),
            )
            handoff = {
                **handoff,
                "files_to_stage": refreshed_files,
                "force_add_files": refreshed_force,
            }
            refreshed_staged_paths = _current_staged_diff_paths(repo_root)
            persist_error = _persist_phase_b_handoff_for_commit_path(repo_root, handoff)
            if persist_error:
                return {
                    "status": "error",
                    "step": "refresh_commit_packet_truth",
                    "errors": [persist_error],
                    "steps_completed": result["steps_completed"],
                }
        except subprocess.CalledProcessError as exc:
            return {
                "status": "error",
                "step": "refresh_commit_packet_truth",
                "errors": [f"git add failed after commit packet truth refresh: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
            }
        result["steps_completed"].append("refresh_commit_packet_truth")
        log(f"Step 5c: refreshed commit packet truth for {handoff.get('tracked_packet')}")
        if refreshed_staged_paths:
            log(
                "Step 5c: rebound and re-staged handoff scope to "
                f"{len(refreshed_staged_paths)} file(s)"
            )

    # ── Steps 6-7: supervisor review + receipt validation ───────────
    if not skip_supervisor:
        # ── Step 6: build_and_run_supervisor ──────────────────────────────
        try:
            changed_files = _run(
                ["git", "diff", "--cached", "--name-only"], cwd=repo_root
            ).stdout.strip().splitlines()
        except subprocess.CalledProcessError:
            changed_files = []

        if not changed_files:
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": ["changed_files empty — nothing staged for supervisor"],
                    "steps_completed": result["steps_completed"]}

        # Discover blockers
        blocking_dir = repo_root / "reports" / "deferred" / "blocking"
        blocker_paths = sorted(
            str(p.relative_to(repo_root))
            for p in blocking_dir.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "README.md"
        ) if blocking_dir.is_dir() else []

        scope_items = handoff.get("scope_items")
        if isinstance(scope_items, list) and scope_items:
            supervisor_scope_items = list(dict.fromkeys([*scope_items, *handoff["files_to_stage"]]))
        else:
            supervisor_scope_items = list(handoff["files_to_stage"])

        evidence_handles: dict[str, str] = {}
        handoff_evidence_handles = handoff.get("evidence_handles")
        if isinstance(handoff_evidence_handles, dict):
            evidence_handles.update(handoff_evidence_handles)
        if "collect_and_stage_indicator" in result["steps_completed"]:
            evidence_handles.setdefault("indicator", indicator_path)
        supervisor_wave_class = str(handoff.get("wave_class", "") or "").strip()
        supervisor_founder_override_token = ""
        if _wave_class_allows_founder_override(supervisor_wave_class):
            if tok := _extract_founder_override_from_tracker_note(
                handoff.get("tracker_note_text", "")
            ):
                supervisor_founder_override_token = f"FOUNDER_OVERRIDE:{tok}"

        supervisor_package = {
            "task_id": handoff["task_id"],
            "wave_name": wave_id,
            "lane": handoff.get("supervisor_lane", handoff["caller"]),
            "changed_files": changed_files,
            "scope_items": supervisor_scope_items,
            "fixes_implemented": handoff["fixes_implemented"],
            "deferred_items": handoff.get("deferred_items", []),
            "bridge_status": handoff.get("bridge_status", {}),
            "evidence_handles": evidence_handles,
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
            "founder_override_token": supervisor_founder_override_token,
            "wave_class": supervisor_wave_class,
        }

        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        pkg_path = scratch_dir / "auto_supervisor_package.json"
        pkg_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        # Run supervisor via structured client
        _safe_emit_pre_commit_supervisor_lifecycle_event(
            repo_root,
            pkg_path,
            event_type="pre_commit_supervisor_started",
            state="started",
        )
        try:
            run_meta_bridge_package, MetaBridgeClientError = _load_repo_meta_bridge_client(repo_root)
            sup_result = run_meta_bridge_package(
                pkg_path,
                wait_for_lock_seconds=30,
                verbose=verbose,
                bus_dir=_active_bus_dir(),
            )
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state=str(getattr(sup_result, "status", "") or "success"),
                decision=str(getattr(sup_result, "decision", "") or "unknown"),
                summary=f"Pre-commit supervisor completed: {getattr(sup_result, 'decision', 'unknown')}",
            )
            if sup_result.decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
                return {"status": "error", "step": "build_and_run_supervisor",
                        "errors": [f"Supervisor returned {sup_result.decision}: {sup_result.summary[:200]}"],
                        "steps_completed": result["steps_completed"]}
            receipt_path_from_supervisor = sup_result.receipt_path
            receipt_decision = sup_result.decision

            # Validate supervisor receipt path is non-empty, relative, within repo.
            # The supervisor-returned receipt path is the runtime authority — it
            # reflects the actual staged state post-injection that the supervisor reviewed.
            if not receipt_path_from_supervisor:
                return {"status": "error", "step": "build_and_run_supervisor",
                        "errors": ["Supervisor returned empty receipt_path — fail closed"],
                        "steps_completed": result["steps_completed"]}
            if os.path.isabs(receipt_path_from_supervisor):
                return {"status": "error", "step": "build_and_run_supervisor",
                        "errors": [f"Supervisor returned absolute receipt_path — fail closed: {receipt_path_from_supervisor}"],
                        "steps_completed": result["steps_completed"]}
            if _has_path_traversal(receipt_path_from_supervisor):
                return {"status": "error", "step": "build_and_run_supervisor",
                        "errors": [f"Path traversal in supervisor receipt_path — fail closed: {receipt_path_from_supervisor}"],
                        "steps_completed": result["steps_completed"]}
            # Verify the receipt resolves inside repo_root
            resolved_repo = repo_root.resolve()
            resolved_receipt = (repo_root / receipt_path_from_supervisor).resolve()
            if not resolved_receipt.is_relative_to(resolved_repo):
                return {"status": "error", "step": "build_and_run_supervisor",
                        "errors": [f"Supervisor receipt_path escapes repo — fail closed: {receipt_path_from_supervisor}"],
                        "steps_completed": result["steps_completed"]}

            handoff_evidence = dict(handoff.get("evidence_handles") or {})
            handoff_evidence["pre_commit_receipt"] = receipt_path_from_supervisor
            handoff = {
                **handoff,
                "evidence_handles": handoff_evidence,
            }
            valid_handoff, validation_errors = validate_handoff(handoff)
            if not valid_handoff:
                return {"status": "error", "step": "build_and_run_supervisor",
                        "errors": [
                            "Refreshed Phase B handoff invalid after supervisor receipt evidence refresh: "
                            + "; ".join(validation_errors)
                        ],
                        "steps_completed": result["steps_completed"]}

            result["steps_completed"].append("build_and_run_supervisor")
            log(f"Step 6: supervisor {receipt_decision}, receipt: {receipt_path_from_supervisor}")
        except ImportError as exc:
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state="error",
                decision="ERROR_INTERNAL",
                summary=f"Pre-commit supervisor import failed: {exc}",
            )
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Cannot import meta_bridge_client: {exc}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state="error",
                decision="ERROR_CODEX_TIMEOUT",
                summary="Pre-commit supervisor timed out",
            )
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": ["Supervisor timed out"],
                    "steps_completed": result["steps_completed"]}
        except Exception as exc:
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state="error",
                decision="ERROR_INTERNAL",
                summary=f"Pre-commit supervisor failed: {exc}",
            )
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Supervisor failed: {exc}"],
                    "steps_completed": result["steps_completed"]}

        # ── Step 7: validate_receipt ──────────────────────────────────────
        # The supervisor receipt (step 6) is the runtime authority — it reflects
        # the actual staged state after tracker/indicator mutations in steps 3-5.
        # The original handoff receipt remains a provenance check and must not be
        # overwritten by the supervisor receipt before validation.
        handoff_receipt_rel = (
            handoff["pre_commit_receipt_path"]
            if "pre_commit_receipt_path" in handoff
            else ""
        )
        handoff_receipt_decision = ""
        if handoff_receipt_rel:
            # Containment check: handoff receipt must resolve inside the repo root.
            # Reject path traversal and symlinks that escape the repo boundary.
            if _has_path_traversal(handoff_receipt_rel):
                return {"status": "error", "step": "validate_receipt",
                        "errors": [f"Path traversal in handoff receipt path: {handoff_receipt_rel}"],
                        "steps_completed": result["steps_completed"]}
            handoff_receipt_file = (repo_root / handoff_receipt_rel).resolve()
            if not handoff_receipt_file.is_relative_to(repo_root.resolve()):
                return {"status": "error", "step": "validate_receipt",
                        "errors": [f"Handoff receipt escapes repo root: {handoff_receipt_rel}"],
                        "steps_completed": result["steps_completed"]}
            if not handoff_receipt_file.exists():
                return {"status": "error", "step": "validate_receipt",
                        "errors": [f"Phase B handoff receipt not found at: {handoff_receipt_rel}"],
                        "steps_completed": result["steps_completed"]}

            try:
                handoff_receipt_data = json.loads(handoff_receipt_file.read_text(encoding="utf-8"))
                handoff_receipt_decision = handoff_receipt_data.get("decision", "")
                if handoff_receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
                    return {"status": "error", "step": "validate_receipt",
                            "errors": [f"Phase B handoff receipt decision '{handoff_receipt_decision}' does not authorize commit"],
                            "steps_completed": result["steps_completed"]}
            except (json.JSONDecodeError, OSError) as exc:
                return {"status": "error", "step": "validate_receipt",
                        "errors": [f"Phase B handoff receipt unreadable: {exc}"],
                        "steps_completed": result["steps_completed"]}
        else:
            handoff_receipt_decision = "STANDALONE_NO_HANDOFF_RECEIPT"

        receipt_file = repo_root / receipt_path_from_supervisor
        if not receipt_file.exists():
            return {"status": "error", "step": "validate_receipt",
                    "errors": [f"Supervisor receipt not found at: {receipt_path_from_supervisor}"],
                    "steps_completed": result["steps_completed"]}

        try:
            receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
            receipt_decision = receipt_data.get("decision", "")
            if receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
                return {"status": "error", "step": "validate_receipt",
                        "errors": [f"Receipt decision '{receipt_decision}' does not authorize commit"],
                        "steps_completed": result["steps_completed"]}
        except (json.JSONDecodeError, OSError) as exc:
            return {"status": "error", "step": "validate_receipt",
                    "errors": [f"Supervisor receipt unreadable: {exc}"],
                    "steps_completed": result["steps_completed"]}

        result["handoff_receipt_path"] = handoff_receipt_rel
        result["handoff_receipt_decision"] = handoff_receipt_decision
        result["receipt_decision"] = receipt_decision
        receipt_refreshed_handoff_sha = _handoff_sha(handoff)
        result["receipt_refreshed_handoff_sha"] = receipt_refreshed_handoff_sha
        if _can_rekey_continuation_to_refreshed_handoff(handoff):
            handoff_sha = receipt_refreshed_handoff_sha
            result["handoff_sha"] = handoff_sha
        persist_error = _persist_phase_b_handoff_for_commit_path(repo_root, handoff)
        if persist_error:
            return {"status": "error", "step": "validate_receipt",
                    "errors": [persist_error],
                    "steps_completed": result["steps_completed"]}
        result["steps_completed"].append("validate_receipt")
        try:
            _emit_commit_ready_event(
                repo_root,
                handoff=handoff,
                receipt_path_from_supervisor=receipt_path_from_supervisor,
                receipt_decision=receipt_decision,
                handoff_receipt_rel=handoff_receipt_rel,
            )
        except Exception as exc:
            return {
                "status": "error",
                "step": "commit_ready_pager",
                "errors": [f"Commit-ready pager emission failed: {exc}"],
                "steps_completed": result["steps_completed"],
            }
        log(
            "Step 7: receipt chain verified "
            f"(handoff={handoff_receipt_decision}, supervisor={receipt_decision})"
        )


    # ── Step 8: run_pre_commit_script ─────────────────────────────────
    pre_commit_script = repo_root / "mu" / "tools" / "hooks" / "pre-commit-doc-check"
    if pre_commit_script.exists():
        # Propagate active bus authority to the hook verifier. Receipt checks
        # must remain active on the commit path.
        step8_env = _commit_subprocess_env(skip_receipt_check=False)
        try:
            _run(["bash", str(pre_commit_script)], cwd=repo_root, timeout=30, env=step8_env)
        except subprocess.CalledProcessError as exc:
            failure_detail = _tail_failure_excerpt(exc.stderr or exc.stdout or "", limit=1000)
            error_text = "pre-commit-doc-check failed"
            if failure_detail:
                error_text = f"{error_text}: {failure_detail}"
            return {"status": "error", "step": "run_pre_commit_script",
                    "errors": [error_text],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "run_pre_commit_script",
                    "errors": ["pre-commit-doc-check timed out"],
                    "steps_completed": result["steps_completed"]}

    try:
        staged_python_files = _run(
            ["git", "diff", "--cached", "--name-only"], cwd=repo_root
        ).stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        staged_python_files = []

    commit_test_files = _collect_commit_test_files(repo_root, staged_python_files)
    if commit_test_files:
        log(f"Step 8b: running pytest on {len(commit_test_files)} affected test file(s)")
        pytest_result = _run_pytest_on_files(repo_root, commit_test_files)
        if not pytest_result["passed"]:
            stderr = (pytest_result.get("stderr") or "").strip()
            stdout = (pytest_result.get("stdout") or "").strip()
            failure_detail = stderr[:1000] if stderr else stdout[:1000]
            return {
                "status": "error",
                "step": "run_pre_commit_script",
                "errors": [
                    f"targeted pytest gate failed (exit={pytest_result['exit_code']}): {failure_detail}"
                ],
                "steps_completed": result["steps_completed"],
            }

    private_attr_gate = run_private_attr_test_gate(repo_root, staged_python_files)
    if not private_attr_gate["passed"]:
        return {
            "status": "error",
            "step": "private_attr_gate",
            "errors": [_private_attr_gate_error(private_attr_gate)],
            "private_attr_gate": private_attr_gate,
            "steps_completed": result["steps_completed"],
        }
    if not private_attr_gate.get("skipped"):
        log(
            "Step 8c: private-attr test-integrity gate passed for "
            f"{len(private_attr_gate.get('test_files') or [])} staged test file(s)"
        )

    result["steps_completed"].append("run_pre_commit_script")
    log("Step 8: pre-commit script passed")

    # ── Step 9: git_commit ────────────────────────────────────────────
    step9_env = _commit_subprocess_env(skip_receipt_check=False)
    try:
        commit_out = _run(
            ["git", "commit", "-m", handoff["commit_message"]],
            cwd=repo_root, timeout=60, env=step9_env,
        )
        commit_sha = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        result["commit_sha"] = commit_sha
        result["steps_completed"].append("git_commit")
        _write_continuation_record(
            continuation_path,
            handoff_sha=handoff_sha,
            target_branch=target_branch,
            commit_sha=commit_sha,
            receipt_decision=receipt_decision,
            steps_completed=result["steps_completed"],
        )
        log(f"Step 9: committed")
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "git_commit",
                "errors": [f"git commit failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"]}
    except subprocess.TimeoutExpired:
        return {"status": "error", "step": "git_commit",
                "errors": ["git commit timed out"],
                "steps_completed": result["steps_completed"]}

    # ── Step 10: hold_check ───────────────────────────────────────────
    if receipt_decision == "COMMIT_GO_HOLD_PUSH":
        sha = result.get("commit_sha", "unknown")
        result["steps_completed"].append("hold_check")
        # Write continuation record so re-run resumes at step 11.
        _write_continuation_record(
            continuation_path,
            handoff_sha=handoff_sha,
            target_branch=target_branch,
            commit_sha=sha,
            receipt_decision=receipt_decision,
            steps_completed=result["steps_completed"],
        )
        return {
            "status": "held",
            "commit_sha": sha,
            "steps_completed": result["steps_completed"],
            "message": (
                "Committed locally. Pipeline held before push per"
                " COMMIT_GO_HOLD_PUSH. Re-run with same --handoff to"
                " continue (steps 11-15)."
            ),
        }

    result["steps_completed"].append("hold_check")
    log("Step 10: COMMIT_GO, continuing to push")
    return _run_post_commit_pipeline(
        handoff=handoff,
        repo_root=repo_root,
        result=result,
        target_branch=target_branch,
        base_branch=base_branch,
        continuation_path=continuation_path,
        log=log,
    )


COMMIT_RETRY_PENDING_STATUS = "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT"


def _safe_tracked_control_packet_path(
    repo_root: Path,
    tracked_packet: str,
) -> tuple[Path | None, str]:
    clean = str(tracked_packet or "").strip()
    if not clean:
        return None, "tracked_packet is empty"
    if os.path.isabs(clean) or ".." in clean.split("/"):
        return None, f"tracked_packet is unsafe: {clean}"
    if not clean.startswith("reports/control_plane/"):
        return None, f"tracked_packet is outside reports/control_plane: {clean}"
    packet_path = (repo_root / clean).resolve()
    control_dir = (repo_root / "reports" / "control_plane").resolve()
    try:
        packet_path.relative_to(control_dir)
    except ValueError:
        return None, f"tracked_packet escapes control plane: {clean}"
    if not packet_path.is_file():
        return None, f"tracked_packet is not a file: {clean}"
    return packet_path, ""


def _rewrite_packet_status_line(packet_path: Path, new_status: str) -> bool:
    text = packet_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for idx, line in enumerate(lines[:40]):
        clean = line.replace("**", "").strip()
        if clean.lower().startswith("status:"):
            replacement = f"Status: {new_status}"
            if lines[idx] == replacement:
                return False
            lines[idx] = replacement
            packet_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
    return False


def _pending_commit_queue_state(current_state: str) -> str:
    upper = current_state.upper()
    evidence = " / LOCAL EVIDENCE" if "LOCAL EVIDENCE" in upper else ""
    date_match = re.search(r"\(\d{4}-\d{2}-\d{2}\)", current_state)
    date_suffix = f" {date_match.group(0)}" if date_match else ""
    return f"{COMMIT_RETRY_PENDING_STATUS}{evidence}{date_suffix}"


def _demote_tasks_queue_state_for_commit_retry(
    repo_root: Path,
    *,
    wave_id: str,
    tracked_packet: str,
) -> bool:
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.is_file():
        return False
    wanted_wave = normalize_wave_id(wave_id)
    wanted_packet = str(tracked_packet or "").strip()
    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    state_re = re.compile(
        r"^(?P<prefix>\s*\d+\.\s+\*\*\[[^\]]+\]\s+)"
        r"(?P<state>.*?)"
        r"(?P<suffix>\.\*\*.*)$"
    )
    for idx, line in enumerate(lines):
        if "FOUNDER-ORDERED-REDTEAM-" not in line:
            continue
        if "Wave ID:" not in line or "Packet:" not in line:
            continue
        entry_wave = normalize_wave_id(_queue_entry_backtick_value(line, "Wave ID"))
        entry_packet = _queue_entry_backtick_value(line, "Packet")
        if wanted_wave and entry_wave != wanted_wave:
            if not wanted_packet or entry_packet != wanted_packet:
                continue
        elif wanted_packet and entry_packet != wanted_packet:
            continue
        match = state_re.match(line.rstrip("\n"))
        if not match:
            continue
        state = match.group("state").strip()
        if not packet_status_is_completed(state):
            continue
        newline = "\n" if line.endswith("\n") else ""
        new_state = _pending_commit_queue_state(state)
        lines[idx] = (
            f"{match.group('prefix')}{new_state}{match.group('suffix')}{newline}"
        )
        changed = True
        break
    if changed:
        tasks_path.write_text("".join(lines), encoding="utf-8")
    return changed


def _demote_completed_handoff_state_for_commit_retry(
    repo_root: Path,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    """Make pre-commit failures routable again before any local commit exists."""
    tracked_packet = str(handoff.get("tracked_packet") or "").strip()
    wave_id = str(handoff.get("wave_id") or "").strip()
    outcome: dict[str, Any] = {"changed": [], "errors": []}
    packet_path, packet_error = _safe_tracked_control_packet_path(
        repo_root,
        tracked_packet,
    )
    if packet_error:
        outcome["errors"].append(packet_error)
    elif packet_path is not None:
        status = read_control_plane_packet_status(repo_root, tracked_packet)
        if packet_status_is_completed(status):
            if _rewrite_packet_status_line(packet_path, COMMIT_RETRY_PENDING_STATUS):
                _run(["git", "add", "--", tracked_packet], cwd=repo_root, timeout=30)
                outcome["changed"].append(tracked_packet)

    if wave_id or tracked_packet:
        if _demote_tasks_queue_state_for_commit_retry(
            repo_root,
            wave_id=wave_id,
            tracked_packet=tracked_packet,
        ):
            _run(["git", "add", "--", "TASKS.md"], cwd=repo_root, timeout=30)
            outcome["changed"].append("TASKS.md")
    return outcome


def _invalidate_durable_handoff_pre_commit_receipt_for_commit_retry(
    repo_root: Path,
    handoff: dict[str, Any],
) -> tuple[bool, str]:
    """Clear stale supervisor receipt evidence after staged retry demotion."""
    handoff_path = agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "executors",
        "phase_b_handoff.json",
    )
    if not handoff_path.is_file():
        return False, ""
    try:
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"failed to read durable Phase B handoff for receipt invalidation: {exc}"
    if not isinstance(payload, dict):
        return False, "durable Phase B handoff is not a JSON object"

    expected_wave = normalize_wave_id(str(handoff.get("wave_id") or ""))
    actual_wave = normalize_wave_id(str(payload.get("wave_id") or ""))
    if expected_wave and actual_wave and expected_wave != actual_wave:
        return False, ""
    expected_packet = str(handoff.get("tracked_packet") or "").strip()
    actual_packet = str(payload.get("tracked_packet") or "").strip()
    if expected_packet and actual_packet and expected_packet != actual_packet:
        return False, ""

    evidence_handles = payload.get("evidence_handles")
    if not isinstance(evidence_handles, dict) or "pre_commit_receipt" not in evidence_handles:
        return False, ""
    refreshed_evidence = {
        key: value
        for key, value in evidence_handles.items()
        if key != "pre_commit_receipt"
    }
    payload["evidence_handles"] = refreshed_evidence
    tracker_note_text = payload.get("tracker_note_text")
    if isinstance(tracker_note_text, str) and tracker_note_text.strip():
        payload["tracker_note_text"] = _mark_tracker_note_pre_commit_receipt_pending(
            tracker_note_text
        )

    valid_handoff, validation_errors = validate_handoff(payload)
    if not valid_handoff:
        return (
            False,
            "durable Phase B handoff invalid after retry receipt invalidation: "
            + "; ".join(validation_errors),
        )
    try:
        handoff_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return False, f"failed to persist durable Phase B handoff receipt invalidation: {exc}"
    return True, ""


def _maybe_demote_completed_handoff_state_for_commit_retry(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    result: dict[str, Any],
) -> None:
    if str(result.get("status") or "") != "error":
        return
    steps_completed = result.get("steps_completed")
    if not isinstance(steps_completed, list):
        return
    if "git_commit" in steps_completed or result.get("commit_sha"):
        return
    if "validate_receipt" not in steps_completed:
        return
    try:
        outcome = _demote_completed_handoff_state_for_commit_retry(repo_root, handoff)
    except (OSError, subprocess.CalledProcessError) as exc:
        warnings = result.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(f"commit retry state demotion failed: {exc}")
        return
    if outcome.get("changed"):
        invalidated, invalidation_error = (
            _invalidate_durable_handoff_pre_commit_receipt_for_commit_retry(
                repo_root,
                handoff,
            )
        )
        if invalidated:
            outcome["handoff_receipt_invalidated"] = True
        if invalidation_error:
            outcome["handoff_receipt_invalidation_error"] = invalidation_error
    if outcome.get("changed") or outcome.get("errors"):
        result["commit_retry_state_demotion"] = outcome
    if outcome.get("changed"):
        warnings = result.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(
                "Demoted completed packet/task state to pending commit after "
                "commit executor failed after receipt validation before git_commit."
            )


def run_commit_pipeline(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool = False,
    skip_supervisor: bool = False,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Execute the commit pipeline with pager lifecycle edges around the run."""
    if bus_dir is not None:
        try:
            resolve_agent_bus_dir(repo_root, bus_dir)
        except ExecutorCommonError as exc:
            return {"status": "error", "step": "bus_dir", "errors": [str(exc)], "steps_completed": []}
        token = _ACTIVE_BUS_DIR.set(agent_bus_relpath(bus_dir))
        try:
            return run_commit_pipeline(
                handoff,
                repo_root=repo_root,
                verbose=verbose,
                skip_supervisor=skip_supervisor,
            )
        finally:
            _ACTIVE_BUS_DIR.reset(token)
    try:
        ensure_not_agent_review_mode("commit_executor.run_commit_pipeline")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "step": "review_mode_guard",
            "errors": [str(exc)],
            "steps_completed": [],
        }
    if skip_supervisor:
        return {
            "status": "error",
            "step": "skip_supervisor_forbidden",
            "errors": [
                "--skip-supervisor is disabled: commit execution requires "
                "pre-commit supervisor review and receipt validation"
            ],
            "steps_completed": [],
        }

    wave_id = str(handoff.get("wave_id") or "unknown").strip() or "unknown"
    handoff_sha = _handoff_sha(handoff) if isinstance(handoff, dict) else "invalid"
    lifecycle_pager_enabled = _commit_lifecycle_pager_enabled(repo_root)
    if lifecycle_pager_enabled:
        try:
            _emit_commit_lifecycle_event(
                repo_root,
                handoff=handoff,
                event_type="commit_started",
                state="started",
                transition_key=f"{wave_id}:{handoff_sha}:started",
                summary=f"Commit executor started for {wave_id}",
                artifact_paths={"handoff_sha": handoff_sha},
            )
        except Exception as exc:
            return {
                "status": "error",
                "step": "commit_started_pager",
                "errors": [f"Commit-start pager emission failed: {exc}"],
                "steps_completed": [],
            }

    result = _run_commit_pipeline_impl(
        handoff,
        repo_root=repo_root,
        verbose=verbose,
        skip_supervisor=skip_supervisor,
    )
    _maybe_demote_completed_handoff_state_for_commit_retry(
        repo_root=repo_root,
        handoff=handoff,
        result=result,
    )
    status = str(result.get("status") or "error")
    event_type = _commit_outcome_event_type(status)
    commit_sha = str(result.get("commit_sha") or "").strip()
    transition_key = f"{wave_id}:{handoff_sha}:{status}:{commit_sha or result.get('step', '')}"
    if lifecycle_pager_enabled:
        try:
            _emit_commit_lifecycle_event(
                repo_root,
                handoff=handoff,
                event_type=event_type,
                state=status,
                transition_key=transition_key,
                summary=f"Commit executor finished with {status}",
                artifact_paths={
                    "commit_sha": commit_sha,
                    "handoff_sha": handoff_sha,
                    "step": str(result.get("step") or ""),
                },
            )
        except Exception as exc:
            outcome_errors = list(result.get("errors") or [])
            outcome_errors.append(f"Commit-outcome pager emission failed: {exc}")
            result = {
                **result,
                "status": "error",
                "step": "commit_outcome_pager",
                "errors": outcome_errors,
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit executor: 15-step mechanical commit pipeline",
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        help="Path to handoff JSON file",
    )
    parser.add_argument(
        "--routing-record",
        type=str,
        help="Routing record JSON string — commit_executor prepares handoff internally",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    # Modular direct flags. Standalone may relax handoff provenance for recovery
    # continuations, but supervisor and receipt authority are always required.
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Standalone mode: sets caller=standalone, relaxes receipt requirements",
    )
    parser.add_argument(
        "--skip-supervisor",
        action="store_true",
        help="Disabled: commit execution always requires supervisor receipt validation",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="Override task_id in handoff (e.g., [TASK-NAME])",
    )
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
    )
    args = parser.parse_args()

    if args.skip_supervisor:
        print(
            "[error] --skip-supervisor is disabled: commit execution requires "
            "pre-commit supervisor review and receipt validation",
            file=sys.stderr,
        )
        return 1

    # Block direct standalone mode when called from dispatch (safety guard)
    if os.environ.get("RCX_EXECUTOR_DISPATCH_PID"):
        if args.standalone:
            print("[error] --standalone is blocked when called from dispatch", file=sys.stderr)
            return 1

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("[error] Not in a git repository", file=sys.stderr)
        return 1

    if not args.handoff and not args.routing_record:
        print("[error] Provide --handoff <path> or --routing-record <json>", file=sys.stderr)
        return 1

    if args.handoff:
        try:
            handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[error] Cannot load handoff: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            record = json.loads(args.routing_record)
        except json.JSONDecodeError as exc:
            print(f"[error] Invalid routing record JSON: {exc}", file=sys.stderr)
            return 1
        handoff, prep_errors = prepare_handoff_from_routing_record(
            record,
            repo_root,
            standalone=args.standalone,
            bus_dir=args.bus_dir,
        )
        if prep_errors or handoff is None:
            print(f"[error] Cannot prepare handoff from routing record: {prep_errors}", file=sys.stderr)
            return 1

    # Apply modular flags to handoff
    if args.standalone:
        handoff["caller"] = "standalone"
        if not handoff.get("pre_commit_receipt_path"):
            handoff["pre_commit_receipt_path"] = ""
    if args.task_id:
        handoff["task_id"] = args.task_id

    result = run_commit_pipeline(
        handoff,
        repo_root=repo_root,
        verbose=args.verbose,
        skip_supervisor=args.skip_supervisor,
        bus_dir=args.bus_dir,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = result.get("status", "unknown")
        steps = result.get("steps_completed", [])
        print(f"[commit-executor] Status: {status}")
        print(f"[commit-executor] Steps: {', '.join(steps)}")
        if result.get("pr_number"):
            print(f"[commit-executor] PR: #{result['pr_number']}")
        if result.get("merge_sha"):
            print(f"[commit-executor] Merge SHA: {result['merge_sha'][:8]}")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"[commit-executor] Error: {e}")
        if result.get("message"):
            print(f"[commit-executor] {result['message']}")
        if result.get("bot_findings"):
            print(f"[commit-executor] Bot findings: {len(result['bot_findings'])}")
            for bf in result["bot_findings"]:
                print(f"  - {bf['author']}: {bf['body'][:100]}...")

    # Standalone recovery: route recoverable non-success standalone exits
    # through recovery_gate so bounded repairs can be diagnosed and retried.
    if args.standalone and _should_attempt_standalone_recovery(result):
        try:
            attempt_recovery, normalize_wave_id = _load_repo_recovery_symbols(repo_root)
            wave_id = normalize_wave_id(handoff.get("wave_id", "unknown"))
            recovery = attempt_recovery(repo_root, result, wave_id, bus_dir=args.bus_dir)
            result["recovery"] = recovery
            if args.verbose or not args.json:
                print(f"[commit-executor] Recovery: class={recovery.get('failure_class')} "
                      f"tier={recovery.get('tier')} recovered={recovery.get('recovered')}")
        except Exception as exc:
            if args.verbose or not args.json:
                print(f"[commit-executor] Recovery gate unavailable in standalone: {exc}")

    # Propagate recovery result: if recovery succeeded, treat as recoverable
    # (exit 0 so the caller can re-invoke).
    recovery = result.get("recovery", {})
    if recovery.get("recovered"):
        return 0
    return 0 if result.get("status") in ("success", "held") else 1


if __name__ == "__main__":
    sys.exit(main())
